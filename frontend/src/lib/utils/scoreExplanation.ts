import type { OptimizationResultState } from '$lib/stores/optimization.svelte';
import { normalizeScore } from '$lib/utils/format';
import { SCORE_WEIGHTS, DIMENSION_LABELS, type ScoreDimension } from '$lib/utils/scoreDimensions';

type Scores = OptimizationResultState['scores'];

/**
 * Generate a plain-English narrative explaining the overall score.
 * Highlights the top contributor and the dimension with lowest contribution.
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

	return (
		`Your overall score of ${overall} was primarily driven by ${top.name} ` +
		`(${top.score}, ${top.weight}% weight). ${bottom.name} ` +
		`(${bottom.score}, ${bottom.weight}% weight) had the lowest contribution. ` +
		`The scoring formula weights Faithfulness highest at 30% \u2014 ` +
		`how well the optimization preserves your original intent.`
	);
}
