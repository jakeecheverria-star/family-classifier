"""Ask Claude to classify the rows that no office rule covers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Protocol

from .io import FamilyRow
from .uniclass import UniclassItem

PROMPT_PATH = Path(__file__).parent / "prompts" / "classify.md"
DEFAULT_MODEL = os.environ.get("FAMILY_CLASSIFIER_MODEL", "claude-sonnet-5-5")
CONFIDENCE_LEVELS = ("high", "medium", "low")


class Completer(Protocol):
    """Anything that turns a prompt into text. Tests use a fake."""

    def __call__(self, prompt: str) -> str: ...


class AnthropicCompleter:
    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 4096):
        import anthropic  # Imported here so offline runs and tests don't need it.

        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def __call__(self, prompt: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if block.type == "text")


class AzureOpenAICompleter:
    """Azure OpenAI, for organizations that approve Microsoft-hosted models only.

    Reads AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_API_VERSION.
    `model` is the name of your Azure deployment, not the base model name.
    """

    def __init__(self, model: str, max_tokens: int = 4096):
        from openai import AzureOpenAI  # Optional dependency: pip install openai

        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
        self.model = model
        self.max_tokens = max_tokens

    def __call__(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


PROVIDERS = {"anthropic": AnthropicCompleter, "azure-openai": AzureOpenAICompleter}


def make_completer(provider: str, model: str) -> Completer:
    """Create the completer for a provider name, such as 'anthropic' or 'azure-openai'."""
    try:
        cls = PROVIDERS[provider]
    except KeyError:
        raise ValueError(f"unknown provider {provider!r}; choose from {', '.join(PROVIDERS)}") from None
    return cls(model=model)


def build_prompt(
    rows: list[FamilyRow],
    candidates: list[list[UniclassItem]],
    default_ifc: list[str],
    abbreviations: dict[str, str],
) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    abbrev_text = "\n".join(f"- {k}: {v}" for k, v in abbreviations.items()) or "- (none)"
    blocks = []
    for i, (row, cands, ifc) in enumerate(zip(rows, candidates, default_ifc)):
        cand_text = "\n".join(f"    {c.code}  {c.title}" for c in cands) or "    (no candidates)"
        blocks.append(f"[{i}] {row.describe()}\n  default IFC entity: {ifc}\n  candidates:\n{cand_text}")
    return template.format(abbreviations=abbrev_text, rows="\n\n".join(blocks))


def parse_response(text: str, count: int) -> list[dict]:
    """Pull the JSON array out of the reply and index it by row.

    Missing rows come back as empty dicts, so one bad row never loses a batch.
    """
    match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if not match:
        return [{} for _ in range(count)]
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [{} for _ in range(count)]
    by_id: dict[int, dict] = {}
    for position, item in enumerate(items):
        if isinstance(item, dict):
            key = item.get("id", position)
            if isinstance(key, int):
                by_id[key] = item
    return [by_id.get(i, {}) for i in range(count)]
