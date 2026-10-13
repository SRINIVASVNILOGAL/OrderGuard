import json
from typing import NotRequired, TypedDict

from langgraph.graph import StateGraph, START, END
from app.mcp_client import get_swiggy_tools
from app.verifier import verifier_node

class ItemChoiceRequired(ValueError):
    """Several menu items matched; the user must pick one."""

    def __init__(self, items: list):
        super().__init__(
            "Multiple menu items matched the user's request. "
            "User selection is required."
        )
        self.items = [
            {
                "menu_item_id": item["menu_item_id"],
                "label": item["line"][2:].split(" [image:")[0].strip(),
            }
            for item in items
        ]


class OrderState(TypedDict):
    user_request: str

    # Optional maximum budget (₹) typed into the dashboard.
    budget: NotRequired[float]

    # Menu item the user picked when several matched.
    chosen_item_id: NotRequired[str]

    # User-selected restaurant.
    # For now, test_graph.py will provide this.
    restaurant_name: NotRequired[str]

    address_id: NotRequired[str]
    restaurant_results: NotRequired[dict]
    selected_restaurant: NotRequired[dict]

    menu: NotRequired[str]
    selected_item: NotRequired[dict]

    proposed_order: NotRequired[dict]
    cart: NotRequired[dict]

    verification_result: NotRequired[dict]


# ---------------------------------------------------------
# 1. SEARCH RESTAURANTS
# ---------------------------------------------------------

async def restaurant_search_node(state: OrderState):
    user_request = state["user_request"]

    tools = await get_swiggy_tools()

    # Get saved address
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

    # Search restaurants
    search_restaurants = next(
        tool for tool in tools
        if tool.name == "search_restaurants"
    )

    search_result = await search_restaurants.ainvoke({
        "query": user_request,
        "addressId": address_id,
        "offset": 0,
    })

    restaurant_text = search_result[0]["text"]

    # Remove MCP UI message after JSON
    json_end = restaurant_text.find("\n\n⚠️")

    restaurant_json = (
        restaurant_text[:json_end]
        if json_end != -1
        else restaurant_text
    )

    restaurant_data = json.loads(restaurant_json)

    print("\n===== RESTAURANT SEARCH RESULT =====")

    for index, restaurant in enumerate(
        restaurant_data.get("restaurants", []),
        start=1,
    ):
        print(
            f"{index}. {restaurant['name']} "
            f"(ID: {restaurant['id']})"
        )

    return {
        "address_id": address_id,
        "restaurant_results": restaurant_data,
    }


# ---------------------------------------------------------
# 2. SELECT RESTAURANT
# ---------------------------------------------------------

async def restaurant_selection_node(state: OrderState):
    restaurant_results = state["restaurant_results"]

    restaurants = restaurant_results["restaurants"]

    # For now, the restaurant name comes from the user/input.
    requested_restaurant = state.get("restaurant_name")

    if not requested_restaurant:
        raise ValueError(
            "No restaurant was selected. "
            "Please provide restaurant_name."
        )

    selected_restaurant = next(
        (
            restaurant
            for restaurant in restaurants
            if restaurant["name"].lower()
            == requested_restaurant.lower()
        ),
        None,
    )

    if selected_restaurant is None:
        raise ValueError(
            f"Restaurant '{requested_restaurant}' "
            "was not found in the restaurant search results."
        )

    print("\n===== USER SELECTED RESTAURANT =====")
    print(selected_restaurant["name"])
    print(f"Restaurant ID: {selected_restaurant['id']}")

    return {
        "selected_restaurant": {
            "name": selected_restaurant["name"],
            "id": selected_restaurant["id"],
        }
    }


# ---------------------------------------------------------
# 3. GET RESTAURANT MENU
# ---------------------------------------------------------

async def menu_fetch_node(state: OrderState):
    selected_restaurant = state["selected_restaurant"]
    address_id = state["address_id"]

    restaurant_id = selected_restaurant["id"]

    tools = await get_swiggy_tools()

    get_restaurant_menu = next(
        tool for tool in tools
        if tool.name == "get_restaurant_menu"
    )

    menu_result = await get_restaurant_menu.ainvoke({
        "addressId": address_id,
        "restaurantId": restaurant_id,
    })

    menu_text = menu_result[0]["text"]

    print("\n===== RESTAURANT MENU =====")
    print(menu_text)

    return {
        "menu": menu_text
    }

