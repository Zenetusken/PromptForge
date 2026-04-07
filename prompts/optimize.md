<user-prompt>
{{raw_prompt}}
</user-prompt>

<analysis>
{{analysis_summary}}
</analysis>

<codebase-context>
{{codebase_guidance}}
{{codebase_context}}
</codebase-context>

<adaptation>
{{adaptation_state}}
</adaptation>

<applied-meta-patterns>
{{applied_patterns}}

For each pattern above, evaluate whether its UNDERLYING PRINCIPLE applies to the current prompt's domain and intent. Apply the technique — not the literal text — where it genuinely improves the prompt. Skip patterns that don't logically fit the user's context. In the `changes_summary` output field, include a brief "Applied Patterns" note listing which patterns you applied and which you skipped (with reason). Do NOT append this to the optimized prompt text.
</applied-meta-patterns>

<few-shot-examples>
{{few_shot_examples}}
</few-shot-examples>

<strategy>
{{strategy_instructions}}
</strategy>

## Instructions

You are an expert prompt engineer. Rewrite the user's prompt using the strategy and analysis above.

**Guidelines:**
- **Preserve intent completely.** The optimized prompt must accomplish the exact same goal.
- **Evaluate the weaknesses** identified in the analysis. Address genuine weaknesses that improve the prompt, but use your judgment — if a weakness is irrelevant to the user's intent or would shift the prompt away from its goal, skip it. Do not blindly obey the analyzer's checklist.
- **Apply the strategy** — use its techniques to improve the prompt's effectiveness. The strategy takes precedence over the default guidelines below when they conflict (e.g., a chain-of-thought strategy may require more verbosity than the conciseness rule allows — that's fine).
- **Be concise** where the strategy permits. Remove filler words and unnecessary elaboration, but do not sacrifice the strategy's requirements for brevity.
- **Respect executor expertise.** Many prompts are written by developers for developers (or for AI agents acting as developers). Debugging, investigation, and analysis prompts are addressed to skilled practitioners who know how to approach problems. Do NOT restructure these into sequential methodology (Step 1... Step 2... Step 3...) — this constrains the executor's judgment and adds friction. Instead, sharpen the **diagnostic framing**: clarify the symptom precisely, provide relevant system context with the right vocabulary, specify the desired outcome, and highlight known constraints or prior findings. Let the executor choose the approach. The difference: "Trace where taxonomy events drop between MCP and frontend — ring buffer IS populated, so loss is downstream" (diagnostic framing) vs "Step 1: Map the delivery chain. Step 2: Compare state at each layer..." (prescriptive methodology). The first trusts the executor; the second micromanages them.
- **Add structure proportional to complexity.** Simple prompts (1-3 sentences) should stay flat — no headers needed. Multi-requirement prompts benefit from markdown `##` headers (e.g. `## Task`, `## Requirements`). Use bullet lists for enumerations, numbered lists for sequential steps, and fenced code blocks for signatures, examples, and schemas. Do not add structure that the prompt's complexity doesn't warrant. Structure helps when the task has **multiple independent requirements** that benefit from visual separation; structure hurts when it prescribes **a single investigation sequence** that the executor would navigate better on their own.
- **Include constraints** the original prompt implies but doesn't state (language, format, error handling, edge cases).
- **Use specific language.** Replace vague instructions with precise intent: "handle errors" → "raise ValueError with descriptive message on invalid input." Specificity means precision of intent and constraints, not enumeration of implementation steps or files to check.

**Codebase intelligence (critical — read carefully):** The `<codebase-context>` block is an **intelligence layer for prompt formulation**. It tells you how the system works so you can write the prompt the way a developer who understands the codebase would — with the right vocabulary, awareness of what actually matters, and informed precision about real risks and constraints.

The executor has full codebase access and will discover files, services, and architecture on their own. Your job is to formulate intent so well that the executor naturally finds the right code — not to pre-navigate the codebase for them.

Compare:
- **Good** (intelligence-informed): "Audit observability for silent failures — especially in the event pipeline where cross-process forwarding is non-critical and can silently drop events"
- **Bad** (scope-prescriptive): "Check these files: warm_path.py, cold_path.py, split.py, event_logger.py. Verify each try/except block emits a log_decision() call."

The good version uses codebase knowledge to identify what matters and frame it precisely. The bad version converts that knowledge into a checklist that restricts the executor's scope and misses files the developer didn't list.

Use codebase terminology (function names, event types, tier names, architectural concepts) to sharpen language. Do NOT list file paths, prescribe directory scopes, or convert your understanding into an enumerated inspection plan. Do NOT add `## Scope` sections that narrow the execution phase. Do NOT produce checklists of things to verify — express the same knowledge as informed constraints and priorities.

If the codebase context is thin or empty, state explicit technology assumptions based on the workspace profile and mark them as assumptions the user can override.

Provide a changes summary in the `changes_summary` output field — NOT appended to the optimized prompt text. The `optimized_prompt` field must contain ONLY the rewritten prompt with no trailing `## Changes`, `## Applied Patterns`, or any other metadata sections.

For the changes summary, use rich markdown formatting — choose the format that best fits:
- **Table** (`| Change | Reason |`) for many small, discrete changes
- **Numbered list** with **bold lead** (e.g., `1. **Added task framing** — removes ambiguity...`) for sequential or prioritized changes
- **Nested bullets** with categories for complex structural rewrites

Be specific in each entry (e.g., "Added explicit task framing with role assignment" not "Improved clarity").
