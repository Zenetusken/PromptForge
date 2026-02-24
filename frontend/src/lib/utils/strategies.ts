/**
 * Canonical list of all 10 optimization strategies.
 * Single source of truth — used by ForgeOptionsTray (strategy picker)
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
		bestFor: ['education', 'general', 'writing'],
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
		bestFor: ['coding', 'analysis', 'math'],
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
		bestFor: ['writing', 'creative', 'analysis', 'medical'],
		motivation: 'Injecting domain knowledge and background info helps the model produce responses grounded in real-world context.',
	},
	'persona-assignment': {
		bestFor: ['writing', 'creative', 'medical', 'legal'],
		motivation: 'An expert persona activates domain-specific knowledge — the model writes differently as a "senior engineer" vs a "marketing lead".',
	},
};

/** All derived Tailwind classes for a strategy color. Static literals for Tailwind scanner. */
export interface StrategyColorMeta {
	bar: string;
	text: string;
	border: string;
	btnBg: string;
	rawRgba: string;
}

/** Centralized color metadata per strategy — all class strings are static Tailwind-safe literals. */
export const STRATEGY_COLOR_META: Record<StrategyName, StrategyColorMeta> = {
	'chain-of-thought': {
		bar: 'bg-neon-cyan',
		text: 'text-neon-cyan',
		border: 'border-l-neon-cyan',
		btnBg: 'bg-neon-cyan/10 hover:bg-neon-cyan/20',
		rawRgba: 'rgba(0, 229, 255, 0.35)',
	},
	'co-star': {
		bar: 'bg-neon-purple',
		text: 'text-neon-purple',
		border: 'border-l-neon-purple',
		btnBg: 'bg-neon-purple/10 hover:bg-neon-purple/20',
		rawRgba: 'rgba(168, 85, 247, 0.35)',
	},
	'risen': {
		bar: 'bg-neon-green',
		text: 'text-neon-green',
		border: 'border-l-neon-green',
		btnBg: 'bg-neon-green/10 hover:bg-neon-green/20',
		rawRgba: 'rgba(34, 255, 136, 0.35)',
	},
	'role-task-format': {
		bar: 'bg-neon-red',
		text: 'text-neon-red',
		border: 'border-l-neon-red',
		btnBg: 'bg-neon-red/10 hover:bg-neon-red/20',
		rawRgba: 'rgba(255, 51, 102, 0.35)',
	},
	'few-shot-scaffolding': {
		bar: 'bg-neon-yellow',
		text: 'text-neon-yellow',
		border: 'border-l-neon-yellow',
		btnBg: 'bg-neon-yellow/10 hover:bg-neon-yellow/20',
		rawRgba: 'rgba(251, 191, 36, 0.35)',
	},
	'step-by-step': {
		bar: 'bg-neon-orange',
		text: 'text-neon-orange',
		border: 'border-l-neon-orange',
		btnBg: 'bg-neon-orange/10 hover:bg-neon-orange/20',
		rawRgba: 'rgba(255, 140, 0, 0.35)',
	},
	'structured-output': {
		bar: 'bg-neon-blue',
		text: 'text-neon-blue',
		border: 'border-l-neon-blue',
		btnBg: 'bg-neon-blue/10 hover:bg-neon-blue/20',
		rawRgba: 'rgba(77, 142, 255, 0.35)',
	},
	'constraint-injection': {
		bar: 'bg-neon-pink',
		text: 'text-neon-pink',
		border: 'border-l-neon-pink',
		btnBg: 'bg-neon-pink/10 hover:bg-neon-pink/20',
		rawRgba: 'rgba(255, 110, 180, 0.35)',
	},
	'context-enrichment': {
		bar: 'bg-neon-teal',
		text: 'text-neon-teal',
		border: 'border-l-neon-teal',
		btnBg: 'bg-neon-teal/10 hover:bg-neon-teal/20',
		rawRgba: 'rgba(0, 212, 170, 0.35)',
	},
	'persona-assignment': {
		bar: 'bg-neon-indigo',
		text: 'text-neon-indigo',
		border: 'border-l-neon-indigo',
		btnBg: 'bg-neon-indigo/10 hover:bg-neon-indigo/20',
		rawRgba: 'rgba(123, 97, 255, 0.35)',
	},
};

const FALLBACK_COLOR: StrategyColorMeta = STRATEGY_COLOR_META['chain-of-thought'];

/** Safe lookup returning full color metadata for a strategy. Falls back to cyan for unknown/null. */
export function getStrategyColor(name: string | null | undefined): StrategyColorMeta {
	if (!name) return FALLBACK_COLOR;
	return STRATEGY_COLOR_META[name as StrategyName] ?? FALLBACK_COLOR;
}