async def item_selection_node(state: OrderState):
    user_request = state["user_request"]
    menu = state["menu"]

    ignored_words = {
        "i",
        "want",
        "a",
        "an",
        "the",
        "from",
        "please",
        "order",
        "get",
        "give",
        "me",
        "at",
        "restaurant",
        "under",
        "rs",
        "₹",
    }

    # Remove the restaurant name from the request, so that
    # "paneer biryani from Andhra Biriyani House" only searches
    # for "paneer biryani".
    request_text = user_request.lower()

    restaurant_name = state.get("restaurant_name")

    if restaurant_name:
        request_text = request_text.replace(
            restaurant_name.lower(),
            " ",
        )

    requested_words = [
        word.strip(".,!?₹")
        for word in request_text.split()
        if word.strip(".,!?₹") not in ignored_words
        and word.strip(".,!?₹") != ""
    ]

    # Get actual menu-item lines
    menu_lines = [
        line.strip()
        for line in menu.splitlines()
        if line.strip().startswith("- ")
        and "(ID: " in line
    ]

    # The user already picked one of several matching items.
    chosen_item_id = state.get("chosen_item_id")

    if chosen_item_id:
        for line in menu_lines:
            if f"(ID: {chosen_item_id})" in line:
                return {
                    "selected_item": {
                        "name": line[2:].split(" — ")[0].strip(),
                        "menu_line": line,
                        "menu_item_id": chosen_item_id,
                    }
                }

    # ---------------------------------------------------------
    # STEP 1: Find exact item-name matches
    # ---------------------------------------------------------

    exact_matches = []

    for line in menu_lines:

        item_part = line[2:].split(" — ")[0].strip()

        item_words = item_part.lower().split()

        if (
            len(item_words) == len(requested_words)
            and all(
                word in item_words
                for word in requested_words
            )
        ):
            menu_item_id = (
                line.split("(ID: ")[1]
                .split(")")[0]
            )

            exact_matches.append({
                "name": item_part,
                "line": line,
                "menu_item_id": menu_item_id,
            })

    # ---------------------------------------------------------
    # STEP 2: Remove duplicate menu entries
    #
    # Swiggy may show the same item in multiple categories.
    # Same ID = same actual item.
    # ---------------------------------------------------------

    unique_matches = {}

    for item in exact_matches:
        unique_matches[item["menu_item_id"]] = item

    exact_matches = list(unique_matches.values())

    # ---------------------------------------------------------
    # STEP 3: Exactly one unique match
    # ---------------------------------------------------------

    if len(exact_matches) == 1:

        selected_item = exact_matches[0]

        print("\n===== EXACT MENU ITEM MATCH =====")
        print(selected_item["line"])

        return {
            "selected_item": {
                "name": selected_item["name"],
                "menu_line": selected_item["line"],
                "menu_item_id": selected_item["menu_item_id"],
            }
        }

    # ---------------------------------------------------------
    # STEP 4: Multiple unique matches
    # ---------------------------------------------------------

    if len(exact_matches) > 1:

        print("\n===== MULTIPLE MENU ITEMS FOUND =====")

        for index, item in enumerate(
            exact_matches,
            start=1,
        ):
            print(f"{index}. {item['line']}")

        raise ItemChoiceRequired(exact_matches)

    # ---------------------------------------------------------
    # STEP 5: No exact match
    # Try broader matching
    # ---------------------------------------------------------

    candidate_matches = []

    for line in menu_lines:

        item_part = line[2:].split(" — ")[0].strip()

        item_lower = item_part.lower()

        if all(
            word in item_lower
            for word in requested_words
        ):
            menu_item_id = (
                line.split("(ID: ")[1]
                .split(")")[0]
            )

            candidate_matches.append({
                "name": item_part,
                "line": line,
                "menu_item_id": menu_item_id,
            })

    # Remove duplicate IDs here too

    unique_candidates = {}

    for item in candidate_matches:
        unique_candidates[item["menu_item_id"]] = item

    candidate_matches = list(unique_candidates.values())

    # ---------------------------------------------------------
    # STEP 6: One broader match
    # ---------------------------------------------------------

    if len(candidate_matches) == 1:

        selected_item = candidate_matches[0]

        print("\n===== MENU ITEM MATCH =====")
        print(selected_item["line"])

        return {
            "selected_item": {
                "name": selected_item["name"],
                "menu_line": selected_item["line"],
                "menu_item_id": selected_item["menu_item_id"],
            }
        }

    # ---------------------------------------------------------
    # STEP 7: Multiple broader matches
    # ---------------------------------------------------------

    if len(candidate_matches) > 1:

        print("\n===== MULTIPLE MENU OPTIONS FOUND =====")

        for index, item in enumerate(
            candidate_matches,
            start=1,
        ):
            print(f"{index}. {item['line']}")

        raise ItemChoiceRequired(candidate_matches)

    # ---------------------------------------------------------
    # STEP 8: Nothing found
    # ---------------------------------------------------------

    raise ValueError(
        f"Could not find a menu item matching: {user_request}"
    )


