import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def main():
    user_request = "I want 1 paneer biryani under ₹400."

    cart = {
        "item": "Paneer Hyderabadi Biryani",
        "quantity": 1,
        "price": 365.0,
        "taxes": 62.48,
        "total": 427.0,
    }

    payload = {
        "model": "typesafe/jev-1.13",
        "state": (
            f"Original user request: {user_request}\n"
            f"Actual Swiggy cart: {cart}"
        ),
        "questions": {
            "matches_request": {
                "type": "noul",
                "instructions": (
                    "Does the actual cart match the item "
                    "and quantity requested by the user?"
                ),
            },
            "within_budget": {
                "type": "noul",
                "instructions": (
                    "Is the actual cart total within the "
                    "maximum budget stated by the user?"
                ),
            },
        },
    }

    response = requests.post(
        "https://openrouter.ai/api/alpha/decisions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    response.raise_for_status()

    result = response.json()

    print("Jev response:")
    print(result)


if __name__ == "__main__":
    main()