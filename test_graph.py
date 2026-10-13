import asyncio

from app.agent import graph


async def main():
    result = await graph.ainvoke({
        "user_request": "I want paneer biryani",
        "restaurant_name": "Biryani Blues",
    })

    print("\n===== GRAPH RESULT =====")
    print(result)


asyncio.run(main())