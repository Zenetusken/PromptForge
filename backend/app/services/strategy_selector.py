"""Strategy selector service - chooses the best optimization strategy for a prompt."""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from app.constants import LEGACY_STRATEGY_ALIASES, Strategy
from app.prompts.strategy_prompt import STRATEGY_SYSTEM_PROMPT
from app.providers import LLMProvider, get_provider
from app.providers.types import CompletionRequest, TokenUsage
from app.services.analyzer import AnalysisResult

if TYPE_CHECKING:
    from app.schemas.context import CodebaseContext

logger = logging.getLogger(__name__)


@dataclass
class StrategySelection:
    """The selected optimization strategy and reasoning."""

    strategy: Strategy
    reasoning: str
    confidence: float = 0.75
    task_type: str = ""
    is_override: bool = False
    secondary_frameworks: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


# ---------------------------------------------------------------------------
# Framework combination model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FrameworkCombo:
    """A primary framework + up to 2 secondary frameworks."""

    primary: Strategy
    secondary: tuple[Strategy, ...] = ()


# Maps each analyzer task_type to its spec-defined 3-framework combo.
TASK_TYPE_FRAMEWORK_MAP: dict[str, FrameworkCombo] = {
    "coding": FrameworkCombo(
        Strategy.STRUCTURED_OUTPUT,
        (Strategy.CONSTRAINT_INJECTION, Strategy.STEP_BY_STEP),
    ),
    "writing": FrameworkCombo(
        Strategy.PERSONA_ASSIGNMENT,
        (Strategy.CONTEXT_ENRICHMENT, Strategy.CO_STAR),
    ),
    "creative": FrameworkCombo(
        Strategy.PERSONA_ASSIGNMENT,
        (Strategy.CO_STAR, Strategy.CONTEXT_ENRICHMENT),
    ),
    "reasoning": FrameworkCombo(
        Strategy.CHAIN_OF_THOUGHT,
        (Strategy.STRUCTURED_OUTPUT, Strategy.CO_STAR),
    ),
    "analysis": FrameworkCombo(
        Strategy.CHAIN_OF_THOUGHT,
        (Strategy.CO_STAR, Strategy.STRUCTURED_OUTPUT),
    ),
    "math": FrameworkCombo(
        Strategy.CHAIN_OF_THOUGHT,
        (Strategy.STEP_BY_STEP, Strategy.CONSTRAINT_INJECTION),
    ),
    "extraction": FrameworkCombo(
        Strategy.STRUCTURED_OUTPUT,
        (Strategy.FEW_SHOT_SCAFFOLDING, Strategy.CONSTRAINT_INJECTION),
    ),
    "classification": FrameworkCombo(
        Strategy.FEW_SHOT_SCAFFOLDING,
        (Strategy.STRUCTURED_OUTPUT, Strategy.CONSTRAINT_INJECTION),
    ),
    "formatting": FrameworkCombo(
        Strategy.STRUCTURED_OUTPUT,
        (Strategy.FEW_SHOT_SCAFFOLDING, Strategy.CONSTRAINT_INJECTION),
    ),
    "medical": FrameworkCombo(
        Strategy.PERSONA_ASSIGNMENT,
        (Strategy.CONSTRAINT_INJECTION, Strategy.CONTEXT_ENRICHMENT),
    ),
    "legal": FrameworkCombo(
        Strategy.PERSONA_ASSIGNMENT,
        (Strategy.CONSTRAINT_INJECTION, Strategy.CONTEXT_ENRICHMENT),
    ),
    "education": FrameworkCombo(
        Strategy.RISEN,
        (Strategy.STEP_BY_STEP, Strategy.CONTEXT_ENRICHMENT),
    ),
    "general": FrameworkCombo(
        Strategy.ROLE_TASK_FORMAT,
        (Strategy.CONTEXT_ENRICHMENT, Strategy.STRUCTURED_OUTPUT),
    ),
    "other": FrameworkCombo(
        Strategy.RISEN,
        (Strategy.ROLE_TASK_FORMAT, Strategy.CONTEXT_ENRICHMENT),
    ),
}

_DEFAULT_COMBO = FrameworkCombo(
    Strategy.ROLE_TASK_FORMAT,
    (Strategy.CONTEXT_ENRICHMENT, Strategy.STRUCTURED_OUTPUT),
)


