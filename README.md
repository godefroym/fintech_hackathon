# AI Token ROI Analytics Engine

This module analyzes whether AI token spend is financially justified compared with employee output, delivery quality, model usage, employee background, and shipped feature value.

The target readers are CFOs, finance teams, and budget owners. The output is designed to feed a frontend dashboard with concise financial summaries, clickable issue cards, and action-oriented recommendations.

## Repository Structure

```txt
.
├── main.py
├── analytics.py
├── forecast.py
├── llm_engine.py
├── report_generator.py
├── requirements.txt
├── inputs/
│   ├── input_example.json
│   ├── company.json
│   ├── employees.jsonl
│   ├── employee_profiles.jsonl
│   ├── model_usage.jsonl
│   └── features.jsonl
└── outputs/
    ├── index.json
    ├── output.json
    ├── dashboard_data.json
    ├── executive_report.json
    ├── forecast_scenarios.json
    ├── action_plan.json
    ├── issue_cards.json
    └── comparative_analysis.json
```

## What The Engine Answers

The engine is built around finance-oriented questions:

- Is AI spend financially justified?
- Which users create the most value from AI?
- Which users consume too many tokens for weak output?
- Which models cost the most, and which models are most efficient by use case?
- Does employee seniority or skill level explain token efficiency?
- Which features justify premium AI usage?
- Which features show high token usage with weak estimated business value?
- What happens over 12 months if we do nothing versus applying the action plan?

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Input Contract

See [inputs/input_example.json](inputs/input_example.json) for the complete input contract, field definitions, join keys, and example records.

Required input files:

| File | Format | Purpose |
| --- | --- | --- |
| `inputs/company.json` | JSON object | Company-level revenue, burn, payroll, AI budget, productivity, completion speed, and bugs. |
| `inputs/employees.jsonl` | JSON Lines | Employee-level token usage, productivity, and quality metrics. |
| `inputs/employee_profiles.jsonl` | JSON Lines | Employee seniority, years of experience, role, skill, skill level, and business unit. |
| `inputs/model_usage.jsonl` | JSON Lines | Token usage and estimated cost by employee, provider, model, and use case. |
| `inputs/features.jsonl` | JSON Lines | Token usage and estimated business value by shipped feature. |

Join keys:

| Relationship | Join |
| --- | --- |
| Employee metrics to profiles | `employees.name = employee_profiles.name` |
| Employee metrics to model usage | `employees.name = model_usage.employee_name` |
| Employee metrics to features | `employees.name = features.owner` |

## Run

Deterministic run without LLM:

```bash
python main.py \
  --employees inputs/employees.jsonl \
  --company inputs/company.json \
  --employee-profiles inputs/employee_profiles.jsonl \
  --model-usage inputs/model_usage.jsonl \
  --features inputs/features.jsonl \
  --no-llm \
  --output outputs/output.json \
  --report-dir outputs
```

Run with OpenAI:

```bash
export LLM_PROVIDER="openai"
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4.1"

python main.py \
  --employees inputs/employees.jsonl \
  --company inputs/company.json \
  --employee-profiles inputs/employee_profiles.jsonl \
  --model-usage inputs/model_usage.jsonl \
  --features inputs/features.jsonl \
  --output outputs/output.json \
  --report-dir outputs
```

Run with Gemini:

```bash
export LLM_PROVIDER="gemini"
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-2.5-flash"

python main.py \
  --employees inputs/employees.jsonl \
  --company inputs/company.json \
  --employee-profiles inputs/employee_profiles.jsonl \
  --model-usage inputs/model_usage.jsonl \
  --features inputs/features.jsonl \
  --output outputs/output.json \
  --report-dir outputs
```

If no API key is available, use `--no-llm`. The engine still returns valid JSON using deterministic fallback content.

## Core Outputs

The frontend should start from `outputs/index.json`.

| File | Purpose |
| --- | --- |
| `outputs/output.json` | Full analytics object. Useful for debugging or full dashboard hydration. |
| `outputs/dashboard_data.json` | Summary cards, charts, rankings, issue cards, and comparative analysis for dashboard pages. |
| `outputs/executive_report.json` | CFO-facing report: decision summary, financial situation, diagnosis, risk level, issue cards, action plan, and assumptions. |
| `outputs/issue_cards.json` | Clickable problem cards for the UI. Each card has a one-line issue, impact level, details, and solution. |
| `outputs/comparative_analysis.json` | Model efficiency, employee background efficiency, and feature efficiency. |
| `outputs/forecast_scenarios.json` | 12-month forecast comparing `baseline_no_action` and `with_action_plan`. |
| `outputs/action_plan.json` | Recommended actions with owner, timeframe, and expected effect. |

## CFO Issue Card Format

`outputs/issue_cards.json` is intended for expandable frontend cards.

Each card follows this structure:

```json
{
  "id": "overspender_concentration",
  "headline": "Overspenders consume 42.2% of employee tokens while producing weak ROI.",
  "efficiency_impact": "high",
  "financial_impact": {
    "tokens_at_risk": 1634000,
    "estimated_monthly_savings": 13.1
  },
  "problem_details": {
    "affected_users": ["Yanis Mercier", "Nathan Colin"],
    "why_it_matters": "High consumption with low measured output is the clearest finance control opportunity."
  },
  "recommended_solution": {
    "action": "Set spend caps for low-ROI high spenders and require manager review before premium usage is expanded.",
    "owner": "Finance and Engineering Managers",
    "timeframe": "30 days"
  }
}
```

`efficiency_impact` means how much fixing the issue is expected to matter:

- `high`: likely to materially improve cost efficiency or ROI.
- `medium`: meaningful control or optimization opportunity.
- `low`: useful context, but not a priority finance action.

## Metrics Computed

Employee metrics:

- `tokens_per_ticket`
- `tokens_per_story_point`
- `business_output_generated`
- `business_output_per_1k_tokens`
- `reopen_rate`
- `clarification_rate`
- `productivity_score`
- `quality_score`
- `roi_score`
- `roi_percentile`
- `token_percentile`
- `category`

Company metrics:

- `monthly_ai_spend_growth_percent`
- `budget_usage_percent`
- `forecast_next_month_ai_spend`
- `productivity_gain_percent`
- `completion_time_improvement_percent`
- `bugs_reduction_percent`
- `annual_ai_spend_to_revenue_percent`
- `overall_ai_roi_score`

Comparative analysis:

- Tokens and cost by provider and model.
- ROI proxy by model.
- Best model by use case.
- Tokens and ROI by seniority level.
- Tokens and ROI by skill and skill level.
- Tokens, AI cost, and value per feature.
- High-value features and waste-risk features.

## Design Principle

The engine does not ask the LLM to invent numbers.

Python computes the metrics, classifications, issue cards, and forecasts from structured inputs. The LLM is used as a CFO-grade analyst to make the report clearer: summary, diagnosis, action plan, recommendations, and conservative assumptions.

This keeps the financial report auditable while still making AI central to the executive analysis.
