import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

restaurants = [
    "Narmada Chain of Restaurant",
    "Biryani Blues",
    "Andhra Gunpowder (Ad)",
    "Mani's Dum Biryani",
    "1947 Restaurant (Ad)",
    "Meghana Foods (Ad)",
    "Guntur Biryani",
    "Thalairaj Biryani",
    "Sharief Bhai Biryani",
]

response = client.chat.completions.create(
    model="deepseek/deepseek-v3.2",
    messages=[
        {
            "role": "system",
            "content": (
                "Choose the most suitable restaurant from the provided list "
                "for the user's request. "
                "Return ONLY the exact restaurant name from the list. "
                "Do not explain. "
                "Do not return anything except the restaurant name."
            ),
        },
        {
            "role": "user",
            "content": (
                "User request: I want paneer biryani\n\n"
                f"Restaurants:\n{restaurants}"
            ),
        },
    ],
)

print("\n===== RAW MODEL RESPONSE =====")
print(response)