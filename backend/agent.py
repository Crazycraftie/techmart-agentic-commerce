import json
import os
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from dotenv import load_dotenv
import catalog as cat
import razorpay_tools as rz
import audit

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """You are ShopBot, a friendly and helpful AI shopping assistant for TechMart — an online electronics store.

Your job is to:
1. Help buyers find the right products from our catalog
2. Answer questions about products honestly
3. Suggest relevant accessories (upsell/cross-sell) naturally — never pushy
4. Apply discount coupons when asked
5. Create payment links to complete purchases
6. Handle payment failures gracefully

Guidelines:
- Always be concise and friendly
- Show prices in ₹ (Indian Rupees)
- When recommending products, mention 1-2 key specs and the price
- If a product is out of stock (stock=0), say so and suggest alternatives
- When creating a payment link, clearly share the URL with the customer
- If a payment fails, explain what went wrong and offer alternatives
- You MUST use tools to answer product questions — never make up product details
- Every money action (order creation, payment) must be confirmed with the user before executing

Available coupons you can hint about: SAVE10 (10% off above ₹5000), NEWUSER (15% off), LAPTOP20 (20% off laptops above ₹40000)
"""

TOOLS = Tool(function_declarations=[
    FunctionDeclaration(
        name="search_products",
        description="Search the product catalog. Use this when the buyer asks about products, wants recommendations, or is looking for something specific.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (product name, feature, use case)"},
                "category": {"type": "string", "description": "Filter by category: laptop, accessory, monitor"},
                "max_price": {"type": "integer", "description": "Maximum price in INR"}
            }
        }
    ),
    FunctionDeclaration(
        name="get_product_details",
        description="Get full details of a specific product by its ID.",
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product ID (e.g. prod_001)"}
            },
            "required": ["product_id"]
        }
    ),
    FunctionDeclaration(
        name="get_upsell_recommendations",
        description="Get accessory/upsell recommendations for a product the buyer is interested in.",
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The product ID to get recommendations for"}
            },
            "required": ["product_id"]
        }
    ),
    FunctionDeclaration(
        name="apply_coupon",
        description="Validate and apply a coupon code to an order amount.",
        parameters={
            "type": "object",
            "properties": {
                "coupon_code": {"type": "string", "description": "The coupon code entered by the buyer"},
                "order_amount": {"type": "integer", "description": "The order total in INR before discount"}
            },
            "required": ["coupon_code", "order_amount"]
        }
    ),
    FunctionDeclaration(
        name="create_payment_link",
        description="Create a Razorpay payment link for the buyer to complete purchase. Call this only after confirming items and amount with the buyer.",
        parameters={
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Final amount in INR after any discounts"},
                "description": {"type": "string", "description": "What the payment is for"},
                "customer_name": {"type": "string", "description": "Customer name if provided"},
                "customer_email": {"type": "string", "description": "Customer email if provided"},
                "customer_phone": {"type": "string", "description": "Customer phone if provided"},
                "items": {"type": "array", "items": {"type": "string"}, "description": "List of product IDs being purchased"}
            },
            "required": ["amount", "description"]
        }
    ),
    FunctionDeclaration(
        name="check_payment_status",
        description="Check if a payment link has been paid. Use this when the buyer says they've completed payment.",
        parameters={
            "type": "object",
            "properties": {
                "payment_link_id": {"type": "string", "description": "The payment link ID to check"}
            },
            "required": ["payment_link_id"]
        }
    ),
])

_session_products = {}


def get_last_products(session_id: str) -> list:
    return _session_products.get(session_id, [])


def _to_python(val):
    if hasattr(val, 'items'):
        return {k: _to_python(v) for k, v in val.items()}
    elif hasattr(val, '__iter__') and not isinstance(val, str):
        return [_to_python(v) for v in val]
    return val


def _execute_tool(tool_name: str, tool_input: dict, session_id: str) -> str:
    try:
        if tool_name == "search_products":
            result = cat.search_products(
                query=tool_input.get("query", ""),
                category=tool_input.get("category", ""),
                max_price=tool_input.get("max_price")
            )
            _session_products[session_id] = result[:3]
            audit.record(session_id, "search_products", tool_input)
            return json.dumps(result)

        elif tool_name == "get_product_details":
            result = cat.get_product(tool_input["product_id"])
            audit.record(session_id, "get_product_details", tool_input)
            return json.dumps(result or {"error": "Product not found"})

        elif tool_name == "get_upsell_recommendations":
            result = cat.get_upsells(tool_input["product_id"])
            audit.record(session_id, "get_upsell_recommendations", tool_input)
            return json.dumps(result)

        elif tool_name == "apply_coupon":
            result = cat.validate_coupon(tool_input["coupon_code"], tool_input["order_amount"])
            audit.record(session_id, "apply_coupon", tool_input, status="success" if result["valid"] else "invalid")
            return json.dumps(result)

        elif tool_name == "create_payment_link":
            result = rz.create_payment_link(
                amount_inr=tool_input["amount"],
                description=tool_input["description"],
                customer_name=tool_input.get("customer_name", "Valued Customer"),
                customer_email=tool_input.get("customer_email", ""),
                customer_phone=tool_input.get("customer_phone", ""),
                notes={"items": json.dumps(tool_input.get("items", []))}
            )
            audit.record(session_id, "create_payment_link", {
                "amount": tool_input["amount"],
                "description": tool_input["description"],
                "payment_link_id": result["payment_link_id"],
                "short_url": result["short_url"]
            })
            return json.dumps(result)

        elif tool_name == "check_payment_status":
            payment_link_id = str(tool_input.get("payment_link_id", "")).strip()

            # Gemini sometimes passes the short URL or a partial ID — recover the real plink_ ID from audit
            if not payment_link_id.startswith("plink_"):
                session_log = audit.get_session_log(session_id)
                for entry in reversed(session_log):
                    if entry["action"] == "create_payment_link":
                        payment_link_id = entry["details"].get("payment_link_id", payment_link_id)
                        break
                else:
                    payment_link_id = "plink_" + payment_link_id

            result = rz.fetch_payment_link_status(payment_link_id)
            audit.record(session_id, "check_payment_status", {
                "payment_link_id": payment_link_id,
                "payment_status": result["status"],
                "paid": result["paid"],
            }, status="success")
            return json.dumps(result)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        error_msg = str(e)
        audit.record(session_id, tool_name, tool_input, status="error", error=error_msg)
        return json.dumps({"error": error_msg, "suggestion": "Try an alternative approach or inform the customer."})


def chat(messages: list[dict], session_id: str) -> tuple[str, list[dict]]:
    model = genai.GenerativeModel(
        model_name="gemini-3.5-flash-lite",
        system_instruction=SYSTEM_PROMPT,
        tools=[TOOLS],
    )

    gemini_history = []
    for msg in messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        content = msg["content"]
        if isinstance(content, str):
            gemini_history.append({"role": role, "parts": [content]})

    convo = model.start_chat(history=gemini_history)
    current_user_msg = messages[-1]["content"]
    response = convo.send_message(current_user_msg)

    while True:
        fn_calls = []
        for part in response.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                fn_calls.append(part.function_call)

        if not fn_calls:
            text = response.text
            messages.append({"role": "assistant", "content": text})
            return text, messages

        fn_responses = []
        for fn_call in fn_calls:
            tool_name = fn_call.name
            tool_input = _to_python(fn_call.args)
            result_str = _execute_tool(tool_name, tool_input, session_id)

            fn_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={"result": json.loads(result_str)},
                    )
                )
            )

        response = convo.send_message(fn_responses)