# Task types where chain-of-thought is the natural strategy.  Priority 1
# (high-complexity override) only fires for these — other task types fall
# through to Priorities 2/3 for strategy diversity even at high complexity.
_COT_NATURAL_TASK_TYPES: frozenset[str] = frozenset({"reasoning", "analysis", "math"})

_SPECIFICITY_PATTERNS = (
    "lacks specific", "not specific", "vague", "unspecific", "lack of detail",
    "ambiguous", "unclear", "underspecified", "too broad", "too general",
    "needs more detail", "insufficiently detailed", "broad scope",
)

# Compiled regex for faster specificity matching (Issue 4.2).
# Word boundaries (\b) prevent false matches inside longer words
# (e.g. "vague" inside "extravagant", "broad" inside "abroad").
_SPECIFICITY_RE = re.compile(
    "|".join(r"\b" + re.escape(p) + r"\b" for p in _SPECIFICITY_PATTERNS),
    re.IGNORECASE,
)

# Strategies that already address vagueness through their own structure,
# so the P2 specificity override (→ constraint-injection) should not
# eclipse them.  P2 only fires for non-exempt task types like coding,
# formatting, extraction, general, and unknowns.
_SPECIFICITY_EXEMPT_STRATEGIES: frozenset[Strategy] = frozenset({
    Strategy.CHAIN_OF_THOUGHT,       # step-by-step reasoning addresses vagueness naturally
    Strategy.PERSONA_ASSIGNMENT,     # domain expertise addresses vagueness
    Strategy.FEW_SHOT_SCAFFOLDING,   # examples define expectations better than constraints
    Strategy.RISEN,                  # RISEN's "Narrowing constraints" subsumes constraint-injection
})

# Strengths that make a strategy redundant — if the prompt already has
# what a strategy would add, fall back instead.
# Raw patterns kept for test introspection; compiled regex for matching.
_STRENGTH_REDUNDANCY_PATTERNS: dict[Strategy, tuple[str, ...]] = {
    Strategy.CO_STAR: (
        "clear context", "well-defined audience", "specifies tone", "context and objective",
    ),
    Strategy.RISEN: (
        "clear role and instructions", "end-goal defined", "narrowing constraints",
    ),
    Strategy.CHAIN_OF_THOUGHT: (
        "step-by-step", "numbered steps", "sequential reasoning", "chain of thought",
    ),
    Strategy.FEW_SHOT_SCAFFOLDING: (
        "includes examples", "provides examples", "has examples", "example-driven",
    ),
    Strategy.ROLE_TASK_FORMAT: (
        "clear role definition", "task and format specified", "role-task structure",
    ),
    Strategy.STRUCTURED_OUTPUT: (
        "well-structured", "clear format", "good organization",
        "well-organized", "clear structure", "good formatting",
    ),
    Strategy.STEP_BY_STEP: (
        "numbered steps", "sequential instructions", "ordered steps",
    ),
    Strategy.CONSTRAINT_INJECTION: (
        "explicit constraints", "clear constraints",
        "well-defined boundaries", "specific requirements",
    ),
    Strategy.CONTEXT_ENRICHMENT: (
        "rich context", "background provided", "domain context included",
    ),
    Strategy.PERSONA_ASSIGNMENT: (
        "expert persona", "assigns a role", "defines a role", "clear role definition",
    ),
}

# Compiled regex with word boundaries to prevent false positives.
_STRENGTH_REDUNDANCY_RE: dict[Strategy, re.Pattern[str]] = {
    strategy: re.compile(
        "|".join(r"\b" + re.escape(p) + r"\b" for p in patterns),
        re.IGNORECASE,
    )
    for strategy, patterns in _STRENGTH_REDUNDANCY_PATTERNS.items()
}

# Maps each strategy to its human-readable reasoning suffix.
_STRATEGY_REASON_MAP: dict[Strategy, str] = {
    Strategy.CO_STAR: (
        "structures prompt with Context, Objective, Style, Tone, "
        "Audience, Response format."
    ),
    Strategy.RISEN: (
        "organizes prompt with Role, Instructions, Steps, "
        "End-goal, Narrowing constraints."
    ),
    Strategy.CHAIN_OF_THOUGHT: "enables step-by-step reasoning.",
    Strategy.FEW_SHOT_SCAFFOLDING: "provides concrete examples for pattern-based tasks.",
    Strategy.ROLE_TASK_FORMAT: "structures prompt with role, task description, and output format.",
    Strategy.STRUCTURED_OUTPUT: "specifies structured output format (JSON, tables, etc.).",
    Strategy.STEP_BY_STEP: "breaks task into ordered sequential instructions.",
    Strategy.CONSTRAINT_INJECTION: (
        "addresses identified specificity weaknesses "
        "with explicit constraints."
    ),
    Strategy.CONTEXT_ENRICHMENT: "enriches prompt with background information and domain context.",
    Strategy.PERSONA_ASSIGNMENT: "leverages domain-specific expert persona.",
}

