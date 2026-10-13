import asyncio
import html
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.agent import graph, ItemChoiceRequired
from app.scenarios import SCENARIOS, build_state
from app.verifier import PASS_THRESHOLD, verifier_node


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OrderGuard — Jev Verification",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# STYLES
# Swiggy-inspired look: white page, orange accent, grey cards.
# Not Swiggy's logo or branding.
# ============================================================

STYLES = """
<style>
  :root {
    --og-orange: #fc8019;
    --og-orange-dark: #e56e0c;
    --og-ink: #282c3f;
    --og-muted: #686b78;
    --og-line: #e9e9eb;
    --og-soft: #f5f5f6;
    --og-green: #20a464;
    --og-red: #e45757;
  }

  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  footer { display: none !important; }

  .stApp { background: #ffffff; }

  .block-container {
    max-width: 1100px;
    padding-top: 0;
    padding-bottom: 3rem;
  }

  /* ---------- Top nav ---------- */

  .og-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0;
    border-bottom: 1px solid var(--og-line);
    margin-bottom: 28px;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .og-brand { display: flex; align-items: center; gap: 12px; }
  .og-logo {
    width: 40px; height: 40px; border-radius: 10px;
    background: var(--og-orange); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
  }
  .og-brand-name { font-size: 20px; font-weight: 800; color: var(--og-ink); }
  .og-brand-sub { font-size: 12px; color: var(--og-muted); }
  .og-pill {
    border: 1px solid var(--og-line); border-radius: 20px;
    padding: 7px 14px; font-size: 13px; font-weight: 600;
    color: var(--og-muted);
  }

  /* ---------- Hero ---------- */

  .og-hero {
    text-align: center;
    padding: 12px 0 8px 0;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .og-hero h1 {
    font-size: 36px; font-weight: 800; color: var(--og-ink);
    margin: 0 0 8px 0; line-height: 1.2;
  }
  .og-hero h1 span { color: var(--og-orange); }
  .og-hero p {
    color: var(--og-muted); font-size: 16px; margin: 0;
    max-width: 640px; margin-left: auto; margin-right: auto;
  }

  /* ---------- Search button ---------- */

  .stButton > button {
    background: var(--og-orange);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    min-height: 46px;
  }
  .stButton > button:hover,
  .stButton > button:focus {
    background: var(--og-orange-dark);
    color: #ffffff;
    border: none;
  }

  /* ---------- Steps ---------- */

  .og-steps {
    display: flex; flex-wrap: wrap; gap: 10px;
    justify-content: center; margin: 26px 0 30px 0;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .og-step {
    border: 1px solid var(--og-line); border-radius: 30px;
    padding: 8px 16px; font-size: 13px; font-weight: 600;
    color: var(--og-muted); background: #ffffff;
  }
  .og-step.done { border-color: var(--og-orange); color: var(--og-orange-dark); background: #fff6ee; }
  .og-step.jev { border-color: var(--og-orange); color: var(--og-ink); }

  /* ---------- Section titles ---------- */

  .og-section {
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 13px; font-weight: 800; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--og-muted);
    margin: 28px 0 12px 0;
  }

  /* ---------- Cards ---------- */

  .og-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
    align-items: stretch;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .og-card {
    background: var(--og-soft); border: 1px solid var(--og-line);
    border-radius: 16px; padding: 20px; color: var(--og-ink);
  }
  .og-card-title {
    font-size: 12px; font-weight: 800; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--og-muted); margin-bottom: 10px;
  }
  .og-card-main { font-size: 20px; font-weight: 800; margin-bottom: 6px; }
  .og-card-text { font-size: 14px; color: var(--og-muted); line-height: 1.6; }
  .og-empty { text-align: center; padding: 40px 20px; }
  .og-empty-icon { font-size: 40px; margin-bottom: 8px; }

  .og-cart {
    background: #ffffff; border: 1px solid var(--og-line);
    border-radius: 10px; padding: 14px; margin: 0;
    font-family: ui-monospace, Consolas, monospace; font-size: 12px;
    color: var(--og-ink); white-space: pre-wrap; word-break: break-word;
    max-height: 260px; overflow-y: auto;
  }

  /* ---------- Verdict ---------- */

  .og-verdict {
    border-radius: 18px; padding: 26px; text-align: center;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    border: 2px solid;
  }
  .og-verdict.pass { border-color: var(--og-green); background: #f3fbf7; }
  .og-verdict.fail { border-color: var(--og-red); background: #fff5f5; }
  .og-verdict-status { font-size: 28px; font-weight: 800; }
  .og-verdict.pass .og-verdict-status { color: #16834e; }
  .og-verdict.fail .og-verdict-status { color: #d63f3f; }
  .og-verdict-text { color: var(--og-muted); font-size: 14px; margin-top: 6px; }

  .og-score { margin-top: 16px; text-align: left; }
  .og-score-row { display: flex; justify-content: space-between; font-size: 13px; color: var(--og-ink); margin-bottom: 4px; font-weight: 600; }
  .og-bar { position: relative; height: 10px; background: #ececee; border-radius: 6px; margin-bottom: 14px; }
  .og-bar-fill { height: 100%; background: var(--og-orange); border-radius: 6px; }
  .og-bar-line { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--og-ink); opacity: 0.55; }
  .og-score-note { font-style: normal; font-size: 11px; font-weight: 700; margin-left: 6px; }
  .og-score-note.pass { color: var(--og-green); }
  .og-score-note.fail { color: var(--og-red); }
  .og-evidence { margin-top: 10px; text-align: left; font-size: 12px; color: var(--og-muted); }
  .og-evidence summary { cursor: pointer; font-weight: 700; }
  .og-evidence pre {
    margin: 8px 0 0 0; padding: 10px; background: #ffffff;
    border: 1px solid var(--og-line); border-radius: 8px;
    white-space: pre-wrap; word-break: break-word; font-size: 11px;
    font-family: ui-monospace, Consolas, monospace; color: var(--og-ink);
  }
  .og-verdict-rule {
    margin-top: 10px; padding-top: 12px; border-top: 1px dashed var(--og-line);
    font-size: 12px; color: var(--og-muted); line-height: 1.5; text-align: left;
  }
  .og-bar-fill.pass { background: var(--og-green); }
  .og-bar-fill.fail { background: var(--og-red); }

  /* ---------- Explanation ---------- */

  .og-explain {
    background: #fff6ee; border-left: 4px solid var(--og-orange);
    border-radius: 10px; padding: 18px 20px; margin-top: 24px;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    color: var(--og-ink);
  }
  .og-explain h3 { margin: 0 0 6px 0; font-size: 16px; }
  .og-explain p { margin: 0 0 8px 0; font-size: 14px; color: var(--og-muted); line-height: 1.6; }
  .og-explain ul { margin: 0 0 8px 18px; padding: 0; font-size: 14px; color: var(--og-muted); line-height: 1.7; }

  .og-footer {
    text-align: center; margin-top: 40px; padding-top: 20px;
    border-top: 1px solid var(--og-line); color: #9a9ca6; font-size: 12px;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }

  @media (max-width: 768px) {
    .og-grid { grid-template-columns: 1fr; }
    .og-hero h1 { font-size: 26px; }
    .og-pill { display: none; }
  }
</style>
"""


