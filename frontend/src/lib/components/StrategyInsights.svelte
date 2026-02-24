<script lang="ts">
	import type { StatsResponse } from "$lib/api/client";
	import { normalizeScore } from "$lib/utils/format";
	import {
		ALL_STRATEGIES,
		STRATEGY_LABELS,
		STRATEGY_DESCRIPTIONS,
		STRATEGY_DETAILS,
		getStrategyColor,
	} from "$lib/utils/strategies";
	import { getTaskTypeColor } from "$lib/utils/taskTypes";
	import type {
		StrategyName,
		StrategyColorMeta,
	} from "$lib/utils/strategies";
	import {
		computeRecommendations,
		selectTopPerformer,
		buildTaskFrequency,
		buildGlobalTags,
	} from "$lib/utils/recommendation";
	import type {
		RecommendationResult,
		TopPerformerResult,
		ScoredStrategy,
		RecommendationConfidence,
		ConfidenceTier,
	} from "$lib/utils/recommendation";
	import { Tooltip, MetaBadge } from "./ui";

	let {
		stats,
		lastPrompt = "",
		onStrategySelect,
	}: {
		stats: StatsResponse;
		lastPrompt?: string;
		onStrategySelect?: (strategy: string) => void;
	} = $props();

	let expandedStrategy: string | null = $state(null);
	let showSecondaryOverlay: boolean = $state(true);
	let showRunnerUps: boolean = $state(false);

	// --- Shared derived data ---
	const distribution = $derived(stats.strategy_distribution ?? {});
	const scoreByStrategy = $derived(stats.score_by_strategy ?? {});
	const taskTypesByStrategy = $derived(stats.task_types_by_strategy ?? {});
	const secondaryDistribution = $derived(
		stats.secondary_strategy_distribution ?? {},
	);
	const tagsByStrategy = $derived(stats.tags_by_strategy ?? {});
	const total = $derived(
		Object.values(distribution).reduce((sum, c) => sum + c, 0),
	);
	const hasAnySecondary = $derived(
		Object.values(secondaryDistribution).some((c) => c > 0),
	);

	const CONFIDENCE_TIER_COLORS: Record<
		ConfidenceTier,
		{ text: string; bg: string; border: string }
	> = {
		high: {
			text: "text-neon-green/80",
			bg: "bg-neon-green/5",
			border: "border-neon-green/15",
		},
		moderate: {
			text: "text-neon-cyan/70",
			bg: "bg-neon-cyan/5",
			border: "border-neon-cyan/15",
		},
		exploratory: {
			text: "text-neon-purple/70",
			bg: "bg-neon-purple/5",
			border: "border-neon-purple/15",
		},
	};

	const CONFIDENCE_GLOW_COLORS: Record<ConfidenceTier, string> = {
		high: "rgba(34, 255, 136, 0.25)",
		moderate: "rgba(0, 229, 255, 0.20)",
		exploratory: "rgba(168, 85, 247, 0.20)",
	};

	type InsightCategory =
		| "task_match"
		| "coverage_gap"
		| "new_territory"
		| "familiar_pick"
		| "tag_alignment"
		| "usage_pattern"
		| "signal_synergy"
		| "data_profile";

	interface RichInsight {
		category: InsightCategory;
		icon: string;
		message: string;
		priority: number;
	}

	const INSIGHT_CATEGORY_COLORS: Record<
		InsightCategory,
		{ text: string; textDim: string; border: string; glow: string }
	> = {
		task_match: {
			text: "text-neon-green",
			textDim: "text-neon-green/70",
			border: "border-l-neon-green/30",
			glow: "34, 255, 136",
		},
		coverage_gap: {
			text: "text-neon-red",
			textDim: "text-neon-red/70",
			border: "border-l-neon-red/30",
			glow: "255, 51, 102",
		},
		new_territory: {
			text: "text-neon-cyan",
			textDim: "text-neon-cyan/70",
			border: "border-l-neon-cyan/30",
			glow: "0, 229, 255",
		},
		familiar_pick: {
			text: "text-neon-purple",
			textDim: "text-neon-purple/70",
			border: "border-l-neon-purple/30",
			glow: "168, 85, 247",
		},
		tag_alignment: {
			text: "text-neon-teal",
			textDim: "text-neon-teal/70",
			border: "border-l-neon-teal/30",
			glow: "0, 212, 170",
		},
		usage_pattern: {
			text: "text-neon-orange",
			textDim: "text-neon-orange/70",
			border: "border-l-neon-orange/30",
			glow: "255, 140, 0",
		},
		signal_synergy: {
			text: "text-neon-indigo",
			textDim: "text-neon-indigo/70",
			border: "border-l-neon-indigo/30",
			glow: "123, 97, 255",
		},
		data_profile: {
			text: "text-neon-blue",
			textDim: "text-neon-blue/70",
			border: "border-l-neon-blue/30",
			glow: "77, 142, 255",
		},
	};

	// Unique SVG icons per insight category — each has a distinct silhouette readable at 11px.
	// All use currentColor for color inheritance from the parent's text-color class.
	const INSIGHT_SVG_ICONS: Record<InsightCategory, string> = {
		// Bullseye: concentric rings + center dot
		task_match: `<svg width="11" height="11" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.2"/><circle cx="6" cy="6" r="2.5" stroke="currentColor" stroke-width="1"/><circle cx="6" cy="6" r="0.8" fill="currentColor"/></svg>`,
		// Arrow up: chevron + vertical stem
		coverage_gap: `<svg width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M3.5 6L6 3L8.5 6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 4V10.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>`,
		// Compass rose: four-point star with emphasized north
		new_territory: `<svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor"><path d="M6 0.5L7.2 4.8L11.5 6L7.2 7.2L6 11.5L4.8 7.2L0.5 6L4.8 4.8Z"/></svg>`,
		// Cycle: two curved arrows forming a refresh loop
		familiar_pick: `<svg width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M8.5 3A4 4 0 0 0 3 4.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><path d="M5 3L3 4.5L4.5 6" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/><path d="M3.5 9A4 4 0 0 0 9 7.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><path d="M7 9L9 7.5L7.5 6" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
		// Tag: label shape with hole
		tag_alignment: `<svg width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M1.5 2.5H7L10.5 6L7 9.5H1.5Z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/><circle cx="4" cy="6" r="1" fill="currentColor"/></svg>`,
		// Bar chart: three ascending bars
		usage_pattern: `<svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor"><rect x="1.5" y="7" width="2.2" height="4" rx="0.5"/><rect x="4.9" y="4.5" width="2.2" height="6.5" rx="0.5"/><rect x="8.3" y="2" width="2.2" height="9" rx="0.5"/></svg>`,
		// Node convergence: center dot with radiating connections
		signal_synergy: `<svg width="11" height="11" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="1.2" fill="currentColor"/><path d="M2 2L4.8 4.8M10 2L7.2 4.8M2 10L4.8 7.2M10 10L7.2 7.2" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/><circle cx="2" cy="2" r="0.7" fill="currentColor"/><circle cx="10" cy="2" r="0.7" fill="currentColor"/><circle cx="2" cy="10" r="0.7" fill="currentColor"/><circle cx="10" cy="10" r="0.7" fill="currentColor"/></svg>`,
		// Gauge: semicircle arc + needle + pivot
		data_profile: `<svg width="11" height="11" viewBox="0 0 12 12" fill="none"><path d="M1.5 9A5.2 5.2 0 0 1 10.5 9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><path d="M6 8.5L7.8 4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><circle cx="6" cy="8.5" r="0.8" fill="currentColor"/></svg>`,
	};

	interface SignalMeta {
		humanName: string;
		explanation: string;
	}

	const SIGNAL_META: Record<string, SignalMeta> = {
		affinityScore: {
			humanName: "Task affinity",
			explanation: "How well this strategy fits your typical task types",
		},
		gapScore: {
			humanName: "Performance gap",
			explanation: "Opportunity to improve on underperforming task types",
		},
		diversityScore: {
			humanName: "Coverage diversity",
			explanation:
				"Covers task types not well-served by current strategies",
		},
		secondaryComposite: {
			humanName: "Secondary signals",
			explanation:
				"Blended score from familiarity, tags, frequency, and synergy",
		},
		secondaryFamiliarityScore: {
			humanName: "Familiarity",
			explanation: "Prior exposure through secondary framework usage",
		},
		tagAffinityBoost: {
			humanName: "Tag affinity",
			explanation:
				"Overlap between your tags and this strategy's strengths",
		},
		frequencyScore: {
			humanName: "Usage frequency",
			explanation:
				"How often this appears in your secondary framework choices",
		},
		synergyScore: {
			humanName: "Signal synergy",
			explanation:
				"Bonus from multiple secondary signals reinforcing each other",
		},
	};

	interface SignalBreakdown {
		fieldName: string;
		humanName: string;
		explanation: string;
		score: number;
	}

	function getTopSignals(
		strategy: ScoredStrategy,
		count: number = 3,
	): SignalBreakdown[] {
		const fields: [string, number][] = [
			["affinityScore", strategy.affinityScore],
			["gapScore", strategy.gapScore],
			["diversityScore", strategy.diversityScore],
			["secondaryComposite", strategy.secondaryComposite],
			["secondaryFamiliarityScore", strategy.secondaryFamiliarityScore],
			["tagAffinityBoost", strategy.tagAffinityBoost],
			["frequencyScore", strategy.frequencyScore],
			["synergyScore", strategy.synergyScore],
		];
		return fields
			.filter(([, score]) => score > 0)
			.sort(([, a], [, b]) => b - a)
			.slice(0, count)
			.map(([fieldName, score]) => ({
				fieldName,
				humanName: SIGNAL_META[fieldName]?.humanName ?? fieldName,
				explanation: SIGNAL_META[fieldName]?.explanation ?? "",
				score,
			}));
	}

	function getHeadlineSummary(strategy: ScoredStrategy): string {
		const signals = getTopSignals(strategy, 1);
		if (signals.length === 0) return strategy.motivation;
		switch (signals[0].fieldName) {
			case "affinityScore":
				return `Your work profile and this strategy are a natural fit`;
			case "gapScore":
				return `Targets a blind spot in your current strategy mix`;
			case "diversityScore":
				return `Expands your toolkit into uncovered territory`;
			case "secondaryComposite":
				return `Strong secondary signals back this as your next primary`;
			case "secondaryFamiliarityScore":
				return `A familiar complement — ready to take the lead`;
			case "tagAffinityBoost":
				return `Your labeling patterns align with this strategy's DNA`;
			case "frequencyScore":
				return `The strategy you keep reaching for as a secondary`;
			case "synergyScore":
				return `Everything in your profile points in the same direction`;
			default:
				return strategy.motivation;
		}
	}

	function getConfidenceRationale(
		confidence: RecommendationConfidence,
		totalOpts: number,
		triedStrategyCount: number,
	): string {
		if (confidence.tier === "high") {
			return `Strong signal from ${totalOpts} optimizations across ${triedStrategyCount} of ${ALL_STRATEGIES.length} strategies \u2014 this recommendation is well-supported by your history.`;
		} else if (confidence.tier === "moderate") {
			return `Promising pattern from ${totalOpts} optimizations across ${triedStrategyCount} of ${ALL_STRATEGIES.length} strategies. A few more forges will sharpen this pick.`;
		}
		if (totalOpts < 10) {
			return `With ${totalOpts} optimizations across ${triedStrategyCount} of ${ALL_STRATEGIES.length} strategies, this is an early suggestion. Keep forging to unlock sharper recommendations.`;
		}
		return `An exploratory pick to add variety to your toolkit. Try it and see how it scores.`;
	}

	function generateRichInsights(
		rec: ScoredStrategy,
		taskFreqData: { freq: Record<string, number>; total: number },
		globalTagData: { tags: Record<string, number>; total: number },
		totalOpts: number,
		triedStrategyCount: number,
		secondaryCount: number,
		secDistribution: Record<string, number>,
	): RichInsight[] {
		const insights: RichInsight[] = [];
		const details = STRATEGY_DETAILS[rec.name];
		const bestFor = details?.bestFor ?? [];
		const matchingBestFor = bestFor.filter(
			(t) => (taskFreqData.freq[t] ?? 0) > 0,
		);
		const formatTypes = (types: string[]) => {
			if (types.length <= 1) return types[0] ?? "";
			if (types.length === 2) return `${types[0]} and ${types[1]}`;
			return `${types.slice(0, -1).join(", ")}, and ${types[types.length - 1]}`;
		};

		// 1. Task Match — specific type COUNTS (not percentages — tooltip handles that)
		if (rec.affinityScore >= 0.15 && matchingBestFor.length > 0) {
			const typesWithCounts = matchingBestFor
				.slice(0, 3)
				.map((t) => ({ type: t, count: taskFreqData.freq[t] ?? 0 }))
				.sort((a, b) => b.count - a.count);
			let message: string;
			if (typesWithCounts.length >= 2) {
				message = `Built for ${typesWithCounts[0].type} (${typesWithCounts[0].count}\u00d7) and ${typesWithCounts[1].type} (${typesWithCounts[1].count}\u00d7) \u2014 your highest-volume task types`;
			} else {
				message = `Specializes in ${typesWithCounts[0].type} tasks (${typesWithCounts[0].count} in your history) \u2014 your most common work`;
			}
			insights.push({
				category: "task_match",
				icon: INSIGHT_SVG_ICONS.task_match,
				message,
				priority: rec.affinityScore,
			});
		}

		// 2. Coverage Gap — performance angle (not type names — task_match handles those)
		if (rec.gapScore >= 0.2 && matchingBestFor.length > 0) {
			const types = formatTypes(matchingBestFor.slice(0, 2));
			const message =
				rec.gapScore >= 0.5
					? `Your current strategies score below average on ${types} \u2014 this approach tackles them differently`
					: `There's room to lift ${types} results with a fresh strategic angle`;
			insights.push({
				category: "coverage_gap",
				icon: INSIGHT_SVG_ICONS.coverage_gap,
				message,
				priority: rec.gapScore,
			});
		}

		// 3. New Territory — name specific UNCOVERED types (not vague statements)
		if (rec.diversityScore >= 0.3) {
			const uncoveredTypes = bestFor.filter(
				(t) => (taskFreqData.freq[t] ?? 0) === 0,
			);
			let message: string;
			if (uncoveredTypes.length > 0) {
				const types = formatTypes(uncoveredTypes.slice(0, 2));
				message = `Opens up ${types} tasks \u2014 a capability your current toolkit lacks`;
			} else if (rec.diversityScore >= 0.6) {
				message = `Tackles familiar task types from an angle your current strategies don't cover well`;
			} else {
				message = `Brings dedicated focus to task types your toolkit handles but doesn't specialize in`;
			}
			insights.push({
				category: "new_territory",
				icon: INSIGHT_SVG_ICONS.new_territory,
				message,
				priority: rec.diversityScore,
			});
		}

		// 4. Familiar Pick — promotion narrative (not raw count — tooltip handles that)
		if (secondaryCount >= 2) {
			const message =
				secondaryCount >= 4
					? `Proven as a complement ${secondaryCount} times \u2014 ready to step up as a primary strategy`
					: `You've seen this work alongside your primaries \u2014 a natural candidate for promotion`;
			insights.push({
				category: "familiar_pick",
				icon: INSIGHT_SVG_ICONS.familiar_pick,
				message,
				priority: rec.secondaryFamiliarityScore,
			});
		}

		// 5. Tag Alignment — specific tags with COUNTS (not just names)
		if (rec.tagAffinityBoost >= 0.08) {
			const matchingTags = bestFor
				.filter((t) => (globalTagData.tags[t.toLowerCase()] ?? 0) > 0)
				.slice(0, 3);
			if (matchingTags.length > 0) {
				const tagStrs = matchingTags.map((t) => {
					const count = globalTagData.tags[t.toLowerCase()] ?? 0;
					return `#${t} (${count}\u00d7)`;
				});
				const formatted =
					tagStrs.length <= 2
						? tagStrs.join(" and ")
						: `${tagStrs.slice(0, -1).join(", ")}, and ${tagStrs[tagStrs.length - 1]}`;
				insights.push({
					category: "tag_alignment",
					icon: INSIGHT_SVG_ICONS.tag_alignment,
					message: `Your ${formatted} tags map directly to this strategy's strengths`,
					priority: rec.tagAffinityBoost,
				});
			}
		}

		// 6. Usage Pattern — comparative RANKING (not raw count — familiar_pick handles that)
		if (rec.frequencyScore >= 0.1) {
			const count = secDistribution[rec.name] ?? 0;
			const secValues = Object.values(secDistribution).filter(
				(c) => c > 0,
			);
			const rank = secValues.filter((c) => c > count).length + 1;
			const totalWithSec = secValues.length;
			let message: string;
			if (rank === 1 && totalWithSec > 1) {
				message = `Your most-selected secondary \u2014 chosen ahead of ${totalWithSec - 1} other${totalWithSec - 1 > 1 ? "s" : ""}`;
			} else if (rank === 1 && totalWithSec === 1) {
				message = `Your sole secondary pick \u2014 a clear preference signal for this approach`;
			} else if (rank <= 3 && totalWithSec > 2) {
				message = `Ranked #${rank} among your ${totalWithSec} secondary picks`;
			} else {
				message = `Part of your regular secondary rotation across ${totalWithSec} strategies`;
			}
			insights.push({
				category: "usage_pattern",
				icon: INSIGHT_SVG_ICONS.usage_pattern,
				message,
				priority: rec.frequencyScore,
			});
		}

		// 7. Signal Synergy — name WHICH signals converge (not generic "multiple signals")
		if (rec.synergyScore >= 0.1) {
			insights.push({
				category: "signal_synergy",
				icon: INSIGHT_SVG_ICONS.signal_synergy,
				message: `Your hands-on secondary experience and tag choices both independently endorse this strategy`,
				priority: rec.synergyScore,
			});
		}

		// 8. Data Profile — strategy COVERAGE angle (not total count — rationale handles that)
		let dataMessage: string;
		if (totalOpts >= 20) {
			dataMessage = `${triedStrategyCount} of ${ALL_STRATEGIES.length} strategies explored \u2014 this fills the highest-priority gap`;
		} else if (totalOpts >= 8) {
			dataMessage = `${triedStrategyCount} strategies tried so far \u2014 clear patterns point to this as your next move`;
		} else {
			dataMessage = `Early days with ${triedStrategyCount} strategies explored \u2014 keep forging to sharpen this pick`;
		}
		insights.push({
			category: "data_profile",
			icon: INSIGHT_SVG_ICONS.data_profile,
			message: dataMessage,
			priority: 0,
		});

		// Sort by priority descending, cap at 6
		insights.sort((a, b) => b.priority - a.priority);
		return insights.slice(0, 6);
	}

	// Thresholds mirror classifyConfidence() in recommendation.ts
	function classifyRunnerConfidence(
		strategy: ScoredStrategy,
	): ConfidenceTier {
		if (strategy.compositeScore > 0.3 && strategy.confidenceWeight > 0.5)
			return "high";
		if (strategy.compositeScore > 0.1) return "moderate";
		return "exploratory";
	}

	function classifyRunnerConfidenceLabel(strategy: ScoredStrategy): string {
		const tier = classifyRunnerConfidence(strategy);
		if (tier === "high") return "Strong";
		if (tier === "moderate") return "Viable";
		return "Explore";
	}

	interface StrategyEntry {
		name: StrategyName;
		label: string;
		count: number;
		secondaryCount: number;
		percentage: number;
		secondaryPercentage: number;
		normalizedWidth: number;
		normalizedSecondaryWidth: number;
		score: number | null;
		colors: StrategyColorMeta;
		tier: "used" | "secondary-only" | "unused";
	}

	// --- All 10 strategies (3-tier grouping: used → secondary-only → unused) ---
	const allStrategies: StrategyEntry[] = $derived.by(() => {
		const used: StrategyEntry[] = [];
		const secondaryOnly: StrategyEntry[] = [];
		const unused: StrategyEntry[] = [];
		const maxPrimaryCount = Math.max(
			...ALL_STRATEGIES.map((s) => distribution[s] ?? 0),
			1,
		);

		for (const name of ALL_STRATEGIES) {
			const count = distribution[name] ?? 0;
			const secCount = secondaryDistribution[name] ?? 0;
			const tier: "used" | "secondary-only" | "unused" =
				count > 0 ? "used" : secCount > 0 ? "secondary-only" : "unused";

			const entry: StrategyEntry = {
				name,
				label: STRATEGY_LABELS[name] ?? name,
				count,
				secondaryCount: secCount,
				percentage: total > 0 ? Math.round((count / total) * 100) : 0,
				secondaryPercentage:
					total > 0 ? Math.round((secCount / total) * 100) : 0,
				normalizedWidth: Math.min(
					Math.round((count / maxPrimaryCount) * 100),
					100,
				),
				normalizedSecondaryWidth: Math.min(
					Math.round((secCount / maxPrimaryCount) * 100),
					100,
				),
				score: scoreByStrategy[name] ?? null,
				colors: getStrategyColor(name),
				tier,
			};

			if (tier === "used") used.push(entry);
			else if (tier === "secondary-only") secondaryOnly.push(entry);
			else unused.push(entry);
		}

		used.sort((a, b) => b.count - a.count);
		secondaryOnly.sort((a, b) => b.secondaryCount - a.secondaryCount);
		unused.sort((a, b) => a.label.localeCompare(b.label));

		return [...used, ...secondaryOnly, ...unused];
	});

	// --- Usage counter for section heading ---
	const usedCount = $derived(
		allStrategies.filter((e) => e.tier !== "unused").length,
	);

	// --- Top performer (improved: min count 3, deterministic tie-breaking, variance-aware) ---
	const topPerformer: TopPerformerResult | null = $derived(
		selectTopPerformer(
			distribution,
			scoreByStrategy,
			undefined,
			stats.score_variance ?? undefined,
		),
	);

	// --- Multi-signal recommendation engine ---
	const recommendation: RecommendationResult | null = $derived(
		computeRecommendations({
			strategyDistribution: distribution,
			scoreByStrategy,
			taskTypesByStrategy,
			secondaryDistribution,
			tagsByStrategy,
			scoreMatrix: stats.score_matrix ?? undefined,
			scoreVariance: stats.score_variance ?? undefined,
			confidenceByStrategy: stats.confidence_by_strategy ?? undefined,
			comboEffectiveness: stats.combo_effectiveness ?? undefined,
			improvementByStrategy: stats.improvement_by_strategy ?? undefined,
		}),
	);

	// --- Derived recommendation details ---
	const topSignals: SignalBreakdown[] = $derived(
		recommendation ? getTopSignals(recommendation.strategy) : [],
	);
	const headlineSummary: string = $derived(
		recommendation ? getHeadlineSummary(recommendation.strategy) : "",
	);
	const taskFreq = $derived(buildTaskFrequency(taskTypesByStrategy));
	const globalTags = $derived(buildGlobalTags(tagsByStrategy));
	const triedCount = $derived(Object.keys(distribution).length);
	const recSecondaryCount = $derived(
		recommendation
			? (secondaryDistribution[recommendation.strategy.name] ?? 0)
			: 0,
	);
	const confidenceRationale: string = $derived(
		recommendation
			? getConfidenceRationale(
					recommendation.confidence,
					total,
					triedCount,
				)
			: "",
	);
	const richInsights: RichInsight[] = $derived(
		recommendation
			? generateRichInsights(
					recommendation.strategy,
					taskFreq,
					globalTags,
					total,
					triedCount,
					recSecondaryCount,
					secondaryDistribution,
				)
			: [],
	);
	const runnerUps: ScoredStrategy[] = $derived(
		recommendation ? recommendation.ranked.slice(1, 4) : [],
	);

	function handleSelect(strategy: string) {
		onStrategySelect?.(strategy);
	}

	function toggleExpanded(name: string) {
		expandedStrategy = expandedStrategy === name ? null : name;
	}

	function barTooltipText(entry: StrategyEntry): string {
		if (entry.tier === "unused") {
			return `${entry.label} — not used yet`;
		}
		if (entry.tier === "secondary-only") {
			const scoreStr =
				entry.score !== null
					? ` | Score: ${normalizeScore(entry.score)}`
					: "";
			return `Secondary only: ${entry.secondaryCount} uses${scoreStr}`;
		}
		const primaryPct = entry.percentage;
		const secPct = entry.secondaryPercentage;
		const scoreStr =
			entry.score !== null
				? ` | Score: ${normalizeScore(entry.score)}`
				: "";
		if (entry.secondaryCount > 0) {
			return `Primary: ${entry.count} uses (${primaryPct}%) | Secondary: ${entry.secondaryCount} uses (${secPct}%)${scoreStr}`;
		}
		return `${entry.count} uses (${primaryPct}%)${scoreStr}`;
	}
