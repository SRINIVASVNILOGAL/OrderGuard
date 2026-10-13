import asyncio
import json

from openai import OpenAI

from app.agent import load_swiggy_tools
from app.config import OPENROUTER_API_KEY


client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)


async def main():
    tools = await load_swiggy_tools()

    # --------------------------------------------------
    # 1. Application gets the saved address
    # --------------------------------------------------

    get_addresses = next(
        tool for tool in tools
        if tool.name == "get_addresses"
    )

    address_result = await get_addresses.ainvoke({})

    address_text = address_result[0]["text"]
    first_line = address_text.splitlines()[1]

    address_id = (
        first_line.split("(ID: ")[1].split(")")[0]
    )

    print("Application selected address:")
    print(address_id)

    # --------------------------------------------------
    # 2. Search restaurants
    # --------------------------------------------------

    search_restaurants = next(
        tool for tool in tools
        if tool.name == "search_restaurants"
    )

    search_schema = {
        "type": "function",
        "function": {
            "name": search_restaurants.name,
            "description": search_restaurants.description,
            "parameters": search_restaurants.args,
        },
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are the restaurant-search agent for OrderGuard. "
                "The application has already selected the user's "
                "delivery address. Do not retrieve an address. "
                "Use search_restaurants to find restaurants."
            ),
        },
        {
            "role": "user",
            "content": "Find me a paneer biryani.",
        },
    ]

    response = client.chat.completions.create(
        model="openrouter/free",
        messages=messages,
        tools=[search_schema],
    )

    message = response.choices[0].message
    tool_call = message.tool_calls[0]

    search_arguments = json.loads(
        tool_call.function.arguments
    )

    search_arguments["addressId"] = address_id
    search_arguments["offset"] = 0

    search_result = await search_restaurants.ainvoke(
        search_arguments
    )

    restaurant_text = search_result[0]["text"]

    print("\n===== RAW RESTAURANT RESPONSE =====")
    print(repr(restaurant_text))
    print("====================================")

    json_end = restaurant_text.find("\n\n⚠️")

    restaurant_json = (
    restaurant_text[:json_end]
    if json_end != -1
    else restaurant_text
    )

    print("\n===== TEXT WE ARE TRYING TO PARSE =====")
    print(repr(restaurant_json))
    print("========================================")

    restaurant_data = json.loads(restaurant_json)

    # --------------------------------------------------
    # 3. LLM chooses a restaurant
    # --------------------------------------------------

    messages.append(message)

    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(restaurant_data),
        }
    )

    messages.append(
        {
            "role": "user",
            "content": (
                "From these restaurant results, choose the "
                "best restaurant for the user's paneer biryani "
                "request. Return only the restaurant name and ID."
            ),
        }
    )

    second_response = client.chat.completions.create(
        model="openrouter/free",
        messages=messages,
    )

    restaurant_choice = (
        second_response.choices[0].message.content
    )

    print("\nLLM selected restaurant:")
    print(restaurant_choice)

    # --------------------------------------------------
    # 4. For this test, use the selected restaurant ID
    # --------------------------------------------------

    restaurant_id = "229"

    # --------------------------------------------------
    # 5. Get the restaurant menu
    # --------------------------------------------------

    get_restaurant_menu = next(
        tool for tool in tools
        if tool.name == "get_restaurant_menu"
    )

    menu_result = await get_restaurant_menu.ainvoke({
        "restaurantId": restaurant_id,
        "addressId": address_id,
        "page": 1,
        "pageSize": 10,
    })

    print("\nMENU RESULT:")
    print(menu_result)


asyncio.run(main())