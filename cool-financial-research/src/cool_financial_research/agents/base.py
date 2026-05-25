from __future__ import annotations

import json
from typing import Any, Generic, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class AgentRuntimeError(RuntimeError):
    pass


class OpenAIJsonAgent(Generic[T]):
    """Thin wrapper around the OpenAI Responses API with strict JSON outputs.

    Each stage is modeled as a separate local "agent" by using a distinct prompt, model,
    schema, and contextual input. This keeps the workflow deterministic and debuggable while
    still letting the model reason deeply within each stage.
    """

    def __init__(self, model: str, output_model: type[T], client: "OpenAI | None" = None) -> None:
        self.model = model
        self.output_model = output_model
        if client is not None:
            self.client = client
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise AgentRuntimeError(
                    "The openai package is required to run agents. Install dependencies with `pip install -e .`."
                ) from exc
            self.client = OpenAI()

    def run(self, *, instructions: str, user_input: str, reasoning_effort: str = "high") -> T:
        schema = self.output_model.model_json_schema()
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=user_input,
                reasoning={"effort": reasoning_effort},
                tools=[{"type": "web_search_preview"}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": self.output_model.__name__,
                        "schema": schema,
                        "strict": True,
                    }
                },
            )  # type: ignore[call-overload]
        except Exception as exc:  # noqa: BLE001 - surface API context cleanly to CLI
            raise AgentRuntimeError(f"OpenAI call failed for model {self.model}: {exc}") from exc

        raw = getattr(response, "output_text", None)
        if not raw:
            # Responses SDKs have changed field shapes over time; keep a defensive fallback.
            raw = _extract_text_response(response)
        try:
            payload = json.loads(raw)
            return self.output_model.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AgentRuntimeError(f"Model returned invalid structured output: {exc}\nRaw: {raw[:2000]}") from exc


def _extract_text_response(response: Any) -> str:
    if hasattr(response, "model_dump"):
        dumped = response.model_dump()
    else:
        dumped = response if isinstance(response, dict) else {}
    chunks: list[str] = []
    for item in dumped.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if text:
                chunks.append(text)
    if not chunks:
        raise AgentRuntimeError("Could not find text output in OpenAI response.")
    return "\n".join(chunks)
