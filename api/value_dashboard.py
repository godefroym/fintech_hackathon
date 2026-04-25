"""
Generate the dashboard view model from employee_metrics.jsonl.

The output follows the provided VIEWMODEL.json contract exactly:
  - executive_summary
  - monthly_metrics
  - employee_metrics

Employee recommendations are based on the relationship between tokens used and
story points delivered, but the internal productivity ratio is not exposed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("employee_metrics.jsonl")
DEFAULT_OUTPUT = Path("outputs/VIEWMODEL.json")
DEFAULT_ENV_FILE = Path("cle.env")


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def round_metric(value: float, digits: int = 2) -> int | float:
    rounded = round(float(value), digits)
    return int(rounded) if rounded.is_integer() else rounded


def month_sort_key(month: str) -> tuple[int, int]:
    match = re.match(r"(\d{1,2})/(\d{4})", month or "")
    if match:
        return (int(match.group(2)), int(match.group(1)))

    match = re.match(r"(\d{4})-(\d{1,2})", month or "")
    if match:
        return (int(match.group(1)), int(match.group(2)))

    return (9999, 99)


def month_label(month: str) -> str:
    year, month_number = month_sort_key(month)
    if year == 9999:
        return month
    return f"{year:04d}-{month_number:02d}"


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc

    return rows


def productivity(story_points: float, tokens_used: float) -> float:
    return safe_divide(story_points, tokens_used) * 1_000_000


def normalized_row(row: dict[str, Any]) -> dict[str, Any]:
    tokens_used = safe_float(
        row.get("token_usage", row.get("token_used", row.get("tokens_used")))
    )
    story_points = safe_float(row.get("story_points"))

    return {
        "name": str(row.get("name") or "Unknown"),
        "month": str(row.get("month") or "unknown"),
        "month_label": month_label(str(row.get("month") or "unknown")),
        "tokens_used": tokens_used,
        "story_points": story_points,
        "bugs_closed": safe_float(row.get("bugs_closed")),
        "productivity": productivity(story_points, tokens_used),
    }


def build_monthly_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["month"]].append(row)

    monthly_metrics = []
    for month in sorted(grouped, key=month_sort_key):
        employees = []
        for row in sorted(grouped[month], key=lambda item: item["name"]):
            employees.append(
                {
                    "name": row["name"],
                    "tokens_used": int(round(row["tokens_used"])),
                    "story_points": round_metric(row["story_points"], 1),
                }
            )

        monthly_metrics.append({"month": month_label(month), "employees": employees})

    return monthly_metrics


def latest_employee_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = latest_by_name.get(row["name"])
        if current is None or month_sort_key(row["month"]) > month_sort_key(current["month"]):
            latest_by_name[row["name"]] = row

    return list(latest_by_name.values())


def fallback_recommendation(category: str) -> str:
    if category == "high_roi":
        return (
            "Maintain this level of AI access and use this person as a benchmark. "
            "Their token consumption is justified by strong story point delivery, so the next action is to document the workflow, prompts, and review habits that make the spend productive."
        )
    if category == "efficient_user":
        return (
            "Turn this person into an internal reference user. "
            "They deliver strong story points without excessive token usage, so ask them to share concrete examples of prompts, context selection, and tasks where AI saves the most time."
        )
    if category == "overspender":
        return (
            "Review this user's AI workflow before increasing their access. "
            "The token spend is high relative to delivered story points, so check whether they are sending too much context, using AI for low-value tasks, or missing basic prompt patterns."
        )
    if category == "low_adoption":
        return (
            "Run a targeted enablement test rather than cutting budget. "
            "This user has low token usage and low story point delivery, so the issue may be under-adoption; give them practical examples and compare their next month against this baseline."
        )
    if category == "quality_risk":
        return (
            "Do not scale AI usage for this user yet. "
            "Story point delivery is weak relative to the usage pattern, so add review checkpoints and focus on task decomposition before encouraging more token consumption."
        )
    return (
        "Keep monitoring this user against peers doing similar work. "
        "Their token usage and story point delivery are not extreme, so the best next step is light coaching using examples from the highest-performing users."
    )


def classify_employee(
    row: dict[str, Any],
    token_values: list[float],
    story_point_values: list[float],
    productivity_values: list[float],
) -> str:
    q25_tokens = percentile(token_values, 0.25)
    q50_tokens = percentile(token_values, 0.50)
    q75_tokens = percentile(token_values, 0.75)
    q25_story_points = percentile(story_point_values, 0.25)
    q50_story_points = percentile(story_point_values, 0.50)
    q75_story_points = percentile(story_point_values, 0.75)
    q25_productivity = percentile(productivity_values, 0.25)
    q75_productivity = percentile(productivity_values, 0.75)

    high_tokens = row["tokens_used"] >= q75_tokens
    low_tokens = row["tokens_used"] <= q25_tokens
    moderate_tokens = q25_tokens < row["tokens_used"] <= q50_tokens
    low_story_points = row["story_points"] <= q25_story_points
    solid_story_points = row["story_points"] >= q50_story_points
    high_story_points = row["story_points"] >= q75_story_points
    low_productivity = row["productivity"] <= q25_productivity
    high_productivity = row["productivity"] >= q75_productivity

    if high_tokens and low_productivity:
        return "overspender"
    if high_productivity and high_story_points:
        return "high_roi"
    if high_productivity and solid_story_points and (moderate_tokens or low_tokens):
        return "efficient_user"
    if low_tokens and low_story_points:
        return "low_adoption"
    if low_story_points and low_productivity:
        return "quality_risk"
    return "average_user"


def build_employee_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    employee_rows = latest_employee_rows(rows)
    token_values = [row["tokens_used"] for row in employee_rows]
    story_point_values = [row["story_points"] for row in employee_rows]
    productivity_values = [row["productivity"] for row in employee_rows]

    employees = []
    for row in employee_rows:
        category = classify_employee(row, token_values, story_point_values, productivity_values)
        employees.append(
            {
                "name": row["name"],
                "category": category,
                "tokens_used": int(round(row["tokens_used"])),
                "story_points": round_metric(row["story_points"], 1),
                "recommendation": fallback_recommendation(category),
            }
        )

    category_rank = {
        "high_roi": 0,
        "efficient_user": 1,
        "average_user": 2,
        "low_adoption": 3,
        "quality_risk": 4,
        "overspender": 5,
    }
    return sorted(
        employees,
        key=lambda item: (category_rank.get(item["category"], 99), item["name"]),
    )


def rows_for_month(rows: list[dict[str, Any]], month: str | None) -> list[dict[str, Any]]:
    if month is None:
        return []
    return [row for row in rows if row["month"] == month]


def fallback_main_recommendation(categories: Counter[str]) -> str:
    if categories.get("overspender", 0) and (
        categories.get("high_roi", 0) or categories.get("efficient_user", 0)
    ):
        return (
            "Prioritize two actions next month: review high-token users who deliver few story points, "
            "and turn efficient users into internal examples. This keeps the AI budget focused on work that converts into measurable delivery."
        )
    if categories.get("overspender", 0):
        return (
            "Cap token-heavy workflows until managers review why the spend is not translating into story points. "
            "The immediate goal is to reduce waste before expanding the AI budget."
        )
    if categories.get("high_roi", 0) or categories.get("efficient_user", 0):
        return (
            "Expand AI usage by copying the workflows of users who already convert tokens into story points. "
            "Use their habits as the onboarding playbook for lower-performing teams."
        )
    return (
        "Keep the AI budget stable and review employee-level outliers monthly. "
        "The dashboard should be used to decide where AI coaching creates more delivery and where token spend needs tighter control."
    )


def build_executive_summary(
    rows: list[dict[str, Any]],
    employee_metrics: list[dict[str, Any]],
    cost_per_1m_tokens: float,
    currency: str,
    monthly_budget: float | None,
) -> dict[str, Any]:
    months = sorted({row["month"] for row in rows}, key=month_sort_key)
    latest_month = months[-1] if months else None
    previous_month = months[-2] if len(months) >= 2 else None
    first_month = months[0] if months else None

    latest_rows = rows_for_month(rows, latest_month)
    previous_rows = rows_for_month(rows, previous_month)
    first_rows = rows_for_month(rows, first_month)

    latest_tokens = sum(row["tokens_used"] for row in latest_rows)
    previous_tokens = sum(row["tokens_used"] for row in previous_rows)
    latest_spend = latest_tokens / 1_000_000 * cost_per_1m_tokens
    previous_spend = previous_tokens / 1_000_000 * cost_per_1m_tokens
    monthly_growth = safe_divide(latest_spend - previous_spend, previous_spend) * 100
    forecast_growth = clamp(monthly_growth, -20, 35)
    forecast_next_month = latest_spend * (1 + forecast_growth / 100)

    first_story_points = sum(row["story_points"] for row in first_rows)
    latest_story_points = sum(row["story_points"] for row in latest_rows)
    productivity_gain = safe_divide(
        latest_story_points - first_story_points,
        first_story_points,
    ) * 100

    first_bugs = sum(row["bugs_closed"] for row in first_rows)
    latest_bugs = sum(row["bugs_closed"] for row in latest_rows)
    bugs_reduction = safe_divide(first_bugs - latest_bugs, first_bugs) * 100

    if monthly_budget is None:
        monthly_budget = latest_spend / 0.817 if latest_spend else 0.0
    budget_usage = safe_divide(latest_spend, monthly_budget) * 100

    categories = Counter(item["category"] for item in employee_metrics)

    return {
        "monthly_ai_spend_total": round_metric(latest_spend, 2),
        "forecast_next_month_ai_spend": round_metric(forecast_next_month, 2),
        "monthly_ai_spend_growth_percent": round_metric(monthly_growth, 1),
        "budget_usage_percent": round_metric(budget_usage, 1),
        "productivity_gain_percent": round_metric(productivity_gain, 1),
        "bugs_reduction_percent": round_metric(bugs_reduction, 1),
        "currency": currency,
        "main_recommendation": fallback_main_recommendation(categories),
    }


def maybe_apply_openai_recommendations(viewmodel: dict[str, Any]) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return "skipped"

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = {
        "task": "Write manager recommendations for an AI token value dashboard.",
        "rules": [
            "Use only the provided JSON.",
            "Do not add, remove, rename, or compute fields.",
            "Return only main_recommendation and employee recommendations by name.",
            "Base reasoning on tokens_used, story_points, and category.",
            "Recommendations should be more detailed than one-liners: 2 clear sentences for each employee.",
            "Explain the business action: retrain, monitor, replicate workflow, or run adoption coaching.",
        ],
        "required_json_shape": {
            "main_recommendation": "string",
            "employee_recommendations": [
                {"name": "string", "recommendation": "two concise sentences"}
            ],
        },
        "viewmodel": viewmodel,
    }
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You produce valid JSON only for a fintech AI spending dashboard.",
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        content = response_payload["choices"][0]["message"]["content"]
        recommendations = json.loads(content)
    except (KeyError, json.JSONDecodeError, urllib.error.URLError, TimeoutError):
        return "fallback"

    main_recommendation = recommendations.get("main_recommendation")
    if isinstance(main_recommendation, str) and main_recommendation.strip():
        viewmodel["executive_summary"]["main_recommendation"] = main_recommendation.strip()

    recommendation_by_name = {
        item.get("name"): item.get("recommendation")
        for item in recommendations.get("employee_recommendations", [])
        if isinstance(item, dict)
    }
    for item in viewmodel["employee_metrics"]:
        recommendation = recommendation_by_name.get(item["name"])
        if isinstance(recommendation, str) and recommendation.strip():
            item["recommendation"] = recommendation.strip()
    return "openai"


def build_viewmodel(
    rows: list[dict[str, Any]],
    cost_per_1m_tokens: float,
    currency: str,
) -> tuple[dict[str, Any], str]:
    normalized_rows = [normalized_row(row) for row in rows]
    employee_metrics = build_employee_metrics(normalized_rows)
    monthly_budget = safe_float(os.environ.get("AI_MONTHLY_BUDGET"), default=0.0) or None

    viewmodel = {
        "executive_summary": build_executive_summary(
            rows=normalized_rows,
            employee_metrics=employee_metrics,
            cost_per_1m_tokens=cost_per_1m_tokens,
            currency=currency,
            monthly_budget=monthly_budget,
        ),
        "monthly_metrics": build_monthly_metrics(normalized_rows),
        "employee_metrics": employee_metrics,
    }
    recommendation_source = maybe_apply_openai_recommendations(viewmodel)
    return viewmodel, recommendation_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build VIEWMODEL-style token value dashboard data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input employee metrics JSONL.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Local env file with API keys.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_env_file(args.env_file)

    cost_per_1m_tokens = safe_float(
        os.environ.get("AI_COST_PER_1M_TOKENS_USD"),
        default=safe_float(os.environ.get("AI_COST_PER_1M_TOKENS_EUR"), default=8.0),
    )
    currency = os.environ.get("AI_COST_CURRENCY", "USD")

    rows = read_jsonl(args.input)
    viewmodel, recommendation_source = build_viewmodel(rows, cost_per_1m_tokens, currency)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(viewmodel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    categories = Counter(item["category"] for item in viewmodel["employee_metrics"])
    print(f"Wrote {args.output} from {len(rows)} JSONL records")
    print(f"Recommendations: {recommendation_source}")
    print(f"Categories: {dict(sorted(categories.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
