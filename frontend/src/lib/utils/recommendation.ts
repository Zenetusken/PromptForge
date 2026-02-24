/**
 * Strategy Explorer Recommendation Engine
 *
 * Multi-signal composite scoring algorithm for recommending untried optimization
 * strategies based on the user's historical task-type distribution, strategy
 * performance, and coverage gaps.
 *
 * Scoring signals (all normalized 0–1):
 *   1. Task-Type Affinity     — how well does the strategy's bestFor match the user's work?
 *   2. Performance Gap        — are tried strategies underperforming on overlapping task types?
 *   3. Diversity Bonus        — does this strategy cover task types not already well-served?
 *   4. Secondary Composite    — blended score from 5 sub-signals (frequency, reach, synergy,
 *                               familiarity, tag affinity) replacing the old separate bonuses
 *   5. Data Confidence        — how much data backs the recommendation? (multiplicative)
 *
 * Composite: (w_a×affinity + w_g×gap + w_d×diversity + w_sc×secondaryComposite) × confidence
 */

/**
 * Data Pipeline Audit (Phase 1 verification)
 *
 * Score normalization path:
 *   Backend DB     → 0.0–1.0 floats (clarity, specificity, structure, faithfulness)
 *   Backend API    → 1–10 integers via `normalize_score()` in `backend/app/utils/scores.py`
 *   Frontend stats → 0.0–1.0 floats (scoreByStrategy averages from /api/history/stats)
 *   Display        → 0–100 via `normalizeScore()` in `frontend/src/lib/utils/format.ts`
 *
 * This engine operates on the frontend 0.0–1.0 values from stats — no re-normalization needed.
 *
 * Edge cases handled:
 *   - Missing scoreByStrategy entries → treated as "no score data" (not zero)
 *   - Empty taskTypesByStrategy → affinity/gap/diversity all return 0
 *   - Null/undefined in stats response → destructured with `?? {}` at call site
 *   - Legacy strategy aliases → normalized in backend before reaching frontend
 */

import type { ScoreMatrixEntry, ScoreVarianceEntry, ComboEntry, ImprovementEntry } from '$lib/api/client';
import { ALL_STRATEGIES, STRATEGY_DETAILS, STRATEGY_LABELS } from './strategies';
import type { StrategyName } from './strategies';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Configurable weights for each scoring signal. All must be >= 0. */
export interface RecommendationWeights {
	/**
	 * Weight for task-type affinity signal.
	 * Higher = recommendations track the user's existing work patterns more closely.
	 * @default 0.50
	 */
	affinity: number;
	/**
	 * Weight for performance gap signal.
	 * Higher = favors strategies that address underperforming task types.
	 * @default 0.25
	 */
	gap: number;
	/**
	 * Weight for diversity/exploration signal.
	 * Higher = encourages trying strategies in uncovered territory.
	 * @default 0.25
	 */
	diversity: number;
	/**
	 * Weight for the blended secondary composite signal (5 sub-signals).
	 * @default 0.20
	 */
	secondary: number;
}

/** Internal blend weights for the SecondaryMetricProcessor. */
export interface SecondaryProcessorWeights {
	frequency: number;
	reach: number;
	synergy: number;
	familiarity: number;
	tagAffinity: number;
}

/** Breakdown of an individual strategy's scoring signals. */
export interface ScoredStrategy {
	name: StrategyName;
	label: string;
	motivation: string;
	/** Normalized 0–1: proportion of user's work matching this strategy's bestFor. */
	affinityScore: number;
	/** Normalized 0–1: degree to which tried strategies underperform on overlapping types. */
	gapScore: number;
	/** Normalized 0–1: proportion of bestFor types not well-served by tried strategies. */
	diversityScore: number;
	/** Normalized 0–1: familiarity from secondary framework usage (0 if no secondary data). */
	secondaryFamiliarityScore: number;
	/** Normalized 0–1: tag-based affinity boost (0 if no tag data). */
	tagAffinityBoost: number;
	/** Normalized 0–1: secondary usage rate relative to total optimizations. */
	frequencyScore: number;
	/** Normalized 0–1: cross-strategy reach proxy. */
	reachScore: number;
	/** Normalized 0–1: geometric mean bonus when familiarity AND tag affinity co-occur. */
	synergyScore: number;
	/** Normalized 0–1: blended output from SecondaryMetricProcessor. */
	secondaryComposite: number;
	/** Percentage (0–100) of compositeScore attributable to secondary signals. */
	secondaryInfluencePct: number;
	/** Multiplicative 0–1: data sufficiency dampener. */
	confidenceWeight: number;
	/** Final composite score (0–1). */
	compositeScore: number;
	/** Optional: score standard deviation from score_variance analytics. */
	scoreStddev?: number;
}

