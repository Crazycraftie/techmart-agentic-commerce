PRODUCTS = [
    {
        "id": "prod_001",
        "name": "Lenovo IdeaPad Slim 5",
        "category": "laptop",
        "price": 45999,
        "original_price": 52999,
        "stock": 8,
        "specs": {
            "processor": "Intel Core i5-12th Gen",
            "ram": "16GB",
            "storage": "512GB SSD",
            "display": "15.6 inch FHD",
            "battery": "Up to 10 hours",
            "os": "Windows 11"
        },
        "tags": ["laptop", "student", "budget", "thin", "light"],
        "description": "Perfect for students and professionals. Thin, light, and powerful.",
        "upsell_ids": ["prod_003", "prod_004"]
    },
    {
        "id": "prod_002",
        "name": "Dell XPS 13",
        "category": "laptop",
        "price": 89999,
        "original_price": 99999,
        "stock": 3,
        "specs": {
            "processor": "Intel Core i7-13th Gen",
            "ram": "16GB",
            "storage": "1TB SSD",
            "display": "13.4 inch OLED Touch",
            "battery": "Up to 12 hours",
            "os": "Windows 11 Pro"
        },
        "tags": ["laptop", "premium", "ultrabook", "professional", "OLED"],
        "description": "Premium ultrabook with stunning OLED display. For professionals who demand the best.",
        "upsell_ids": ["prod_004", "prod_005"]
    },
    {
        "id": "prod_003",
        "name": "HP Laptop Bag 15.6 inch",
        "category": "accessory",
        "price": 1299,
        "original_price": 1999,
        "stock": 25,
        "specs": {
            "compatibility": "Fits upto 15.6 inch laptops",
            "material": "Polyester",
            "compartments": "3",
            "warranty": "1 year"
        },
        "tags": ["bag", "accessory", "laptop-bag", "carry"],
        "description": "Durable and stylish laptop bag with multiple compartments.",
        "upsell_ids": []
    },
    {
        "id": "prod_004",
        "name": "Logitech MX Keys Wireless Keyboard",
        "category": "accessory",
        "price": 8999,
        "original_price": 11999,
        "stock": 12,
        "specs": {
            "connectivity": "Bluetooth + USB Receiver",
            "battery": "10 days rechargeable",
            "compatibility": "Windows, Mac, Linux",
            "backlit": "Yes"
        },
        "tags": ["keyboard", "wireless", "accessory", "productivity"],
        "description": "Premium wireless keyboard with perfect typing experience for productivity.",
        "upsell_ids": ["prod_005"]
    },
    {
        "id": "prod_005",
        "name": "Logitech MX Master 3S Mouse",
        "category": "accessory",
        "price": 7999,
        "original_price": 9999,
        "stock": 15,
        "specs": {
            "connectivity": "Bluetooth + USB Receiver",
            "dpi": "200-8000 DPI",
            "battery": "70 days rechargeable",
            "buttons": "7 programmable buttons"
        },
        "tags": ["mouse", "wireless", "accessory", "productivity"],
        "description": "The master of mice. Ergonomic design with MagSpeed scroll for serious work.",
        "upsell_ids": []
    },
    {
        "id": "prod_006",
        "name": "Samsung 27 inch 4K Monitor",
        "category": "monitor",
        "price": 28999,
        "original_price": 35999,
        "stock": 5,
        "specs": {
            "resolution": "3840x2160 (4K)",
            "panel": "IPS",
            "refresh_rate": "60Hz",
            "ports": "HDMI 2.0, DisplayPort, USB-C",
            "response_time": "4ms"
        },
        "tags": ["monitor", "4K", "display", "productivity", "designer"],
        "description": "Crystal clear 4K IPS monitor. Perfect for designers and developers.",
        "upsell_ids": ["prod_004", "prod_005"]
    }
]

COUPONS = {
    "SAVE10": {"discount_pct": 10, "min_order": 5000, "description": "10% off on orders above ₹5000"},
    "NEWUSER": {"discount_pct": 15, "min_order": 0, "description": "15% off for new users"},
    "LAPTOP20": {"discount_pct": 20, "min_order": 40000, "description": "20% off on laptops above ₹40000"},
}


def search_products(query: str = "", category: str = "", max_price: int = None) -> list:
    results = PRODUCTS
    if category:
        results = [p for p in results if p["category"].lower() == category.lower()]
    if max_price:
        results = [p for p in results if p["price"] <= max_price]
    if query:
        query_lower = query.lower()
        results = [
            p for p in results
            if query_lower in p["name"].lower()
            or query_lower in p["description"].lower()
            or any(query_lower in tag for tag in p["tags"])
        ]
    return results


def get_product(product_id: str):
    return next((p for p in PRODUCTS if p["id"] == product_id), None)


def get_upsells(product_id: str) -> list:
    product = get_product(product_id)
    if not product:
        return []
    return [get_product(uid) for uid in product["upsell_ids"] if get_product(uid)]


def validate_coupon(code: str, order_amount: int) -> dict:
    coupon = COUPONS.get(code.upper())
    if not coupon:
        return {"valid": False, "reason": "Coupon not found"}
    if order_amount < coupon["min_order"]:
        return {"valid": False, "reason": f"Minimum order amount is ₹{coupon['min_order']}"}
    discount = int(order_amount * coupon["discount_pct"] / 100)
    return {
        "valid": True,
        "discount_pct": coupon["discount_pct"],
        "discount_amount": discount,
        "final_amount": order_amount - discount,
        "description": coupon["description"]
    }