</script>

{#if total > 0}
	<div>
		<!-- Strategy Explorer sub-section -->
		<div class="group/explorer">
			<!-- Section heading with usage counter -->
			<h3
				class="section-heading-dim mb-2 animate-fade-in transition-colors duration-200 group-hover/explorer:text-neon-yellow"
				style="animation-delay: 450ms; animation-fill-mode: both;"
			>
				Strategy Explorer
				<span class="ml-2 font-mono text-[10px] text-text-dim/50"
					>{usedCount}/{ALL_STRATEGIES.length} used</span
				>
			</h3>

			<!-- Recommendation card with confidence indicator -->
			{#if recommendation}
				{@const rec = recommendation.strategy}
				{@const conf = recommendation.confidence}
				{@const tierColors = CONFIDENCE_TIER_COLORS[conf.tier]}
				{@const tierGlowColor = CONFIDENCE_GLOW_COLORS[conf.tier]}
				<div
					class="mb-3 rounded-lg border border-neon-yellow/20 bg-neon-yellow/5 px-2.5 py-2 animate-fade-in"
					style="animation-delay: 480ms; animation-fill-mode: both;"
				>
					<!-- Row 1: ★ RECOMMENDED · Strategy Name + nested Try it -->
					<div>
						<div class="flex items-baseline gap-1.5">
							<span class="text-xs leading-none text-neon-yellow"
								>&#9733;</span
							>
							<span
								class="font-display text-[10px] font-semibold uppercase tracking-wider text-neon-yellow/70"
								>Recommended</span
							>
							<span
								class="text-[13px] font-semibold leading-none text-text-primary"
								>{rec.label}</span
							>
						</div>
						<!-- L-connector + Try it button -->
						<div class="relative mt-1 ml-1.5 pl-[18px]">
							<div
								class="l-connector absolute left-[5px] top-0 h-[calc(50%+1px)] w-[13px] rounded-bl-[3px] border-b border-l border-neon-yellow/20"
							></div>
							<button
								onclick={() => handleSelect(rec.name)}
								class="group relative inline-flex items-center gap-1.5 overflow-hidden rounded-full border border-neon-yellow/20 bg-neon-yellow/[0.06] px-2.5 py-[3px] text-[9px] font-semibold text-neon-yellow/80 transition-all duration-200 hover:border-neon-yellow hover:bg-neon-yellow/[0.12] hover:text-neon-yellow insight-action-btn"
							>
								<span
									class="inline-block h-[5px] w-[5px] shrink-0 rounded-[0.5px] bg-neon-yellow"
								></span>
								<span
									>{lastPrompt
										? "Try with last prompt"
										: "Try it"}</span
								>
							</button>
						</div>
					</div>

					<!-- Row 2: Headline summary -->
					<p
						class="mt-1 text-[11px] font-semibold leading-snug text-text-secondary"
					>
						{headlineSummary}
					</p>

					<!-- Row 3: Signal breakdown (top 3 signals) -->
					{#if topSignals.length > 0}
						<div class="mt-1.5 space-y-0.5">
							{#each topSignals as signal}
								<Tooltip
									text={signal.explanation}
									class="block w-full"
								>
									<div class="flex items-center gap-2">
										<span
											class="w-24 shrink-0 truncate text-right text-[9px] text-text-dim/60"
											>{signal.humanName}</span
										>
										<div
											class="relative h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]"
										>
											<div
												class="h-full rounded-full bg-neon-yellow/70 transition-all duration-500"
												style="width: {Math.round(
													signal.score * 100,
												)}%"
											></div>
										</div>
										<span
											class="w-7 shrink-0 text-right font-mono text-[9px] text-neon-yellow/70"
											>{signal.score.toFixed(2)}</span
										>
									</div>
								</Tooltip>
							{/each}
						</div>
					{/if}

					<!-- Row 4: Confidence badge + rationale -->
					<div class="mt-1">
						<div class="flex items-center gap-1.5">
							<div
								class="h-px flex-1 border-t border-dashed border-white/5"
							></div>
							<Tooltip text={conf.detail}>
								<div
									class="inline-flex items-center gap-1.5 rounded-full {tierColors.bg} border {tierColors.border} px-2.5 py-0.5"
								>
									<span
										class="text-[10px] font-bold {tierColors.text}"
										>{conf.label}</span
									>
									<span class="text-[10px] text-text-dim/30"
										>&middot;</span
									>
									<span
										class="text-[10px] font-medium text-text-dim/70"
										>{conf.reason}</span
									>
								</div>
							</Tooltip>
							<div
								class="h-px flex-1 border-t border-dashed border-white/5"
							></div>
						</div>
						<p
							class="mt-1 text-center text-[9px] text-text-dim/65"
						>
							{confidenceRationale}
						</p>
					</div>

					<!-- Row 5: Rich multi-category insights (tiered) -->
					{#if richInsights.length > 0}
						{@const topInsights = richInsights.slice(0, 2)}
						{@const restInsights = richInsights.slice(2)}
						<div class="mt-1">
							<!-- Top 2: symmetric glass cards -->
							<div class="grid grid-cols-2 gap-1.5">
								{#each topInsights as insight, idx}
									{@const catColors =
										INSIGHT_CATEGORY_COLORS[
											insight.category
										]}
									<div
										class="insight-glass-card relative overflow-hidden rounded-md border border-white/[0.06] bg-white/[0.025] px-2 pb-1.5 pt-1.5 animate-fade-in"
										style="animation-delay: {500 +
											idx *
												60}ms; animation-fill-mode: both;"
									>
										<!-- Top accent line -->
										<div
											class="absolute inset-x-0 top-0 h-px bg-[rgba({catColors.glow},0.2)]"
										></div>
										<!-- Icon badge -->
										<div
											class="mx-auto mb-0.5 flex h-5 w-5 items-center justify-center rounded-full {catColors.text} bg-[rgba({catColors.glow},0.08)] border border-[rgba({catColors.glow},0.2)]"
										>
											{@html insight.icon}
										</div>
										<!-- Message -->
										<p
											class="text-center text-[9px] leading-snug text-text-secondary/80"
										>
											{insight.message}
										</p>
									</div>
								{/each}
							</div>
							<!-- Remaining: compact dimmed list -->
							{#if restInsights.length > 0}
								<div class="mt-1 space-y-0.5">
									{#each restInsights as insight}
										{@const catColors =
											INSIGHT_CATEGORY_COLORS[
												insight.category
											]}
										<div
											class="flex items-start gap-1.5 pl-0.5"
										>
											<span
												class="mt-[3px] inline-flex w-3 shrink-0 justify-center {catColors.textDim}"
												>{@html insight.icon}</span
											>
											<p
												class="text-[9px] leading-relaxed text-text-dim/70"
											>
												{insight.message}
											</p>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					{/if}

					<!-- Row 6: Runner-ups -->
					{#if runnerUps.length > 0}
						<div class="mt-1.5 border-t border-neon-yellow/10 pt-1">
							<button
								onclick={() => (showRunnerUps = !showRunnerUps)}
								class="flex w-full items-center gap-1 text-[9px] font-semibold uppercase tracking-wider text-text-dim/40 transition-colors hover:text-text-dim/60"
							>
								<span
									class="transition-transform duration-200 {showRunnerUps
										? 'rotate-90'
										: ''}">&#9656;</span
								>
								Runner-ups ({runnerUps.length})
							</button>
							{#if showRunnerUps}
								<div
									class="mt-0.5 space-y-px animate-section-expand"
								>
									{#each runnerUps as runner, idx}
										{@const runnerTier =
											classifyRunnerConfidence(runner)}
										{@const runnerTierColors =
											CONFIDENCE_TIER_COLORS[runnerTier]}
										<div
											class="flex items-center gap-1.5 rounded-md bg-bg-primary/30 px-2 py-1"
										>
											<span
												class="shrink-0 font-mono text-[10px] font-bold text-text-dim/30"
												>#{idx + 2}</span
											>
											<div class="min-w-0 flex-1">
												<div
													class="flex items-center gap-1.5"
												>
													<span
														class="text-[10px] font-semibold text-text-primary"
														>{runner.label}</span
													>
													<span
														class="font-mono text-[9px] text-text-dim/50"
														>{Math.round(
															runner.compositeScore *
																100,
														)}%</span
													>
													<span
														class="rounded-full {runnerTierColors.bg} border {runnerTierColors.border} px-1.5 py-px text-[8px] font-semibold {runnerTierColors.text}"
														>{classifyRunnerConfidenceLabel(
															runner,
														)}</span
													>
												</div>
												<p
													class="text-[9px] leading-snug text-text-dim/60 truncate"
												>
													{runner.motivation}
												</p>
											</div>
											<button
												onclick={() =>
													handleSelect(runner.name)}
												class="shrink-0 rounded-full bg-neon-yellow/5 px-2 py-0.5 text-[9px] font-semibold text-neon-yellow/70 transition-colors hover:bg-neon-yellow/10"
											>
												Try it
											</button>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Usage Breakdown sub-section -->
		<div class="group/breakdown">
			<h3
				class="section-heading-dim mb-1 mt-2 animate-fade-in transition-colors duration-200 group-hover/breakdown:text-neon-cyan"
				style="animation-delay: 520ms; animation-fill-mode: both;"
			>
				Usage Breakdown
			</h3>

			<!-- Legend + Column headers (single row) -->
			<div
				class="flex items-center gap-1 pb-0 animate-fade-in"
				style="animation-delay: 530ms; animation-fill-mode: both;"
			>
				<span class="w-[100px] shrink-0"></span>
				<span class="w-4 shrink-0"></span>
				<div class="min-w-0 flex-1 flex items-center">
					{#if hasAnySecondary}
						<div class="flex items-center gap-4">
							<div class="flex items-center gap-1.5">
								<span
									class="strategy-bar-primary inline-block h-2.5 w-8 rounded-full bg-neon-cyan/70"
									style="--bar-accent: rgba(0, 229, 255, 0.4)"
								></span>
								<span
									class="text-[9px] font-medium text-text-dim/50"
									>Primary</span
								>
							</div>
							<div class="flex items-center gap-1.5">
								<span
									class="inline-block h-2.5 w-8 rounded-full bg-neon-cyan/25"
								></span>
								<span
									class="text-[9px] font-medium text-text-dim/50"
									>Secondary</span
								>
							</div>
							<button
								onclick={() =>
									(showSecondaryOverlay =
										!showSecondaryOverlay)}
								class="text-[9px] text-text-dim/40 transition-colors hover:text-text-secondary"
							>
								{showSecondaryOverlay ? "Hide" : "Show"}
							</button>
						</div>
					{/if}
				</div>
				<span
					class="w-7 shrink-0 text-right font-display text-[9px] uppercase tracking-wider text-text-dim/30"
					>1st</span
				>
				{#if hasAnySecondary}
					<span
						class="w-7 shrink-0 text-right font-display text-[9px] uppercase tracking-wider text-text-dim/30"
						>2nd</span
					>
				{/if}
				<span
					class="w-8 shrink-0 text-center font-display text-[9px] uppercase tracking-wider text-text-dim/30"
					>Avg</span
				>
				<span class="w-3 shrink-0"></span>
			</div>

			<!-- Strategy bars -->
			<div>
				{#each allStrategies as entry, i}
					<div
						class="animate-stagger-fade-in"
						style="animation-delay: {550 + i * 40}ms"
					>
						<button
							onclick={() => toggleExpanded(entry.name)}
							aria-expanded={expandedStrategy === entry.name}
							class="group flex h-4 w-full items-center gap-1 rounded leading-none text-left transition-all duration-150 hover:bg-bg-hover/30 hover:translate-x-0.5"
						>
							<span
								class="w-[100px] shrink-0 truncate text-right text-[10px] font-medium {entry.tier ===
								'unused'
									? 'text-text-dim/30'
									: entry.colors.text}"
							>
								{entry.label}
							</span>
							<span class="w-4 shrink-0 text-center">
								{#if recommendation?.strategy.name === entry.name}
									<Tooltip
										text="Recommended — try this strategy next"
									>
										<span
											class="text-[10px] text-neon-yellow"
											>&#10035;</span
										>
									</Tooltip>
								{:else if topPerformer?.name === entry.name}
									<Tooltip
										text="Top performer — highest avg score ({topPerformer.count} uses){topPerformer.isSignificant
											? ''
											: ', needs more data'}"
									>
										<span
											class="text-[10px] text-neon-yellow"
											>&#9819;</span
										>
									</Tooltip>
								{/if}
							</span>
							<Tooltip
								text={barTooltipText(entry)}
								class="flex-1 min-w-0"
							>
								<div
									class="relative h-2.5 w-full overflow-hidden rounded-full bg-bg-primary/40"
								>
									{#if entry.tier === "used"}
										<!-- Primary bar -->
										<div
											class="{entry.colors
												.bar} opacity-70 h-full strategy-bar-primary {showSecondaryOverlay &&
											entry.secondaryCount > 0
												? 'rounded-l-full'
												: 'rounded-full'} transition-all duration-500"
											style="width: {entry.normalizedWidth}%; --bar-accent: {entry
												.colors.rawRgba}"
										></div>
										<!-- Secondary bar -->
										{#if showSecondaryOverlay && entry.secondaryCount > 0}
											<div
												class="absolute inset-y-0 left-0 {entry
													.colors
													.bar} opacity-25 rounded-r-full transition-all duration-500"
												style="width: {entry.normalizedSecondaryWidth}%; left: {entry.normalizedWidth}%"
											></div>
											<!-- Junction separator -->
											<div
												class="absolute inset-y-0 w-px bg-bg-primary/60"
												style="left: {entry.normalizedWidth}%"
											></div>
										{/if}
									{:else if entry.tier === "secondary-only"}
										<!-- Secondary-only bar -->
										{#if showSecondaryOverlay}
											<div
												class="absolute inset-y-0 left-0 {entry
													.colors
													.bar} opacity-25 rounded-full transition-all duration-500"
												style="width: {entry.normalizedSecondaryWidth}%"
											></div>
										{/if}
									{/if}
									<!-- Unused: empty track (no inner bars) -->
								</div>
							</Tooltip>
							<span
								class="w-7 shrink-0 text-right font-mono text-[10px] {entry.tier ===
								'unused'
									? 'text-text-dim/20'
									: entry.tier === 'secondary-only'
										? 'text-text-dim/30'
										: 'text-text-dim'}"
							>
								{#if entry.tier === "unused"}&mdash;{:else}{entry.count}{/if}
							</span>
							{#if hasAnySecondary}
								<span
									class="w-7 shrink-0 text-right font-mono text-[10px] text-text-dim/50"
								>
									{#if entry.secondaryCount > 0}+{entry.secondaryCount}{/if}
								</span>
							{/if}
							<Tooltip
								text={entry.score !== null
									? `Average score for ${entry.label}`
									: entry.tier === "unused"
										? `${entry.label} — not used yet`
										: `No score data for ${entry.label}`}
								class="w-8 shrink-0"
							>
								<span
									class="block w-full rounded bg-bg-hover/50 text-center font-mono text-[10px] font-semibold {entry.score !==
									null
										? 'text-text-secondary'
										: 'text-text-dim/30'}"
								>
									{entry.score !== null
										? normalizeScore(entry.score)
										: "—"}
								</span>
							</Tooltip>
							<span
								class="w-3 shrink-0 text-center text-[10px] {entry.tier ===
								'unused'
									? 'text-text-dim/20'
									: entry.tier === 'secondary-only'
										? 'text-text-dim/30'
										: 'text-text-dim/40'} transition-transform duration-200 {expandedStrategy ===
								entry.name
									? 'rotate-90'
									: ''}">&#9656;</span
							>
						</button>

						<!-- Expanded detail panel -->
						{#if expandedStrategy === entry.name}
							<div
								class="ml-[120px] {hasAnySecondary
									? 'mr-[132px]'
									: 'mr-[96px]'} mt-0.5 mb-1 rounded-md border-l-2 {entry
									.colors
									.border} bg-bg-secondary/30 p-2 animate-section-expand"
							>
								<p
									class="text-[9px] leading-snug text-text-dim"
								>
									{STRATEGY_DESCRIPTIONS[entry.name] ?? ""}
								</p>

								{#if entry.tier !== "unused"}
									{#if taskTypesByStrategy[entry.name]}
										<div class="mt-1 flex gap-1.5">
											<span
												class="font-display w-16 shrink-0 pt-0.5 text-right text-[9px] font-semibold uppercase tracking-wider text-text-dim/40"
												>Types</span
											>
											<div class="flex flex-wrap gap-2">
												{#each Object.entries(taskTypesByStrategy[entry.name]) as [taskType, count]}
													<div
														class="flex items-center gap-1.5"
													>
														<MetaBadge
															type="task"
															value={taskType}
															variant="pill"
															showTooltip={false}
														/>
														<span
															class="text-[9px] text-text-dim"
															>({count})</span
														>
													</div>
												{/each}
											</div>
										</div>
									{/if}

									{#if tagsByStrategy[entry.name]}
										<div class="mt-1 flex gap-1.5">
											<span
												class="font-display w-16 shrink-0 pt-0.5 text-right text-[9px] font-semibold uppercase tracking-wider text-text-dim/40"
												>Tags</span
											>
											<div class="flex flex-wrap gap-2">
												{#each Object.entries(tagsByStrategy[entry.name]) as [tag, tagCount]}
													<div
														class="flex items-center gap-1.5"
													>
														<MetaBadge
															type="tag"
															value={tag}
															variant="pill"
															showTooltip={false}
														/>
														<span
															class="text-[9px] text-text-dim/50"
															>({tagCount})</span
														>
													</div>
												{/each}
											</div>
										</div>
									{/if}

									<!-- Combined primary+secondary micro-bar -->
									{#if showSecondaryOverlay && entry.secondaryCount > 0}
										{@const totalCount =
											entry.count + entry.secondaryCount}
										{@const primaryPct =
											totalCount > 0
												? (entry.count / totalCount) *
													100
												: 0}
										{@const secondaryPct =
											totalCount > 0
												? (entry.secondaryCount /
														totalCount) *
													100
												: 0}
										<div
											class="mt-1 flex items-center gap-1.5"
										>
											<span
												class="font-display w-16 shrink-0 text-right text-[9px] font-semibold uppercase tracking-wider text-text-dim/40"
												>Uses</span
											>
											<div
												class="relative h-2 flex-1 overflow-hidden rounded-full bg-bg-primary/30"
											>
												<div
													class="{entry.colors
														.bar} opacity-60 absolute inset-y-0 left-0 rounded-l-full"
													style="width: {primaryPct}%"
												></div>
												<div
													class="absolute inset-y-0 {entry
														.colors
														.bar} opacity-25 rounded-r-full"
													style="left: {primaryPct}%; width: {secondaryPct}%"
												></div>
											</div>
											<span
												class="shrink-0 text-right font-mono text-[9px]"
											>
												<span class="text-text-dim"
													>{entry.count}</span
												>
												<span class="text-text-dim/40">
													+{entry.secondaryCount}</span
												>
											</span>
										</div>
									{/if}
								{:else}
									<!-- Unused: show "Best for" badges from static data -->
									{#if STRATEGY_DETAILS[entry.name]?.bestFor}
										<div class="mt-1 flex gap-1.5">
											<span
												class="font-display w-16 shrink-0 pt-0.5 text-right text-[9px] font-semibold uppercase tracking-wider text-text-dim/40"
												>Best for</span
											>
											<div class="flex flex-wrap gap-1.5">
												{#each STRATEGY_DETAILS[entry.name].bestFor as taskType}
													<MetaBadge
														type="task"
														value={taskType}
														variant="pill"
														showTooltip={false}
													/>
												{/each}
											</div>
										</div>
									{/if}
								{/if}

								<div class="mt-1 pl-[4.5rem]">
									<button
										onclick={() => handleSelect(entry.name)}
										class="rounded-full px-2 py-px text-[9px] font-semibold {entry
											.colors.text} {entry.colors
											.btnBg} transition-colors"
									>
										{lastPrompt
											? "Try with last prompt"
											: "Try this strategy"}
									</button>
								</div>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}
