from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


EMPLOYEE_CATEGORIES = {
    "high_roi",
    "efficient_user",
    "overspender",
    "quality_risk",
    "low_adoption",
    "average_user",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(numeric):
        return default
    return numeric


def safe_divide(numerator: Any, denominator: Any, default: float = 0.0) -> float:
    denom = safe_float(denominator)
    if denom == 0:
        return default
    return safe_float(numerator) / denom


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def round_metric(value: float, digits: int = 1) -> float:
    rounded = round(float(value), digits)
    return int(rounded) if rounded.is_integer() else rounded


def minmax_score(series: pd.Series, invert: bool = False) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0.0)
    minimum = numeric.min()
    maximum = numeric.max()
    if maximum == minimum:
        score = pd.Series([50.0] * len(numeric), index=numeric.index)
    else:
        score = (numeric - minimum) / (maximum - minimum) * 100.0
    return 100.0 - score if invert else score


class EmployeeInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = "Unknown"
    token_used: float = 0
    tickets_resolved: float = 0
    tickets_reopen: float = 0
    comments_for_clarification: float = 0
    time_to_completion: float = 0
    merge_requests_by_tickets: float = 0
    bugs_closed: float = 0
    story_points: float = 0
    lines_of_codes: float = 0
    merge_requests: float = 0

    @field_validator(
        "token_used",
        "tickets_resolved",
        "tickets_reopen",
        "comments_for_clarification",
        "time_to_completion",
        "merge_requests_by_tickets",
        "bugs_closed",
        "story_points",
        "lines_of_codes",
        "merge_requests",
        mode="before",
    )
    @classmethod
    def numeric_default(cls, value: Any) -> float:
        return max(0.0, safe_float(value))


class CompanyInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    company_name: str = "Unknown"
    employee_count: int = 0
    monthly_revenue: float = 0
    monthly_burn: float = 0
    cash_runway_months: float = 0
    monthly_ai_spend_total: float = 0
    previous_month_ai_spend: float = 0
    previous_quarter_ai_spend_avg: float = 0
    previous_12_month_ai_spend_total: float = 0
    previous_12_month_ai_spend_avg: float = 0
    monthly_payroll_total: float = 0
    annual_revenue: float = 0
    annual_burn: float = 0
    annual_ai_spend_total: float = 0
    annual_payroll_total: float = 0
    productivity_before_ai: float = 0
    productivity_after_ai: float = 0
    previous_12_month_productivity_avg: float = 0
    average_completion_time_before_ai_days: float = 0
    average_completion_time_after_ai_days: float = 0
    previous_12_month_completion_time_avg_days: float = 0
    bugs_before_ai: float = 0
    bugs_after_ai: float = 0
    previous_12_month_bugs_avg: float = 0
    estimated_hires_avoided_due_to_ai: float = 0
    monthly_ai_budget: float = 0
    annual_ai_budget: float = 0

    @field_validator(
        "employee_count",
        "monthly_revenue",
        "monthly_burn",
        "cash_runway_months",
        "monthly_ai_spend_total",
        "previous_month_ai_spend",
        "previous_quarter_ai_spend_avg",
        "previous_12_month_ai_spend_total",
        "previous_12_month_ai_spend_avg",
        "monthly_payroll_total",
        "annual_revenue",
        "annual_burn",
        "annual_ai_spend_total",
        "annual_payroll_total",
        "productivity_before_ai",
        "productivity_after_ai",
        "previous_12_month_productivity_avg",
        "average_completion_time_before_ai_days",
        "average_completion_time_after_ai_days",
        "previous_12_month_completion_time_avg_days",
        "bugs_before_ai",
        "bugs_after_ai",
        "previous_12_month_bugs_avg",
        "estimated_hires_avoided_due_to_ai",
        "monthly_ai_budget",
        "annual_ai_budget",
        mode="before",
    )
    @classmethod
    def numeric_default(cls, value: Any) -> float:
        return max(0.0, safe_float(value))


@dataclass(frozen=True)
class AnalyticsResult:
    output: dict[str, Any]
    llm_context: dict[str, Any]


