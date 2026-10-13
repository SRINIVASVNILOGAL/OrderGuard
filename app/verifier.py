import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# A Jev score at or above this counts as a pass.
PASS_THRESHOLD = 0.90


# ---------------------------------------------------------
# CART -> CLEAN EVIDENCE
#
# Swiggy returns the cart as free text with UI hints and the
# same item listed more than once (variant line + base line).
# We only reshape it into plain fields. Jev still makes every
# judgement.
# ---------------------------------------------------------

def _cart_text(cart) -> str:
    if isinstance(cart, list):
        text = "\n".join(
            part.get("text", "") for part in cart if isinstance(part, dict)
        )
    else:
        text = str(cart or "")

    for marker in ("\n\nCart widget", "\n\nNOTE", "\n\nNo widget", "\n\n⚠️"):
        position = text.find(marker)
        if position != -1:
            text = text[:position]

    return text.strip()


def _number(pattern: str, text: str):
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def parse_cart(cart) -> dict:
    text = _cart_text(cart)

    items = {}
    for name, price, item_id in re.findall(
        r"^\s*-\s+(.*?)\s+—\s+₹([\d.]+)\s+\(ID:\s*(\d+)\)",
        text,
        flags=re.MULTILINE,
    ):
        # Same ID = same item. Keep the more detailed (variant) name.
        if item_id not in items or len(name) > len(items[item_id]["name"]):
            items[item_id] = {"name": name, "price": float(price)}

    count_match = re.search(r"Items \((\d+)\)", text)

    delivery_match = re.search(r"Delivery:\s*(.+)", text)

    return {
        "items": list(items.values()),
        "item_count": int(count_match.group(1)) if count_match else len(items),
        "item_total": _number(r"Item total:\s*₹([\d.]+)", text),
        "delivery": delivery_match.group(1).strip() if delivery_match else None,
        "taxes": _number(r"Taxes & charges:\s*₹([\d.]+)", text),
        "to_pay": _number(r"TO PAY:\s*₹([\d.]+)", text),
    }


def menu_diet(selected_item) -> str | None:
    # The menu line carries a Veg / Non-veg tag.
    line = (selected_item or {}).get("menu_line", "")
    match = re.search(r"\|\s*(Non-veg|Veg)\b", line, flags=re.IGNORECASE)
    if not match:
        return None
    return "Non-vegetarian" if match.group(1).lower() == "non-veg" else "Vegetarian"


def _money(value) -> str:
    return "unknown" if value is None else f"₹{value:g}"


def build_evidence(state, cart_info: dict, budget) -> str:
    proposed = state["proposed_order"]
    diet = menu_diet(state.get("selected_item"))

    lines = [f"Original user request:\n{state['user_request']}"]

    if budget is not None:
        lines.append(f"Maximum budget set by the user: {_money(budget)}")

    lines.append(
        "Agent's proposed order:\n"
        f"  item: {proposed.get('item')}\n"
        f"  restaurant: {proposed.get('restaurant_name')}\n"
        f"  quantity: {proposed.get('quantity')}"
    )

    cart_lines = [
        f"  - {item['name']} ({_money(item['price'])})"
        for item in cart_info["items"]
    ] or ["  (no items found)"]

    if diet:
        cart_lines.append(f"  diet tag from the menu: {diet}")

    lines.append(
        "Actual Swiggy cart:\n"
        + "\n".join(cart_lines)
        + f"\n  number of items in cart: {cart_info['item_count']}"
        + f"\n  item total: {_money(cart_info['item_total'])}"
        + f"\n  delivery: {cart_info['delivery'] or 'unknown'}"
        + f"\n  taxes and charges: {_money(cart_info['taxes'])}"
        + f"\n  TO PAY (what the user actually pays): {_money(cart_info['to_pay'])}"
    )

    return "\n\n".join(lines)


