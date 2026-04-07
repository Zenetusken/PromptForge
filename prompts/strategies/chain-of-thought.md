---
tagline: reasoning
description: Guide the AI through explicit reasoning steps before producing output.
---

# Chain of Thought Strategy

Guide the AI through explicit reasoning steps before producing output.

## Techniques
- Add "Think step by step" or "Let's work through this" instructions
- Break complex tasks into numbered sub-problems
- Request intermediate reasoning before the final answer
- Add "Before answering, consider..." prefixes for evaluation tasks
- Use "First... Then... Finally..." sequential structure

## When to Use
- Complex reasoning where THE OUTPUT IS the reasoning (math proofs, logic puzzles)
- Multi-step problems where each step depends on the previous result
- Decision-making with multiple weighted criteria that need explicit comparison
- Planning tasks where sequential dependencies must be enumerated

## When to Avoid
- Simple factual lookups or one-step tasks
- Creative writing (can make output feel mechanical)
- Tasks where speed matters more than accuracy
- **Debugging and investigation prompts** — the executor is a skilled practitioner who determines their own approach. Adding steps constrains their judgment rather than aiding it. Sharpen the diagnostic framing (symptom, context, known constraints) instead of prescribing methodology.
- **Analysis tasks addressed to domain experts** — an expert needs context and scope, not a checklist of how to do their job