class AnalyticsEngine:
    def analyze(
        self,
        employees: list[EmployeeInput],
        company: CompanyInput,
        llm_content: dict[str, Any] | None = None,
    ) -> AnalyticsResult:
        employee_df = self._employee_dataframe(employees)
        company_metrics = self._company_metrics(company, employee_df)
        rankings = self._rankings(employee_df)
        chart_data = self._chart_data(employee_df, company, company_metrics)
        deterministic_insights = self._insights(employee_df, company, company_metrics)
        deterministic_recommendations = self._recommendations(employee_df, company_metrics)

        llm_content = llm_content or {}
        executive_summary = {
            "overall_ai_roi_score": company_metrics["overall_ai_roi_score"],
            "monthly_ai_spend_total": round_metric(company.monthly_ai_spend_total),
            "annual_ai_spend_total": round_metric(company_metrics["annual_ai_spend_total"]),
            "monthly_ai_spend_growth_percent": company_metrics["monthly_ai_spend_growth_percent"],
            "forecast_next_month_ai_spend": company_metrics["forecast_next_month_ai_spend"],
            "budget_usage_percent": company_metrics["budget_usage_percent"],
            "annual_budget_usage_percent": company_metrics["annual_budget_usage_percent"],
            "ai_spend_growth_vs_previous_12_month_avg_percent": company_metrics[
                "ai_spend_growth_vs_previous_12_month_avg_percent"
            ],
            "annual_ai_spend_to_revenue_percent": company_metrics[
                "annual_ai_spend_to_revenue_percent"
            ],
            "productivity_gain_percent": company_metrics["productivity_gain_percent"],
            "productivity_gain_vs_previous_12_month_avg_percent": company_metrics[
                "productivity_gain_vs_previous_12_month_avg_percent"
            ],
            "completion_time_improvement_percent": company_metrics[
                "completion_time_improvement_percent"
            ],
            "completion_time_improvement_vs_previous_12_month_avg_percent": company_metrics[
                "completion_time_improvement_vs_previous_12_month_avg_percent"
            ],
            "bugs_reduction_percent": company_metrics["bugs_reduction_percent"],
            "bugs_reduction_vs_previous_12_month_avg_percent": company_metrics[
                "bugs_reduction_vs_previous_12_month_avg_percent"
            ],
            "verdict": llm_content.get("verdict") or self._default_verdict(company_metrics),
            "main_recommendation": llm_content.get("main_recommendation")
            or self._default_main_recommendation(employee_df),
        }

        output = {
            "executive_summary": executive_summary,
            "employee_metrics": self._employee_records(employee_df, llm_content),
            "analysis_sections": self._analysis_sections(employee_df, company_metrics),
            "rankings": rankings,
            "chart_data": chart_data,
            "insights": llm_content.get("insights") or deterministic_insights,
            "recommendations": llm_content.get("recommendations")
            or deterministic_recommendations,
        }

        return AnalyticsResult(output=output, llm_context=self._llm_context(employee_df, company, company_metrics, rankings))

    def _employee_dataframe(self, employees: list[EmployeeInput]) -> pd.DataFrame:
        rows = [employee.model_dump() for employee in employees]
        if not rows:
            rows = [EmployeeInput(name="No employees supplied").model_dump()]
        df = pd.DataFrame(rows)
        numeric_columns = [
            "token_used",
            "tickets_resolved",
            "tickets_reopen",
            "comments_for_clarification",
            "time_to_completion",
            "merge_requests_by_tickets",
            "bugs_closed",
            "story_points",
            "lines_of_codes",
            "merge_requests",
        ]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df.get(column, 0), errors="coerce").fillna(0.0).clip(lower=0.0)

        df["tokens_per_ticket"] = df["token_used"] / df["tickets_resolved"].clip(lower=1)
        df["tokens_per_story_point"] = df["token_used"] / df["story_points"].clip(lower=1)
        df["reopen_rate"] = df["tickets_reopen"] / df["tickets_resolved"].clip(lower=1)
        df["clarification_rate"] = df["comments_for_clarification"] / df["tickets_resolved"].clip(lower=1)
        df["business_output_generated"] = (
            df["tickets_resolved"] * 1.0
            + df["story_points"] * 1.5
            + df["bugs_closed"] * 2.0
            + df["merge_requests"] * 0.8
        )
        df["business_output_per_1k_tokens"] = (
            df["business_output_generated"] / df["token_used"].clip(lower=1) * 1000
        )

        df["productivity_score"] = (
            minmax_score(df["tickets_resolved"]) * 0.35
            + minmax_score(df["story_points"]) * 0.35
            + minmax_score(df["bugs_closed"]) * 0.15
            + minmax_score(df["merge_requests"]) * 0.15
        ).round(0)

        df["quality_score"] = (
            minmax_score(df["reopen_rate"], invert=True) * 0.40
            + minmax_score(df["clarification_rate"], invert=True) * 0.30
            + minmax_score(df["time_to_completion"], invert=True) * 0.30
        ).round(0)

        df["token_efficiency_score"] = (
            minmax_score(df["tokens_per_ticket"], invert=True) * 0.55
            + minmax_score(df["tokens_per_story_point"], invert=True) * 0.45
        ).round(0)
        df["roi_score"] = (
            df["productivity_score"] * 0.45
            + df["quality_score"] * 0.30
            + df["token_efficiency_score"] * 0.25
        ).clip(lower=0, upper=100).round(0)

        df["spend_efficiency"] = (
            (df["tickets_resolved"] + df["story_points"] + df["bugs_closed"] * 2)
            / df["token_used"].clip(lower=1)
            * 100_000
        )
        df["roi_percentile"] = df["roi_score"].rank(pct=True).mul(100).round(0)
        df["token_percentile"] = df["token_used"].rank(pct=True).mul(100).round(0)
        df["is_anomaly"] = self._token_anomaly_flags(df["token_used"])
        df["category"] = df.apply(self._categorize_employee, axis=1)
        df["recommendation"] = df.apply(self._employee_recommendation, axis=1)
        return df

    def _token_anomaly_flags(self, tokens: pd.Series) -> pd.Series:
        if len(tokens) < 4:
            return pd.Series([False] * len(tokens), index=tokens.index)
        q1 = tokens.quantile(0.25)
        q3 = tokens.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return pd.Series([False] * len(tokens), index=tokens.index)
        return tokens > q3 + 1.5 * iqr

    def _categorize_employee(self, row: pd.Series) -> str:
        if row["roi_score"] >= 85 and row["quality_score"] >= 70:
            return "high_roi"
        if row["token_percentile"] <= 40 and row["roi_score"] >= 75:
            return "efficient_user"
        if row["token_percentile"] >= 75 and row["roi_score"] < 60:
            return "overspender"
        if row["quality_score"] < 45 or row["reopen_rate"] > 0.25:
            return "quality_risk"
        if row["token_percentile"] <= 25 and row["productivity_score"] < 45:
            return "low_adoption"
        return "average_user"

    def _employee_recommendation(self, row: pd.Series) -> str:
        category = row["category"]
        if category == "high_roi":
            return "Maintain usage and replicate workflow."
        if category == "efficient_user":
            return "Document workflow and expand adoption carefully."
        if category == "overspender":
            return "Review prompts, tool usage, and token-heavy workflows."
        if category == "quality_risk":
            return "Add quality gates and reduce rework before scaling usage."
        if category == "low_adoption":
            return "Provide onboarding and targeted AI workflow examples."
        return "Monitor usage and coach toward top-performer patterns."

    def _company_metrics(self, company: CompanyInput, df: pd.DataFrame) -> dict[str, float]:
        budget_usage = safe_divide(company.monthly_ai_spend_total, company.monthly_ai_budget) * 100
        monthly_spend_growth = safe_divide(
            company.monthly_ai_spend_total - company.previous_month_ai_spend,
            company.previous_month_ai_spend,
        ) * 100
        smoothed_growth = (
            monthly_spend_growth * 0.60
            + safe_divide(
                company.monthly_ai_spend_total - company.previous_quarter_ai_spend_avg,
                company.previous_quarter_ai_spend_avg,
            )
            * 100
            * 0.40
        )
        forecast_next_month_spend = company.monthly_ai_spend_total * (
            1 + clamp(smoothed_growth, -20, 35) / 100
        )
        annual_ai_spend = company.annual_ai_spend_total or company.monthly_ai_spend_total * 12
        annual_budget = company.annual_ai_budget or company.monthly_ai_budget * 12
        annual_revenue = company.annual_revenue or company.monthly_revenue * 12
        annual_budget_usage = safe_divide(annual_ai_spend, annual_budget) * 100
        spend_growth_vs_12m = safe_divide(
            company.monthly_ai_spend_total - company.previous_12_month_ai_spend_avg,
            company.previous_12_month_ai_spend_avg,
        ) * 100
        annual_ai_spend_to_revenue = safe_divide(annual_ai_spend, annual_revenue) * 100
        productivity_gain = safe_divide(
            company.productivity_after_ai - company.productivity_before_ai,
            company.productivity_before_ai,
        ) * 100
        productivity_gain_vs_12m = safe_divide(
            company.productivity_after_ai - company.previous_12_month_productivity_avg,
            company.previous_12_month_productivity_avg,
        ) * 100
        completion_improvement = safe_divide(
            company.average_completion_time_before_ai_days
            - company.average_completion_time_after_ai_days,
            company.average_completion_time_before_ai_days,
        ) * 100
        completion_improvement_vs_12m = safe_divide(
            company.previous_12_month_completion_time_avg_days
            - company.average_completion_time_after_ai_days,
            company.previous_12_month_completion_time_avg_days,
        ) * 100
        bugs_reduction = safe_divide(company.bugs_before_ai - company.bugs_after_ai, company.bugs_before_ai) * 100
        bugs_reduction_vs_12m = safe_divide(
            company.previous_12_month_bugs_avg - company.bugs_after_ai,
            company.previous_12_month_bugs_avg,
        ) * 100
        avg_employee_roi = float(df["roi_score"].mean()) if len(df) else 0.0
        company_gain_score = clamp(productivity_gain * 1.5 + completion_improvement + bugs_reduction)
        budget_score = clamp(120 - budget_usage) if company.monthly_ai_budget else 50.0
        overall_roi = avg_employee_roi * 0.45 + company_gain_score * 0.40 + budget_score * 0.15
        return {
            "budget_usage_percent": round_metric(budget_usage),
            "monthly_ai_spend_growth_percent": round_metric(monthly_spend_growth),
            "forecast_next_month_ai_spend": round_metric(forecast_next_month_spend),
            "annual_ai_spend_total": round_metric(annual_ai_spend),
            "annual_budget_usage_percent": round_metric(annual_budget_usage),
            "ai_spend_growth_vs_previous_12_month_avg_percent": round_metric(spend_growth_vs_12m),
            "annual_ai_spend_to_revenue_percent": round_metric(annual_ai_spend_to_revenue, 2),
            "productivity_gain_percent": round_metric(productivity_gain),
            "productivity_gain_vs_previous_12_month_avg_percent": round_metric(productivity_gain_vs_12m),
            "completion_time_improvement_percent": round_metric(completion_improvement),
            "completion_time_improvement_vs_previous_12_month_avg_percent": round_metric(
                completion_improvement_vs_12m
            ),
            "bugs_reduction_percent": round_metric(bugs_reduction),
            "bugs_reduction_vs_previous_12_month_avg_percent": round_metric(bugs_reduction_vs_12m),
            "overall_ai_roi_score": int(round(clamp(overall_roi))),
        }

    def _rankings(self, df: pd.DataFrame) -> dict[str, list[str]]:
        top_n = min(3, len(df))
        return {
            "top_roi_users": df.sort_values(["roi_score", "quality_score"], ascending=False)["name"].head(top_n).tolist(),
            "highest_spenders": df.sort_values("token_used", ascending=False)["name"].head(top_n).tolist(),
            "quality_risks": df[df["category"].eq("quality_risk")]
            .sort_values("quality_score")["name"]
            .head(top_n)
            .tolist(),
            "optimization_targets": df[df["category"].isin(["overspender", "quality_risk", "low_adoption"])]
            .sort_values(["roi_score", "token_used"], ascending=[True, False])["name"]
            .head(top_n)
            .tolist(),
        }

    def _chart_data(
        self,
        df: pd.DataFrame,
        company: CompanyInput,
        company_metrics: dict[str, float],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "tokens_by_employee": [
                {"name": row["name"], "tokens_used": int(round(row["token_used"]))}
                for _, row in df.sort_values("token_used", ascending=False).iterrows()
            ],
            "roi_by_employee": [
                {"name": row["name"], "roi_score": int(row["roi_score"])}
                for _, row in df.sort_values("roi_score", ascending=False).iterrows()
            ],
            "tokens_vs_output": [
                {
                    "name": row["name"],
                    "tokens_used": int(round(row["token_used"])),
                    "output_score": int(row["productivity_score"]),
                    "business_output_generated": round_metric(row["business_output_generated"]),
                    "business_output_per_1k_tokens": round_metric(row["business_output_per_1k_tokens"], 2),
                    "roi_score": int(row["roi_score"]),
                }
                for _, row in df.iterrows()
            ],
            "spend_control": [
                {
                    "metric": "previous_month_ai_spend",
                    "value": round_metric(company.previous_month_ai_spend),
                },
                {
                    "metric": "current_month_ai_spend",
                    "value": round_metric(company.monthly_ai_spend_total),
                },
                {
                    "metric": "previous_quarter_ai_spend_avg",
                    "value": round_metric(company.previous_quarter_ai_spend_avg),
                },
                {
                    "metric": "monthly_ai_budget",
                    "value": round_metric(company.monthly_ai_budget),
                },
                {
                    "metric": "monthly_ai_spend_growth_percent",
                    "value": company_metrics["monthly_ai_spend_growth_percent"],
                },
                {
                    "metric": "budget_usage_percent",
                    "value": company_metrics["budget_usage_percent"],
                },
                {
                    "metric": "forecast_next_month_ai_spend",
                    "value": company_metrics["forecast_next_month_ai_spend"],
                },
            ],
            "before_after_company": [
                {
                    "metric": "productivity",
                    "before": round_metric(company.productivity_before_ai),
                    "after": round_metric(company.productivity_after_ai),
                },
                {
                    "metric": "completion_time_days",
                    "before": round_metric(company.average_completion_time_before_ai_days),
                    "after": round_metric(company.average_completion_time_after_ai_days),
                },
                {
                    "metric": "bugs",
                    "before": round_metric(company.bugs_before_ai),
                    "after": round_metric(company.bugs_after_ai),
                },
            ],
            "annual_company": [
                {
                    "metric": "revenue",
                    "value": round_metric(company.annual_revenue or company.monthly_revenue * 12),
                },
                {
                    "metric": "burn",
                    "value": round_metric(company.annual_burn or company.monthly_burn * 12),
                },
                {
                    "metric": "ai_spend",
                    "value": round_metric(company.annual_ai_spend_total or company.monthly_ai_spend_total * 12),
                },
                {
                    "metric": "payroll",
                    "value": round_metric(company.annual_payroll_total or company.monthly_payroll_total * 12),
                },
            ],
            "previous_12_month_baseline": [
                {
                    "metric": "ai_spend_avg",
                    "value": round_metric(company.previous_12_month_ai_spend_avg),
                },
                {
                    "metric": "productivity_avg",
                    "value": round_metric(company.previous_12_month_productivity_avg),
                },
                {
                    "metric": "completion_time_avg_days",
                    "value": round_metric(company.previous_12_month_completion_time_avg_days),
                },
                {
                    "metric": "bugs_avg",
                    "value": round_metric(company.previous_12_month_bugs_avg),
                },
            ],
        }

    def _insights(
        self,
        df: pd.DataFrame,
        company: CompanyInput,
        company_metrics: dict[str, float],
    ) -> list[dict[str, str]]:
        insights: list[dict[str, str]] = []
        top_count = max(1, int(round(len(df) * 0.2)))
        value_total = float((df["roi_score"] * df["token_efficiency_score"]).sum())
        top_value = float((df.nlargest(top_count, "roi_score")["roi_score"] * df.nlargest(top_count, "roi_score")["token_efficiency_score"]).sum())
        top_share = safe_divide(top_value, value_total) * 100
        insights.append(
            {
                "severity": "high" if top_share >= 50 else "medium",
                "message": f"Top 20% of users generate {round_metric(top_share)}% of measured AI value.",
            }
        )

        anomaly_names = df[df["is_anomaly"]]["name"].tolist()
        if anomaly_names:
            insights.append(
                {
                    "severity": "high",
                    "message": f"Abnormal token usage detected for {', '.join(anomaly_names)}.",
                }
            )

        if company_metrics["budget_usage_percent"] > 90:
            insights.append(
                {
                    "severity": "medium",
                    "message": "AI spend is close to or above the monthly budget threshold.",
                }
            )
        elif company.monthly_ai_budget:
            remaining = company.monthly_ai_budget - company.monthly_ai_spend_total
            insights.append(
                {
                    "severity": "low",
                    "message": f"AI budget has {round_metric(max(0, remaining))} remaining this month.",
                }
            )
        return insights

    def _recommendations(
        self,
        df: pd.DataFrame,
        company_metrics: dict[str, float],
    ) -> list[dict[str, Any]]:
        targets = df[df["category"].isin(["overspender", "quality_risk", "low_adoption"])]
        potential_savings = self._estimated_savings(df)
        recommendations = [
            {
                "priority": 1,
                "action": "Coach low ROI users using top performer workflows.",
                "impact": f"Estimated +{max(5, int(round((100 - mean(df['roi_score'].tolist())) / 3)))}% ROI",
            }
        ]
        if not targets.empty:
            recommendations.append(
                {
                    "priority": 2,
                    "action": "Review token-heavy workflows for optimization targets.",
                    "impact": f"Estimated monthly savings opportunity: {round_metric(potential_savings)}",
                }
            )
        if company_metrics["budget_usage_percent"] > 85:
            recommendations.append(
                {
                    "priority": 3,
                    "action": "Set team-level token budgets and alert thresholds.",
                    "impact": "Improves spend predictability before budget overrun.",
                }
            )
        premium_cut_targets = df[
            (df["token_percentile"] >= 80)
            & (df["roi_score"] < df["roi_score"].median())
        ]
        if not premium_cut_targets.empty:
            recommendations.append(
                {
                    "priority": len(recommendations) + 1,
                    "action": "Cut or downgrade unused premium usage for persistent low ROI high spenders.",
                    "impact": "Reduces avoidable token cost without limiting top performers.",
                }
            )
        return recommendations

    def _estimated_savings(self, df: pd.DataFrame) -> float:
        if df.empty:
            return 0.0
        efficient_threshold = df["tokens_per_story_point"].quantile(0.25)
        inefficient = df[df["tokens_per_story_point"] > df["tokens_per_story_point"].quantile(0.75)]
        excess_tokens = (
            inefficient["tokens_per_story_point"] - efficient_threshold
        ).clip(lower=0) * inefficient["story_points"].clip(lower=1)
        # Conservative blended public API estimate. Can be replaced with actual vendor billing.
        estimated_cost_per_1k_tokens = 0.01
        return float(excess_tokens.sum() / 1000 * estimated_cost_per_1k_tokens)

    def _employee_records(self, df: pd.DataFrame, llm_content: dict[str, Any]) -> list[dict[str, Any]]:
        llm_recommendations = llm_content.get("employee_recommendations", {})
        records: list[dict[str, Any]] = []
        for _, row in df.sort_values("roi_score", ascending=False).iterrows():
            records.append(
                {
                    "name": row["name"],
                    "tokens_used": int(round(row["token_used"])),
                    "roi_score": int(row["roi_score"]),
                    "productivity_score": int(row["productivity_score"]),
                    "quality_score": int(row["quality_score"]),
                    "business_output_generated": round_metric(row["business_output_generated"]),
                    "business_output_per_1k_tokens": round_metric(row["business_output_per_1k_tokens"], 2),
                    "tokens_per_ticket": int(round(row["tokens_per_ticket"])),
                    "tokens_per_story_point": int(round(row["tokens_per_story_point"])),
                    "reopen_rate": round_metric(row["reopen_rate"]),
                    "clarification_rate": round_metric(row["clarification_rate"]),
                    "roi_percentile": int(row["roi_percentile"]),
                    "token_percentile": int(row["token_percentile"]),
                    "is_token_anomaly": bool(row["is_anomaly"]),
                    "category": row["category"],
                    "recommendation": llm_recommendations.get(row["name"], row["recommendation"]),
                }
            )
        return records

    def _analysis_sections(self, df: pd.DataFrame, company_metrics: dict[str, float]) -> dict[str, Any]:
        return {
            "cost_efficiency": {
                "metrics": [
                    "tokens_per_ticket",
                    "tokens_per_story_point",
                    "business_output_per_1k_tokens",
                ],
                "best_users": df.sort_values("business_output_per_1k_tokens", ascending=False)["name"]
                .head(3)
                .tolist(),
                "worst_users": df.sort_values("business_output_per_1k_tokens")["name"].head(3).tolist(),
            },
            "productivity_score": {
                "based_on": ["tickets_resolved", "story_points", "bugs_closed", "merge_requests"],
                "top_users": df.sort_values("productivity_score", ascending=False)["name"].head(3).tolist(),
            },
            "quality_score": {
                "based_on": ["reopen_rate", "clarification_rate", "completion_speed"],
                "quality_risks": df[df["category"].eq("quality_risk")]["name"].tolist(),
            },
            "roi_score": {
                "estimate": "business_output_generated / token_spend, blended with quality and productivity scores",
                "top_users": df.sort_values("roi_score", ascending=False)["name"].head(3).tolist(),
                "waste_users": df[df["category"].isin(["overspender", "quality_risk"])]
                .sort_values("roi_score")["name"]
                .head(5)
                .tolist(),
            },
            "company_level_analysis": {
                "spend_control": {
                    "monthly_growth_in_ai_spend_percent": company_metrics[
                        "monthly_ai_spend_growth_percent"
                    ],
                    "budget_usage_percent": company_metrics["budget_usage_percent"],
                    "forecast_next_month_spend": company_metrics["forecast_next_month_ai_spend"],
                },
                "performance_impact": {
                    "productivity_gain_percent": company_metrics["productivity_gain_percent"],
                    "bugs_reduction_percent": company_metrics["bugs_reduction_percent"],
                    "completion_speed_improvement_percent": company_metrics[
                        "completion_time_improvement_percent"
                    ],
                },
                "strategic_roi": {
                    "is_ai_spend_justified": company_metrics["overall_ai_roi_score"] >= 70,
                    "overall_ai_roi_score": company_metrics["overall_ai_roi_score"],
                    "value_creators": df.sort_values("roi_score", ascending=False)["name"].head(5).tolist(),
                    "waste_sources": df[df["category"].isin(["overspender", "low_adoption"])]
                    .sort_values(["roi_score", "token_used"], ascending=[True, False])["name"]
                    .head(5)
                    .tolist(),
                },
            },
        }

    def _default_verdict(self, company_metrics: dict[str, float]) -> str:
        score = company_metrics["overall_ai_roi_score"]
        if score >= 75:
            return "AI spend is financially justified, but targeted controls are needed to reduce waste."
        if score >= 55:
            return "AI spend has partial ROI and requires finance-led optimization before scaling."
        return "AI spend is not financially justified at current efficiency levels."

    def _default_main_recommendation(self, df: pd.DataFrame) -> str:
        low_share = safe_divide(len(df[df["roi_score"] < 60]), len(df)) * 100
        if low_share >= 15:
            return "Keep the AI budget, but cap and remediate low-ROI usage before increasing spend."
        return "Maintain current spend and scale proven high-ROI workflows with monthly finance review."

    def _llm_context(
        self,
        df: pd.DataFrame,
        company: CompanyInput,
        company_metrics: dict[str, float],
        rankings: dict[str, list[str]],
    ) -> dict[str, Any]:
        top_decile_count = max(1, int(round(len(df) * 0.1)))
        top_efficiency = float(df.nlargest(top_decile_count, "spend_efficiency")["spend_efficiency"].mean())
        bottom_efficiency = float(df.nsmallest(top_decile_count, "spend_efficiency")["spend_efficiency"].mean())
        return {
            "company": company.model_dump(),
            "company_metrics": company_metrics,
            "rankings": rankings,
            "category_counts": df["category"].value_counts().to_dict(),
            "top_10_vs_bottom_10_spend_efficiency": {
                "top_10_percent_avg": round_metric(top_efficiency),
                "bottom_10_percent_avg": round_metric(bottom_efficiency),
                "multiple": round_metric(safe_divide(top_efficiency, bottom_efficiency), 2),
            },
            "employees": [
                {
                    "name": row["name"],
                    "tokens_used": int(row["token_used"]),
                    "roi_score": int(row["roi_score"]),
                    "productivity_score": int(row["productivity_score"]),
                    "quality_score": int(row["quality_score"]),
                    "category": row["category"],
                    "is_token_anomaly": bool(row["is_anomaly"]),
                }
                for _, row in df.sort_values("roi_score", ascending=False).iterrows()
            ],
        }