# Short descriptions for each strategy, sent to the LLM in the user message.
_STRATEGY_DESCRIPTIONS: dict[Strategy, str] = {
    Strategy.CO_STAR: "Context, Objective, Style, Tone, Audience, Response format",
    Strategy.RISEN: "Role, Instructions, Steps, End-goal, Narrowing constraints",
    Strategy.CHAIN_OF_THOUGHT: "Adds step-by-step reasoning structure",
    Strategy.FEW_SHOT_SCAFFOLDING: "Adds concrete input/output examples",
    Strategy.ROLE_TASK_FORMAT: "Assigns role, states task, specifies output format",
    Strategy.STRUCTURED_OUTPUT: "Specifies JSON, table, or parseable output format",
    Strategy.STEP_BY_STEP: "Breaks tasks into ordered sequential instructions",
    Strategy.CONSTRAINT_INJECTION: "Adds explicit constraints, boundaries, and rules",
    Strategy.CONTEXT_ENRICHMENT: "Supplies background info, definitions, references",
    Strategy.PERSONA_ASSIGNMENT: "Assigns specific professional identity and expertise",
}


def _build_reasoning(strategy: str, task_type: str, reason: str) -> str:
    """Build a consistent reasoning string."""
    return f"Selected {strategy} for {task_type} task: {reason}"


