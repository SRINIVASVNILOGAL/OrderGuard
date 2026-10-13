import asyncio

from app.agent import load_swiggy_tools


async def main():
    tools = await load_swiggy_tools()

    get_addresses = next(
        tool for tool in tools
        if tool.name == "get_addresses"
    )

    result = await get_addresses.ainvoke({})

    address_text = result[0]["text"]

    print(address_text)


asyncio.run(main())