async def add_to_cart_node(state: OrderState):
    selected_restaurant = state["selected_restaurant"]
    selected_item = state["selected_item"]
    address_id = state["address_id"]

    restaurant_id = selected_restaurant["id"]
    restaurant_name = selected_restaurant["name"]

    menu_item_id = selected_item["menu_item_id"]
    item_name = selected_item["name"]

    tools = await get_swiggy_tools()

    update_food_cart = next(
        tool for tool in tools
        if tool.name == "update_food_cart"
    )

    # ---------------------------------------------------------
    # STEP 1: Add the selected item to the cart
    # ---------------------------------------------------------

    cart_update_result = await update_food_cart.ainvoke({
        "restaurantId": restaurant_id,
        "cartItems": [
            {
                "menu_item_id": menu_item_id,
                "quantity": 1,
            }
        ],
        "addressId": address_id,
        "restaurantName": restaurant_name,
    })

    print("\n===== CART UPDATE RESULT =====")
    print(cart_update_result)

    # ---------------------------------------------------------
    # STEP 2: Get the actual cart from Swiggy
    # ---------------------------------------------------------

    get_food_cart = next(
        tool for tool in tools
        if tool.name == "get_food_cart"
    )

    actual_cart_result = await get_food_cart.ainvoke({
    "addressId": address_id
})

    print("\n===== ACTUAL FOOD CART =====")
    print(actual_cart_result)

    # ---------------------------------------------------------
    # STEP 3: Store the proposed order + actual cart
    # ---------------------------------------------------------

    proposed_order = {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant_name,
        "item": item_name,
        "quantity": 1,
        "menu_item_id": menu_item_id,
    }

    return {
        "proposed_order": proposed_order,
        "cart": actual_cart_result,
    }



# ---------------------------------------------------------
# GRAPH
# ---------------------------------------------------------

graph_builder = StateGraph(OrderState)

graph_builder.add_node(
    "restaurant_search",
    restaurant_search_node,
)

graph_builder.add_node(
    "restaurant_selection",
    restaurant_selection_node,
)

graph_builder.add_node(
    "menu_fetch",
    menu_fetch_node,
)

graph_builder.add_node(
    "item_selection",
    item_selection_node,
)

graph_builder.add_node(
    "add_to_cart",
    add_to_cart_node,
)
graph_builder.add_node(
    "verification", 
    verifier_node)

# Scenario 2 (no restaurant given): stop after the search so the
# user can pick a restaurant. The picked name is passed back in,
# and the graph continues from restaurant_selection.

def route_start(state: OrderState):
    if state.get("restaurant_results"):
        return "restaurant_selection"

    return "restaurant_search"


def route_after_search(state: OrderState):
    if state.get("restaurant_name"):
        return "restaurant_selection"

    return END


graph_builder.add_conditional_edges(
    START,
    route_start,
)

graph_builder.add_conditional_edges(
    "restaurant_search",
    route_after_search,
)

graph_builder.add_edge(
    "restaurant_selection",
    "menu_fetch",
)

graph_builder.add_edge(
    "menu_fetch",
    "item_selection",
)

graph_builder.add_edge(
    "item_selection",
    "add_to_cart",
)

graph_builder.add_edge("add_to_cart", "verification")
graph_builder.add_edge("verification", END)

graph = graph_builder.compile()