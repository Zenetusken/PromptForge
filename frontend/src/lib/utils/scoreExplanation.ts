import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
import { normalizeScore } from '$lib/utils/format';
import { SCORE_WEIGHTS, DIMENSION_LABELS, SUPPLEMENTARY_META, ALL_SUPPLEMENTARY, type ScoreDimension } from '$lib/utils/scoreDimensions';

type Scores = OptimizationResultState['scores'];

/**
 * Generate a plain-English narrative explaining the overall score.
 * Highlights the top contributor and the dimension with lowest contribution.
 * Appends supplementary dimension info when present.
 */
export function generateScoreExplanation(scores: Scores): string {
	const dims: { name: string; score: number; weight: number; contribution: number }[] = (
		Object.keys(SCORE_WEIGHTS) as ScoreDimension[]
	).map((dim) => {
		const score = normalizeScore(scores[dim]) ?? 0;
		const weight = Math.round(SCORE_WEIGHTS[dim] * 100);
		return { name: DIMENSION_LABELS[dim], score, weight, contribution: score * SCORE_WEIGHTS[dim] };
	});

	dims.sort((a, b) => b.contribution - a.contribution);

	const overall = normalizeScore(scores.overall) ?? 0;
	const top = dims[0];
	const bottom = dims[dims.length - 1];

	// Find the dimension with the highest weight for the closing sentence
	const heaviest = dims.reduce((a, b) => (a.weight >= b.weight ? a : b));

	let text =
		`Your overall score of ${overall} was primarily driven by ${top.name} ` +
		`(${top.score}, ${top.weight}% weight). ${bottom.name} ` +
		`(${bottom.score}, ${bottom.weight}% weight) had the lowest contribution. ` +
		`The scoring formula weights ${heaviest.name} highest at ${heaviest.weight}%.`;

	// Append supplementary dimension info when present
	for (const suppDim of ALL_SUPPLEMENTARY) {
		const suppScore = scores[suppDim as keyof typeof scores];
		if (suppScore != null) {
			const suppPct = normalizeScore(suppScore) ?? 0;
			const meta = SUPPLEMENTARY_META[suppDim];
			text += ` ${meta.label} scored ${suppPct} (supplementary, not in weighted average).`;
		}
	}

	return text;
}
