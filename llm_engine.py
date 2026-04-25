from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


class Insight(BaseModel):
    severity: str = "medium"
    message: str

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: Any) -> str:
        normalized = str(value or "medium").lower()
        return normalized if normalized in {"low", "medium", "high"} else "medium"


class Recommendation(BaseModel):
    priority: int
    action: str
    impact: str


class ActionPlanItem(BaseModel):
    priority: int
    title: str
    owner: str
    timeframe: str
    action: str
    expected_effect: str
    productivity_lift_percent: float = Field(default=0, ge=0, le=30)
    ai_spend_reduction_percent: float = Field(default=0, ge=0, le=50)
    bug_reduction_percent: float = Field(default=0, ge=0, le=30)

    @field_validator(
        "productivity_lift_percent",
        "ai_spend_reduction_percent",
        "bug_reduction_percent",
        mode="before",
    )
    @classmethod
    def numeric_default(cls, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


class ForecastAssumption(BaseModel):
    name: str
    value: float
    unit: str
    rationale: str


class IssueCard(BaseModel):
    id: str
    headline: str
    efficiency_impact: str = "medium"
    financial_impact: dict[str, Any] = Field(default_factory=dict)
    problem_details: dict[str, Any] = Field(default_factory=dict)
    recommended_solution: dict[str, Any] = Field(default_factory=dict)

    @field_validator("efficiency_impact", mode="before")
    @classmethod
    def normalize_impact(cls, value: Any) -> str:
        normalized = str(value or "medium").lower()
        return normalized if normalized in {"low", "medium", "high"} else "medium"


class LLMAnalyticsContent(BaseModel):
    verdict: str
    main_recommendation: str
    situation_status: str = "partially_reasoned"
    executive_brief: list[str] = Field(default_factory=list)
    diagnosis: list[Insight] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    action_plan: list[ActionPlanItem] = Field(default_factory=list)
    forecast_assumptions: list[ForecastAssumption] = Field(default_factory=list)
    issue_cards: list[IssueCard] = Field(default_factory=list)
    employee_recommendations: dict[str, str] = Field(default_factory=dict)

    @field_validator("situation_status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> str:
        normalized = str(value or "partially_reasoned").lower()
        allowed = {
            "reasoned_and_justified",
            "partially_reasoned",
            "unreasonable_spend",
            "insufficient_data",
        }
        return normalized if normalized in allowed else "partially_reasoned"


class GeminiAPIError(RuntimeError):
    pass


class LLMEngine:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.provider = (
            provider
            or os.getenv("LLM_PROVIDER")
            or ("openai" if os.getenv("OPENAI_API_KEY") else "gemini")
        ).lower()
        if self.provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1")
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        else:
            self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            self.base_url = (
                base_url
                or os.getenv("GEMINI_BASE_URL")
                or "https://generativelanguage.googleapis.com/v1beta"
            ).rstrip("/")
        self.temperature = temperature

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def generate(self, analytics_context: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {}
        schema = LLMAnalyticsContent.model_json_schema()
        prompt = {
            "task": (
                "Generate concise CFO-ready analytics content for an AI token ROI dashboard. "
                "The audience is finance leadership and budget owners."
            ),
            "rules": [
                "Return JSON only.",
                "Do not invent numeric metrics that are not supported by the context.",
                "You may propose forecast assumptions, but they must be conservative and explicitly justified.",
                "Keep wording clear, concise, financial, and decision-oriented.",
                "Focus on spend justification, budget risk, value creation, waste sources, and next financial controls.",
                "Use comparative metrics by model, employee background, and feature when available.",
                "Issue cards must be clickable-card ready: one short headline, efficiency_impact low/medium/high, financial details, problem details, and recommended solution.",
                "Recommendations must tell finance leaders what decision to make, who should own it, and what impact to expect.",
                "Employee recommendations should be one sentence per relevant employee.",
                "Action plan items must include numeric expected effects for deterministic forecast calculation.",
            ],
            "required_schema": schema,
            "analytics_context": analytics_context,
        }

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a CFO-grade analytics strategist. "
                            "Output valid JSON only, matching the requested schema."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(prompt, ensure_ascii=False)}],
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
            },
        }

        content = (
            self._generate_openai_content(prompt)
            if self.provider == "openai"
            else self._generate_content(payload)
        )
        try:
            parsed = json.loads(content)
            return LLMAnalyticsContent.model_validate(parsed).model_dump()
        except (json.JSONDecodeError, ValidationError):
            return {}

    def _generate_content(self, payload: dict[str, Any]) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key or "",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GeminiAPIError(f"Gemini request failed: {exc}") from exc

        candidates = response_payload.get("candidates", [])
        if not candidates:
            return "{}"
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts) or "{}"

    def _generate_openai_content(self, prompt: dict[str, Any]) -> str:
        url = f"{self.base_url}/responses"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a CFO-grade analytics strategist. "
                        "Output valid JSON only, matching the requested schema."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "text": {"format": {"type": "json_object"}},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key or ''}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GeminiAPIError(f"OpenAI request failed: {exc}") from exc

        output_text = response_payload.get("output_text")
        if output_text:
            return output_text
        chunks: list[str] = []
        for item in response_payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    chunks.append(text)
        return "".join(chunks) or "{}"
