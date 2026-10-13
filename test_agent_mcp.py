import asyncio
import re

from app.agent import load_swiggy_tools


async def main():
    tools = await load_swiggy_tools()

    get_addresses = next(
        tool for tool in tools
        if tool.name == "get_addresses"
    )

    get_food_cart = next(
        tool for tool in tools
        if tool.name == "get_food_cart"
    )

    # Get the saved address
    address_result = await get_addresses.ainvoke({})

    address_text = address_result[0]["text"]
    first_line = address_text.splitlines()[1]

    first_address_id = (
        first_line.split("(ID: ")[1].split(")")[0]
    )

    print("Using address ID:", first_address_id)

    # Get the current cart
    cart_result = await get_food_cart.ainvoke({
        "addressId": first_address_id
    })

    cart_text = cart_result[0]["text"]

    print("\nRaw cart text:")
    print(cart_text)

    # Extract item
    item_match = re.search(
        r"- (.+?) — ₹(\d+) \(ID:",
        cart_text
    )

    # Extract quantity
    quantity_match = re.search(
        r"Items \((\d+)\):",
        cart_text
    )

    # Extract item price
    price_match = re.search(
        r"- .+? — ₹(\d+) \(ID:",
        cart_text
    )

    # Extract taxes
    taxes_match = re.search(
        r"Taxes & charges: ₹([\d.]+)",
        cart_text
    )

    # Extract total
    total_match = re.search(
        r"TO PAY: ₹([\d.]+)",
        cart_text
    )

    cart = {
        "item": item_match.group(1) if item_match else None,
        "quantity": int(quantity_match.group(1))
        if quantity_match else None,
        "price": float(price_match.group(1))
        if price_match else None,
        "taxes": float(taxes_match.group(1))
        if taxes_match else None,
        "total": float(total_match.group(1))
        if total_match else None,
    }

    print("\nExtracted cart:")
    print(cart)


asyncio.run(main())