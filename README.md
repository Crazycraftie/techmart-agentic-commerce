# TechMart — Agentic Commerce Assistant

> Razorpay AI Buildathon · Track 01: AI Growth & Agentic Commerce

An AI-powered electronics store where a Gemini agent handles the full shopping journey — from product discovery to real Razorpay payment links — and a second autonomous buyer agent completes purchases with zero human involvement.

---

## Features

### Human Buyer Flow
- **Streaming chat** — typewriter SSE streaming via `/chat/stream`
- **Product cards** — rendered after every search with one-click **Place Order** and **Details** buttons
- **Coupon engine** — validates SAVE10, NEWUSER, LAPTOP20 codes mid-conversation
- **Upsell recommendations** — agent suggests accessories naturally, never pushily
- **Real payment links** — Razorpay test-mode links created and shared inline
- **Payment status check** — agent confirms when payment goes through
- **Audit trail** — every agent action logged live in the sidebar

### Agent-to-Agent (A2A) Commerce
- `/discover` — machine-readable store manifest for AI buyer agents
- `/catalog/products` — structured catalog endpoint (query, category, price filters)
- `/agent/purchase` — autonomous purchase endpoint; creates a real Razorpay payment link
- **Autonomous buyer agent** — given a goal + budget, it discovers the catalog, evaluates products, decides, and transacts with no human in the loop
- Live event feed in the UI shows every step: thinking → tool calls → decision → payment

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.9 · FastAPI · SSE streaming |
| AI Agent | Google Gemini 2.5 Flash via `google-generativeai` |
| Payments | Razorpay test-mode (Orders + Payment Links) via direct REST |
| Frontend | Vanilla HTML/CSS/JS — zero dependencies |

---

## Quickstart

### 1. Clone
```bash
git clone https://github.com/Crazycraftie/techmart-agentic-commerce.git
cd techmart-agentic-commerce
```

### 2. Set up environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in your keys:
#   GEMINI_API_KEY  — from Google AI Studio (free)
#   RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET — from Razorpay test dashboard
```

### 3. Run
```bash
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | Non-streaming chat |
| POST | `/chat/stream` | SSE streaming chat |
| GET | `/discover` | Agent-readable store manifest |
| GET | `/catalog/products` | Structured catalog (filterable) |
| POST | `/agent/purchase` | Autonomous purchase endpoint |
| POST | `/agent/run` | Run the full autonomous buyer agent |
| GET | `/audit/{session_id}` | Session audit log |
| GET | `/health` | Health check |

---

## Project Structure

```
techmart-agentic-commerce/
├── backend/
│   ├── main.py          # FastAPI app, all endpoints
│   ├── agent.py         # Human-buyer Gemini agent + tool execution
│   ├── buyer_agent.py   # Autonomous A2A buyer agent
│   ├── catalog.py       # 6 products + coupon engine
│   ├── razorpay_tools.py# Payment link creation + status check
│   ├── audit.py         # In-memory + JSON audit logger
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html       # Full UI (streaming, product cards, A2A demo)
```

---

## Available Coupons (test mode)

| Code | Discount | Minimum Order |
|---|---|---|
| `SAVE10` | 10% off | ₹5,000 |
| `NEWUSER` | 15% off | None |
| `LAPTOP20` | 20% off | ₹40,000 (laptops only) |

---

## Razorpay Buildathon

**Track:** 01 — AI Growth & Agentic Commerce  
**Submission deadline:** 5 September 2026  
**Built by:** Dhirendra Pratap Singh