# ============================================================
# HTML HELPERS
# st.html renders raw HTML, so no indentation issues.
# Every value that comes from the agent, Swiggy or Jev is
# escaped before it goes into the page.
# ============================================================

def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def render_nav() -> str:
    return (
        '<div class="og-nav">'
        '<div class="og-brand">'
        '<div class="og-logo">🛡</div>'
        '<div><div class="og-brand-name">OrderGuard</div>'
        '<div class="og-brand-sub">Jev Verification Layer</div></div>'
        '</div>'
        '<div class="og-pill">Built with Swiggy MCP</div>'
        '</div>'
    )


def render_hero() -> str:
    return (
        '<div class="og-hero">'
        '<h1>Can an AI agent\'s order be <span>trusted?</span></h1>'
        '<p>OrderGuard checks an agent\'s proposed order against what '
        'Swiggy actually put in the cart, using Jev as an independent '
        'verifier.</p>'
        '</div>'
    )


def render_steps(done: bool) -> str:
    steps = [
        ("User request", False),
        ("Agent proposal", False),
        ("Swiggy MCP cart", False),
        ("Jev verification", True),
    ]
    items = []
    for label, is_jev in steps:
        classes = ["og-step"]
        if done:
            classes.append("done")
        if is_jev:
            classes.append("jev")
        items.append(f'<div class="{" ".join(classes)}">{esc(label)}</div>')
    return '<div class="og-steps">' + "".join(items) + "</div>"


