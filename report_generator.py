from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReportGenerator:
    def write(
        self,
        report_dir: Path,
        analytics_output: dict[str, Any],
        forecast: dict[str, Any],
        llm_content: dict[str, Any] | None = None,
        pretty: bool = True,
    ) -> dict[str, str]:
        llm_content = llm_content or {}
        report_dir.mkdir(parents=True, exist_ok=True)
        indent = 2 if pretty else None

        dashboard_data = self._dashboard_data(analytics_output, forecast)
        executive_report = self._executive_report(analytics_output, forecast, llm_content)
        action_plan = llm_content.get("action_plan") or self._fallback_action_plan(forecast)

        files = {
            "raw_output": report_dir / "output.json",
            "dashboard_data": report_dir / "dashboard_data.json",
            "executive_report": report_dir / "executive_report.json",
            "forecast_scenarios": report_dir / "forecast_scenarios.json",
            "action_plan": report_dir / "action_plan.json",
        }

        payloads = {
            "raw_output": analytics_output,
            "dashboard_data": dashboard_data,
            "executive_report": executive_report,
            "forecast_scenarios": forecast,
            "action_plan": {"items": action_plan},
        }
        for key, path in files.items():
            path.write_text(
                json.dumps(payloads[key], ensure_ascii=False, indent=indent) + "\n",
                encoding="utf-8",
            )

        index = {
            "files": {key: path.name for key, path in files.items()},
            "frontend_entrypoint": "dashboard_data.json",
            "executive_entrypoint": "executive_report.json",
            "forecast_entrypoint": "forecast_scenarios.json",
        }
        index_path = report_dir / "index.json"
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
        return {**{key: str(path) for key, path in files.items()}, "index": str(index_path)}

    def _dashboard_data(
        self,
        analytics_output: dict[str, Any],
        forecast: dict[str, Any],
    ) -> dict[str, Any]:
        summary = analytics_output["executive_summary"]
        return {
            "summary_cards": [
                {
                    "label": "Overall AI ROI",
                    "value": summary["overall_ai_roi_score"],
                    "unit": "score",
                    "status": self._score_status(summary["overall_ai_roi_score"]),
                },
                {
                    "label": "Monthly AI Spend",
                    "value": summary["monthly_ai_spend_total"],
                    "unit": "currency",
                    "status": "watch" if summary["budget_usage_percent"] >= 80 else "healthy",
                },
                {
                    "label": "Next Month AI Spend",
                    "value": summary["forecast_next_month_ai_spend"],
                    "unit": "currency",
                    "status": "watch"
                    if summary["forecast_next_month_ai_spend"] > summary["monthly_ai_spend_total"]
                    else "healthy",
                },
                {
                    "label": "Productivity Gain",
                    "value": summary["productivity_gain_percent"],
                    "unit": "percent",
                    "status": "healthy",
                },
                {
                    "label": "Forecast Profit Delta",
                    "value": forecast["delta_summary"]["operating_profit_delta"],
                    "unit": "currency",
                    "status": "healthy"
                    if forecast["delta_summary"]["operating_profit_delta"] >= 0
                    else "risk",
                },
            ],
            "charts": {
                **analytics_output["chart_data"],
                "forecast_revenue": self._forecast_chart(forecast, "projected_revenue"),
                "forecast_operating_profit": self._forecast_chart(
                    forecast, "projected_operating_profit"
                ),
                "forecast_ai_spend": self._forecast_chart(forecast, "projected_ai_spend"),
                "category_distribution": self._category_distribution(
                    analytics_output["employee_metrics"]
                ),
            },
            "rankings": analytics_output["rankings"],
            "analysis_sections": analytics_output.get("analysis_sections", {}),
        }

    def _executive_report(
        self,
        analytics_output: dict[str, Any],
        forecast: dict[str, Any],
        llm_content: dict[str, Any],
    ) -> dict[str, Any]:
        summary = analytics_output["executive_summary"]
        return {
            "cfo_decision_summary": self._cfo_decision_summary(
                analytics_output=analytics_output,
                forecast=forecast,
            ),
            "status": llm_content.get("situation_status")
            or self._situation_status(summary["overall_ai_roi_score"], summary["budget_usage_percent"]),
            "summary": llm_content.get("executive_brief")
            or [
                summary["verdict"],
                f"AI spend uses {summary['budget_usage_percent']}% of the monthly budget and is forecast at {summary['forecast_next_month_ai_spend']} next month.",
                f"Applying the action plan projects {forecast['delta_summary']['operating_profit_delta']} additional operating profit over 12 months.",
            ],
            "diagnosis": llm_content.get("diagnosis") or analytics_output["insights"],
            "risk_level": self._risk_level(summary, analytics_output),
            "recommended_action_plan": llm_content.get("action_plan")
            or self._fallback_action_plan(forecast),
            "forecast_delta_summary": forecast["delta_summary"],
            "analysis_sections": analytics_output.get("analysis_sections", {}),
            "assumptions": forecast["assumptions"],
        }

    def _cfo_decision_summary(
        self,
        analytics_output: dict[str, Any],
        forecast: dict[str, Any],
    ) -> dict[str, Any]:
        summary = analytics_output["executive_summary"]
        analysis = analytics_output.get("analysis_sections", {})
        strategic = analysis.get("company_level_analysis", {}).get("strategic_roi", {})
        spend = analysis.get("company_level_analysis", {}).get("spend_control", {})
        action = "maintain_with_controls"
        if summary["overall_ai_roi_score"] < 55:
            action = "freeze_expansion"
        elif summary["budget_usage_percent"] >= 90:
            action = "approve_controls_before_scaling"
        return {
            "recommended_budget_decision": action,
            "financial_position": summary["verdict"],
            "budget_usage_percent": summary["budget_usage_percent"],
            "monthly_ai_spend_growth_percent": summary["monthly_ai_spend_growth_percent"],
            "forecast_next_month_ai_spend": summary["forecast_next_month_ai_spend"],
            "projected_12_month_operating_profit_delta": forecast["delta_summary"][
                "operating_profit_delta"
            ],
            "primary_value_creators": strategic.get("value_creators", []),
            "primary_waste_sources": strategic.get("waste_sources", []),
            "finance_controls_to_apply": [
                "Set monthly token budget thresholds by team and user segment.",
                "Require review for high-spend users below ROI threshold.",
                "Preserve access for high-ROI users and replicate their workflows.",
                "Downgrade or pause premium usage where ROI remains low after remediation.",
            ],
            "spend_control": spend,
        }

    def _forecast_chart(self, forecast: dict[str, Any], metric: str) -> list[dict[str, Any]]:
        points = []
        for scenario_key in ("baseline_no_action", "with_action_plan"):
            for item in forecast[scenario_key]:
                points.append(
                    {
                        "scenario": scenario_key,
                        "month": item["month"],
                        "value": item[metric],
                    }
                )
        return points

    def _category_distribution(self, employees: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for employee in employees:
            category = employee["category"]
            counts[category] = counts.get(category, 0) + 1
        return [{"category": key, "count": value} for key, value in sorted(counts.items())]

    def _fallback_action_plan(self, forecast: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "priority": 1,
                "title": "Execute ROI optimization plan",
                "owner": "COO",
                "timeframe": "90 days",
                "action": "Apply the forecast action plan assumptions and review impact monthly.",
                "expected_effect": f"Projected operating profit delta: {forecast['delta_summary']['operating_profit_delta']}.",
            }
        ]

    def _score_status(self, score: float) -> str:
        if score >= 75:
            return "healthy"
        if score >= 55:
            return "watch"
        return "risk"

    def _situation_status(self, roi_score: float, budget_usage: float) -> str:
        if roi_score >= 75 and budget_usage <= 85:
            return "reasoned_and_justified"
        if roi_score >= 55:
            return "partially_reasoned"
        return "unreasonable_spend"

    def _risk_level(self, summary: dict[str, Any], analytics_output: dict[str, Any]) -> str:
        high_insights = [
            insight for insight in analytics_output.get("insights", []) if insight.get("severity") == "high"
        ]
        if summary["overall_ai_roi_score"] < 55 or len(high_insights) >= 2:
            return "high"
        if summary["budget_usage_percent"] >= 80 or high_insights:
            return "medium"
        return "low"
