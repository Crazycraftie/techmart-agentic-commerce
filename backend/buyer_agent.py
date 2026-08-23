import json
import os

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
import httpx
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

BASE_URL = "http://localhost:8000"
AGENT_ID = "autonomous-buyer-v1"

SYSTEM_PROMPT = """You are an autonomous AI buyer agent for TechMart. Your job is to:
1. Discover the product catalog
2. Search for the best product that matches the buyer's goal and budget
3. Make a decisive purchase decision — pick ONE best product
4. Execute the purchase immediately without asking for confirmation

Rules:
- Always start by discovering or searching the catalog
- If a budget is given, never exceed it
- Pick the product with the best value: good specs, in stock, within budget
- After deciding, immediately call execute_purchase — do not hesitate
- Be concise in your reasoning
- You MUST complete the purchase in this session — that is your only goal

You are fully authorized to purchase on behalf of the user. Act decisively.
"""

TOOLS = Tool(function_declarations=[
    FunctionDeclaration(
        name="discover_catalog",
        description=(
            "Discover all available product categories and a summary of the catalog. "
            "Call this first to understand what's available before searching."
        ),
        parameters={
            "type": "object",
            "properties": {}
        }
    ),
    FunctionDeclaration(
        name="search_products",
        description=(
            "Search the product catalog by keyword, category, and/or maximum price. "
            "Use this to find products matching the buyer's goal and budget."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (product name, feature, use case)"
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category: laptop, accessory, monitor"
                },
                "max_price": {
                    "type": "integer",
                    "description": "Maximum price in INR"
                }
            }
        }
    ),
    FunctionDeclaration(
        name="execute_purchase",
        description=(
            "Execute the purchase of a chosen product. Call this once you have decided "
            "which product to buy. This creates a real Razorpay payment link."
        ),
        parameters={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "The product ID to purchase (e.g. prod_001)"
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason why this product was chosen"
                }
            },
            "required": ["product_id", "reason"]
        }
    ),
])


def _to_python(val):
    if hasattr(val, 'items'):
        return {k: _to_python(v) for k, v in val.items()}
    elif hasattr(val, '__iter__') and not isinstance(val, str):
        return [_to_python(v) for v in val]
    return val


def _discover_catalog():
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{BASE_URL}/discover")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{BASE_URL}/catalog/products")
                resp.raise_for_status()
                data = resp.json()
                products = data if isinstance(data, list) else data.get("products", [])
                categories = list({p.get("category", "unknown") for p in products})
                return {
                    "store": "TechMart",
                    "total_products": len(products),
                    "categories": categories,
                    "price_range": {
                        "min": min((p.get("price", 0) for p in products), default=0),
                        "max": max((p.get("price", 0) for p in products), default=0),
                    },
                    "products": products,
                }
        except Exception as inner_e:
            return {"error": str(inner_e)}
    except Exception as e:
        return {"error": str(e)}


