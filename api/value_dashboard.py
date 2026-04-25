"""
Generate the dashboard view model from employee_metrics.jsonl.

The output intentionally follows the shape of VIEWMODEL.json:
  - executive_summary
  - monthly_metrics
  - employee_metrics

Core metrics:
  - story_points_per_token = story_points / tokens_used
  - tokens_per_story_point = tokens_used / story_points

OpenAI is optional. If OPENAI_API_KEY is present in cle.env, it only generates
recommendation text from computed metrics; it does not compute the metrics.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


def round_metric(value: float, digits: int = 2) -> float:
    rounded = round(float(value), digits)
    return int(rounded) if rounded.is_integer() else rounded


def round_ratio(value: float) -> float:
    return round(float(value), 12)


def parse_days(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d*\.?\d+", str(value))
    if not match:
        return None
    return float(match.group(0))


def month_sort_key(month: str) -> tuple[int, int]:
    match = re.match(r"(\d{1,2})/(\d{4})", month or "")
    if not match:
        match = re.match(r"(\d{4})-(\d{1,2})", month or "")
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (9999, 99)
    return (int(match.group(2)), int(match.group(1)))


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


def normalized_row(row: dict[str, Any], cost_per_1m_tokens: float) -> dict[str, Any]:
    tokens = safe_float(row.get("token_usage"))
    story_points = safe_float(row.get("story_points"))
    tickets_closed = safe_float(row.get("tickets_resolved"))
    avg_completion_days = parse_days(row.get("time_to_completion")) or 0.0
    lines_of_code = safe_float(row.get("lines_of_code"))
    bugs_closed = safe_float(row.get("bugs_closed"))
    merge_requests = safe_float(row.get("merge_requests"))

    return {
        "name": str(row.get("name") or "Unknown"),
        "month": str(row.get("month") or "unknown"),
        "month_label": month_label(str(row.get("month") or "unknown")),
        "tokens_used": tokens,
        "story_points": story_points,
        "tickets_closed": tickets_closed,
        "lines_of_code": lines_of_code,
        "avg_completion_days": avg_completion_days,
        "completion_days_total": avg_completion_days * tickets_closed,
        "bugs_closed": bugs_closed,
        "merge_requests": merge_requests,
        "estimated_ai_cost": tokens / 1_000_000 * cost_per_1m_tokens,
        "story_points_per_token": safe_divide(story_points, tokens),
        "story_points_per_1k_tokens": safe_divide(story_points, tokens) * 1000,
        "tokens_per_story_point": safe_divide(tokens, story_points),
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
                    "tickets_closed": int(round(row["tickets_closed"])),
                    "lines_of_code": int(round(row["lines_of_code"])),
                    "avg_days_per_story_point": round_metric(
                        safe_divide(row["completion_days_total"], row["story_points"]),
                        3,
                    ),
                    "story_points_per_token": round_ratio(row["story_points_per_token"]),
                    "story_points_per_1m_tokens": round_metric(row["story_points_per_token"] * 1_000_000, 2),
                    "tokens_per_story_point": round_metric(row["tokens_per_story_point"], 1),
                }
            )
        monthly_metrics.append({"month": month_label(month), "employees": employees})
    return monthly_metrics


def aggregate_employees(rows: list[dict[str, Any]], cost_per_1m_tokens: float) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "name": "",
            "tokens_used": 0.0,
            "story_points": 0.0,
            "tickets_closed": 0.0,
            "lines_of_code": 0.0,
            "completion_days_total": 0.0,
            "bugs_closed": 0.0,
            "merge_requests": 0.0,
            "months": set(),
        }
    )

    for row in rows:
        item = grouped[row["name"]]
        item["name"] = row["name"]
        item["tokens_used"] += row["tokens_used"]
        item["story_points"] += row["story_points"]
        item["tickets_closed"] += row["tickets_closed"]
        item["lines_of_code"] += row["lines_of_code"]
        item["completion_days_total"] += row["completion_days_total"]
        item["bugs_closed"] += row["bugs_closed"]
        item["merge_requests"] += row["merge_requests"]
        item["months"].add(row["month"])

    employees = []
    for item in grouped.values():
        item["estimated_ai_cost"] = item["tokens_used"] / 1_000_000 * cost_per_1m_tokens
        item["story_points_per_token"] = safe_divide(item["story_points"], item["tokens_used"])
        item["story_points_per_1k_tokens"] = item["story_points_per_token"] * 1000
        item["tokens_per_story_point"] = safe_divide(item["tokens_used"], item["story_points"])
        item["avg_days_per_story_point"] = safe_divide(
            item["completion_days_total"],
            item["story_points"],
        )
        item["months"] = sorted(item["months"], key=month_sort_key)
        employees.append(item)
    return employees


def classify_employees(employees: list[dict[str, Any]]) -> list[dict[str, Any]]:
    token_values = [item["tokens_used"] for item in employees]
    story_point_values = [item["story_points"] for item in employees]
    tokens_per_story_point_values = [
        item["tokens_per_story_point"] for item in employees if item["tokens_per_story_point"] > 0
    ]
    story_points_per_token_values = [
        item["story_points_per_token"] for item in employees if item["story_points_per_token"] > 0
    ]

    q25_tokens = percentile(token_values, 0.25)
    q75_tokens = percentile(token_values, 0.75)
    q25_story_points = percentile(story_point_values, 0.25)
    q75_story_points = percentile(story_point_values, 0.75)
    q75_tokens_per_story_point = percentile(tokens_per_story_point_values, 0.75)
    q75_story_points_per_token = percentile(story_points_per_token_values, 0.75)

    for item in employees:
        high_tokens = item["tokens_used"] >= q75_tokens
        low_tokens = item["tokens_used"] <= q25_tokens
        moderate_tokens = q25_tokens < item["tokens_used"] < q75_tokens
        low_story_points = item["story_points"] <= q25_story_points
        high_story_points = item["story_points"] >= q75_story_points
        inefficient = item["tokens_per_story_point"] >= q75_tokens_per_story_point
        efficient = item["story_points_per_token"] >= q75_story_points_per_token

        category = "normal"
        outlier_reason = "No major outlier pattern detected."
        action_type = "monitor"

        if high_tokens and low_story_points and inefficient:
            category = "high_token_low_story_points"
            outlier_reason = "High token usage with low story point delivery."
            action_type = "retrain_user"
        elif moderate_tokens and high_story_points and efficient:
            category = "moderate_tokens_high_productivity"
            outlier_reason = "Moderate token usage with very strong story point delivery."
            action_type = "share_playbook"
        elif low_tokens and high_story_points and efficient:
            category = "low_tokens_high_productivity"
            outlier_reason = "Low token usage with strong story point delivery."
            action_type = "share_playbook"
        elif high_tokens and high_story_points:
            category = "high_tokens_high_productivity"
            outlier_reason = "High token usage is paired with high story point delivery."
            action_type = "monitor_budget"
        elif low_tokens and low_story_points:
            category = "low_tokens_low_productivity"
            outlier_reason = "Low token usage with low story point delivery."
            action_type = "test_ai_enablement"
        elif high_tokens and inefficient:
            category = "high_token_efficiency_risk"
            outlier_reason = "High token usage with weak tokens per story point."
            action_type = "review_usage"

        item["category"] = category
        item["outlier_reason"] = outlier_reason
        item["action_type"] = action_type
        item["recommendation"] = fallback_recommendation(item)

    return sorted(employees, key=lambda item: item["tokens_per_story_point"], reverse=True)


def fallback_recommendation(employee: dict[str, Any]) -> str:
    category = employee["category"]
    if category == "high_token_low_story_points":
        return (
            "Retrain this user on prompt structure, context selection, and task decomposition; "
            "review their highest-token sessions before expanding access."
        )
    if category in {"moderate_tokens_high_productivity", "low_tokens_high_productivity"}:
        return (
            "Ask this user to document their AI workflow and run a short enablement session "
            "for peers with lower story points per token."
        )
    if category == "high_tokens_high_productivity":
        return "Keep access, but monitor tokens per story point so high productivity does not hide budget drift."
    if category == "low_tokens_low_productivity":
        return "Run a controlled AI adoption experiment to see whether targeted usage improves story point delivery."
    if category == "high_token_efficiency_risk":
        return "Review whether the user is over-sending context or using premium models for low-complexity work."
    return "Monitor month-by-month trend and compare against peers doing similar work."


def format_employee_metrics(employees: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for item in employees:
        output.append(
            {
                "name": item["name"],
                "category": item["category"],
                "tokens_used": int(round(item["tokens_used"])),
                "story_points": round_metric(item["story_points"], 1),
                "story_points_per_token": round_ratio(item["story_points_per_token"]),
                "story_points_per_1m_tokens": round_metric(item["story_points_per_token"] * 1_000_000, 2),
                "tokens_per_story_point": round_metric(item["tokens_per_story_point"], 1),
                "tickets_closed": int(round(item["tickets_closed"])),
                "lines_of_code": int(round(item["lines_of_code"])),
                "avg_days_per_story_point": round_metric(item["avg_days_per_story_point"], 3),
                "outlier_reason": item["outlier_reason"],
                "action_type": item["action_type"],
                "recommendation": item["recommendation"],
            }
        )
    return output


def build_executive_summary(
    rows: list[dict[str, Any]],
    employee_metrics: list[dict[str, Any]],
    cost_per_1m_tokens: float,
    currency: str,
    monthly_budget: float | None,
) -> dict[str, Any]:
    months = sorted({row["month"] for row in rows}, key=month_sort_key)
    last_month = months[-1] if months else None
    previous_month = months[-2] if len(months) >= 2 else None

    def month_rows(month: str | None) -> list[dict[str, Any]]:
        if month is None:
            return []
        return [row for row in rows if row["month"] == month]

    current_rows = month_rows(last_month)
    previous_rows = month_rows(previous_month)
    current_tokens = sum(row["tokens_used"] for row in current_rows)
    previous_tokens = sum(row["tokens_used"] for row in previous_rows)
    current_spend = current_tokens / 1_000_000 * cost_per_1m_tokens
    previous_spend = previous_tokens / 1_000_000 * cost_per_1m_tokens
    monthly_growth = safe_divide(current_spend - previous_spend, previous_spend) * 100
    forecast_next_month = current_spend * (1 + max(min(monthly_growth, 35), -20) / 100)

    first_story_points = sum(row["story_points"] for row in month_rows(months[0] if months else None))
    current_story_points = sum(row["story_points"] for row in current_rows)
    productivity_gain = safe_divide(current_story_points - first_story_points, first_story_points) * 100

    first_bugs = sum(row["bugs_closed"] for row in month_rows(months[0] if months else None))
    current_bugs = sum(row["bugs_closed"] for row in current_rows)
    bugs_reduction = safe_divide(first_bugs - current_bugs, first_bugs) * 100

    if monthly_budget is None:
        monthly_budget = current_spend / 0.817 if current_spend else 0.0
    budget_usage = safe_divide(current_spend, monthly_budget) * 100

    categories = Counter(item["category"] for item in employee_metrics)
    main_recommendation = fallback_main_recommendation(categories)

    return {
        "monthly_ai_spend_total": round_metric(current_spend, 2),
        "forecast_next_month_ai_spend": round_metric(forecast_next_month, 2),
        "monthly_ai_spend_growth_percent": round_metric(monthly_growth, 1),
        "budget_usage_percent": round_metric(budget_usage, 1),
        "productivity_gain_percent": round_metric(productivity_gain, 1),
        "bugs_reduction_percent": round_metric(bugs_reduction, 1),
        "currency": currency,
        "main_recommendation": main_recommendation,
    }


def fallback_main_recommendation(categories: Counter[str]) -> str:
    waste_count = categories.get("high_token_low_story_points", 0) + categories.get(
        "high_token_efficiency_risk", 0
    )
    benchmark_count = categories.get("moderate_tokens_high_productivity", 0) + categories.get(
        "low_tokens_high_productivity", 0
    )
    if waste_count and benchmark_count:
        return "Retrain high-token low-output users and replicate workflows from high-productivity efficient users."
    if waste_count:
        return "Focus the next cycle on reducing tokens per story point for high-consumption outliers."
    if benchmark_count:
        return "Scale the workflows of efficient high-productivity users before increasing token budgets."
    return "Keep monitoring tokens per story point and review outliers monthly."


def maybe_apply_openai_recommendations(
    viewmodel: dict[str, Any],
    employee_metrics: list[dict[str, Any]],
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return "fallback"

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    context = {
        "executive_summary": viewmodel["executive_summary"],
        "employees": [
            {
                "name": item["name"],
                "category": item["category"],
                "tokens_used": item["tokens_used"],
                "story_points": item["story_points"],
                "story_points_per_token": item["story_points_per_token"],
                "story_points_per_1m_tokens": round_metric(item["story_points_per_token"] * 1_000_000, 2),
                "tokens_per_story_point": item["tokens_per_story_point"],
                "outlier_reason": item["outlier_reason"],
                "action_type": item["action_type"],
            }
            for item in employee_metrics
        ],
    }
    prompt = {
        "task": (
            "Generate concise action recommendations for a dashboard that detects AI token usage outliers. "
            "Use only the metrics provided. Do not invent new numbers."
        ),
        "required_json_shape": {
            "main_recommendation": "string",
            "employee_recommendations": [
                {
                    "name": "string",
                    "recommendation": "one concise sentence",
                }
            ],
        },
        "rules": [
            "For high_token_low_story_points, recommend retraining or workflow review.",
            "For moderate_tokens_high_productivity or low_tokens_high_productivity, recommend sharing the user's AI workflow with peers.",
            "For normal users, recommend monitoring unless a metric is clearly unusual.",
            "Keep recommendations concrete and manager-friendly.",
        ],
        "context": context,
    }
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You produce valid JSON only for an AI token efficiency dashboard.",
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

    if isinstance(recommendations.get("main_recommendation"), str):
        viewmodel["executive_summary"]["main_recommendation"] = recommendations["main_recommendation"]

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


def build_viewmodel(rows: list[dict[str, Any]], cost_per_1m_tokens: float, currency: str) -> dict[str, Any]:
    normalized_rows = [normalized_row(row, cost_per_1m_tokens) for row in rows]
    employees = classify_employees(aggregate_employees(normalized_rows, cost_per_1m_tokens))
    employee_metrics = format_employee_metrics(employees)
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
    recommendation_source = maybe_apply_openai_recommendations(viewmodel, employee_metrics)
    viewmodel["recommendation_source"] = recommendation_source
    viewmodel["generated_at"] = datetime.now(timezone.utc).isoformat()
    return viewmodel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build VIEWMODEL-style token outlier dashboard data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input employee metrics JSONL.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Local env file with API keys.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_env_file(args.env_file)
    cost_per_1m_tokens = safe_float(os.environ.get("AI_COST_PER_1M_TOKENS_EUR"), default=8.0)
    currency = os.environ.get("AI_COST_CURRENCY", "EUR")

    rows = read_jsonl(args.input)
    viewmodel = build_viewmodel(rows, cost_per_1m_tokens, currency)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(viewmodel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    outliers = Counter(item["category"] for item in viewmodel["employee_metrics"])
    print(f"Wrote {args.output} from {len(rows)} JSONL records")
    print(f"Recommendation source: {viewmodel['recommendation_source']}")
    print(f"Categories: {dict(sorted(outliers.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
