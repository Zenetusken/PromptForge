/**
 * Canonical list of all 10 optimization strategies.
 * Single source of truth — used by PromptInput (strategy picker)
 * and StrategyInsights (distribution panel).
 */
export const ALL_STRATEGIES = [
	'chain-of-thought',
	'co-star',
	'risen',
	'role-task-format',
	'few-shot-scaffolding',
	'step-by-step',
	'structured-output',
	'constraint-injection',
	'context-enrichment',
	'persona-assignment',
] as const;

export type StrategyName = (typeof ALL_STRATEGIES)[number];

/** Display labels for each strategy. */
export const STRATEGY_LABELS: Record<StrategyName, string> = {
	'chain-of-thought': 'Chain of Thought',
	'co-star': 'CO-STAR',
	'risen': 'RISEN',
	'role-task-format': 'Role-Task-Format',
	'few-shot-scaffolding': 'Few-Shot',
	'step-by-step': 'Step by Step',
	'structured-output': 'Structured Output',
	'constraint-injection': 'Constraint Injection',
	'context-enrichment': 'Context Enrichment',
	'persona-assignment': 'Persona Assignment',
};

/** Short descriptions for each strategy. */
export const STRATEGY_DESCRIPTIONS: Record<StrategyName, string> = {
	'co-star': 'Context, Objective, Style, Tone, Audience, Response',
	'risen': 'Role, Instructions, Steps, End-goal, Narrowing',
	'role-task-format': 'Role + task description + output format',
	'chain-of-thought': 'Step-by-step reasoning scaffolding',
	'few-shot-scaffolding': 'Input/output example pairs',
	'step-by-step': 'Numbered sequential instructions',
	'structured-output': 'JSON, markdown, table format spec',
	'constraint-injection': "Explicit do/don't rules and boundaries",
	'context-enrichment': 'Background info, domain context',
	'persona-assignment': 'Expert role with domain expertise',
};

/** Extended strategy details for the Strategy Explorer. */
export const STRATEGY_DETAILS: Record<StrategyName, { bestFor: string[]; motivation: string }> = {
	'chain-of-thought': {
		bestFor: ['reasoning', 'analysis', 'math'],
		motivation: 'Forces the model to show its work — ideal for logic-heavy prompts where implicit reasoning leads to errors.',
	},
	'co-star': {
		bestFor: ['writing', 'creative', 'reasoning'],
		motivation: 'The 6-dimension framework (Context, Objective, Style, Tone, Audience, Response) gives the model maximum context to nail tone and audience.',
	},
	'risen': {
		bestFor: ['general', 'writing'],
		motivation: 'RISEN gives clear structure with explicit end-goals — great for complex multi-step tasks that need focus.',
	},
	'role-task-format': {
		bestFor: ['general'],
		motivation: 'Simple but effective: assign a role, describe the task, specify the output format. Good baseline for any prompt.',
	},
	'few-shot-scaffolding': {
		bestFor: ['classification', 'extraction', 'formatting'],
		motivation: 'Providing input/output examples is the fastest way to get consistent, predictable results for pattern-matching tasks.',
	},
	'step-by-step': {
		bestFor: ['math', 'coding'],
		motivation: 'Numbered instructions enforce sequential execution — perfect when order matters and steps shouldn\'t be skipped.',
	},
	'structured-output': {
		bestFor: ['coding', 'extraction', 'formatting'],
		motivation: 'When you need JSON, tables, or specific formats, this strategy ensures the model follows your exact output schema.',
	},
	'constraint-injection': {
		bestFor: ['coding', 'medical', 'extraction'],
		motivation: 'Explicit do/don\'t rules prevent the model from going off-script — essential for safety-critical or compliance-sensitive tasks.',
	},
	'context-enrichment': {
		bestFor: ['writing', 'creative', 'medical'],
		motivation: 'Injecting domain knowledge and background info helps the model produce responses grounded in real-world context.',
	},
	'persona-assignment': {
		bestFor: ['writing', 'creative', 'medical'],
		motivation: 'An expert persona activates domain-specific knowledge — the model writes differently as a "senior engineer" vs a "marketing lead".',
	},
};

/** Deterministic per-strategy color assignment (no position-based cycling). */
export const STRATEGY_FIXED_COLORS: Record<StrategyName, { bar: string; text: string }> = {
	'chain-of-thought': { bar: 'bg-neon-cyan', text: 'text-neon-cyan' },
	'co-star': { bar: 'bg-neon-purple', text: 'text-neon-purple' },
	'risen': { bar: 'bg-neon-green', text: 'text-neon-green' },
	'role-task-format': { bar: 'bg-neon-red', text: 'text-neon-red' },
	'few-shot-scaffolding': { bar: 'bg-neon-cyan', text: 'text-neon-cyan' },
	'step-by-step': { bar: 'bg-neon-purple', text: 'text-neon-purple' },
	'structured-output': { bar: 'bg-neon-green', text: 'text-neon-green' },
	'constraint-injection': { bar: 'bg-neon-red', text: 'text-neon-red' },
	'context-enrichment': { bar: 'bg-neon-cyan', text: 'text-neon-cyan' },
	'persona-assignment': { bar: 'bg-neon-purple', text: 'text-neon-purple' },
};
