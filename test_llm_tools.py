import asyncio
import json

from app.agent import load_swiggy_tools
from app.config import OPENROUTER_API_KEY
from openai import OpenAI


async def main():
    tools = await load_swiggy_tools()

    get_addresses = next(
        tool for tool in tools
        if tool.name == "get_addresses"
    )

    search_restaurants = next(
        tool for tool in tools
        if tool.name == "search_restaurants"
    )

    # Get saved addresses
    address_result = await get_addresses.ainvoke({})

    address_text = address_result[0]["text"]

    first_line = address_text.splitlines()[1]

    first_address_id = first_line.split("(ID: ")[1].split(")")[0]

    print("Using first saved address ID:", first_address_id)

    # Create LLM client
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )

    tool_schema = {
        "type": "function",
        "function": {
            "name": search_restaurants.name,
            "description": search_restaurants.description,
            "parameters": search_restaurants.args,
        },
    }

    # Ask LLM what tool to use
    response = client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {
                "role": "user",
                "content": (
                    "Find restaurants for paneer biryani. "
                    "The application will automatically provide "
                    "the user's saved delivery address. "
                    "You only need to provide the search query."
                )
            }
        ],
        tools=[tool_schema],
    )

    message = response.choices[0].message

    print("\nLLM response:")
    print(message)

    print("\nTool calls:")
    print(message.tool_calls)

    # Execute the tool call
    if message.tool_calls:
        tool_call = message.tool_calls[0]

        arguments = json.loads(
            tool_call.function.arguments
        )

        arguments["addressId"] = first_address_id
        arguments["offset"] = 0

        print("\nArguments sent to Swiggy MCP:")
        print(arguments)

        result = await search_restaurants.ainvoke(arguments)

        print("\nSwiggy MCP result:")
        print(result)


asyncio.run(main())