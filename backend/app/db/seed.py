from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.user import User

_PRODUCTS = [
    Product(
        name="Laptop",
        description="14-inch ultrabook with 16GB RAM and 512GB SSD.",
        image_url="/products/laptop.jpg",
        price=999.99,
        stock_quantity=10,
    ),
    Product(
        name="Wireless Mouse",
        description="Ergonomic wireless mouse with long battery life.",
        image_url="/products/wireless-mouse.jpg",
        price=29.99,
        stock_quantity=20,
    ),
    Product(
        name="Mechanical Keyboard",
        description="Tactile mechanical keyboard with RGB backlight.",
        image_url="/products/mechanical-keyboard.jpg",
        price=149.99,
        stock_quantity=15,
    ),
    Product(
        name="USB-C Hub",
        description="7-in-1 USB-C hub with HDMI, USB-A, and SD card reader.",
        image_url="/products/usb-c-hub.jpg",
        price=49.99,
        stock_quantity=18,
    ),
    Product(
        name="Monitor Stand",
        description="Adjustable aluminum monitor stand with storage shelf.",
        image_url="/products/monitor-stand.jpg",
        price=79.99,
        stock_quantity=12,
    ),
    Product(
        name="Webcam",
        description="1080p HD webcam with built-in microphone.",
        image_url="/products/webcam.jpg",
        price=89.99,
        stock_quantity=14,
    ),
    Product(
        name="Apple AirTag",
        description=(
            "Apple AirTag is a small, round Bluetooth tracker that attaches to keys, bags, "
            "or valuables. Uses Apple's Find My network — hundreds of millions of Apple devices — "
            "to locate lost items. Precision Finding with Ultra Wideband guides you to the exact "
            "spot. Water-resistant (IP67), replaceable CR2032 battery (~1 year), works seamlessly "
            "with iPhone and iPad."
        ),
        image_url="/products/round-item-tracker.jpg",
        price=29.99,
        stock_quantity=25,
    ),
    Product(
        name="Tile Mate",
        description=(
            "Tile Mate is a Bluetooth item tracker that attaches to keys, wallets, or bags. "
            "Uses the Tile community network to locate lost items outside Bluetooth range. "
            "Loud 90dB built-in speaker lets you ring the Tile to find nearby items. "
            "Water-resistant (IP67), replaceable CR1632 battery (~3 years), works with both "
            "Android and iPhone via the Tile app."
        ),
        image_url="/products/square-item-tracker.jpg",
        price=24.99,
        stock_quantity=30,
    ),
]


def seed_database(db: Session) -> None:
    if db.query(User).count() == 0:
        db.add_all(
            [
                User(name="Alice Nguyen", email="alice@example.com", balance=1000.0),
                User(name="Bob Tanaka", email="bob@example.com", balance=1000.0),
                User(name="Carol Okafor", email="carol@example.com", balance=1000.0),
            ]
        )

    existing_names = {name for (name,) in db.query(Product.name).all()}
    new_products = [p for p in _PRODUCTS if p.name not in existing_names]
    if new_products:
        db.add_all(new_products)

    product_images = {p.name: p.image_url for p in _PRODUCTS}
    for product in db.query(Product).filter(Product.name.in_(product_images)).all():
        product.image_url = product_images[product.name]

    db.commit()
