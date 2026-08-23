import asyncio
import json
import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from pathlib import Path
import audit
import agent
import catalog as cat
import razorpay_tools as rz

app = FastAPI(title="Agentic Commerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions = {}


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    audit_trail: List[dict]
    products: List[dict] = []


class AgentPurchaseRequest(BaseModel):
    agent_id: str
    product_id: str
    reason: str = ""


class BuyerAgentRequest(BaseModel):
    goal: str
    budget: Optional[int] = None


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = []

    _sessions[session_id].append({"role": "user", "content": req.message})

    try:
        reply, updated_messages = await asyncio.to_thread(
            agent.chat, _sessions[session_id], session_id
        )
        _sessions[session_id] = updated_messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        audit_trail=audit.get_session_log(session_id),
        products=agent.get_last_products(session_id),
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = []

    _sessions[session_id].append({"role": "user", "content": req.message})

    async def generate():
        try:
            reply, updated_messages = await asyncio.to_thread(
                agent.chat, _sessions[session_id], session_id
            )
            _sessions[session_id] = updated_messages
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        for char in reply:
            yield f"data: {json.dumps({'type': 'chunk', 'text': char})}\n\n"
            await asyncio.sleep(0.012)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'audit_trail': audit.get_session_log(session_id), 'products': agent.get_last_products(session_id)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/discover")
async def discover():
    products = cat.PRODUCTS
    categories = list(set(p["category"] for p in products))
    return {
        "store": "TechMart",
        "description": "Electronics store specializing in laptops, monitors, and productivity accessories",
        "agent_api_version": "1.0",
        "capabilities": ["browse_catalog", "search_products", "checkout", "coupon_redemption"],
        "endpoints": {
            "catalog": "/catalog/products",
            "purchase": "/agent/purchase",
            "discover": "/discover",
        },
        "supported_currencies": ["INR"],
        "payment_provider": "Razorpay",
        "total_products": len(products),
        "categories": categories,
        "available_coupons": [
            {"code": "SAVE10", "discount": "10%", "min_order": 5000},
            {"code": "LAPTOP20", "discount": "20%", "min_order": 40000, "category": "laptop"},
            {"code": "NEWUSER", "discount": "15%", "min_order": 0},
        ],
    }


@app.get("/catalog/products")
async def catalog_products(query: str = "", category: str = "", max_price: int = None):
    results = cat.search_products(query=query, category=category, max_price=max_price)
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "price_inr": p["price"],
            "original_price_inr": p["original_price"],
            "discount_pct": round((p["original_price"] - p["price"]) / p["original_price"] * 100),
            "in_stock": p["stock"] > 0,
            "stock_count": p["stock"],
            "description": p["description"],
            "key_specs": [f"{k}: {v}" for k, v in list(p["specs"].items())[:4]],
            "tags": p["tags"],
            "upsell_product_ids": p["upsell_ids"],
        }
        for p in results
    ]


@app.post("/agent/purchase")
async def agent_purchase(req: AgentPurchaseRequest):
    product = cat.get_product(req.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product["stock"] == 0:
        raise HTTPException(status_code=400, detail="Product out of stock")

    try:
        result = await asyncio.to_thread(
            rz.create_payment_link,
            product["price"],
            f"AI Agent Purchase: {product['name']}",
            req.agent_id,
            "",
            "",
            {"agent_id": req.agent_id, "reason": req.reason, "product_id": req.product_id},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Payment creation failed: {e}")

    audit.record(
        req.agent_id, "agent_purchase",
        {"product_id": req.product_id, "product_name": product["name"],
         "amount": product["price"], "reason": req.reason,
         "payment_link_id": result["payment_link_id"]},
    )

    return {
        "success": True,
        "product": product,
        "amount": product["price"],
        "payment_url": result["short_url"],
        "payment_link_id": result["payment_link_id"],
        "agent_decision": req.reason,
    }


@app.post("/agent/run")
async def run_buyer_agent(req: BuyerAgentRequest):
    try:
        import buyer_agent
        events = await asyncio.to_thread(buyer_agent.run_buyer_agent, req.goal, req.budget)
        return {"success": True, "events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/audit/{session_id}")
async def get_audit(session_id: str):
    return {"session_id": session_id, "log": audit.get_session_log(session_id)}


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"status": "cleared"}


@app.get("/health")
async def health():
    return {"status": "ok"}


frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(frontend_path / "index.html"))
