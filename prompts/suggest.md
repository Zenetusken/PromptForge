<optimized-prompt>
{{optimized_prompt}}
</optimized-prompt>

<scores>
{{scores}}
</scores>

<weaknesses>
{{weaknesses}}
</weaknesses>

<strategy>
Strategy used: {{strategy_used}}
</strategy>

<score-deltas>
{{score_deltas}}
</score-deltas>

<score-trajectory>
{{score_trajectory}}
</score-trajectory>

## Instructions

Generate exactly 3 actionable refinement suggestions for the optimized prompt above.

Each suggestion should be a single, specific instruction the user could give to improve the prompt. Draw from three sources:

1. **Score-driven** — Target the lowest-scoring dimension. Example: "Improve specificity — currently 6.2/10"
2. **Analysis-driven** — Address a weakness detected by the analyzer. Example: "Add error handling constraints"
3. **Strategic** — Apply a technique from the strategy. Example: "Add few-shot examples to demonstrate expected output"

### Trade-off rules

- **Net-positive impact required.** Each suggestion must improve the target dimension WITHOUT degrading other dimensions by more than 0.5 points. If improving one dimension would significantly lengthen the prompt, the suggestion MUST include a compression directive (e.g., "Add X while condensing the existing Y section").
- **Conciseness guard.** If conciseness is below 6.0, do NOT suggest adding length, detail, or examples. Instead suggest restructuring, replacing verbose prose with lists, or removing redundancy.
- **No circular suggestions.** Check `score-deltas` — if a previous refinement already degraded a dimension, do not suggest changes that would degrade it further. If the trajectory is "oscillating" or "degrading", suggest a fundamentally different approach rather than incremental additions.
- **Protect strong dimensions.** If a dimension scores above 7.5, suggestions should not risk degrading it.

Return exactly 3 suggestions. Each should be actionable in one sentence. Be specific, not vague.

## Output format

Return a JSON object with a single `suggestions` array containing exactly 3 objects. Each object must have:
- `text`: the suggestion as a single actionable sentence
- `source`: one of `"score"`, `"analysis"`, or `"strategy"`