class HeuristicStrategySelector:
    """Selects the most appropriate optimization strategy based on prompt analysis.

    Uses task type, complexity, and identified weaknesses to choose
    the best optimization approach.

    Priority order:
      1. High complexity + CoT-natural task type (reasoning, analysis, math)
         → chain-of-thought.  Non-CoT task types fall through even at high
         complexity, preserving strategy diversity.
      2. Specificity weakness → constraint-injection, UNLESS the task-type's
         natural strategy is exempt (chain-of-thought, persona-assignment,
         few-shot-scaffolding, risen).  P2 only fires for coding, formatting,
         extraction, general, and unknown task types.
      3. Task-type map → lookup with role-task-format fallback,
         with a strengths-based redundancy check: if the prompt already
         has what the candidate strategy would add, tries the combo's first
         secondary as primary instead.
         High complexity adds a +0.10 confidence boost (capped at 0.95).
    """

    # Very short prompts are harder to classify accurately; apply a small
    # confidence penalty to signal uncertainty.
    _SHORT_PROMPT_THRESHOLD = 50
    _SHORT_PROMPT_PENALTY = 0.05

    def select(
        self,
        analysis: AnalysisResult,
        prompt_length: int = 0,
        *,
        codebase_context: CodebaseContext | None = None,
    ) -> StrategySelection:
        """Select the best optimization strategy given an analysis result.

        Args:
            analysis: The analysis result from PromptAnalyzer.
            prompt_length: Length of the raw prompt in characters. When < 50,
                a small confidence penalty is applied.
            codebase_context: Optional codebase context for context-aware
                strategy preference adjustments at P3 level.

        Returns:
            A StrategySelection with the chosen strategy name and reasoning.
        """
        result = self._select_core(analysis, codebase_context=codebase_context)

        # Short-prompt penalty: very short prompts are harder to classify
        # accurately, so reduce confidence to reflect that uncertainty.
        if 0 < prompt_length < self._SHORT_PROMPT_THRESHOLD:
            adjusted = max(0.0, result.confidence - self._SHORT_PROMPT_PENALTY)
            if adjusted != result.confidence:
                logger.info(
                    "Short-prompt penalty: length=%d < %d, confidence %.2f → %.2f",
                    prompt_length, self._SHORT_PROMPT_THRESHOLD,
                    result.confidence, adjusted,
                )
                result = StrategySelection(
                    strategy=result.strategy,
                    reasoning=result.reasoning,
                    confidence=adjusted,
                    secondary_frameworks=result.secondary_frameworks,
                )

        return result

    def _select_core(
        self,
        analysis: AnalysisResult,
        *,
        codebase_context: CodebaseContext | None = None,
    ) -> StrategySelection:
        """Core selection logic without prompt-length adjustments."""
        task_key = analysis.task_type.lower()
        combo = TASK_TYPE_FRAMEWORK_MAP.get(task_key, _DEFAULT_COMBO)
        natural_strategy = combo.primary
        is_high = analysis.complexity.lower() == "high"

        # Priority 1: High complexity + CoT-natural task type → chain-of-thought
        # BUT if the prompt already has what CoT adds (step-by-step etc.),
        # redirect to the combo's first secondary instead (avoids redundancy).
        if is_high and task_key in _COT_NATURAL_TASK_TYPES:
            cot_redundancy_re = _STRENGTH_REDUNDANCY_RE.get(Strategy.CHAIN_OF_THOUGHT)
            p1_is_redundant = cot_redundancy_re and any(
                cot_redundancy_re.search(str(s)) for s in analysis.strengths
            )
            if p1_is_redundant:
                # Use first secondary from the combo as fallback primary
                fallback = combo.secondary[0] if combo.secondary else Strategy.ROLE_TASK_FORMAT
                fallback_secondaries = [
                    s.value for s in combo.secondary if s != fallback
                ]
                logger.info(
                    "P1-redundancy: CoT redundant for high-complexity task_type=%s "
                    "→ %s",
                    task_key, fallback,
                )
                return StrategySelection(
                    strategy=fallback,
                    reasoning=_build_reasoning(
                        fallback,
                        analysis.task_type,
                        "prompt already exhibits step-by-step reasoning; "
                        f"{fallback} more useful than redundant CoT.",
                    ),
                    confidence=0.85,
                    secondary_frameworks=fallback_secondaries,
                )
            logger.info(
                "P1: high complexity + CoT-natural task_type=%s → chain-of-thought",
                task_key,
            )
            return StrategySelection(
                strategy=Strategy.CHAIN_OF_THOUGHT,
                reasoning=_build_reasoning(
                    Strategy.CHAIN_OF_THOUGHT,
                    analysis.task_type,
                    "high complexity requires step-by-step reasoning.",
                ),
                confidence=0.95,
                secondary_frameworks=[s.value for s in combo.secondary],
            )

        # Priority 2: Specificity weakness → constraint-injection
        # Skip the override when the task-type's natural strategy is in
        # _SPECIFICITY_EXEMPT_STRATEGIES (e.g. math→chain-of-thought),
        # since those strategies already address vagueness better (Issue 2.1).

        specificity_match_count = sum(
            1 for w in analysis.weaknesses if _SPECIFICITY_RE.search(str(w))
        )
        if specificity_match_count > 0 and natural_strategy not in _SPECIFICITY_EXEMPT_STRATEGIES:
            # Scale confidence with severity: more matching weaknesses = higher confidence
            if specificity_match_count >= 3:
                p2_confidence = 0.90
            elif specificity_match_count == 2:
                p2_confidence = 0.85
            else:
                p2_confidence = 0.80

            # Build secondaries: use combo's secondaries excluding constraint-injection
            p2_secondaries = [
                s.value for s in combo.secondary
                if s != Strategy.CONSTRAINT_INJECTION
            ][:2]

            logger.info(
                "P2: %d specificity weakness(es) for task_type=%s → constraint-injection "
                "(confidence=%.2f)",
                specificity_match_count, task_key, p2_confidence,
            )
            return StrategySelection(
                strategy=Strategy.CONSTRAINT_INJECTION,
                reasoning=_build_reasoning(
                    Strategy.CONSTRAINT_INJECTION,
                    analysis.task_type,
                    "addressing identified specificity weaknesses.",
                ),
                confidence=p2_confidence,
                secondary_frameworks=p2_secondaries,
            )

        # Priority 3: Task-type map → lookup, with strengths redundancy check
        strategy = natural_strategy

        # Before returning the task-type result, check whether the prompt
        # already exhibits the strength that strategy would add.  If so,
        # try the combo's first secondary as primary instead.
        # Special case: if the fallback is also redundant, return it at lower confidence.
        redundancy_re = _STRENGTH_REDUNDANCY_RE.get(strategy)
        if redundancy_re:
            is_redundant = any(
                redundancy_re.search(str(s)) for s in analysis.strengths
            )
            if is_redundant:
                # Try first secondary as fallback primary
                if combo.secondary:
                    fallback = combo.secondary[0]
                    fallback_re = _STRENGTH_REDUNDANCY_RE.get(fallback)
                    fallback_redundant = fallback_re and any(
                        fallback_re.search(str(s)) for s in analysis.strengths
                    )
                    if fallback_redundant:
                        # Both primary and first secondary are redundant
                        logger.info(
                            "P3-redundancy: %s and %s both redundant for task_type=%s "
                            "→ %s at reduced confidence",
                            strategy, fallback, task_key, fallback,
                        )
                        return StrategySelection(
                            strategy=fallback,
                            reasoning=_build_reasoning(
                                fallback,
                                analysis.task_type,
                                "prompt is already well-structured; "
                                "minor refinements may still help.",
                            ),
                            confidence=0.60,
                            secondary_frameworks=[
                                s.value for s in combo.secondary if s != fallback
                            ][:2],
                        )
                    logger.info(
                        "P3-redundancy: %s redundant for task_type=%s → %s",
                        strategy, task_key, fallback,
                    )
                    return StrategySelection(
                        strategy=fallback,
                        reasoning=_build_reasoning(
                            fallback,
                            analysis.task_type,
                            f"prompt already exhibits strengths that {strategy} would add.",
                        ),
                        confidence=0.70,
                        secondary_frameworks=[
                            s.value for s in combo.secondary if s != fallback
                        ][:2],
                    )
                else:
                    # No secondaries to fall back to
                    logger.info(
                        "P3-redundancy: %s redundant, no secondaries for task_type=%s",
                        strategy, task_key,
                    )
                    return StrategySelection(
                        strategy=strategy,
                        reasoning=_build_reasoning(
                            strategy,
                            analysis.task_type,
                            "prompt is already well-structured; "
                            "minor refinements may still help.",
                        ),
                        confidence=0.60,
                    )

        reason = _STRATEGY_REASON_MAP.get(strategy, "applies general structural improvements.")
        confidence = 0.75 if task_key in TASK_TYPE_FRAMEWORK_MAP else 0.50

        # High-complexity boost: when P1 didn't fire (non-CoT task type),
        # still reward the higher complexity with a confidence bump.
        if is_high:
            confidence = min(confidence + 0.10, 0.95)

        # Context-aware adjustment: boost confidence when codebase context
        # aligns with the selected strategy.
        ctx_pref = _context_strategy_preference(codebase_context)
        if ctx_pref:
            pref_strategy, pref_boost, pref_reason = ctx_pref
            if pref_strategy == strategy:
                confidence = min(confidence + pref_boost, 0.95)
                reason = f"{reason} {pref_reason}"
                logger.info(
                    "P3-context: %s matches context preference, boost +%.2f",
                    strategy, pref_boost,
                )

        logger.info(
            "P3: task_type=%s → %s (confidence=%.2f, high_boost=%s)",
            task_key, strategy, confidence, is_high,
        )
        return StrategySelection(
            strategy=strategy,
            reasoning=_build_reasoning(strategy, analysis.task_type, reason),
            confidence=confidence,
            secondary_frameworks=[s.value for s in combo.secondary],
        )


