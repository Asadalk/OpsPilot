import json
from typing import Any, Protocol

from app.agent.schemas import AgentDecision, AgentState
from app.core.config import settings


class DecisionProvider(Protocol):
    async def decide(self, state: AgentState, tool_descriptions: list[dict[str, Any]]) -> AgentDecision:
        ...


class GeminiDecisionProvider:
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["call_tool", "diagnose"]},
            "tool_name": {"type": "STRING"},
            "arguments": {"type": "OBJECT"},
            "service": {"type": "STRING"},
            "severity": {"type": "STRING"},
            "hypotheses": {"type": "ARRAY", "items": {"type": "STRING"}},
            "diagnosis": {"type": "STRING"},
            "proposed_action": {"type": "STRING"},
        },
        "required": ["action", "arguments", "hypotheses"],
    }

    def __init__(self, model: str = settings.gemini_model):
        self.model = model

    async def decide(self, state: AgentState, tool_descriptions: list[dict[str, Any]]) -> AgentDecision:
        if not settings.gemini_api_key.strip():
            raise RuntimeError("GEMINI_API_KEY is missing in backend/.env")
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=settings.gemini_timeout_seconds * 1000),
        )
        prompt = (
            "You are a controlled operations investigator. Choose exactly one registered read-only tool "
            "or finish with a concise evidence-backed diagnosis. Never propose execution or arbitrary access. "
            "Do not provide chain-of-thought; return only the structured decision.\n\n"
            f"USER REQUEST:\n{state.user_request}\n\n"
            f"OBSERVED EVIDENCE:\n{json.dumps(state.evidence, default=str)}\n\n"
            f"RETRIEVED KNOWLEDGE:\n{json.dumps([item.model_dump(mode='json') for item in state.knowledge])}\n\n"
            f"AVAILABLE TOOLS:\n{json.dumps(tool_descriptions)}\n\n"
            "Use arguments matching the selected tool schema. A diagnose decision must include diagnosis and "
            "may include proposed_action as a recommendation only. Cite supporting knowledge using a Sources "
            "section with numbered source filenames; knowledge is context, not unquestionable authority."
        )
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": self.response_schema},
        )
        return AgentDecision.model_validate(json.loads(response.text or "{}"))