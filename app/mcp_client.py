import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

SWIGGY_ACCESS_TOKEN = os.getenv("SWIGGY_ACCESS_TOKEN")


async def get_swiggy_mcp_client():
    client = MultiServerMCPClient(
        {
            "swiggy": {
                "transport": "streamable_http",
                "url": "https://mcp.swiggy.com/food",
                "headers": {
                    "Authorization": f"Bearer {SWIGGY_ACCESS_TOKEN}"
                },
            }
        }
    )

    return client

async def get_swiggy_tools():
    client = await get_swiggy_mcp_client()
    tools = await client.get_tools()

    return tools