def _context_strategy_preference(
    ctx: CodebaseContext | None,
) -> tuple[Strategy, float, str] | None:
    """Map codebase context signals to a strategy preference.

    Returns (preferred_strategy, confidence_boost, reason) or None.
    Only used to boost confidence when the context aligns with the already-
    selected strategy — never overrides P1 or P2.
    """
    if not ctx:
        return None

    lang = (ctx.language or "").lower()
    framework = (ctx.framework or "").lower()
    conventions = " ".join(ctx.conventions).lower() if ctx.conventions else ""
    patterns = " ".join(ctx.patterns).lower() if ctx.patterns else ""

    # Strict type systems → structured-output gets a boost
    strict_signals = (
        "strict mode" in conventions
        or "typescript strict" in conventions
        or lang in ("rust", "go")
    )
    if strict_signals:
        reason = "Strict type system aligns with structured output."
        return (Strategy.STRUCTURED_OUTPUT, 0.05, reason)

    # Domain-specific frameworks → persona-assignment boost
    domain_signals = any(
        kw in framework or kw in patterns
        for kw in ("medical", "legal", "healthcare", "clinical", "juridical")
    )
    if domain_signals:
        reason = "Domain-specific project benefits from expert persona."
        return (Strategy.PERSONA_ASSIGNMENT, 0.05, reason)

    # Complex multi-service patterns → step-by-step boost
    service_signals = (
        "service layer" in patterns
        and "repository pattern" in patterns
    ) or "microservice" in patterns
    if service_signals:
        reason = "Multi-layer architecture suits step-by-step decomposition."
        return (Strategy.STEP_BY_STEP, 0.05, reason)

    # Rich conventions/patterns → constraint-injection boost
    has_rich_context = (
        len(ctx.conventions) >= 3 and len(ctx.patterns) >= 3
    )
    if has_rich_context:
        reason = "Rich project conventions ground constraint injection."
        return (Strategy.CONSTRAINT_INJECTION, 0.05, reason)

    return None


