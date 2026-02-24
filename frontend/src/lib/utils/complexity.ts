/**
 * Per-complexity-level color registry.
 * Mirrors the `strategies.ts` pattern — static Tailwind-safe class literals.
 * Includes alias normalization (simple→low, moderate→medium, complex→high).
 */

export interface ComplexityColorMeta {
	text: string;
	chipBg: string;
	btnBg: string;
	border: string;
	rawRgba: string;
}

const LOW: ComplexityColorMeta = {
	text: 'text-neon-green',
	chipBg: 'bg-neon-green/10 text-neon-green',
	btnBg: 'bg-neon-green/15 text-neon-green',
	border: 'border-neon-green/30',
	rawRgba: 'rgba(34, 255, 136, 0.35)',
};

const MEDIUM: ComplexityColorMeta = {
	text: 'text-neon-yellow',
	chipBg: 'bg-neon-yellow/10 text-neon-yellow',
	btnBg: 'bg-neon-yellow/15 text-neon-yellow',
	border: 'border-neon-yellow/30',
	rawRgba: 'rgba(251, 191, 36, 0.35)',
};

const HIGH: ComplexityColorMeta = {
	text: 'text-neon-red',
	chipBg: 'bg-neon-red/10 text-neon-red',
	btnBg: 'bg-neon-red/15 text-neon-red',
	border: 'border-neon-red/30',
	rawRgba: 'rgba(255, 51, 102, 0.35)',
};

/** Alias normalization map. */
const ALIASES: Record<string, ComplexityColorMeta> = {
	low: LOW,
	simple: LOW,
	medium: MEDIUM,
	moderate: MEDIUM,
	high: HIGH,
	complex: HIGH,
};

const FALLBACK: ComplexityColorMeta = MEDIUM;

/** Safe lookup with alias normalization. Falls back to yellow (medium) for unknown/null. */
export function getComplexityColor(name: string | null | undefined): ComplexityColorMeta {
	if (!name) return FALLBACK;
	return ALIASES[name.toLowerCase()] ?? FALLBACK;
}