def render_empty() -> str:
    return (
        '<div class="og-card og-empty">'
        '<div class="og-empty-icon">🛡️</div>'
        '<div class="og-card-main">Ready when you are</div>'
        '<div class="og-card-text">Enter a request and a restaurant, '
        'then click <b>Verify order</b>.</div>'
        '</div>'
    )


def render_restaurant_choices(restaurant_results: dict) -> str:
    restaurants = restaurant_results.get("restaurants", [])

    if not restaurants:
        return (
            '<div class="og-card og-empty">'
            '<div class="og-card-main">No restaurants found</div>'
            '<div class="og-card-text">Try a different request.</div>'
            '</div>'
        )

    return (
        '<div class="og-card">'
        '<div class="og-card-title">Restaurants with this item</div>'
        '<div class="og-card-text">Pick one to see its menu and add the item to the cart.</div>'
        '</div>'
    )


def render_agent_card(order: dict, budget=None) -> str:
    item = order.get("item", "Not available")
    restaurant = order.get("restaurant_name", "Not available")
    quantity = order.get("quantity", 1)
    budget_line = f"<br>Budget: up to ₹{budget:g}" if budget else ""
    return (
        '<div class="og-card">'
        '<div class="og-card-title">Agent\'s proposed order</div>'
        f'<div class="og-card-main">{esc(item)}</div>'
        '<div class="og-card-text">'
        f'Restaurant: {esc(restaurant)}<br>Quantity: {esc(quantity)}'
        f'{budget_line}'
        '</div></div>'
    )


def cart_text(cart) -> str:
    # The MCP returns [{"type": "text", "text": "..."}]. Keep only the
    # cart lines and drop the widget / UI hints Swiggy appends.
    if isinstance(cart, list):
        text = "\n".join(
            part.get("text", "") for part in cart if isinstance(part, dict)
        )
    else:
        text = str(cart or "")

    for marker in ("\n\nCart widget", "\n\nNOTE", "\n\nNo widget", "\n\n⚠️"):
        position = text.find(marker)
        if position != -1:
            text = text[:position]

    return text.strip() or "No cart returned"


def render_cart_card(cart) -> str:
    return (
        '<div class="og-card">'
        '<div class="og-card-title">Actual Swiggy cart</div>'
        f'<pre class="og-cart">{esc(cart_text(cart))}</pre>'
        '</div>'
    )


def score_row(label: str, value, passed: bool) -> str:
    percent = round(float(value) * 100)
    line = round(PASS_THRESHOLD * 100)
    fill = "pass" if passed else "fail"
    status = "✓ passes" if passed else f"✗ needs {line}%"
    return (
        '<div class="og-score">'
        f'<div class="og-score-row"><span>{esc(label)}</span>'
        f'<span>{percent}% <em class="og-score-note {fill}">{status}</em></span></div>'
        '<div class="og-bar">'
        f'<div class="og-bar-fill {fill}" style="width:{percent}%"></div>'
        f'<div class="og-bar-line" style="left:{line}%"></div>'
        '</div>'
        '</div>'
    )


def render_verdict(verification: dict) -> str:
    passed = bool(verification.get("passed", False))
    matches = verification.get("matches_request")
    budget = verification.get("within_budget")

    if passed:
        status_class, status_text = "pass", "✓ VERIFIED"
        message = "Jev found the proposed order consistent with the user's request."
    else:
        status_class, status_text = "fail", "⚠ FLAGGED"
        message = "Jev found a possible mismatch between the request and the order."

    scores = ""
    checks = verification.get("checks")

    if checks:
        for check in checks:
            score = check.get("score")
            if isinstance(score, (int, float)):
                scores += score_row(
                    check.get("label", "Check"), score, score >= PASS_THRESHOLD
                )
    else:
        if isinstance(matches, (int, float)):
            scores += score_row("Request match", matches, matches >= PASS_THRESHOLD)
        if isinstance(budget, (int, float)):
            scores += score_row("Budget match", budget, budget >= PASS_THRESHOLD)

    line = round(PASS_THRESHOLD * 100)

    latency = verification.get("latency_seconds")
    latency_text = f" Jev answered in {latency}s." if latency is not None else ""

    evidence = verification.get("evidence")
    evidence_html = (
        '<details class="og-evidence"><summary>What Jev was shown</summary>'
        f'<pre>{esc(evidence)}</pre></details>'
        if evidence else ""
    )

    return (
        f'<div class="og-verdict {status_class}">'
        f'<div class="og-verdict-status">{status_text}</div>'
        f'<div class="og-verdict-text">{esc(message)}</div>'
        f'{scores}'
        f'<div class="og-verdict-rule">Pass line: every check must score at least {line}%.'
        f'{esc(latency_text)}</div>'
        f'{evidence_html}'
        '</div>'
    )


