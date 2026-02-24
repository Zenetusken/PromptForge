"""Static model catalog — pure data, no provider imports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    """Metadata for a single LLM model."""

    id: str
    name: str
    description: str
    context_window: int
    tier: str  # "performance" | "cost-effective"
    capabilities: frozenset[str] = frozenset({"text"})


# --- Claude models (shared by claude-cli and anthropic) ---
_CLAUDE_CAPS = frozenset({"text", "vision", "json_mode", "prompt_caching"})
_CLAUDE_OPUS_4_6 = ModelInfo(
    id="claude-opus-4-6",
    name="Claude Opus 4.6",
    description="Most intelligent, best for complex reasoning and coding",
    context_window=200_000,
    tier="performance",
    capabilities=_CLAUDE_CAPS,
)
_CLAUDE_HAIKU_4_5 = ModelInfo(
    id="claude-haiku-4-5",
    name="Claude Haiku 4.5",
    description="Fast and affordable, near-frontier intelligence",
    context_window=200_000,
    tier="cost-effective",
    capabilities=_CLAUDE_CAPS,
)

# --- OpenAI models ---
_OPENAI_CAPS = frozenset({"text", "vision", "json_mode", "function_calling"})
_GPT_4_1 = ModelInfo(
    id="gpt-4.1",
    name="GPT-4.1",
    description="Latest flagship, 1M context, optimized for coding",
    context_window=1_000_000,
    tier="performance",
    capabilities=_OPENAI_CAPS,
)
_GPT_4_1_MINI = ModelInfo(
    id="gpt-4.1-mini",
    name="GPT-4.1 Mini",
    description="Fast and affordable, 1M context",
    context_window=1_000_000,
    tier="cost-effective",
    capabilities=_OPENAI_CAPS,
)

# --- Gemini models ---
_GEMINI_CAPS = frozenset({"text", "vision", "json_mode"})
_GEMINI_2_5_PRO = ModelInfo(
    id="gemini-2.5-pro",
    name="Gemini 2.5 Pro",
    description="Advanced reasoning, 1M context, best stable model",
    context_window=1_000_000,
    tier="performance",
    capabilities=_GEMINI_CAPS,
)
_GEMINI_2_5_FLASH = ModelInfo(
    id="gemini-2.5-flash",
    name="Gemini 2.5 Flash",
    description="Fast reasoning at low cost, 1M context",
    context_window=1_000_000,
    tier="cost-effective",
    capabilities=_GEMINI_CAPS,
)

MODEL_CATALOG: dict[str, list[ModelInfo]] = {
    "claude-cli": [_CLAUDE_OPUS_4_6, _CLAUDE_HAIKU_4_5],
    "anthropic": [_CLAUDE_OPUS_4_6, _CLAUDE_HAIKU_4_5],
    "openai": [_GPT_4_1, _GPT_4_1_MINI],
    "gemini": [_GEMINI_2_5_PRO, _GEMINI_2_5_FLASH],
}

# Providers that require an API key (claude-cli uses MAX subscription)
REQUIRES_API_KEY: dict[str, bool] = {
    "claude-cli": False,
    "anthropic": True,
    "openai": True,
    "gemini": True,
}
