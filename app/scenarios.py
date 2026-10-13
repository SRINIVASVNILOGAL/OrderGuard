"""Labelled test scenarios for OrderGuard.

Each scenario is a user request, the order an agent proposed and the cart
Swiggy returned, plus the verdict we EXPECT (pass or flag). They are
synthetic, so they run with no Swiggy login and never touch a real cart.
The same list feeds evaluate.py and the dashboard's scenario picker.
"""

import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    user_request: str
    restaurant: str
    item: str             # item that ended up in the cart
    price: float          # price of one unit
    diet: str             # "Veg" or "Non-veg"
    expect_pass: bool     # verdict we expect from a good verifier
    mistake: str          # "" for correct orders, else the kind of mistake
    budget: float | None = None
    cart_count: int = 1   # units actually in the cart
    proposed_quantity: int = 1
    taxes: float = 60.0


SCENARIOS = [
    # ---------------- correct orders (should PASS) ----------------
    Scenario("ok-biryani", "Paneer biryani, exact item",
             "I want paneer biryani", "Biryani Blues",
             "Paneer Biryani", 249, "Veg", True, ""),
    Scenario("ok-burger-variant", "Veg burger -> 'Veg Longer Burger'",
             "i want veg burger", "KFC",
             "Veg Longer Burger - 2pc", 198, "Veg", True, "",
             budget=400, taxes=72.88),
    Scenario("ok-pizza-budget", "Veg pizza under budget",
             "i want veg pizza", "Domino's Pizza",
             "Veg Extravaganza Pizza", 329, "Veg", True, "",
             budget=450, taxes=66.98),
    Scenario("ok-chicken", "Chicken biryani, non-veg",
             "I want chicken biryani", "Meghana Foods",
             "Chicken Dum Biryani", 299, "Non-veg", True, ""),
    Scenario("ok-dosa", "Masala dosa within budget",
             "i want masala dosa", "Udupi Grand",
             "Masala Dosa", 90, "Veg", True, "",
             budget=200, taxes=30),
    Scenario("ok-two-pizzas", "Two margherita pizzas, quantity 2",
             "I want 2 margherita pizza", "Domino's Pizza",
             "Margherita Pizza", 112, "Veg", True, "",
             cart_count=2, proposed_quantity=2),
    Scenario("ok-coffee", "Cold coffee",
             "i want a cold coffee", "Cafe Coffee Day",
             "Cold Coffee", 120, "Veg", True, "", taxes=25),
    Scenario("ok-nonveg-burger", "Non-veg burger, chicken",
             "i want non veg burger", "KFC",
             "Zinger Chicken Burger", 189, "Non-veg", True, ""),

    # ---------------- deliberate mistakes (should FLAG) ----------------
    Scenario("bad-diet-pizza", "Veg pizza but cart has chicken pizza",
             "i want veg pizza", "Domino's Pizza",
             "Chicken Pepperoni Pizza", 379, "Non-veg", False, "wrong diet"),
    Scenario("bad-dish-biryani", "Paneer biryani but cart has chicken biryani",
             "I want paneer biryani", "Biryani Blues",
             "Chicken Dum Biryani", 299, "Non-veg", False, "wrong dish and diet"),
    Scenario("bad-budget-combo", "Veg burger, budget 250, combo costs more",
             "i want veg burger", "Leon's - Burgers & Wings",
             "Veggie Supreme Burger Combo", 359, "Veg", False, "over budget",
             budget=250, taxes=72.68),
    Scenario("bad-dish-garlic", "Veg burger but cart has garlic bread",
             "i want veg burger", "Domino's Pizza",
             "Garlic Bread", 99, "Veg", False, "wrong dish"),
    Scenario("bad-qty-short", "Asked for 2 pizzas, cart has 1",
             "I want 2 margherita pizza", "Domino's Pizza",
             "Margherita Pizza", 112, "Veg", False, "wrong quantity",
             cart_count=1, proposed_quantity=1),
    Scenario("bad-qty-extra", "Asked for 1 dosa, cart has 3",
             "i want masala dosa", "Udupi Grand",
             "Masala Dosa", 90, "Veg", False, "wrong quantity",
             cart_count=3, proposed_quantity=3, taxes=40),
    Scenario("bad-dish-drink", "Pizza requested, cart has a soft drink",
             "i want pizza", "McDonald's",
             "Coca-Cola 500ml", 60, "Veg", False, "wrong dish", taxes=15),
    Scenario("bad-budget-taxes", "Dosa fits budget by item price, not by TO PAY",
             "i want masala dosa", "Udupi Grand",
             "Masala Dosa", 90, "Veg", False, "over budget",
             budget=100, taxes=62),
    Scenario("bad-diet-burger", "Non-veg burger but cart has veg burger",
             "i want non veg burger", "KFC",
             "Veg Longer Burger - 2pc", 198, "Veg", False, "wrong diet",
             taxes=72.88),
    Scenario("bad-budget-paneer", "Paneer butter masala, budget 250, TO PAY 305",
             "i want paneer butter masala", "Punjabi Dhaba",
             "Paneer Butter Masala", 240, "Veg", False, "over budget",
             budget=250, taxes=65),
]


def make_cart(scenario: Scenario) -> list:
    """Cart in the same shape the Swiggy MCP returns it, including the
    duplicated item line and the trailing widget notes."""
    item_total = scenario.price * scenario.cart_count
    to_pay = item_total + scenario.taxes
    item_id = 100000 + (zlib.crc32(scenario.id.encode()) % 900000)

    line = f"  - {scenario.item} — ₹{scenario.price:g} (ID: {item_id})"

    text = (
        f"Items ({scenario.cart_count}):\n"
        f"{line}\n{line}\n\n"
        f"Item total: ₹{item_total:g}\n"
        "Delivery: FREE\n"
        f"Taxes & charges: ₹{scenario.taxes:g}\n"
        f"TO PAY: ₹{to_pay:g}\n\n"
        "Cart widget is displayed — do not repeat the cart items, prices, or totals in text."
    )

    return [{"type": "text", "text": text}]


def build_state(scenario: Scenario) -> dict:
    """State dict in the shape verifier_node expects."""
    tag = scenario.diet
    menu_line = f"- {scenario.item} — ₹{scenario.price:g} | {tag}, has variants (ID: 1)"

    state = {
        "user_request": scenario.user_request,
        "proposed_order": {
            "restaurant_name": scenario.restaurant,
            "item": scenario.item,
            "quantity": scenario.proposed_quantity,
        },
        "selected_item": {"name": scenario.item, "menu_line": menu_line},
        "cart": make_cart(scenario),
    }

    if scenario.budget is not None:
        state["budget"] = scenario.budget

    return state