def render_explanation(has_budget: bool) -> str:
    budget_line = (
        "<li>Whether the cart total is within the budget you mentioned.</li>"
        if has_budget else ""
    )
    return (
        '<div class="og-explain">'
        '<h3>What was checked</h3>'
        '<ul>'
        '<li>Whether the cart matches the item and quantity you asked for.</li>'
        f'{budget_line}'
        '</ul>'
        '<p><b>Why this matters:</b> the agent does the work, but Jev checks '
        'its decision independently before anything is ordered. OrderGuard '
        'does not place any order.</p>'
        '</div>'
    )


# ============================================================
# PAGE
# ============================================================

st.html(STYLES)
st.html(render_nav())
st.html(render_hero())

search_col, restaurant_col, budget_col, button_col = st.columns([4, 3, 2, 2])

with search_col:
    user_request = st.text_input(
        "Request",
        value="",
        label_visibility="collapsed",
        placeholder="What do you want?",
    )

with restaurant_col:
    restaurant_name = st.text_input(
        "Restaurant",
        value="",
        label_visibility="collapsed",
        placeholder="Where do you want it from?",
    )

with budget_col:
    budget_value = st.number_input(
        "Budget",
        min_value=0,
        value=None,
        step=50,
        label_visibility="collapsed",
        placeholder="Max budget ₹ (optional)",
    )

budget = float(budget_value) if budget_value else None

with button_col:
    verify_clicked = st.button("Order", use_container_width=True)


# ------------------------------------------------------------
# TEST SCENARIOS
# Labelled cases that run Jev with no Swiggy login or real cart.
# ------------------------------------------------------------

with st.expander("Try a test scenario (no Swiggy login needed)"):
    scenario_by_title = {
        f"{'✓' if s.expect_pass else '✗'}  {s.title}": s for s in SCENARIOS
    }

    chosen_title = st.selectbox(
        "Scenario",
        list(scenario_by_title),
        label_visibility="collapsed",
    )

    if st.button("Run scenario", key="run_scenario"):
        chosen = scenario_by_title[chosen_title]
        state = build_state(chosen)

        try:
            with st.spinner("Running Jev..."):
                verification = verifier_node(state)["verification_result"]
        except Exception as error:
            st.error(f"Jev call failed:\n\n{type(error).__name__}: {error}")
        else:
            for key in ("search_state", "item_choice", "picked_restaurant", "picked_item"):
                st.session_state.pop(key, None)

            st.session_state["verification_result"] = {
                "user_request": chosen.user_request,
                "proposed_order": state["proposed_order"],
                "cart": state["cart"],
                "budget": state.get("budget"),
                "verification_result": verification,
                "expected": "PASS" if chosen.expect_pass else "FLAG",
            }


# ------------------------------------------------------------
# RUN THE PIPELINE
# ------------------------------------------------------------

def describe_error(error: BaseException) -> str:
    # Unwrap TaskGroup / ExceptionGroup so the real cause is visible.
    if isinstance(error, BaseExceptionGroup):
        return "\n\n".join(describe_error(sub) for sub in error.exceptions)
    return f"{type(error).__name__}: {error}"


def find_item_choice(error: BaseException):
    # Looks through (possibly nested) exception groups for ItemChoiceRequired.
    if isinstance(error, ItemChoiceRequired):
        return error
    if isinstance(error, BaseExceptionGroup):
        for sub in error.exceptions:
            found = find_item_choice(sub)
            if found:
                return found
    return None


def run_pipeline(payload: dict):
    # Returns (result, error). Only one of them is set.
    try:
        return asyncio.run(graph.ainvoke(payload)), None
    except Exception as error:
        return None, error