/** Insight generated from secondary metric analysis. */
export interface SecondaryInsight {
	type: 'tag_engagement' | 'familiarity' | 'frequency_impact';
	message: string;
	impact: number;
}

/** Confidence tier for the recommendation card display. */
export type ConfidenceTier = 'high' | 'moderate' | 'exploratory';

/** Confidence metadata attached to a recommendation. */
export interface RecommendationConfidence {
	tier: ConfidenceTier;
	/** Short label for the badge (e.g., "Strong match", "Worth trying"). */
	label: string;
	/** One-line reason shown on the card (e.g., "Matches your coding and analysis tasks"). */
	reason: string;
	/** Longer human-readable detail for tooltip hover — explains the "why" in plain language. */
	detail: string;
}

/** Complete recommendation result, or null when no recommendation applies. */
export interface RecommendationResult {
	/** The top-ranked untried strategy. */
	strategy: ScoredStrategy;
	/** All untried strategies sorted by composite score descending. */
	ranked: ScoredStrategy[];
	/** Confidence assessment for the recommendation. */
	confidence: RecommendationConfidence;
	/** Secondary metric insights for the top recommendation (0–3 items). */
	insights: SecondaryInsight[];
}

// Re-export shared analytics types from client for consumers that import from here
export type { ScoreMatrixEntry, ScoreVarianceEntry, ComboEntry, ImprovementEntry };

/** Input data shape matching StatsResponse fields. */
export interface RecommendationInput {
	strategyDistribution: Record<string, number>;
	scoreByStrategy: Record<string, number>;
	taskTypesByStrategy: Record<string, Record<string, number>>;
	secondaryDistribution?: Record<string, number>;
	tagsByStrategy?: Record<string, Record<string, number>>;
	/** Strategy × task-type score matrix for score-weighted affinity and precise gap analysis. */
	scoreMatrix?: Record<string, Record<string, ScoreMatrixEntry>>;
	/** Per-strategy score variance for tie-breaking in top performer selection. */
	scoreVariance?: Record<string, ScoreVarianceEntry>;
	/** Per-strategy average confidence scores. */
	confidenceByStrategy?: Record<string, number>;
	/** Primary × secondary combo effectiveness data. */
	comboEffectiveness?: Record<string, Record<string, ComboEntry>>;
	/** Per-strategy improvement rates. */
	improvementByStrategy?: Record<string, ImprovementEntry>;
}