# ---------------------------------------------------------
# QUESTIONS
#
# Several narrow questions, each answerable on its own, so a
# failure points at exactly one thing.
# ---------------------------------------------------------

BUDGET_KEYWORDS = [
    "budget", "under", "below", "less than", "maximum", "max",
    "within", "₹", "rs", "rupees",
]


def build_questions(user_request: str, has_budget: bool) -> dict:
    text = user_request.lower()

    questions = {
        "right_item": {
            "type": "noul",
            "label": "Right dish",
            "instructions": (
                "Is the item in the actual cart the kind of dish the user "
                "asked for? The name does not need to match word for word: "
                "a specific variant of the requested dish is fine "
                "(for example 'Veg Longer Burger' for 'veg burger'). "
                "A different kind of dish is not fine."
            ),
        },
        "right_quantity": {
            "type": "noul",
            "label": "Quantity",
            "instructions": (
                "Does the cart contain the quantity the user asked for? "
                "If the user did not state a quantity, one unit is expected. "
                "Use 'number of items in cart', not repeated lines."
            ),
        },
    }

    if re.search(r"\bnon[- ]?veg", text):
        questions["right_diet"] = {
            "type": "noul",
            "label": "Diet",
            "instructions": (
                "The user asked for a non-vegetarian item. Is the item in "
                "the actual cart non-vegetarian?"
            ),
        }
    elif re.search(r"\bveg(etarian)?\b", text):
        questions["right_diet"] = {
            "type": "noul",
            "label": "Diet",
            "instructions": (
                "The user asked for a vegetarian item. Is the item in the "
                "actual cart vegetarian?"
            ),
        }

    if has_budget:
        questions["within_budget"] = {
            "type": "noul",
            "label": "Budget",
            "instructions": (
                "Is the TO PAY amount in the actual cart less than or equal "
                "to the maximum budget the user specified?"
            ),
        }

    return questions


# ---------------------------------------------------------
# GRAPH NODE
# ---------------------------------------------------------

def verifier_node(state):
    user_request = state["user_request"]

    # A budget typed into the dashboard's budget box is passed separately.
    budget = state.get("budget")

    has_budget = budget is not None or any(
        keyword in user_request.lower()
        for keyword in BUDGET_KEYWORDS
    )

    cart_info = parse_cart(state["cart"])
    evidence = build_evidence(state, cart_info, budget)
    questions = build_questions(user_request, has_budget)

    # "label" is for our dashboard only, so it is not sent to Jev.
    labels = {key: q["label"] for key, q in questions.items()}
    api_questions = {
        key: {k: v for k, v in q.items() if k != "label"}
        for key, q in questions.items()
    }

    payload = {
        "model": "typesafe/jev-1.13",
        "state": evidence,
        "questions": api_questions,
    }

    started = time.perf_counter()

    response = requests.post(
        "https://openrouter.ai/api/alpha/decisions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    latency = time.perf_counter() - started

    response.raise_for_status()

    result = response.json()

    scores = {
        key: result["answers"][key]["noul"]
        for key in questions
    }

    passed = all(score >= PASS_THRESHOLD for score in scores.values())

    request_scores = [
        score for key, score in scores.items() if key != "within_budget"
    ]

    verification_result = {
        "passed": passed,
        "checks": [
            {"key": key, "label": labels[key], "score": score}
            for key, score in scores.items()
        ],
        # Kept for older callers / tests.
        "matches_request": min(request_scores),
        "within_budget": scores.get("within_budget"),
        "latency_seconds": round(latency, 2),
        # Token / cost info if the API returns it, else None.
        "usage": result.get("usage"),
        "evidence": evidence,
    }

    print("\n===== JEV VERIFICATION =====")
    for key, score in scores.items():
        print(f"{labels[key]}: {score}")
    print(f"Latency: {latency:.2f}s")
    print(f"Verification passed: {passed}")

    return {
        "verification_result": verification_result
    }
