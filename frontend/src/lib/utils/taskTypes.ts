/**
 * Per-task-type color registry.
 * Mirrors the `strategies.ts` pattern — static Tailwind-safe class literals.
 */

const ALL_TASK_TYPES = [
	'coding',
	'analysis',
	'reasoning',
	'math',
	'writing',
	'creative',
	'extraction',
	'classification',
	'formatting',
	'medical',
	'legal',
	'education',
	'general',
	'other',
] as const;

export type TaskTypeName = (typeof ALL_TASK_TYPES)[number];

/** All derived Tailwind classes for a task type color. Static literals for Tailwind scanner. */
interface TaskTypeColorMeta {
	text: string;
	chipBg: string;
	cssColor: string;
	rawRgba: string;
}

/** Centralized color metadata per task type — all class strings are static Tailwind-safe literals. */
const TASK_TYPE_COLOR_META: Record<TaskTypeName, TaskTypeColorMeta> = {
	coding: {
		text: 'text-neon-cyan',
		chipBg: 'bg-neon-cyan/10 text-neon-cyan',
		cssColor: '#00e5ff',
		rawRgba: 'rgba(0, 229, 255, 0.35)',
	},
	analysis: {
		text: 'text-neon-blue',
		chipBg: 'bg-neon-blue/10 text-neon-blue',
		cssColor: '#4d8eff',
		rawRgba: 'rgba(77, 142, 255, 0.35)',
	},
	reasoning: {
		text: 'text-neon-indigo',
		chipBg: 'bg-neon-indigo/10 text-neon-indigo',
		cssColor: '#7b61ff',
		rawRgba: 'rgba(123, 97, 255, 0.35)',
	},
	math: {
		text: 'text-neon-purple',
		chipBg: 'bg-neon-purple/10 text-neon-purple',
		cssColor: '#a855f7',
		rawRgba: 'rgba(168, 85, 247, 0.35)',
	},
	writing: {
		text: 'text-neon-green',
		chipBg: 'bg-neon-green/10 text-neon-green',
		cssColor: '#22ff88',
		rawRgba: 'rgba(34, 255, 136, 0.35)',
	},
	creative: {
		text: 'text-neon-pink',
		chipBg: 'bg-neon-pink/10 text-neon-pink',
		cssColor: '#ff6eb4',
		rawRgba: 'rgba(255, 110, 180, 0.35)',
	},
	extraction: {
		text: 'text-neon-teal',
		chipBg: 'bg-neon-teal/10 text-neon-teal',
		cssColor: '#00d4aa',
		rawRgba: 'rgba(0, 212, 170, 0.35)',
	},
	classification: {
		text: 'text-neon-orange',
		chipBg: 'bg-neon-orange/10 text-neon-orange',
		cssColor: '#ff8c00',
		rawRgba: 'rgba(255, 140, 0, 0.35)',
	},
	formatting: {
		text: 'text-neon-yellow',
		chipBg: 'bg-neon-yellow/10 text-neon-yellow',
		cssColor: '#fbbf24',
		rawRgba: 'rgba(251, 191, 36, 0.35)',
	},
	medical: {
		text: 'text-neon-red',
		chipBg: 'bg-neon-red/10 text-neon-red',
		cssColor: '#ff3366',
		rawRgba: 'rgba(255, 51, 102, 0.35)',
	},
	legal: {
		text: 'text-neon-red/70',
		chipBg: 'bg-neon-red/8 text-neon-red/70',
		cssColor: 'rgba(255, 51, 102, 0.7)',
		rawRgba: 'rgba(255, 51, 102, 0.25)',
	},
	education: {
		text: 'text-neon-teal/70',
		chipBg: 'bg-neon-teal/8 text-neon-teal/70',
		cssColor: 'rgba(0, 212, 170, 0.7)',
		rawRgba: 'rgba(0, 212, 170, 0.25)',
	},
	general: {
		text: 'text-neon-cyan/60',
		chipBg: 'bg-neon-cyan/8 text-neon-cyan/60',
		cssColor: 'rgba(0, 229, 255, 0.6)',
		rawRgba: 'rgba(0, 229, 255, 0.20)',
	},
	other: {
		text: 'text-text-dim',
		chipBg: 'bg-bg-hover/60 text-text-dim',
		cssColor: 'rgba(255, 255, 255, 0.4)',
		rawRgba: 'rgba(255, 255, 255, 0.10)',
	},
};

const FALLBACK_COLOR: TaskTypeColorMeta = TASK_TYPE_COLOR_META['other'];

/** Safe lookup returning full color metadata for a task type. Falls back to dim for unknown/null. */
export function getTaskTypeColor(name: string | null | undefined): TaskTypeColorMeta {
	if (!name) return FALLBACK_COLOR;
	return TASK_TYPE_COLOR_META[name as TaskTypeName] ?? FALLBACK_COLOR;
}
