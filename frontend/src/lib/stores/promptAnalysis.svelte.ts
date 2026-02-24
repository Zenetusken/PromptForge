/**
 * Client-side prompt analysis store.
 * Provides real-time heuristic task type estimation and strategy recommendations
 * based on the user's prompt text and historical stats.
 */

import { estimateTaskType, type HeuristicResult } from '$lib/utils/promptHeuristics';
import { computeRecommendations, type RecommendationInput, type ScoredStrategy } from '$lib/utils/recommendation';
import { statsState } from '$lib/stores/stats.svelte';
import type { StatsResponse } from '$lib/api/client';

class PromptAnalysisState {
	/** Current heuristic analysis result. Null when text is too short or no match. */
	heuristic: HeuristicResult | null = $state(null);

	/** Top recommended strategies based on heuristic + stats. */
	recommendedStrategies: ScoredStrategy[] = $state([]);

	/** Whether analysis is in progress (debounce pending). */
	isAnalyzing: boolean = $state(false);

	private _debounceTimer: ReturnType<typeof setTimeout> | null = null;

	/**
	 * Debounced analysis — call on every text input change.
	 * Runs heuristic task type estimation and feeds it into the recommendation engine.
	 */
	analyzePrompt(text: string): void {
		if (this._debounceTimer) clearTimeout(this._debounceTimer);

		if (!text || text.length < 50) {
			this.heuristic = null;
			this.recommendedStrategies = [];
			this.isAnalyzing = false;
			return;
		}

		this.isAnalyzing = true;
		this._debounceTimer = setTimeout(() => {
			this.heuristic = estimateTaskType(text);
			this._computeRecommendations();
			this.isAnalyzing = false;
		}, 300);
	}

	/**
	 * Update with authoritative pipeline data after a forge completes.
	 * Overrides the heuristic with the actual classification.
	 */
	updateFromPipeline(taskType: string, complexity?: string): void {
		this.heuristic = {
			taskType: taskType as HeuristicResult['taskType'],
			confidence: 1.0,
			matchedKeywords: [],
		};
		this._computeRecommendations();
	}

	/** Clear analysis state. */
	reset(): void {
		if (this._debounceTimer) clearTimeout(this._debounceTimer);
		this.heuristic = null;
		this.recommendedStrategies = [];
		this.isAnalyzing = false;
	}

	/**
	 * Compute recommendations using the heuristic task type and stats data.
	 * Builds a synthetic RecommendationInput that emphasizes the estimated task type.
	 */
	private _computeRecommendations(): void {
		const stats = statsState.stats;
		if (!stats || !this.heuristic) {
			this.recommendedStrategies = [];
			return;
		}

		const input = buildRecommendationInput(stats);
		const result = computeRecommendations(input);

		if (result) {
			// Take top 3 recommendations
			this.recommendedStrategies = result.ranked.slice(0, 3);
		} else {
			this.recommendedStrategies = [];
		}
	}
}

/** Build a RecommendationInput from stats data. */
function buildRecommendationInput(stats: StatsResponse): RecommendationInput {
	return {
		strategyDistribution: stats.strategy_distribution ?? {},
		scoreByStrategy: stats.score_by_strategy ?? {},
		taskTypesByStrategy: stats.task_types_by_strategy ?? {},
		secondaryDistribution: stats.secondary_strategy_distribution ?? undefined,
		tagsByStrategy: stats.tags_by_strategy ?? undefined,
		scoreMatrix: stats.score_matrix ?? undefined,
		scoreVariance: stats.score_variance ?? undefined,
		confidenceByStrategy: stats.confidence_by_strategy ?? undefined,
		comboEffectiveness: stats.combo_effectiveness ?? undefined,
		improvementByStrategy: stats.improvement_by_strategy ?? undefined,
	};
}

export const promptAnalysis = new PromptAnalysisState();
