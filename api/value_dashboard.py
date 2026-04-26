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


def percentile_rank(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    return safe_divide(sum(1 for item in values if item <= value), len(values)) * 100


def rank_desc(values: list[float], value: float) -> int:
    return 1 + sum(1 for item in values if item > value)


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


def parse_days(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d*\.?\d+", str(value))
    if not match:
        return 0.0
    return float(match.group(0))


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
        "tickets_resolved": safe_float(row.get("tickets_resolved")),
        "time_to_completion_days": parse_days(row.get("time_to_completion")),
        "merge_requests_per_ticket": safe_float(row.get("merge_requests_per_ticket")),
        "bugs_closed": safe_float(row.get("bugs_closed")),
        "lines_of_code": safe_float(row.get("lines_of_code")),
        "merge_requests": safe_float(row.get("merge_requests")),
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


def signed_metric(value: float, digits: int = 1) -> str:
    rounded = round_metric(value, digits)
    return f"+{rounded}" if value > 0 else str(rounded)


def percent_label(value: float) -> str:
    return f"P{round_metric(value, 0)}"


def top_share_label(rank: int, total: int) -> str:
    return f"top {round_metric(safe_divide(rank, total) * 100, 1)}%"


def vs_median(value: float, median: float) -> float:
    return safe_divide(value - median, median) * 100


def build_recommendation_context(
    row: dict[str, Any],
    token_values: list[float],
    story_point_values: list[float],
    productivity_values: list[float],
    ticket_values: list[float],
    completion_day_values: list[float],
    bug_values: list[float],
    line_values: list[float],
    merge_request_values: list[float],
) -> dict[str, Any]:
    employee_count = len(token_values)
    token_rank = rank_desc(token_values, row["tokens_used"])
    story_point_rank = rank_desc(story_point_values, row["story_points"])
    efficiency_rank = rank_desc(productivity_values, row["productivity"])
    token_percentile = percentile_rank(token_values, row["tokens_used"])
    story_point_percentile = percentile_rank(story_point_values, row["story_points"])
    efficiency_percentile = percentile_rank(productivity_values, row["productivity"])
    tokens_per_story_point_values = [
        safe_divide(tokens, story_points)
        for tokens, story_points in zip(token_values, story_point_values)
        if story_points > 0
    ]
    tokens_per_story_point = safe_divide(row["tokens_used"], row["story_points"])
    median_tokens = percentile(token_values, 0.5)
    median_story_points = percentile(story_point_values, 0.5)
    median_efficiency = percentile(productivity_values, 0.5)
    median_tokens_per_story_point = percentile(tokens_per_story_point_values, 0.5)
    median_tickets = percentile(ticket_values, 0.5)
    median_completion_days = percentile(completion_day_values, 0.5)
    median_bugs = percentile(bug_values, 0.5)
    median_lines = percentile(line_values, 0.5)
    median_merge_requests = percentile(merge_request_values, 0.5)

    flags = []
    if token_rank / employee_count <= 0.05 and efficiency_percentile <= 60:
        flags.append("top_5_percent_usage_with_average_or_lower_efficiency")
    if token_percentile >= 75 and efficiency_percentile <= 25:
        flags.append("high_usage_low_efficiency")
    if efficiency_percentile >= 90 and story_point_percentile >= 75:
        flags.append("benchmark_user")
    if token_percentile <= 25 and story_point_percentile <= 25:
        flags.append("low_adoption")

    return {
        "name": row["name"],
        "tokens_used": int(round(row["tokens_used"])),
        "story_points": round_metric(row["story_points"], 1),
        "tickets_resolved": int(round(row["tickets_resolved"])),
        "time_to_completion_days": round_metric(row["time_to_completion_days"], 2),
        "bugs_closed": int(round(row["bugs_closed"])),
        "lines_of_code": int(round(row["lines_of_code"])),
        "merge_requests": int(round(row["merge_requests"])),
        "merge_requests_per_ticket": round_metric(row["merge_requests_per_ticket"], 2),
        "story_points_per_million_tokens": round_metric(row["productivity"], 2),
        "tokens_per_story_point": round_metric(tokens_per_story_point, 0),
        "employee_count": employee_count,
        "token_rank": token_rank,
        "story_point_rank": story_point_rank,
        "efficiency_rank": efficiency_rank,
        "token_top_share_percent": round_metric(safe_divide(token_rank, employee_count) * 100, 1),
        "story_point_top_share_percent": round_metric(
            safe_divide(story_point_rank, employee_count) * 100,
            1,
        ),
        "efficiency_top_share_percent": round_metric(
            safe_divide(efficiency_rank, employee_count) * 100,
            1,
        ),
        "token_percentile": round_metric(token_percentile, 0),
        "story_point_percentile": round_metric(story_point_percentile, 0),
        "efficiency_percentile": round_metric(efficiency_percentile, 0),
        "team_median_tokens_used": int(round(median_tokens)),
        "team_median_story_points": round_metric(median_story_points, 1),
        "team_median_tickets_resolved": round_metric(median_tickets, 1),
        "team_median_time_to_completion_days": round_metric(median_completion_days, 2),
        "team_median_bugs_closed": round_metric(median_bugs, 1),
        "team_median_lines_of_code": int(round(median_lines)),
        "team_median_merge_requests": round_metric(median_merge_requests, 1),
        "team_median_story_points_per_million_tokens": round_metric(median_efficiency, 2),
        "team_median_tokens_per_story_point": round_metric(median_tokens_per_story_point, 0),
        "token_vs_median_percent": round_metric(
            vs_median(row["tokens_used"], median_tokens),
            1,
        ),
        "story_points_vs_median_percent": round_metric(
            vs_median(row["story_points"], median_story_points),
            1,
        ),
        "efficiency_vs_median_percent": round_metric(
            vs_median(row["productivity"], median_efficiency),
            1,
        ),
        "tokens_per_story_point_vs_median_percent": round_metric(
            vs_median(tokens_per_story_point, median_tokens_per_story_point),
            1,
        ),
        "tickets_vs_median_percent": round_metric(
            vs_median(row["tickets_resolved"], median_tickets),
            1,
        ),
        "completion_days_vs_median_percent": round_metric(
            vs_median(row["time_to_completion_days"], median_completion_days),
            1,
        ),
        "bugs_vs_median_percent": round_metric(
            vs_median(row["bugs_closed"], median_bugs),
            1,
        ),
        "lines_of_code_vs_median_percent": round_metric(
            vs_median(row["lines_of_code"], median_lines),
            1,
        ),
        "merge_requests_vs_median_percent": round_metric(
            vs_median(row["merge_requests"], median_merge_requests),
            1,
        ),
        "flags": flags,
    }


def fallback_recommendation(category: str, context: dict[str, Any]) -> str:
    name = context["name"]
    total = context["employee_count"]
    token_position = (
        f"{top_share_label(context['token_rank'], total)} token usage "
        f"(rank #{context['token_rank']}/{total}, {percent_label(context['token_percentile'])})"
    )
    story_position = (
        f"{top_share_label(context['story_point_rank'], total)} story point delivery "
        f"(rank #{context['story_point_rank']}/{total}, {percent_label(context['story_point_percentile'])})"
    )
    efficiency_position = (
        f"{top_share_label(context['efficiency_rank'], total)} efficiency "
        f"(rank #{context['efficiency_rank']}/{total}, {percent_label(context['efficiency_percentile'])})"
    )
    story_points_per_million_tokens = context["story_points_per_million_tokens"]
    tokens_per_story_point = context["tokens_per_story_point"]
    token_vs_median = signed_metric(context["token_vs_median_percent"])
    story_vs_median = signed_metric(context["story_points_vs_median_percent"])
    efficiency_vs_median = signed_metric(context["efficiency_vs_median_percent"])
    tickets_vs_median = signed_metric(context["tickets_vs_median_percent"])
    completion_days_vs_median = signed_metric(context["completion_days_vs_median_percent"])
    tokens_per_story_point_vs_median = signed_metric(
        context["tokens_per_story_point_vs_median_percent"]
    )
    delivery_detail = (
        f"{context['tickets_resolved']} tickets resolved versus a team median of "
        f"{context['team_median_tickets_resolved']}, {context['time_to_completion_days']} days "
        f"average completion time versus {context['team_median_time_to_completion_days']} days median, "
        f"{context['bugs_closed']} bugs closed, {context['merge_requests']} merge requests, "
        f"and {context['lines_of_code']} lines of code"
    )

    if category == "high_roi":
        return (
            f"{name} is a benchmark: {story_position} and {efficiency_position}, using {tokens_per_story_point} tokens per story point versus a team median of {context['team_median_tokens_per_story_point']}. "
            f"Usage is {token_position} ({token_vs_median}% vs median), but delivery is {story_vs_median}% vs median and efficiency is {efficiency_vs_median}% vs median. "
            f"Delivery context: {delivery_detail}. Recognize this person as a top AI user and have them coach others on token discipline."
        )
    if category == "efficient_user":
        return (
            f"{name} is efficient: {story_position} with {token_position}, producing {story_points_per_million_tokens} story points per million tokens versus a team median of {context['team_median_story_points_per_million_tokens']}. "
            f"Because token usage is {token_vs_median}% vs median while efficiency is {efficiency_vs_median}% vs median, praise this usage pattern. "
            f"Delivery context: {delivery_detail}. Have this employee share prompts, context-selection habits, and task patterns with the rest of the team."
        )
    if category == "overspender":
        return (
            f"{name} is a cost-reduction priority: {token_position}, but only {story_position} and {efficiency_position}, using {tokens_per_story_point} tokens per story point versus a team median of {context['team_median_tokens_per_story_point']}. "
            f"Token usage is {token_vs_median}% vs median while efficiency is {efficiency_vs_median}% vs median. "
            f"Delivery context: {delivery_detail}. Review prompt logs, cap oversized context, and retrain before increasing this user's AI budget."
        )
    if category == "low_adoption":
        return (
            f"{name} looks like an adoption problem rather than pure waste: usage is {token_position} and delivery is {story_position}, with {story_points_per_million_tokens} story points per million tokens. "
            f"Because both usage and story points sit below the peer median ({token_vs_median}% tokens, {story_vs_median}% story points), run targeted coaching before cutting access. "
            f"Delivery context: {delivery_detail}; tickets are {tickets_vs_median}% versus median and completion time is {completion_days_vs_median}% versus median."
        )
    if category == "quality_risk":
        return (
            f"{name} should not receive more AI budget yet: delivery is only {story_position} and efficiency is {efficiency_position}, using {tokens_per_story_point} tokens per story point versus a team median of {context['team_median_tokens_per_story_point']}. "
            f"Usage is {token_vs_median}% vs median but story points are {story_vs_median}% vs median. "
            f"Delivery context: {delivery_detail}. Add task decomposition, review checkpoints, and quality gates before encouraging heavier AI usage."
        )
    return (
        f"{name} is not an extreme outlier: {token_position}, {story_position}, and {efficiency_position}, using {tokens_per_story_point} tokens per story point versus a team median of {context['team_median_tokens_per_story_point']}. "
        f"Delivery context: {delivery_detail}. Keep monitoring the trend, then use efficient-user playbooks if efficiency stays below the peer median ({efficiency_vs_median}% vs median) or token usage rises without a matching delivery increase."
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


def build_employee_metrics(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    employee_rows = latest_employee_rows(rows)
    token_values = [row["tokens_used"] for row in employee_rows]
    story_point_values = [row["story_points"] for row in employee_rows]
    productivity_values = [row["productivity"] for row in employee_rows]
    ticket_values = [row["tickets_resolved"] for row in employee_rows]
    completion_day_values = [row["time_to_completion_days"] for row in employee_rows]
    bug_values = [row["bugs_closed"] for row in employee_rows]
    line_values = [row["lines_of_code"] for row in employee_rows]
    merge_request_values = [row["merge_requests"] for row in employee_rows]

    employees = []
    recommendation_context = []
    for row in employee_rows:
        category = classify_employee(row, token_values, story_point_values, productivity_values)
        context = build_recommendation_context(
            row,
            token_values,
            story_point_values,
            productivity_values,
            ticket_values,
            completion_day_values,
            bug_values,
            line_values,
            merge_request_values,
        )
        context["category"] = category
        recommendation_context.append(context)
        employees.append(
            {
                "name": row["name"],
                "category": category,
                "month": row["month_label"],
                "tokens_used": int(round(row["tokens_used"])),
                "story_points": round_metric(row["story_points"], 1),
                "tickets_resolved": int(round(row["tickets_resolved"])),
                "time_to_completion_days": round_metric(row["time_to_completion_days"], 2),
                "bugs_closed": int(round(row["bugs_closed"])),
                "lines_of_code": int(round(row["lines_of_code"])),
                "merge_requests": int(round(row["merge_requests"])),
                "merge_requests_per_ticket": round_metric(row["merge_requests_per_ticket"], 2),
                "recommendation": fallback_recommendation(category, context),
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
    sorted_employees = sorted(
        employees,
        key=lambda item: (category_rank.get(item["category"], 99), item["name"]),
    )
    sorted_names = [item["name"] for item in sorted_employees]
    context_by_name = {item["name"]: item for item in recommendation_context}
    return sorted_employees, [context_by_name[name] for name in sorted_names]


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
            "and recognize efficient users as internal coaches. This keeps the AI budget focused on work that converts into measurable delivery while spreading the habits that already work."
        )
    if categories.get("overspender", 0):
        return (
            "Cap token-heavy workflows until managers review why the spend is not translating into story points. "
            "The immediate goal is to reduce waste before expanding the AI budget."
        )
    if categories.get("high_roi", 0) or categories.get("efficient_user", 0):
        return (
            "Expand AI usage by recognizing users who already convert tokens into story points efficiently. "
            "Use their habits as the onboarding playbook for lower-performing teams and ask them to coach peers."
        )
    return (
        "Keep the AI budget stable and review employee-level outliers monthly. "
        "The dashboard should be used to decide where AI coaching creates more delivery and where token spend needs tighter control."
    )


def build_global_recommendation_context(
    rows: list[dict[str, Any]],
    recommendation_context: list[dict[str, Any]],
    cost_per_1m_tokens: float,
    currency: str,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"tokens_used": 0.0, "story_points": 0.0})
    for row in rows:
        grouped[row["month"]]["tokens_used"] += row["tokens_used"]
        grouped[row["month"]]["story_points"] += row["story_points"]

    monthly_spend = []
    for month in sorted(grouped, key=month_sort_key):
        tokens_used = grouped[month]["tokens_used"]
        story_points = grouped[month]["story_points"]
        monthly_spend.append(
            {
                "month": month_label(month),
                "tokens_used": int(round(tokens_used)),
                "estimated_spend": round_metric(tokens_used / 1_000_000 * cost_per_1m_tokens, 2),
                "story_points": round_metric(story_points, 1),
            }
        )

    first_month = monthly_spend[0] if monthly_spend else {}
    latest_month = monthly_spend[-1] if monthly_spend else {}
    peak_month = max(monthly_spend, key=lambda item: item["estimated_spend"], default={})
    month_to_month_increases = sum(
        1
        for previous, current in zip(monthly_spend, monthly_spend[1:])
        if current["estimated_spend"] > previous["estimated_spend"]
    )

    def by_category(category: str) -> list[dict[str, Any]]:
        return [item for item in recommendation_context if item["category"] == category]

    def employee_summary(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": item["name"],
            "tokens_used": item["tokens_used"],
            "story_points": item["story_points"],
            "tickets_resolved": item["tickets_resolved"],
            "time_to_completion_days": item["time_to_completion_days"],
            "tokens_per_story_point": item["tokens_per_story_point"],
            "story_points_per_million_tokens": item["story_points_per_million_tokens"],
            "team_median_tokens_per_story_point": item["team_median_tokens_per_story_point"],
            "team_median_story_points_per_million_tokens": item[
                "team_median_story_points_per_million_tokens"
            ],
        }

    overspenders = sorted(
        by_category("overspender"),
        key=lambda item: item["tokens_per_story_point"],
        reverse=True,
    )
    efficient_users = sorted(
        by_category("high_roi") + by_category("efficient_user"),
        key=lambda item: item["story_points_per_million_tokens"],
        reverse=True,
    )
    low_adoption_users = sorted(
        by_category("low_adoption"),
        key=lambda item: (item["tokens_used"], item["story_points"]),
    )

    return {
        "currency": currency,
        "monthly_spend": monthly_spend,
        "spend_first_month": first_month,
        "spend_latest_month": latest_month,
        "spend_peak_month": peak_month,
        "spend_period_growth_percent": round_metric(
            safe_divide(
                latest_month.get("estimated_spend", 0.0) - first_month.get("estimated_spend", 0.0),
                first_month.get("estimated_spend", 0.0),
            )
            * 100,
            1,
        ),
        "month_to_month_increases": month_to_month_increases,
        "month_to_month_periods": max(len(monthly_spend) - 1, 0),
        "overspenders_to_reduce": [employee_summary(item) for item in overspenders[:4]],
        "efficient_users_to_replicate": [employee_summary(item) for item in efficient_users[:5]],
        "low_adoption_low_delivery_users": [
            employee_summary(item) for item in low_adoption_users[:4]
        ],
    }


def build_global_main_recommendation(global_context: dict[str, Any]) -> str:
    first_month = global_context["spend_first_month"]
    latest_month = global_context["spend_latest_month"]
    peak_month = global_context["spend_peak_month"]
    currency = global_context["currency"]
    overspenders = global_context["overspenders_to_reduce"]
    efficient_users = global_context["efficient_users_to_replicate"]
    low_adoption_users = global_context["low_adoption_low_delivery_users"]

    overspender_text = ", ".join(
        f"{item['name']} ({item['tokens_per_story_point']} tokens/story point)"
        for item in overspenders[:3]
    )
    efficient_text = ", ".join(
        f"{item['name']} ({item['story_points_per_million_tokens']} story points/M tokens)"
        for item in efficient_users[:3]
    )
    low_adoption_text = ", ".join(
        f"{item['name']} ({item['tokens_used']} tokens, {item['story_points']} story points)"
        for item in low_adoption_users[:3]
    )

    return (
        f"Pain point: AI spend rose from {first_month.get('estimated_spend', 0)} {currency} in {first_month.get('month')} "
        f"to {latest_month.get('estimated_spend', 0)} {currency} in {latest_month.get('month')} "
        f"({signed_metric(global_context['spend_period_growth_percent'])}%), with increases in "
        f"{global_context['month_to_month_increases']} of {global_context['month_to_month_periods']} month-to-month periods and a peak at "
        f"{peak_month.get('estimated_spend', 0)} {currency} in {peak_month.get('month')}. "
        f"The first waste bucket is high consumption with weak delivery: {overspender_text}; cap or reduce usage for these users and retrain them on smaller context and prompt discipline. "
        f"The second opportunity is to replicate good usage: {efficient_text}; recognize these employees and have them coach peers because they turn tokens into delivery efficiently. "
        f"The third pain point is low AI adoption with low delivery: {low_adoption_text}; do targeted enablement and watch whether story points and tickets resolved improve next month."
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


def maybe_apply_openai_recommendations(
    viewmodel: dict[str, Any],
    recommendation_context: list[dict[str, Any]],
    global_context: dict[str, Any],
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return "skipped"

    model = os.environ.get("OPENAI_MODEL", "gpt-5.4")
    prompt = {
        "task": (
            "Write CFO and engineering-manager recommendations for an AI token value dashboard. "
            "The recommendations must justify whether AI spend is productive, wasteful, or under-adopted."
        ),
        "rules": [
            "Use only the provided dashboard fields and KPI context.",
            "Do not add, remove, rename, or compute output fields.",
            "Return only main_recommendation and employee recommendations by name.",
            "The main_recommendation must surface pain points first: monthly AI spend trend, high-token low-delivery employees, efficient users to replicate, and low-adoption low-delivery employees.",
            "The main_recommendation must name concrete employees from the provided groups and give clear actions for each group.",
            "The main_recommendation must mention the spend trend using the monthly_spend values, including the period growth and peak month.",
            "Each employee recommendation must be 3 to 4 concise sentences.",
            "Each employee recommendation must be understandable without knowing finance or analytics jargon.",
            "Do not mention any abstract invented metric.",
            "Use only plain comparisons: tokens_used, story_points, tokens per story point, story points per million tokens, peer rank, percentile, and median comparison.",
            "Also use the employee delivery data when relevant: tickets_resolved, time_to_completion_days, bugs_closed, lines_of_code, merge_requests, and merge_requests_per_ticket.",
            "When using a derived ratio, explain it directly, for example: 'tokens per story point means how many tokens were spent to deliver one story point; lower is better'.",
            "Do not use the word productivity in employee recommendations; use 'efficiency' only when it is tied to a direct ratio such as story points per million tokens.",
            "Each employee recommendation must include a clear business action: reduce/cap usage, retrain, monitor, replicate workflow, or run adoption coaching.",
            "The dashboard should not only criticize poor usage. For high_roi and efficient_user employees, explicitly praise the behavior and recommend that they coach or mentor peers on token usage.",
            "Each employee recommendation must include one next-month KPI to watch.",
            "For overspenders, explicitly explain why cost should be reduced or controlled.",
            "For efficient users and high_roi users, explicitly explain what should be replicated.",
            "For low_adoption users, explicitly explain why enablement may create more value than budget cuts.",
            "Write for a CFO or manager, not for a developer.",
        ],
        "required_json_shape": {
            "main_recommendation": "string",
            "employee_recommendations": [
                {"name": "string", "recommendation": "3 to 4 concise sentences with KPI comparisons and actions"}
            ],
        },
        "dashboard": {
            "executive_summary": viewmodel["executive_summary"],
            "employee_metrics": viewmodel["employee_metrics"],
        },
        "kpi_context": recommendation_context,
        "global_context": global_context,
    }
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You produce valid JSON only for a fintech AI spending dashboard. "
                    "Your audience is a CFO and engineering manager who need justified, actionable decisions."
                ),
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
        with urllib.request.urlopen(request, timeout=90) as response:
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
    return f"openai:{model}"


def build_viewmodel(
    rows: list[dict[str, Any]],
    cost_per_1m_tokens: float,
    currency: str,
) -> tuple[dict[str, Any], str]:
    normalized_rows = [normalized_row(row) for row in rows]
    employee_metrics, recommendation_context = build_employee_metrics(normalized_rows)
    monthly_budget = safe_float(os.environ.get("AI_MONTHLY_BUDGET"), default=0.0) or None
    global_context = build_global_recommendation_context(
        normalized_rows,
        recommendation_context,
        cost_per_1m_tokens,
        currency,
    )

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
    viewmodel["executive_summary"]["main_recommendation"] = build_global_main_recommendation(
        global_context
    )
    recommendation_source = maybe_apply_openai_recommendations(
        viewmodel,
        recommendation_context,
        global_context,
    )
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
