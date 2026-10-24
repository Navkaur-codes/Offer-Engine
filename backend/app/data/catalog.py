"""Category economics + a ~120-product catalogue with Indian market names and ₹ prices.

Margins follow public Indian e-commerce norms (electronics ~10%, grocery ~15%, fashion/beauty ~50%);
they feed the margin guard (Session B) and the impact estimate (scoring.impact). Prices are whole rupees.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts import Category


@dataclass(frozen=True)
class CategorySpec:
    margin: float  # gross margin share
    aov_median: int  # median single-order value (₹); order values are lognormal around it
    aov_sigma: float  # lognormal σ
    price_band: tuple[int, int]
    return_rate: float  # base share of orders returned
    shipping_cost: int  # what free shipping costs us per order (₹)


CATEGORIES: dict[Category, CategorySpec] = {
    "fashion": CategorySpec(0.50, 1100, 0.55, (299, 4999), 0.21, 60),
    "ethnic_wear": CategorySpec(0.48, 1800, 0.60, (499, 12999), 0.17, 70),
    "electronics": CategorySpec(0.10, 7500, 0.90, (499, 74999), 0.07, 120),
    "beauty": CategorySpec(0.50, 650, 0.50, (149, 2999), 0.05, 50),
    "home_decor": CategorySpec(0.40, 1300, 0.60, (199, 9999), 0.08, 90),
    "kitchen": CategorySpec(0.30, 1500, 0.60, (249, 9999), 0.06, 90),
    "grocery": CategorySpec(0.15, 700, 0.45, (99, 2999), 0.02, 40),
    "jewellery": CategorySpec(0.25, 5500, 0.90, (299, 49999), 0.05, 80),
    "gifting": CategorySpec(0.35, 1200, 0.55, (299, 7999), 0.04, 60),
    "winter_wear": CategorySpec(0.45, 1900, 0.50, (399, 8999), 0.14, 70),
}

# (name, price ₹) per category: 12 each, spread across the price band so lognormal draws find a match.
_PRODUCTS: dict[Category, list[tuple[str, int]]] = {
    "fashion": [
        ("Cotton Kurta", 1450),
        ("Slim Fit Denim Jeans", 1699),
        ("Printed Cotton T-Shirt", 499),
        ("Linen Casual Shirt", 1299),
        ("Palazzo Pants", 799),
        ("Running Sneakers", 2499),
        ("Kolhapuri Chappals", 899),
        ("Polo T-Shirt Pack of 2", 999),
        ("Chikankari Short Kurti", 1199),
        ("Leather Belt", 599),
        ("Canvas Backpack", 1499),
        ("Aviator Sunglasses", 2999),
    ],
    "ethnic_wear": [
        ("Phulkari Dupatta", 1299),
        ("Patiala Salwar Suit Set", 2499),
        ("Banarasi Silk Saree", 6499),
        ("Embroidered Lehenga Choli", 8999),
        ("Men's Nehru Jacket", 1899),
        ("Cotton Anarkali Kurta", 1599),
        ("Silk Kurta Pyjama Set", 2799),
        ("Punjabi Jutti", 999),
        ("Georgette Sharara Set", 3299),
        ("Pathani Suit", 1999),
        ("Chanderi Dupatta", 749),
        ("Sherwani with Stole", 11999),
    ],
    "electronics": [
        ("boAt Airdopes TWS Earbuds", 1299),
        ("Redmi 13C Smartphone", 9999),
        ("Mi Smart Band", 2499),
        ("Samsung 43-inch 4K Smart TV", 31990),
        ("JBL Bluetooth Speaker", 4999),
        ("Philips Trimmer", 1499),
        ("Lenovo IdeaPad Laptop", 48990),
        ("Realme 10000mAh Power Bank", 1199),
        ("Noise Smartwatch", 2999),
        ("Canon Inkjet Printer", 3999),
        ("Sony Soundbar", 14990),
        ("Wall Mount for TV", 799),
    ],
    "beauty": [
        ("Lakmé Lipstick", 449),
        ("Mamaearth Face Wash", 299),
        ("Nykaa Kajal", 199),
        ("Biotique Sunscreen SPF 50", 399),
        ("Forest Essentials Facial Mist", 1275),
        ("Kama Ayurveda Kumkumadi Oil", 2195),
        ("Plum Green Tea Toner", 390),
        ("Minimalist Niacinamide Serum", 599),
        ("Bridal Mehendi Cone Pack", 249),
        ("Beard Grooming Kit", 899),
        ("Perfume Gift Set", 1499),
        ("Hair Straightener", 1899),
    ],
    "home_decor": [
        ("Brass Diya Set of 4", 699),
        ("LED String Lights 10 m", 399),
        ("Jaipuri Cotton Bedsheet", 1199),
        ("Handloom Cushion Covers Set of 5", 899),
        ("Wall Clock Wooden", 1499),
        ("Rangoli Stencil Kit", 249),
        ("Torans Door Hanging", 549),
        ("Ceramic Vase", 999),
        ("Blackout Curtains Pair", 1799),
        ("Pooja Thali Set", 1299),
        ("Floor Rug 5x7", 3499),
        ("Decorative Wall Mirror", 4999),
    ],
    "kitchen": [
        ("Prestige Pressure Cooker 5 L", 2199),
        ("Non-stick Tawa", 899),
        ("Steel Dinner Set 24 pcs", 2999),
        ("Mixer Grinder 750 W", 3499),
        ("Copper Water Bottle", 799),
        ("Masala Dabba", 649),
        ("Electric Kettle 1.5 L", 1099),
        ("Air Fryer 4 L", 5999),
        ("Glass Storage Jars Set", 999),
        ("Cast Iron Kadai", 1499),
        ("Induction Cooktop", 2799),
        ("Silver-plated Serving Bowl", 1899),
    ],
    "grocery": [
        ("Basmati Rice 5 kg", 699),
        ("Dry Fruit Gift Box 500 g", 1199),
        ("Desi Ghee 1 L", 649),
        ("Masala Chai 500 g", 299),
        ("Kaju Katli 500 g", 599),
        ("Gajak & Rewri Combo", 349),
        ("Organic Atta 10 kg", 549),
        ("Cold-pressed Mustard Oil 1 L", 249),
        ("Soan Papdi Box", 199),
        ("Assorted Namkeen Pack", 399),
        ("Premium Almonds 1 kg", 1099),
        ("Festive Sweets Hamper", 1899),
    ],
    "jewellery": [
        ("Oxidised Jhumka Earrings", 399),
        ("Kundan Necklace Set", 2499),
        ("Silver Anklets Pair", 1899),
        ("Gold Coin 1 g 24K", 7499),
        ("Silver Coin 10 g", 1299),
        ("Diamond Stud Earrings", 18999),
        ("Gold-plated Bangles Set", 999),
        ("Kada for Men", 1499),
        ("Temple Jewellery Set", 3999),
        ("Gold Coin 5 g 24K", 36999),
        ("Pearl Mala", 1799),
        ("Nose Pin Gold", 4999),
    ],
    "gifting": [
        ("Personalised Photo Frame", 599),
        ("Chocolate Gift Hamper", 999),
        ("Rakhi & Sweets Combo", 699),
        ("Corporate Diwali Hamper", 2999),
        ("Scented Candle Gift Set", 799),
        ("Leather Wallet Gift Box", 1299),
        ("Silver-plated Ganesh Idol", 1499),
        ("Couple Watch Set", 3999),
        ("Karwa Chauth Thali Set", 899),
        ("Dry Fruit & Diya Hamper", 1599),
        ("Premium Tea Gift Box", 1199),
        ("Gift Card ₹5,000", 5000),
    ],
    "winter_wear": [
        ("Woollen Shawl", 1299),
        ("Puffer Jacket", 3499),
        ("Thermal Inner Set", 799),
        ("Pashmina Stole", 4999),
        ("Hand-knit Sweater", 1599),
        ("Leather Jacket", 7999),
        ("Woollen Cap & Muffler", 499),
        ("Fleece Hoodie", 1199),
        ("Kashmiri Pheran", 2499),
        ("Winter Gloves", 399),
        ("Long Overcoat", 5499),
        ("Woollen Socks Pack of 3", 449),
    ],
}


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: Category
    price: int
    margin: float


def products() -> list[Product]:
    out: list[Product] = []
    for category, items in _PRODUCTS.items():
        margin = CATEGORIES[category].margin
        for name, price in items:
            out.append(Product(f"P{len(out) + 1:03d}", name, category, price, margin))
    return out


PRODUCTS: list[Product] = products()
