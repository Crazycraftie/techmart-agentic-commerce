import os
import httpx
import razorpay
from dotenv import load_dotenv

load_dotenv()

_client = None


def _auth():
    return (os.getenv("RAZORPAY_KEY_ID", "").strip(), os.getenv("RAZORPAY_KEY_SECRET", "").strip())


def get_client() -> razorpay.Client:
    global _client
    if _client is None:
        _client = razorpay.Client(auth=_auth())
    return _client


def create_order(amount_inr: float, currency: str = "INR", notes: dict = None) -> dict:
    client = get_client()
    amount_paise = int(amount_inr * 100)
    payload = {
        "amount": amount_paise,
        "currency": currency,
        "notes": notes or {},
    }
    order = client.order.create(data=payload)
    return {
        "order_id": order["id"],
        "amount": amount_inr,
        "currency": currency,
        "status": order["status"],
        "receipt": order.get("receipt"),
    }


def create_payment_link(
    amount_inr: float,
    description: str,
    customer_name: str = "Valued Customer",
    customer_email: str = "",
    customer_phone: str = "",
    notes: dict = None,
) -> dict:
    client = get_client()
    amount_paise = int(amount_inr * 100)
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "description": description,
        "customer": {
            "name": customer_name,
            "email": customer_email,
            "contact": customer_phone,
        },
        "notify": {"sms": False, "email": False},
        "notes": notes or {},
        "callback_url": "http://localhost:3000/payment-success",
        "callback_method": "get",
    }
    link = client.payment_link.create(data=payload)
    return {
        "payment_link_id": link["id"],
        "short_url": link["short_url"],
        "amount": amount_inr,
        "status": link["status"],
    }


def fetch_payment_link_status(payment_link_id: str) -> dict:
    response = httpx.get(
        f"https://api.razorpay.com/v1/payment_links/{payment_link_id}",
        auth=_auth(),
        timeout=15,
    )
    response.raise_for_status()
    link = response.json()
    return {
        "payment_link_id": link["id"],
        "status": link["status"],
        "amount": link["amount"] / 100,
        "paid": link["status"] == "paid",
        "payments": link.get("payments", []),
    }


def fetch_order_payments(order_id: str) -> dict:
    client = get_client()
    payments = client.order.payments(order_id)
    return {
        "order_id": order_id,
        "count": payments["count"],
        "payments": [
            {
                "payment_id": p["id"],
                "amount": p["amount"] / 100,
                "status": p["status"],
                "method": p.get("method"),
                "error_code": p.get("error_code"),
                "error_description": p.get("error_description"),
            }
            for p in payments.get("items", [])
        ],
    }