def _search_products(query="", category="", max_price=None):
    try:
        params = {}
        if query:
            params["query"] = query
        if category:
            params["category"] = category
        if max_price is not None:
            params["max_price"] = max_price

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{BASE_URL}/catalog/products", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("products", [])
    except httpx.HTTPStatusError as e:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{BASE_URL}/products", params=params)
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else data.get("products", [])
        except Exception:
            return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def _execute_purchase(product_id, reason):
    try:
        payload = {
            "agent_id": AGENT_ID,
            "product_id": product_id,
            "reason": reason,
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{BASE_URL}/agent/purchase", json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


def _execute_tool(tool_name, tool_input, events):
    if tool_name == "discover_catalog":
        events.append({
            "type": "tool_call",
            "tool": "discover_catalog",
            "input": {},
            "summary": "Discovering the TechMart product catalog",
        })
        result = _discover_catalog()
        products = result.get("products", [])
        events.append({
            "type": "tool_result",
            "tool": "discover_catalog",
            "count": result.get("total_products", len(products)),
            "products": products[:3],
        })
        return json.dumps(result)

    elif tool_name == "search_products":
        query = tool_input.get("query", "")
        category = tool_input.get("category", "")
        max_price = tool_input.get("max_price")

        parts = []
        if query:
            parts.append(f"'{query}'")
        if category:
            parts.append(f"category={category}")
        if max_price:
            parts.append(f"under ₹{max_price:,}")
        summary = "Searching for " + (", ".join(parts) if parts else "all products")

        events.append({
            "type": "tool_call",
            "tool": "search_products",
            "input": tool_input,
            "summary": summary,
        })
        result = _search_products(query=query, category=category, max_price=max_price)
        products = result if isinstance(result, list) else []
        events.append({
            "type": "tool_result",
            "tool": "search_products",
            "count": len(products),
            "products": products[:3],
        })
        return json.dumps(result)

    elif tool_name == "execute_purchase":
        product_id = tool_input.get("product_id", "")
        reason = tool_input.get("reason", "best match for goal")

        events.append({
            "type": "tool_call",
            "tool": "execute_purchase",
            "input": tool_input,
            "summary": f"Purchasing product {product_id}: {reason}",
        })
        result = _execute_purchase(product_id, reason)
        return json.dumps(result)

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run_buyer_agent(goal, budget=None):
    events = []

    user_prompt = f"Goal: {goal}"
    if budget is not None:
        user_prompt += f"\nBudget: ₹{budget:,} (do not exceed this)"
    user_prompt += "\n\nPlease discover the catalog, find the best product, and complete the purchase now."

    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash-lite",
            system_instruction=SYSTEM_PROMPT,
            tools=[TOOLS],
        )

        events.append({
            "type": "thinking",
            "message": f"Starting autonomous buyer agent. Goal: {goal}"
            + (f" | Budget: ₹{budget:,}" if budget else ""),
        })

        convo = model.start_chat(history=[])
        response = convo.send_message(user_prompt)

        purchased = False

        while True:
            fn_calls = []
            for part in response.parts:
                if hasattr(part, "function_call") and part.function_call.name:
                    fn_calls.append(part.function_call)

            if not fn_calls:
                final_text = ""
                try:
                    final_text = response.text
                except Exception:
                    pass

                if final_text and not purchased:
                    events.append({
                        "type": "thinking",
                        "message": final_text,
                    })
                break

            model_text = ""
            try:
                model_text = response.text
            except Exception:
                pass
            if model_text and model_text.strip():
                events.append({
                    "type": "thinking",
                    "message": model_text.strip(),
                })

            fn_responses = []
            for fn_call in fn_calls:
                tool_name = fn_call.name
                tool_input = _to_python(fn_call.args)

                result_str = _execute_tool(tool_name, tool_input, events)
                result_data = json.loads(result_str)

                if tool_name == "execute_purchase":
                    if "error" in result_data:
                        events.append({
                            "type": "error",
                            "message": result_data["error"],
                        })
                    elif result_data.get("success"):
                        product = result_data.get("product", {})
                        events.append({
                            "type": "decision",
                            "product": product,
                            "reason": tool_input.get("reason", "best match for goal"),
                        })
                        events.append({
                            "type": "purchase",
                            "product_name": product.get("name", ""),
                            "amount": result_data.get("amount", product.get("price", 0)),
                            "payment_url": result_data.get("payment_url", ""),
                            "payment_link_id": result_data.get("payment_link_id", ""),
                        })
                        purchased = True
                    else:
                        events.append({
                            "type": "error",
                            "message": result_data.get("message", "Purchase failed — unknown error"),
                        })

                fn_responses.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": result_data},
                        )
                    )
                )

            events.append({
                "type": "thinking",
                "message": "Processing tool results and deciding next step...",
            })
            response = convo.send_message(fn_responses)

    except Exception as e:
        events.append({
            "type": "error",
            "message": f"Agent error: {str(e)}",
        })

    return events


if __name__ == "__main__":
    import sys

    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "I need a good laptop for programming"
    budget = None
    # last arg treated as budget if it's a number
    if len(sys.argv) > 2:
        try:
            budget = int(sys.argv[-1])
            goal = " ".join(sys.argv[1:-1])
        except ValueError:
            pass

    print(f"\n=== TechMart Autonomous Buyer Agent ===")
    print(f"Goal  : {goal}")
    print(f"Budget: {'₹' + str(budget) if budget else 'No limit'}")
    print("=" * 40)

    result_events = run_buyer_agent(goal, budget)

    for event in result_events:
        etype = event.get("type")
        if etype == "thinking":
            print(f"\n[THINKING] {event['message']}")
        elif etype == "tool_call":
            print(f"\n[TOOL CALL] {event['tool']} — {event['summary']}")
        elif etype == "tool_result":
            print(f"[TOOL RESULT] {event['tool']} → {event['count']} product(s) found")
        elif etype == "decision":
            p = event.get("product", {})
            print(f"\n[DECISION] Chose: {p.get('name', '?')} @ ₹{p.get('price', '?'):,}")
            print(f"           Reason: {event.get('reason')}")
        elif etype == "purchase":
            print(f"\n[PURCHASE COMPLETE]")
            print(f"  Product : {event['product_name']}")
            print(f"  Amount  : ₹{event['amount']:,}")
            print(f"  Pay URL : {event['payment_url']}")
            print(f"  Link ID : {event['payment_link_id']}")
        elif etype == "error":
            print(f"\n[ERROR] {event['message']}")