_VALID_STRATEGIES: frozenset[str] = frozenset(s.value for s in Strategy)


class StrategySelector:
    """LLM-based strategy selector with heuristic fallback.

    Sends the analysis and prompt to an LLM to select the best strategy.
    Falls back to HeuristicStrategySelector on LLM errors.
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider or get_provider()
        self.last_usage: TokenUsage | None = None
        self._heuristic = HeuristicStrategySelector()

    async def select(
        self,
        analysis: AnalysisResult,
        raw_prompt: str = "",
        prompt_length: int = 0,
        *,
        codebase_context: CodebaseContext | None = None,
    ) -> StrategySelection:
        """Select strategy via LLM, falling back to heuristic on error."""
        try:
            result = await self._select_via_llm(
                analysis, raw_prompt, codebase_context=codebase_context,
            )
        except Exception:
            logger.warning(
                "LLM strategy selection failed, falling back to heuristic",
                exc_info=True,
            )
            result = self._heuristic.select(
                analysis, prompt_length=prompt_length, codebase_context=codebase_context,
            )

        result.task_type = analysis.task_type
        return result

    async def _select_via_llm(
        self,
        analysis: AnalysisResult,
        raw_prompt: str,
        *,
        codebase_context: CodebaseContext | None = None,
    ) -> StrategySelection:
        """Call the LLM to select a strategy."""
        user_payload: dict = {
            "raw_prompt": raw_prompt,
            "analysis": asdict(analysis),
            "available_strategies": {
                s.value: _STRATEGY_DESCRIPTIONS[s] for s in Strategy
            },
        }
        if codebase_context:
            rendered = codebase_context.render()
            if rendered:
                user_payload["codebase_context"] = rendered
        request = CompletionRequest(
            system_prompt=STRATEGY_SYSTEM_PROMPT,
            user_message=json.dumps(user_payload),
        )
        response, completion = await self.llm.complete_json(request)
        self.last_usage = completion.usage

        return self._validate_response(response, analysis.task_type)

    def _validate_response(
        self,
        response: dict,
        task_type: str,
    ) -> StrategySelection:
        """Validate and normalize the LLM response into a StrategySelection."""
        # Validate strategy
        raw_strategy = str(response.get("strategy", "")).strip().lower()
        # Handle legacy aliases from LLM
        if raw_strategy in LEGACY_STRATEGY_ALIASES:
            raw_strategy = LEGACY_STRATEGY_ALIASES[raw_strategy]
        if raw_strategy in _VALID_STRATEGIES:
            strategy = Strategy(raw_strategy)
        else:
            logger.warning(
                "Unknown strategy %r from LLM, defaulting to role-task-format",
                raw_strategy,
            )
            strategy = Strategy.ROLE_TASK_FORMAT

        # Validate confidence
        raw_confidence = response.get("confidence", 0.75)
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            logger.warning(
                "Non-numeric confidence %r from LLM, defaulting to 0.75",
                raw_confidence,
            )
            confidence = 0.75
        confidence = max(0.0, min(1.0, confidence))

        # Validate reasoning
        reasoning = str(response.get("reasoning", "")).strip()
        if not reasoning:
            reasoning = f"Selected {strategy} for {task_type} task."

        # Validate secondary_frameworks
        raw_secondary = response.get("secondary_frameworks", [])
        secondary: list[str] = []
        if isinstance(raw_secondary, list):
            for fw in raw_secondary[:2]:
                fw_str = str(fw).strip().lower()
                # Handle legacy aliases
                if fw_str in LEGACY_STRATEGY_ALIASES:
                    fw_str = LEGACY_STRATEGY_ALIASES[fw_str]
                if fw_str in _VALID_STRATEGIES and fw_str != strategy.value:
                    secondary.append(fw_str)

        return StrategySelection(
            strategy=strategy,
            reasoning=reasoning,
            confidence=confidence,
            secondary_frameworks=secondary,
        )
