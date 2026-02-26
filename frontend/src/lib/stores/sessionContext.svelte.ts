/**
 * Session Context Store — tracks recent analyses and strategies across forges
 * within a single browser session. Used to provide context hints for subsequent
 * forge operations (e.g., "you've been working on coding prompts").
 */

import type { OptimizationResultState } from './optimization.svelte';

const MAX_ANALYSES = 5;
const MAX_STRATEGIES = 10;

interface RecentAnalysis {
	task_type: string;
	complexity: string;
	weaknesses: string[];
}

interface RecentStrategy {
	strategy: string;
	score: number;
}

class SessionContextState {
	recentAnalyses: RecentAnalysis[] = $state([]);
	recentStrategies: RecentStrategy[] = $state([]);

	/** Record a completed forge result into session context. */
	record(result: OptimizationResultState): void {
		if (result.task_type) {
			this.recentAnalyses = [
				{ task_type: result.task_type, complexity: result.complexity, weaknesses: result.weaknesses },
				...this.recentAnalyses,
			].slice(0, MAX_ANALYSES);
		}
		if (result.strategy && result.scores.overall > 0) {
			this.recentStrategies = [
				{ strategy: result.strategy, score: result.scores.overall },
				...this.recentStrategies,
			].slice(0, MAX_STRATEGIES);
		}
	}

	/**
	 * Build a context hint string summarizing the session's patterns.
	 * Suitable for injection into codebase_context.documentation.
	 */
	buildContextHint(): string {
		const parts: string[] = [];

		if (this.recentAnalyses.length > 0) {
			const types = [...new Set(this.recentAnalyses.map(a => a.task_type))];
			parts.push(`Recent task types: ${types.join(', ')}.`);

			const allWeaknesses = this.recentAnalyses.flatMap(a => a.weaknesses);
			const uniqueWeaknesses = [...new Set(allWeaknesses)].slice(0, 5);
			if (uniqueWeaknesses.length > 0) {
				parts.push(`Common weaknesses: ${uniqueWeaknesses.join(', ')}.`);
			}
		}

		if (this.recentStrategies.length > 0) {
			const bestStrategy = this.recentStrategies.reduce((a, b) => a.score > b.score ? a : b);
			parts.push(`Best-scoring strategy this session: ${bestStrategy.strategy} (${Math.round(bestStrategy.score * 10)}/10).`);
		}

		return parts.length > 0 ? `Session context: ${parts.join(' ')}` : '';
	}

	/** True when there is any session context worth injecting. */
	get hasContext(): boolean {
		return this.recentAnalyses.length > 0 || this.recentStrategies.length > 0;
	}

	reset(): void {
		this.recentAnalyses = [];
		this.recentStrategies = [];
	}
}

export const sessionContext = new SessionContextState();
