export type ScoreDimension = 'clarity' | 'specificity' | 'structure' | 'faithfulness';

/** Scoring formula weights (must match backend/app/services/validator.py) */
export const SCORE_WEIGHTS: Record<ScoreDimension, number> = {
	clarity: 0.25,
	specificity: 0.25,
	structure: 0.20,
	faithfulness: 0.30,
};

/** Display-friendly labels for each dimension */
export const DIMENSION_LABELS: Record<ScoreDimension, string> = {
	clarity: 'Clarity',
	specificity: 'Specificity',
	structure: 'Structure',
	faithfulness: 'Faithfulness',
};

/** Neon color per dimension for visual bars and indicators */
export const DIMENSION_COLORS: Record<ScoreDimension, string> = {
	clarity: 'neon-cyan',
	specificity: 'neon-purple',
	structure: 'neon-green',
	faithfulness: 'neon-yellow',
};

/** Ordered list of all dimensions for iteration */
export const ALL_DIMENSIONS: ScoreDimension[] = ['clarity', 'specificity', 'structure', 'faithfulness'];

/** Pipeline step status → Tailwind dot class mapping */
const STEP_DOT_CLASSES: Record<string, string> = {
	complete: 'bg-neon-green',
	running: 'bg-neon-cyan animate-pulse',
	error: 'bg-neon-red',
};

/** Get dot class for a pipeline step status (with pending fallback). */
export function stepDotClass(status: string): string {
	return STEP_DOT_CLASSES[status] ?? 'bg-text-dim/30';
}

/** Keyword patterns that associate analysis findings with score dimensions.
 *  Uses prefix matching (no trailing \b) so stems like "ambigu" match "ambiguous". */
const DIMENSION_PATTERNS: Record<ScoreDimension, RegExp> = {
	clarity: /\b(clear|clarity|ambigu|confus|instruct|explicit|unambiguous|readab)/i,
	specificity: /\b(specif|detail|vague|broad|general|concrete|precise|underspec)/i,
	structure: /\b(struct|organiz|format|section|layout|order\b|flow|hierarch)/i,
	faithfulness: /\b(intent|faithful|preserv|original|deviat|scope|core meaning|rewrit)/i,
};

/**
 * Tag an analysis finding with the score dimensions it relates to.
 * A finding may match zero, one, or multiple dimensions.
 */
export function tagFinding(text: string): ScoreDimension[] {
	return (Object.entries(DIMENSION_PATTERNS) as [ScoreDimension, RegExp][])
		.filter(([, pattern]) => pattern.test(text))
		.map(([dim]) => dim);
}

/**
 * Compute the weighted point contribution of a score (0-100) for a dimension.
 * E.g. clarity 95 × 0.25 = 23.75
 */
export function computeContribution(score: number, dimension: ScoreDimension): number {
	return score * SCORE_WEIGHTS[dimension];
}
