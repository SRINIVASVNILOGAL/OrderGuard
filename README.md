# OrderGuard

A verification layer for AI-agent food orders on Swiggy.

An AI agent can misread a request: wrong restaurant, wrong item, wrong quantity,
a veg/non-veg mix-up, or an order over budget. OrderGuard checks the cart the
agent built against what the user actually asked for, using **Jev**
(`typesafe/jev-1.13`, called through OpenRouter), before anything is placed.

## How it works

The agent is a LangGraph workflow that talks to Swiggy's MCP server:

```
restaurant search -> restaurant selection -> menu fetch
   -> item selection -> add to cart -> verification (Jev)
```

After the item is added to the cart, the verifier turns the cart into plain
evidence and asks Jev a set of yes/no questions (right restaurant? right item?
right quantity? diet match? within budget?). A Jev score of **0.90 or above**
passes; anything lower is flagged.

## Project structure

| Path | Purpose |
|---|---|
| `app/agent.py` | LangGraph workflow (search, select, add to cart, verify) |
| `app/verifier.py` | Cart parsing, evidence building, Jev call |
| `app/mcp_client.py` | Connection to the Swiggy MCP server |
| `app/scenarios.py` | Labelled test scenarios (correct and mistaken orders) |
| `app/oauth.py`, `app/main.py` | FastAPI app and Swiggy OAuth routes |
| `dashboard/streamlit_app.py` | Streamlit dashboard |
| `evaluate.py` | Measures Jev on the scenarios |
| `tests/` | pytest tests |

## Setup

```powershell
git clone https://github.com/SRINIVASVNILOGAL/OrderGuard.git
cd OrderGuard
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit it):

```
OPENROUTER_API_KEY=your_key
SWIGGY_ACCESS_TOKEN=your_token
MONGODB_URI=your_mongodb_uri
LANGSMITH_API_KEY=your_key
TYPESAFE_API_KEY=your_key
```

## Run

```powershell
# Dashboard
streamlit run dashboard/streamlit_app.py

# Evaluate Jev on the labelled scenarios (no Swiggy login needed)
python evaluate.py
python evaluate.py --llm --repeat 3   # also compare with a full-LLM verifier

# Tests
pytest
```

## Notes

- The scenarios are small and hand-written. They show how the verifier behaves
  on those cases, not how Jev performs in general.
- Secrets live in `.env`, which is git-ignored.