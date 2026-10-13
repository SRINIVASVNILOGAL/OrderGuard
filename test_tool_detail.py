import asyncio

from app.agent import load_swiggy_tools


async def main():
    tools = await load_swiggy_tools()

    search_restaurants = next(
        tool for tool in tools
        if tool.name == "search_restaurants"
    )

    result = await search_restaurants.ainvoke({
        "addressId": "da5iros1d96obq34rd20__AMUkMgSgQ0sRfEzhQQE9Qv",
        "query": "paneer biryani",
        "offset": 0
    })

    print(result)


asyncio.run(main())