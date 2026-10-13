"""Measure Jev on labelled scenarios, optionally next to a full-LLM verifier.

    python evaluate.py              # Jev only
    python evaluate.py --llm        # also run a full-LLM verifier
    python evaluate.py --llm --repeat 3

Results are printed and saved to evaluation_results.json.

These are small, hand-written scenarios. They show how the verifier behaves
on those cases; they are not a claim about Jev in general.
"""

import argparse
import json
import os
import statistics
import time

import requests
from dotenv import load_dotenv

from app.scenarios import SCENARIOS, build_state
from app.verifier import verifier_node

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_MODEL = os.getenv("LLM_VERIFIER_MODEL", "openai/gpt-4o-mini")


def run_jev(scenario) -> dict:
    result = verifier_node(build_state(scenario))["verification_result"]
    return {
        "passed": result["passed"],
        "latency": result["latency_seconds"],
        "scores": {c["label"]: round(c["score"], 2) for c in result["checks"]},
        "usage": result.get("usage"),
        "evidence": result["evidence"],
    }


def run_llm(evidence: str, has_budget: bool) -> dict:
    """Same evidence, one general-purpose LLM call asked for a verdict."""
    prompt = (
        "You verify an AI food-ordering agent's work before it is trusted.\n"
        "Decide whether the actual cart satisfies the user's request: "
        "right kind of dish (the name need not match exactly), right diet, "
        "right quantity"
        + (", and TO PAY must not exceed the maximum budget" if has_budget else "")
        + '.\nAnswer with JSON only: {"passed": true|false, "reason": "..."}\n\n'
        + evidence
    )

    started = time.perf_counter()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "usage": {"include": True},
        },
        timeout=60,
    )

    latency = time.perf_counter() - started
    response.raise_for_status()
    body = response.json()

    text = body["choices"][0]["message"]["content"]

    try:
        passed = bool(json.loads(text)["passed"])
    except (ValueError, KeyError, TypeError):
        passed = None  # unparseable answer

    return {"passed": passed, "latency": round(latency, 2), "usage": body.get("usage")}


def summarise(rows: list, key: str) -> dict:
    """Confusion counts for one verifier. 'Positive' = a real mistake."""
    caught = missed = false_alarm = correct_pass = unparsed = 0

    for row in rows:
        verdict = row[key]["passed"]
        is_mistake = not row["expect_pass"]

        if verdict is None:
            unparsed += 1
        elif is_mistake and not verdict:
            caught += 1
        elif is_mistake and verdict:
            missed += 1
        elif not is_mistake and not verdict:
            false_alarm += 1
        else:
            correct_pass += 1

    latencies = [row[key]["latency"] for row in rows]

    mistakes = caught + missed
    correct = false_alarm + correct_pass

    return {
        "mistakes_caught": f"{caught}/{mistakes}",
        "mistakes_missed": missed,
        "false_alarms": f"{false_alarm}/{correct}",
        "unparsed": unparsed,
        "avg_latency_s": round(statistics.mean(latencies), 2),
        "median_latency_s": round(statistics.median(latencies), 2),
    }


def total_cost(rows: list, key: str):
    costs = [
        (row[key].get("usage") or {}).get("cost")
        for row in rows
    ]
    costs = [c for c in costs if isinstance(c, (int, float))]
    return round(sum(costs), 6) if costs else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="also run a full-LLM verifier")
    parser.add_argument("--repeat", type=int, default=1, help="runs per scenario")
    args = parser.parse_args()

    rows = []

    for scenario in SCENARIOS:
        for _ in range(args.repeat):
            jev = run_jev(scenario)
            row = {
                "id": scenario.id,
                "title": scenario.title,
                "mistake": scenario.mistake,
                "expect_pass": scenario.expect_pass,
                "jev": jev,
            }

            if args.llm:
                row["llm"] = run_llm(jev["evidence"], scenario.budget is not None)

            rows.append(row)

    print("\n" + "=" * 78)
    print(f"{'scenario':<22}{'expected':<10}{'Jev':<8}" + (f"{'LLM':<8}" if args.llm else "") + "notes")
    print("=" * 78)

    def word(passed):
        return "?" if passed is None else ("PASS" if passed else "FLAG")

    for row in rows:
        expected = "PASS" if row["expect_pass"] else "FLAG"
        jev_word = word(row["jev"]["passed"])
        line = f"{row['id']:<22}{expected:<10}{jev_word:<8}"

        if args.llm:
            line += f"{word(row['llm']['passed']):<8}"

        notes = []
        if jev_word != expected:
            notes.append("Jev disagrees with label")
        if args.llm and word(row["llm"]["passed"]) != expected:
            notes.append("LLM disagrees with label")
        print(line + "; ".join(notes))

    summary = {"jev": summarise(rows, "jev"), "jev_cost_usd": total_cost(rows, "jev")}

    if args.llm:
        summary["llm"] = summarise(rows, "llm")
        summary["llm_cost_usd"] = total_cost(rows, "llm")
        summary["llm_model"] = LLM_MODEL

    print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))

    # Cost is only reported when the API returns it.
    if summary["jev_cost_usd"] is None:
        print("\nNote: the Jev endpoint returned no cost figure, so cost is not compared.")

    with open("evaluation_results.json", "w", encoding="utf-8") as handle:
        json.dump(
            {"summary": summary, "rows": rows, "scenario_count": len(SCENARIOS)},
            handle,
            indent=2,
            ensure_ascii=False,
        )

    print("\nSaved evaluation_results.json")


if __name__ == "__main__":
    main()
