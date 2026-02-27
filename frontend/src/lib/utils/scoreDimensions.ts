export type ScoreDimension = 'clarity' | 'specificity' | 'structure' | 'faithfulness' | 'conciseness';

/** Scoring formula weights (must match backend/app/services/validator.py) */
export const SCORE_WEIGHTS: Record<ScoreDimension, number> = {
	clarity: 0.20,
	specificity: 0.20,
	structure: 0.15,
	faithfulness: 0.25,
	conciseness: 0.20,
};

/** Display-friendly labels for each dimension */
export const DIMENSION_LABELS: Record<ScoreDimension, string> = {
	clarity: 'Clarity',
	specificity: 'Specificity',
	structure: 'Structure',
	faithfulness: 'Faithfulness',
	conciseness: 'Conciseness',
};

/** Neon color per dimension for visual bars and indicators */
export const DIMENSION_COLORS: Record<ScoreDimension, string> = {
	clarity: 'neon-cyan',
	specificity: 'neon-purple',
	structure: 'neon-green',
	faithfulness: 'neon-yellow',
	conciseness: 'neon-teal',
};

/** Ordered list of all dimensions for iteration */
export const ALL_DIMENSIONS: ScoreDimension[] = ['clarity', 'specificity', 'structure', 'faithfulness', 'conciseness'];

/** Short 3-letter abbreviations for compact displays */
export const DIMENSION_ABBREVS: Record<ScoreDimension, string> = {
	clarity: 'CLR',
	specificity: 'SPC',
	structure: 'STR',
	faithfulness: 'FTH',
	conciseness: 'CNC',
};

/** Tooltip descriptions for each dimension */
export const DIMENSION_TOOLTIPS: Record<ScoreDimension, string> = {
	clarity: 'How clearly the prompt communicates intent',
	specificity: 'How concrete and detailed the instructions are',
	structure: 'How well-organized the prompt layout is',
	faithfulness: 'How well the original intent is preserved',
	conciseness: 'How efficiently the prompt uses tokens without redundancy',
};

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
	conciseness: /\b(concis|verbose|bloat|redund|token|length|compact|terse|efficien|brief|wordy)/i,
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
 * E.g. clarity 95 × 0.20 = 19.0
 */
export function computeContribution(score: number, dimension: ScoreDimension): number {
	return score * SCORE_WEIGHTS[dimension];
}

/** Supplementary (non-weighted) score dimensions */
export type SupplementaryDimension = 'framework_adherence';

export const SUPPLEMENTARY_META: Record<SupplementaryDimension, {
	label: string; color: string; abbrev: string; tooltip: string;
}> = {
	framework_adherence: {
		label: 'Strategy Fit',
		color: 'neon-orange',
		abbrev: 'ADH',
		tooltip: 'How well the optimized prompt adheres to the selected strategy framework',
	},
};

export const ALL_SUPPLEMENTARY: SupplementaryDimension[] = ['framework_adherence'];
