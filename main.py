from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from analytics import (
    AnalyticsEngine,
    CompanyInput,
    EmployeeInput,
    EmployeeProfileInput,
    FeatureInput,
    ModelUsageInput,
)
from forecast import ForecastEngine
from llm_engine import LLMEngine
from report_generator import ReportGenerator


def load_employees(path: Path) -> list[EmployeeInput]:
    employees: list[EmployeeInput] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
                employees.append(EmployeeInput.model_validate(raw))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValueError(f"Invalid employee JSONL at line {line_number}: {exc}") from exc
    return employees


def load_jsonl_model(path: Path | None, model: type[Any], label: str) -> list[Any]:
    if path is None:
        return []
    records: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(model.model_validate(json.loads(stripped)))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValueError(f"Invalid {label} JSONL at line {line_number}: {exc}") from exc
    return records


def load_company(path: Path) -> CompanyInput:
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return CompanyInput.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Invalid company JSON: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze whether AI token spend is profitable compared to employee ROI."
    )
    parser.add_argument("--employees", required=True, type=Path, help="Path to employees.jsonl")
    parser.add_argument("--company", required=True, type=Path, help="Path to company.json")
    parser.add_argument("--employee-profiles", type=Path, help="Optional path to employee_profiles.jsonl")
    parser.add_argument("--model-usage", type=Path, help="Optional path to model_usage.jsonl")
    parser.add_argument("--features", type=Path, help="Optional path to features.jsonl")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM-generated narrative fields even when OPENAI_API_KEY is set.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output for local debugging.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output.json"),
        help="Path where the JSON result is written. Defaults to output.json.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("generated_report"),
        help="Directory where frontend-ready report JSON files are written.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        employees = load_employees(args.employees)
        company = load_company(args.company)
        employee_profiles = load_jsonl_model(
            args.employee_profiles,
            EmployeeProfileInput,
            "employee profile",
        )
        model_usage = load_jsonl_model(args.model_usage, ModelUsageInput, "model usage")
        features = load_jsonl_model(args.features, FeatureInput, "feature")

        engine = AnalyticsEngine()
        deterministic = engine.analyze(
            employees=employees,
            company=company,
            employee_profiles=employee_profiles,
            model_usage=model_usage,
            features=features,
        )

        llm_content = {}
        if not args.no_llm:
            try:
                llm_content = LLMEngine().generate(deterministic.llm_context)
            except Exception:
                llm_content = {}

        result = engine.analyze(
            employees=employees,
            company=company,
            employee_profiles=employee_profiles,
            model_usage=model_usage,
            features=features,
            llm_content=llm_content,
        ).output

        indent = 2 if args.pretty else None
        json_output = json.dumps(result, ensure_ascii=False, indent=indent)
        args.output.write_text(json_output + "\n", encoding="utf-8")
        forecast = ForecastEngine().build(
            analytics_output=result,
            company=company,
            llm_content=llm_content,
        )
        ReportGenerator().write(
            report_dir=args.report_dir,
            analytics_output=result,
            forecast=forecast,
            llm_content=llm_content,
            pretty=True,
        )
        print(json_output)
        return 0
    except Exception as exc:
        error_output = {"error": str(exc)}
        print(json.dumps(error_output), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
