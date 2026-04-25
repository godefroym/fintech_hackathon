from __future__ import annotations

from typing import Any


def _round(value: float, digits: int = 2) -> float:
    rounded = round(float(value), digits)
    return int(rounded) if rounded.is_integer() else rounded


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ForecastEngine:
    def build(
        self,
        analytics_output: dict[str, Any],
        company: Any,
        llm_content: dict[str, Any] | None = None,
        months: int = 12,
    ) -> dict[str, Any]:
        llm_content = llm_content or {}
        action_plan = llm_content.get("action_plan") or self._fallback_action_plan(analytics_output)

        monthly_revenue = float(company.monthly_revenue)
        monthly_ai_spend = float(company.monthly_ai_spend_total)
        monthly_burn = float(company.monthly_burn)
        monthly_payroll = float(company.monthly_payroll_total)

        baseline_growth = 0.004
        baseline_ai_spend_growth = self._monthly_growth_from_percent(
            analytics_output["executive_summary"].get(
                "ai_spend_growth_vs_previous_12_month_avg_percent", 0
            )
        )

        productivity_lift = self._sum_effect(action_plan, "productivity_lift_percent", 18) / 100
        ai_spend_reduction = self._sum_effect(action_plan, "ai_spend_reduction_percent", 35) / 100
        bug_reduction = self._sum_effect(action_plan, "bug_reduction_percent", 18) / 100

        action_growth = baseline_growth + productivity_lift * 0.35 + bug_reduction * 0.08
        action_ai_spend_growth = max(-0.01, baseline_ai_spend_growth - ai_spend_reduction / 10)
        action_burn_reduction = ai_spend_reduction * monthly_ai_spend + bug_reduction * monthly_payroll * 0.015

        baseline = self._project_series(
            label="baseline_no_action",
            months=months,
            monthly_revenue=monthly_revenue,
            monthly_burn=monthly_burn,
            monthly_ai_spend=monthly_ai_spend,
            revenue_growth=baseline_growth,
            ai_spend_growth=baseline_ai_spend_growth,
            monthly_burn_delta=0,
        )
        with_action = self._project_series(
            label="with_action_plan",
            months=months,
            monthly_revenue=monthly_revenue,
            monthly_burn=monthly_burn,
            monthly_ai_spend=monthly_ai_spend,
            revenue_growth=action_growth,
            ai_spend_growth=action_ai_spend_growth,
            monthly_burn_delta=-action_burn_reduction,
        )

        return {
            "forecast_horizon_months": months,
            "baseline_no_action": baseline,
            "with_action_plan": with_action,
            "delta_summary": self._delta_summary(baseline, with_action),
            "assumptions": self._assumptions(
                llm_content=llm_content,
                baseline_growth=baseline_growth,
                baseline_ai_spend_growth=baseline_ai_spend_growth,
                productivity_lift=productivity_lift,
                ai_spend_reduction=ai_spend_reduction,
                bug_reduction=bug_reduction,
            ),
        }

    def _project_series(
        self,
        label: str,
        months: int,
        monthly_revenue: float,
        monthly_burn: float,
        monthly_ai_spend: float,
        revenue_growth: float,
        ai_spend_growth: float,
        monthly_burn_delta: float,
    ) -> list[dict[str, Any]]:
        series: list[dict[str, Any]] = []
        revenue = monthly_revenue
        ai_spend = monthly_ai_spend
        for month in range(1, months + 1):
            if month > 1:
                revenue *= 1 + revenue_growth
                ai_spend *= 1 + ai_spend_growth
            adjusted_burn = max(0, monthly_burn + monthly_burn_delta + ai_spend - monthly_ai_spend)
            operating_profit = revenue - adjusted_burn
            series.append(
                {
                    "scenario": label,
                    "month": month,
                    "projected_revenue": _round(revenue),
                    "projected_ai_spend": _round(ai_spend),
                    "projected_burn": _round(adjusted_burn),
                    "projected_operating_profit": _round(operating_profit),
                }
            )
        return series

    def _delta_summary(
        self,
        baseline: list[dict[str, Any]],
        with_action: list[dict[str, Any]],
    ) -> dict[str, float]:
        baseline_revenue = sum(item["projected_revenue"] for item in baseline)
        action_revenue = sum(item["projected_revenue"] for item in with_action)
        baseline_ai_spend = sum(item["projected_ai_spend"] for item in baseline)
        action_ai_spend = sum(item["projected_ai_spend"] for item in with_action)
        baseline_profit = sum(item["projected_operating_profit"] for item in baseline)
        action_profit = sum(item["projected_operating_profit"] for item in with_action)
        return {
            "revenue_delta": _round(action_revenue - baseline_revenue),
            "ai_spend_delta": _round(action_ai_spend - baseline_ai_spend),
            "operating_profit_delta": _round(action_profit - baseline_profit),
        }

    def _assumptions(
        self,
        llm_content: dict[str, Any],
        baseline_growth: float,
        baseline_ai_spend_growth: float,
        productivity_lift: float,
        ai_spend_reduction: float,
        bug_reduction: float,
    ) -> list[dict[str, Any]]:
        assumptions = llm_content.get("forecast_assumptions") or []
        deterministic = [
            {
                "name": "baseline_monthly_revenue_growth",
                "value": _round(baseline_growth * 100),
                "unit": "percent",
                "rationale": "Conservative default for do-nothing revenue projection.",
            },
            {
                "name": "baseline_monthly_ai_spend_growth",
                "value": _round(baseline_ai_spend_growth * 100),
                "unit": "percent",
                "rationale": "Derived from current spend versus previous 12-month average.",
            },
            {
                "name": "action_plan_productivity_lift",
                "value": _round(productivity_lift * 100),
                "unit": "percent",
                "rationale": "Capped aggregate lift from action plan items.",
            },
            {
                "name": "action_plan_ai_spend_reduction",
                "value": _round(ai_spend_reduction * 100),
                "unit": "percent",
                "rationale": "Capped aggregate spend reduction from action plan items.",
            },
            {
                "name": "action_plan_bug_reduction",
                "value": _round(bug_reduction * 100),
                "unit": "percent",
                "rationale": "Capped aggregate quality improvement from action plan items.",
            },
        ]
        return assumptions + deterministic

    def _fallback_action_plan(self, analytics_output: dict[str, Any]) -> list[dict[str, Any]]:
        targets = analytics_output.get("rankings", {}).get("optimization_targets", [])
        return [
            {
                "priority": 1,
                "title": "Coach low ROI users",
                "owner": "Engineering Manager",
                "timeframe": "30 days",
                "action": f"Coach optimization targets: {', '.join(targets) or 'bottom ROI users'}.",
                "expected_effect": "Improve weak AI workflows without reducing high-value usage.",
                "productivity_lift_percent": 6,
                "ai_spend_reduction_percent": 8,
                "bug_reduction_percent": 3,
            },
            {
                "priority": 2,
                "title": "Introduce token budget guardrails",
                "owner": "Finance and Platform",
                "timeframe": "45 days",
                "action": "Set token alerts, review expensive prompts, and monitor outliers weekly.",
                "expected_effect": "Reduce waste among high spenders and improve budget predictability.",
                "productivity_lift_percent": 2,
                "ai_spend_reduction_percent": 10,
                "bug_reduction_percent": 2,
            },
            {
                "priority": 3,
                "title": "Scale top performer workflows",
                "owner": "Product Engineering",
                "timeframe": "60 days",
                "action": "Turn top ROI workflows into reusable templates and team playbooks.",
                "expected_effect": "Increase repeatable productivity gains across the team.",
                "productivity_lift_percent": 5,
                "ai_spend_reduction_percent": 3,
                "bug_reduction_percent": 4,
            },
        ]

    def _sum_effect(self, action_plan: list[dict[str, Any]], key: str, cap: float) -> float:
        return _clamp(sum(float(item.get(key, 0) or 0) for item in action_plan), 0, cap)

    def _monthly_growth_from_percent(self, annualized_percent: float) -> float:
        return _clamp(float(annualized_percent or 0) / 100 / 12, -0.02, 0.04)