def run_and_store(payload: dict, spinner_text: str):
    # Runs the pipeline. On success keeps the result; if several menu
    # items match, keeps them so the user can choose one.
    if budget is not None:
        payload = {**payload, "budget": budget}

    with st.spinner(spinner_text):
        result, error = run_pipeline(payload)

    if error is None:
        st.session_state["verification_result"] = result
        return

    choice = find_item_choice(error)
    if choice is not None:
        st.session_state["item_choice"] = {
            "payload": payload,
            "items": choice.items,
        }
    else:
        st.error(f"Something went wrong while running the pipeline:\n\n{describe_error(error)}")


def pick_restaurant(name: str):
    st.session_state["picked_restaurant"] = name


def pick_item(menu_item_id: str):
    st.session_state["picked_item"] = menu_item_id


if verify_clicked:
    st.session_state.pop("verification_result", None)
    st.session_state.pop("search_state", None)
    st.session_state.pop("picked_restaurant", None)
    st.session_state.pop("item_choice", None)
    st.session_state.pop("picked_item", None)

    if not user_request.strip():
        st.error("Please enter a request.")

    elif restaurant_name.strip():
        # Scenario 1: item and restaurant given, run the full pipeline.
        run_and_store(
            {
                "user_request": user_request,
                "restaurant_name": restaurant_name.strip(),
            },
            "Asking the agent, checking the Swiggy cart, and running Jev...",
        )

    else:
        # Scenario 2: only the item given, search for restaurants first.
        with st.spinner("Finding restaurants that serve this..."):
            search, error = run_pipeline({"user_request": user_request})

        if error:
            st.error(f"Something went wrong while searching restaurants:\n\n{describe_error(error)}")
        else:
            st.session_state["search_state"] = search

# The user picked a restaurant from the list (scenario 2).
picked = st.session_state.pop("picked_restaurant", None)

if picked and "search_state" in st.session_state:
    search = st.session_state.pop("search_state")

    run_and_store(
        {
            "user_request": search["user_request"],
            "restaurant_name": picked,
            "address_id": search["address_id"],
            "restaurant_results": search["restaurant_results"],
        },
        "Adding the item to the cart and running Jev...",
    )

# The user picked one of several matching menu items.
picked_item = st.session_state.pop("picked_item", None)

if picked_item and "item_choice" in st.session_state:
    pending = st.session_state.pop("item_choice")

    run_and_store(
        {**pending["payload"], "chosen_item_id": picked_item},
        "Adding the item to the cart and running Jev...",
    )


search = st.session_state.get("search_state")
result = st.session_state.get("verification_result")
item_choice = st.session_state.get("item_choice")

if item_choice is not None and result is None:
    st.html('<div class="og-section">Choose an item</div>')

    for index, item in enumerate(item_choice["items"]):
        st.button(
            item["label"],
            key=f"item_{index}",
            on_click=pick_item,
            args=(item["menu_item_id"],),
            use_container_width=True,
        )

elif search is not None and result is None:
    st.html('<div class="og-section">01 · Choose a restaurant</div>')
    st.html(render_restaurant_choices(search.get("restaurant_results", {})))

    for index, restaurant in enumerate(search.get("restaurant_results", {}).get("restaurants", [])):
        st.button(
            f"Order from {restaurant.get('name', 'this restaurant')}",
            key=f"pick_{index}",
            on_click=pick_restaurant,
            args=(restaurant.get("name", ""),),
            use_container_width=True,
        )

elif result is not None:
    # Jev result, the agent's order and the actual cart, in small boxes.
    st.html(
        '<div class="og-grid">'
        + render_verdict(result.get("verification_result", {}))
        + render_agent_card(result.get("proposed_order", {}), result.get("budget"))
        + render_cart_card(result.get("cart"))
        + '</div>'
    )

    expected = result.get("expected")
    if expected:
        actual = "PASS" if result["verification_result"].get("passed") else "FLAG"
        agreed = actual == expected
        st.html(
            '<div class="og-card-text" style="text-align:center;margin-top:12px">'
            f'Expected: <b>{expected}</b> · Jev said: <b>{actual}</b> · '
            f'{"✓ agreed" if agreed else "✗ disagreed"}'
            '</div>'
        )