/** Top performer result with confidence metadata. */
export interface TopPerformerResult {
	name: StrategyName;
	label: string;
	score: number;
	count: number;
	/** Whether the selection is statistically meaningful. */
	isSignificant: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default weights — affinity-dominant with balanced gap/diversity, plus blended secondary. */
export const DEFAULT_WEIGHTS: RecommendationWeights = {
	affinity: 0.50,
	gap: 0.25,
	diversity: 0.25,
	secondary: 0.20,
};

/** Default internal blend weights for the secondary composite processor. */
export const DEFAULT_SECONDARY_WEIGHTS: SecondaryProcessorWeights = {
	frequency: 0.20,
	reach: 0.15,
	synergy: 0.25,
	familiarity: 0.25,
	tagAffinity: 0.15,
};

/**
 * Minimum number of uses for a strategy to qualify as "top performer".
 * At count=3 we have marginally meaningful averages; count=2 is too noisy.
 */
const TOP_PERFORMER_MIN_COUNT = 3;

/**
 * Confidence curve midpoint.
 * At this many total optimizations, confidenceWeight reaches ~0.50.
 */
const CONFIDENCE_MIDPOINT = 10;

// ---------------------------------------------------------------------------
// Scoring Functions (pure, unit-testable)
// ---------------------------------------------------------------------------

/**
 * Compute the global task-type frequency map from per-strategy task breakdowns.
 * Returns both the frequency map and the total count for normalization.
 */
export function buildTaskFrequency(
	taskTypesByStrategy: Record<string, Record<string, number>>,
): { freq: Record<string, number>; total: number } {
	const freq: Record<string, number> = {};
	let total = 0;
	for (const tasks of Object.values(taskTypesByStrategy)) {
		for (const [taskType, count] of Object.entries(tasks)) {
			freq[taskType] = (freq[taskType] ?? 0) + count;
			total += count;
		}
	}
	return { freq, total };
}

/**
 * Task-Type Affinity Score (0–1).
 *
 * Measures what proportion of the user's historical optimizations fall within
 * this strategy's declared bestFor task types.
 *
 * When scoreMatrix is provided, each bestFor type's frequency is weighted by a
 * "need factor" derived from per-task-type performance gaps. Low existing performance
 * on a task type increases its weight, making strategies that target underperforming
 * areas score higher. Falls back to pure frequency when scoreMatrix is unavailable.
 *
 * Formula (basic): sum(taskFreq[t] for t in bestFor) / totalFreq
 * Formula (enhanced): sum(taskFreq[t] * needFactor[t] for t in bestFor) / sum(taskFreq[t] * needFactor[t] for all t)
 *
 * Returns 0 when totalFreq is 0 (no data) or when no bestFor types match.
 */
export function computeAffinityScore(
	bestFor: readonly string[],
	taskFreq: Record<string, number>,
	totalFreq: number,
	scoreMatrix?: Record<string, Record<string, { count: number; avg_score: number | null }>>,
): number {
	if (totalFreq === 0 || bestFor.length === 0) return 0;

	// When scoreMatrix is available, use score-weighted affinity
	if (scoreMatrix) {
		// Compute per-task-type average performance across all strategies
		const taskAvgScores: Record<string, { totalScore: number; totalCount: number }> = {};
		for (const typeMap of Object.values(scoreMatrix)) {
			for (const [taskType, entry] of Object.entries(typeMap)) {
				if (entry.avg_score !== null) {
					const accum = taskAvgScores[taskType] ?? { totalScore: 0, totalCount: 0 };
					accum.totalScore += entry.avg_score * entry.count;
					accum.totalCount += entry.count;
					taskAvgScores[taskType] = accum;
				}
			}
		}

		// needFactor: 1.0 + (1.0 - taskAvgScore) for each task type
		// Higher need = lower existing performance = more room for improvement
		let weightedMatch = 0;
		let weightedTotal = 0;
		let hasScoreData = false;

		for (const [taskType, freq] of Object.entries(taskFreq)) {
			const accum = taskAvgScores[taskType];
			let needFactor = 1.0;
			if (accum && accum.totalCount > 0) {
				const avgScore = accum.totalScore / accum.totalCount;
				needFactor = 1.0 + (1.0 - avgScore);
				hasScoreData = true;
			}
			const weighted = freq * needFactor;
			weightedTotal += weighted;
			if (bestFor.includes(taskType)) {
				weightedMatch += weighted;
			}
		}

		if (hasScoreData && weightedTotal > 0) {
			return weightedMatch / weightedTotal;
		}
	}

	// Fallback: pure frequency-based affinity
	let matchSum = 0;
	for (const t of bestFor) {
		matchSum += taskFreq[t] ?? 0;
	}
	return matchSum / totalFreq;
}

/**
 * Build a map of tried strategy names → their bestFor arrays.
 * Only includes strategies that appear in the distribution (i.e., have been used).
 */
export function buildTriedStrategyBestFor(
	distribution: Record<string, number>,
): Record<string, readonly string[]> {
	const result: Record<string, readonly string[]> = {};
	for (const name of Object.keys(distribution)) {
		const details = STRATEGY_DETAILS[name as StrategyName];
		if (details) {
			result[name] = details.bestFor;
		}
	}
	return result;
}

/**
 * Performance Gap Score (0–1).
 *
 * For each task type in the untried strategy's bestFor, checks whether tried
 * strategies targeting the same type are underperforming relative to the global
 * average score. A high gap score means there's room for improvement.
 *
 * When scoreMatrix is provided, uses per-task-type avg scores from the matrix
 * instead of strategy-wide averages for more precise gap detection.
 *
 * For each bestFor type:
 *   - Find all tried strategies whose bestFor includes this type
 *   - Compute their average score (weighted by usage count)
 *   - If avg < globalAvg: gap = 1 - (avg / globalAvg), clamped to [0,1]
 *   - If no tried strategies target this type: gap = 1.0 (completely uncovered)
 *   - If no score data for those strategies: gap = 0.0 (can't assess)
 *
 * Final: average across all bestFor types.
 */
export function computeGapScore(
	bestFor: readonly string[],
	triedBestFor: Record<string, readonly string[]>,
	scoreByStrategy: Record<string, number>,
	distribution: Record<string, number>,
	globalAvgScore: number | null,
	scoreMatrix?: Record<string, Record<string, { count: number; avg_score: number | null }>>,
): number {
	if (bestFor.length === 0) return 0;
	if (globalAvgScore === null || globalAvgScore === 0) return 0;

	let gapSum = 0;
	for (const taskType of bestFor) {
		// Find tried strategies that also target this task type
		let weightedScoreSum = 0;
		let totalCount = 0;
		let hasCoverage = false;
		let hasScoreData = false;

		for (const [stratName, stratBestFor] of Object.entries(triedBestFor)) {
			if (stratBestFor.includes(taskType)) {
				hasCoverage = true;

				// When scoreMatrix is available, use per-task-type score for this strategy
				if (scoreMatrix) {
					const matrixEntry = scoreMatrix[stratName]?.[taskType];
					if (matrixEntry && matrixEntry.avg_score !== null && matrixEntry.count > 0) {
						weightedScoreSum += matrixEntry.avg_score * matrixEntry.count;
						totalCount += matrixEntry.count;
						hasScoreData = true;
						continue;
					}
				}

				// Fallback: use strategy-wide average
				const score = scoreByStrategy[stratName];
				const count = distribution[stratName] ?? 0;
				if (score !== undefined && count > 0) {
					weightedScoreSum += score * count;
					totalCount += count;
					hasScoreData = true;
				}
			}
		}

		if (!hasCoverage) {
			// No tried strategy declares this type in bestFor → completely uncovered
			gapSum += 1.0;
		} else if (!hasScoreData) {
			// Tried strategies cover this type but have no scores → can't assess gap
			// gapSum += 0 (implicit)
		} else {
			const avgTriedScore = weightedScoreSum / totalCount;
			if (avgTriedScore < globalAvgScore) {
				// Tried strategies underperform → gap proportional to shortfall
				gapSum += Math.max(0, Math.min(1, 1 - avgTriedScore / globalAvgScore));
			}
			// If avgTriedScore >= globalAvgScore, gap = 0 (well-covered)
		}
	}

	return gapSum / bestFor.length;
}

/**
 * Diversity Score (0–1).
 *
 * Measures the proportion of the untried strategy's bestFor types that are NOT
 * already well-served by tried strategies. A type is "well-served" when at least
 * one tried strategy targets it AND that strategy's score is above the global average.
 *
 * Encourages exploring strategies that cover new ground.
 */
export function computeDiversityScore(
	bestFor: readonly string[],
	triedBestFor: Record<string, readonly string[]>,
	scoreByStrategy: Record<string, number>,
	globalAvgScore: number | null,
): number {
	if (bestFor.length === 0) return 0;

	let unservedCount = 0;
	for (const taskType of bestFor) {
		let isWellServed = false;
		for (const [stratName, stratBestFor] of Object.entries(triedBestFor)) {
			if (stratBestFor.includes(taskType)) {
				const score = scoreByStrategy[stratName];
				if (score !== undefined && globalAvgScore !== null && score >= globalAvgScore) {
					isWellServed = true;
					break;
				}
			}
		}
		if (!isWellServed) {
			unservedCount++;
		}
	}

	return unservedCount / bestFor.length;
}

/**
 * Data Confidence Weight (0–1).
 *
 * Hyperbolic saturation curve: confidenceWeight = 1 - 1 / (1 + total / midpoint)
 *
 * Behavior:
 *   - 0 optimizations → 0.00 (no data)
 *   - 5 optimizations → 0.33
 *   - 10 optimizations → 0.50
 *   - 20 optimizations → 0.67
 *   - 50 optimizations → 0.83
 *   - 100 optimizations → 0.91
 *
 * Multiplicative dampener: prevents high-confidence recommendations with little data.
 */
export function computeConfidenceWeight(totalOptimizations: number): number {
	if (totalOptimizations <= 0) return 0;
	return 1 - 1 / (1 + totalOptimizations / CONFIDENCE_MIDPOINT);
}

/**
 * Secondary Familiarity Score (0–1).
 *
 * Measures how familiar the user is with this strategy through secondary
 * framework usage. Normalized relative to the highest secondary count
 * across all strategies.
 *
 * A strategy with high secondary usage is a safer recommendation — the user
 * already benefits from its approach as a complement to their primary strategies.
 *
 * Returns 0 when the strategy has no secondary usage or when no secondary data exists.
 */
export function computeSecondaryFamiliarityScore(
	strategyName: string,
	secondaryDistribution: Record<string, number>,
): number {
	const count = secondaryDistribution[strategyName] ?? 0;
	if (count === 0) return 0;
	const maxCount = Math.max(...Object.values(secondaryDistribution));
	if (maxCount === 0) return 0;
	return count / maxCount;
}

/**
 * Build a case-insensitive global tag frequency map from per-strategy tag data.
 * Shared by `computeTagAffinityBoost` and `generateSecondaryInsights`.
 */
export function buildGlobalTags(
	tagsByStrategy: Record<string, Record<string, number>>,
): { tags: Record<string, number>; total: number } {
	const tags: Record<string, number> = {};
	let total = 0;
	for (const stratTags of Object.values(tagsByStrategy)) {
		for (const [tag, count] of Object.entries(stratTags)) {
			const normalized = tag.toLowerCase();
			tags[normalized] = (tags[normalized] ?? 0) + count;
			total += count;
		}
	}
	return { tags, total };
}

/**
 * Tag Affinity Boost (0–1).
 *
 * Checks if any of the candidate strategy's bestFor task types appear
 * as tags in the user's global tag profile built from all tried strategies.
 * This captures direct semantic overlap between what the user tags their
 * work as and what the strategy specializes in.
 *
 * Tags are compared case-insensitively. Returns 0 when no tag data exists.
 */
export function computeTagAffinityBoost(
	bestFor: readonly string[],
	tagsByStrategy: Record<string, Record<string, number>>,
): number {
	if (bestFor.length === 0) return 0;

	const { tags: globalTags, total: totalTags } = buildGlobalTags(tagsByStrategy);
	if (totalTags === 0) return 0;

	let matchSum = 0;
	for (const t of bestFor) {
		matchSum += globalTags[t.toLowerCase()] ?? 0;
	}
	return matchSum / totalTags;
}

/**
 * Frequency Score (0–1).
 *
 * How often this strategy appears as a secondary framework relative to
 * the total number of optimizations. Capped at 1.
 *
 * Returns 0 when totalOptimizations is 0 or the strategy has no secondary usage.
 */
export function computeFrequencyScore(
	strategyName: string,
	secondaryDistribution: Record<string, number>,
	totalOptimizations: number,
): number {
	if (totalOptimizations <= 0) return 0;
	const count = secondaryDistribution[strategyName] ?? 0;
	if (count === 0) return 0;
	return Math.min(count / totalOptimizations, 1);
}

/**
 * Reach Score (0–1).
 *
 * Cross-strategy versatility proxy. Measures how widely this strategy is used
 * as a secondary, normalized against a saturation cap K (number of tried primary
 * strategies, minimum 1).
 *
 * Returns 0 when the strategy has no secondary usage or numTriedPrimaries is 0.
 */
export function computeReachScore(
	strategyName: string,
	secondaryDistribution: Record<string, number>,
	numTriedPrimaries: number,
): number {
	const K = Math.max(numTriedPrimaries, 1);
	const count = secondaryDistribution[strategyName] ?? 0;
	if (count === 0) return 0;
	return Math.min(count, K) / K;
}

/**
 * Synergy Score (0–1).
 *
 * Geometric mean bonus when both familiarity and tag affinity co-occur.
 * Rewards convergence of multiple secondary signals.
 *
 * Returns 0 when either signal is 0.
 */
export function computeSynergyScore(
	familiarity: number,
	tagAffinity: number,
): number {
	if (familiarity <= 0 || tagAffinity <= 0) return 0;
	return Math.sqrt(familiarity * tagAffinity);
}

/**
 * Compute the blended secondary composite from all 5 sub-signals.
 *
 * This replaces the old separate secondary + tagAffinity bonuses with a single
 * richer 0–1 composite that carries 5 sub-signals: frequency, reach, synergy,
 * familiarity, and tagAffinity.
 */
export function computeSecondaryComposite(
	familiarity: number,
	tagAffinity: number,
	frequency: number,
	reach: number,
	weights: SecondaryProcessorWeights = DEFAULT_SECONDARY_WEIGHTS,
): number {
	const synergy = computeSynergyScore(familiarity, tagAffinity);
	return (
		weights.frequency * frequency +
		weights.reach * reach +
		weights.synergy * synergy +
		weights.familiarity * familiarity +
		weights.tagAffinity * tagAffinity
	);
}

/**
 * Combo Score (0–1).
 *
 * Measures how well a strategy performs as a secondary across all primary pairings.
 * Uses the combo_effectiveness data from the backend analytics.
 *
 * Returns 0 when no combo effectiveness data is available or the strategy
 * has never been used as a secondary.
 */
export function computeComboScore(
	strategyName: string,
	comboEffectiveness: Record<string, Record<string, { count: number; avg_score: number | null }>>,
	globalAvgScore: number | null,
): number {
	if (!comboEffectiveness || globalAvgScore === null || globalAvgScore === 0) return 0;

	let totalWeightedScore = 0;
	let totalCount = 0;

	for (const secondaries of Object.values(comboEffectiveness)) {
		const entry = secondaries[strategyName];
		if (entry && entry.avg_score !== null && entry.count > 0) {
			totalWeightedScore += entry.avg_score * entry.count;
			totalCount += entry.count;
		}
	}

	if (totalCount === 0) return 0;

	const avgComboScore = totalWeightedScore / totalCount;
	// Normalize: how much better than average? Clamped to [0, 1]
	// If combo avg >= global avg, score is proportional to outperformance
	// If combo avg < global avg, score is still positive but reduced
	return Math.max(0, Math.min(1, avgComboScore / globalAvgScore));
}

/**
 * Compute the composite recommendation score for a single untried strategy.
 *
 * Base signals (affinity, gap, diversity) are weighted and summed.
 * The secondary composite replaces the old separate bonus signals.
 * The entire sum is then multiplied by the confidence dampener.
 *
 * composite = (w_a×affinity + w_g×gap + w_d×diversity + w_sc×secondaryComposite) × confidence
 */
export function computeCompositeScore(
	affinity: number,
	gap: number,
	diversity: number,
	confidence: number,
	weights: RecommendationWeights,
	secondaryComposite: number = 0,
): number {
	const base = weights.affinity * affinity + weights.gap * gap + weights.diversity * diversity;
	const secondary = weights.secondary * secondaryComposite;
	return (base + secondary) * confidence;
}

// ---------------------------------------------------------------------------
// Confidence Tier Classification
// ---------------------------------------------------------------------------

/**
 * Generate human-readable insight for a recommendation.
 *
 * Tier thresholds:
 *   High:        composite > 0.30 AND confidence > 0.5
 *   Moderate:    composite > 0.10
 *   Exploratory: everything else
 *
 * Only references task types the user has actually used — never mentions
 * bestFor types absent from the user's history (they're noise, not signal).
 *
 * When secondaryCount > 0, adds a mention to the tooltip detail text and
 * uses secondary-aware reason text in moderate tier.
 */
export function classifyConfidence(
	scored: ScoredStrategy,
	taskFreq: Record<string, number>,
	secondaryCount: number = 0,
): RecommendationConfidence {
	const { compositeScore, confidenceWeight, affinityScore, diversityScore, gapScore } = scored;
	const details = STRATEGY_DETAILS[scored.name];
	const bestFor = details?.bestFor ?? [];

	// Only task types from bestFor that the user actually has in their history
	const matchingTypes = bestFor
		.filter((t) => (taskFreq[t] ?? 0) > 0)
		.sort((a, b) => (taskFreq[b] ?? 0) - (taskFreq[a] ?? 0));

	// Format a list: "coding and analysis" or "coding, analysis, and writing"
	const formatList = (types: string[]): string => {
		if (types.length === 0) return '';
		if (types.length === 1) return types[0];
		if (types.length === 2) return `${types[0]} and ${types[1]}`;
		return `${types.slice(0, -1).join(', ')}, and ${types[types.length - 1]}`;
	};

	// Build the tooltip detail — focused on the user's actual work patterns
	const detailParts: string[] = [];
	if (matchingTypes.length > 0) {
		const pct = Math.round(affinityScore * 100);
		detailParts.push(`${pct}% of your work is ${formatList(matchingTypes)} tasks`);
	}
	if (gapScore > 0.2 && matchingTypes.length > 0) {
		detailParts.push(`Current strategies may be underperforming on ${formatList(matchingTypes)}`);
	}
	if (secondaryCount > 0) {
		detailParts.push(`Already used ${secondaryCount}× as secondary`);
	}
	if (detailParts.length === 0) {
		detailParts.push('A different approach to complement your toolkit');
	}
	const detail = detailParts.join('. ');

	// --- High tier: strong signal backed by data ---
	if (compositeScore > 0.30 && confidenceWeight > 0.5) {
		const reason = matchingTypes.length > 0
			? `Matches your ${formatList(matchingTypes.slice(0, 2))} tasks`
			: 'Strong match across your workflow';
		return { tier: 'high', label: 'Strong match', reason, detail };
	}

	// --- Moderate tier: meaningful signal ---
	if (compositeScore > 0.10) {
		let reason: string;
		if (affinityScore > 0.2 && matchingTypes.length > 0) {
			reason = `Relevant to your ${formatList(matchingTypes.slice(0, 2))} work`;
		} else if (secondaryCount > 0) {
			reason = 'Already in your toolkit — try it as primary';
		} else if (diversityScore > 0.5) {
			reason = 'Covers different territory from your current strategies';
		} else if (gapScore > 0.3) {
			reason = 'May improve results on underperforming task types';
		} else {
			reason = 'Complements your existing strategies';
		}
		return { tier: 'moderate', label: 'Worth trying', reason, detail };
	}

	// --- Exploratory: low signal or low data ---
	return {
		tier: 'exploratory',
		label: 'Explore',
		reason: 'Broaden your strategy toolkit',
		detail: confidenceWeight < 0.3
			? 'Keep forging to build up enough data for personalized recommendations'
			: detail,
	};
}

// ---------------------------------------------------------------------------
// Secondary Insight Generator
// ---------------------------------------------------------------------------

/**
 * Generate 0–3 insight messages from secondary metric analysis.
 *
 * Insights are sorted by impact (highest first) and only included when
 * they cross minimum thresholds — avoids noise on low-data profiles.
 */
export function generateSecondaryInsights(
	scored: ScoredStrategy,
	secondaryCount: number,
	tagsByStrategy: Record<string, Record<string, number>>,
): SecondaryInsight[] {
	const insights: SecondaryInsight[] = [];

	// 1. Tag engagement — when tag affinity is meaningful
	if (scored.tagAffinityBoost > 0.1) {
		const { tags: globalTags } = buildGlobalTags(tagsByStrategy);
		const details = STRATEGY_DETAILS[scored.name];
		const bestFor = details?.bestFor ?? [];
		const matchingTags = bestFor
			.filter((t) => (globalTags[t.toLowerCase()] ?? 0) > 0)
			.slice(0, 3);
		if (matchingTags.length > 0) {
			insights.push({
				type: 'tag_engagement',
				message: `Boosted by engagement across ${matchingTags.length} related tag${matchingTags.length > 1 ? 's' : ''}: ${matchingTags.join(', ')}`,
				impact: scored.tagAffinityBoost,
			});
		}
	}

	// 2. Familiarity — when user has secondary usage
	const hasFamiliarity = secondaryCount > 0 && scored.secondaryFamiliarityScore > 0.1;
	if (hasFamiliarity) {
		insights.push({
			type: 'familiarity',
			message: `Already in your toolkit (${secondaryCount}× as secondary), contributing ${scored.secondaryInfluencePct}% to recommendation`,
			impact: scored.secondaryFamiliarityScore,
		});
	}

	// 3. Frequency impact — only when familiarity didn't already report the percentage
	if (!hasFamiliarity && scored.secondaryInfluencePct > 5) {
		insights.push({
			type: 'frequency_impact',
			message: `Secondary signals contribute ${scored.secondaryInfluencePct}% to final score`,
			impact: scored.secondaryInfluencePct / 100,
		});
	}

	// Sort by impact descending
	insights.sort((a, b) => b.impact - a.impact);
	return insights;
}

// ---------------------------------------------------------------------------
// Top Performer Selection
// ---------------------------------------------------------------------------

/**
 * Select the top-performing tried strategy.
 *
 * Requirements:
 *   - Must have at least TOP_PERFORMER_MIN_COUNT uses (default 3)
 *   - Must have score data
 *   - Selected by highest weighted average score
 *   - Ties broken by lower variance (more consistent), then higher usage count,
 *     then alphabetical name for determinism
 *
 * The `isSignificant` flag indicates whether the count is high enough
 * for the average to be statistically meaningful (count >= 5).
 */
export function selectTopPerformer(
	distribution: Record<string, number>,
	scoreByStrategy: Record<string, number>,
	minCount: number = TOP_PERFORMER_MIN_COUNT,
	scoreVariance?: Record<string, ScoreVarianceEntry>,
): TopPerformerResult | null {
	let best: TopPerformerResult | null = null;
	let bestStddev: number | undefined;

	for (const [name, count] of Object.entries(distribution)) {
		if (count < minCount) continue;
		const score = scoreByStrategy[name];
		if (score === undefined) continue;

		const candidate: TopPerformerResult = {
			name: name as StrategyName,
			label: STRATEGY_LABELS[name as StrategyName] ?? name,
			score,
			count,
			isSignificant: count >= 5,
		};
		const candidateStddev = scoreVariance?.[name]?.stddev;

		if (!best) {
			best = candidate;
			bestStddev = candidateStddev;
		} else if (candidate.score > best.score) {
			best = candidate;
			bestStddev = candidateStddev;
		} else if (candidate.score === best.score) {
			// Tie-break 1: lower variance wins (more consistent)
			if (candidateStddev !== undefined && bestStddev !== undefined) {
				if (candidateStddev < bestStddev) {
					best = candidate;
					bestStddev = candidateStddev;
					continue;
				} else if (candidateStddev > bestStddev) {
					continue;
				}
			}
			// Tie-break 2: higher count wins
			if (candidate.count > best.count) {
				best = candidate;
				bestStddev = candidateStddev;
			} else if (candidate.count === best.count && candidate.name < best.name) {
				best = candidate;
				bestStddev = candidateStddev;
			}
		}
	}

	return best;
}

// ---------------------------------------------------------------------------
// Main Recommendation Engine
// ---------------------------------------------------------------------------

/**
 * Compute ranked strategy recommendations from backend stats data.
 *
 * Returns null in these edge cases:
 *   - No optimizations at all (empty distribution)
 *   - All 10 strategies have been tried (no untried strategies)
 *
 * When task-type data is unavailable, falls back to exploration mode
 * with all signals except affinity zeroed.
 */
export function computeRecommendations(
	input: RecommendationInput,
	weights: RecommendationWeights = DEFAULT_WEIGHTS,
): RecommendationResult | null {
	const {
		strategyDistribution, scoreByStrategy, taskTypesByStrategy,
		secondaryDistribution, tagsByStrategy,
		scoreMatrix, scoreVariance, comboEffectiveness,
	} = input;

	// Edge case: no data at all
	const totalOptimizations = Object.values(strategyDistribution).reduce((s, c) => s + c, 0);
	if (totalOptimizations === 0) return null;

	// Find untried strategies
	const untriedNames = ALL_STRATEGIES.filter((s) => !(s in strategyDistribution));
	if (untriedNames.length === 0) return null;

	// Build shared data structures
	const { freq: taskFreq, total: totalFreq } = buildTaskFrequency(taskTypesByStrategy);
	const triedBestFor = buildTriedStrategyBestFor(strategyDistribution);
	const confidence = computeConfidenceWeight(totalOptimizations);

	// Global average score across all tried strategies (weighted by count)
	let globalAvgScore: number | null = null;
	{
		let weightedSum = 0;
		let totalCount = 0;
		for (const [name, count] of Object.entries(strategyDistribution)) {
			const score = scoreByStrategy[name];
			if (score !== undefined) {
				weightedSum += score * count;
				totalCount += count;
			}
		}
		if (totalCount > 0) {
			globalAvgScore = weightedSum / totalCount;
		}
	}

	const numTriedPrimaries = Object.keys(strategyDistribution).length;
	const secDist = secondaryDistribution ?? {};
	const tagStrat = tagsByStrategy ?? {};

	const comboEff = comboEffectiveness ?? {};

	// Score each untried strategy
	const scored: ScoredStrategy[] = untriedNames.map((name) => {
		const details = STRATEGY_DETAILS[name];
		const bestFor = details?.bestFor ?? [];
		const motivation = details?.motivation ?? '';
		const label = STRATEGY_LABELS[name] ?? name;

		const affinityScore = computeAffinityScore(bestFor, taskFreq, totalFreq, scoreMatrix);
		const gapScore = computeGapScore(
			bestFor,
			triedBestFor,
			scoreByStrategy,
			strategyDistribution,
			globalAvgScore,
			scoreMatrix,
		);
		const diversityScore = computeDiversityScore(
			bestFor,
			triedBestFor,
			scoreByStrategy,
			globalAvgScore,
		);
		const secondaryFamiliarityScore = computeSecondaryFamiliarityScore(name, secDist);
		const tagAffinityBoostValue = computeTagAffinityBoost(bestFor, tagStrat);
		const frequencyScore = computeFrequencyScore(name, secDist, totalOptimizations);
		const reachScore = computeReachScore(name, secDist, numTriedPrimaries);
		const synergyScore = computeSynergyScore(secondaryFamiliarityScore, tagAffinityBoostValue);
		const comboScoreValue = computeComboScore(name, comboEff, globalAvgScore);
		const secondaryComp = computeSecondaryComposite(
			secondaryFamiliarityScore,
			tagAffinityBoostValue,
			frequencyScore,
			reachScore,
		) + comboScoreValue * 0.10;  // Combo adds ~10% bonus to secondary composite
		const compositeScore = computeCompositeScore(
			affinityScore,
			gapScore,
			diversityScore,
			confidence,
			weights,
			secondaryComp,
		);

		// Compute secondary influence percentage
		const baseOnly = computeCompositeScore(
			affinityScore, gapScore, diversityScore, confidence,
			{ ...weights, secondary: 0 },
		);
		const secondaryInfluencePct = compositeScore > 0
			? Math.round(((compositeScore - baseOnly) / compositeScore) * 100)
			: 0;

		return {
			name,
			label,
			motivation,
			affinityScore,
			gapScore,
			diversityScore,
			secondaryFamiliarityScore,
			tagAffinityBoost: tagAffinityBoostValue,
			frequencyScore,
			reachScore,
			synergyScore,
			secondaryComposite: secondaryComp,
			secondaryInfluencePct,
			confidenceWeight: confidence,
			compositeScore,
			scoreStddev: scoreVariance?.[name]?.stddev,
		};
	});

	// Sort: composite descending, then alphabetical name for determinism
	scored.sort((a, b) => {
		if (b.compositeScore !== a.compositeScore) return b.compositeScore - a.compositeScore;
		return a.name.localeCompare(b.name);
	});

	const top = scored[0];
	const topSecondaryCount = secDist[top.name] ?? 0;
	const confidenceTier = classifyConfidence(top, taskFreq, topSecondaryCount);
	const insights = generateSecondaryInsights(top, topSecondaryCount, tagStrat);

	return {
		strategy: top,
		ranked: scored,
		confidence: confidenceTier,
		insights,
	};
}
