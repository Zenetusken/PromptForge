<script lang="ts">
	import BrandLogo from "$lib/components/BrandLogo.svelte";
	import OnboardingHero from "$lib/components/OnboardingHero.svelte";
	import StrategyInsights from "$lib/components/StrategyInsights.svelte";
	import RecentForges from "$lib/components/RecentForges.svelte";
	import RecentProjects from "$lib/components/RecentProjects.svelte";
	import Icon from "$lib/components/Icon.svelte";
	import { optimizationState } from "$lib/stores/optimization.svelte";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { historyState } from "$lib/stores/history.svelte";
	import { statsState } from "$lib/stores/stats.svelte";

	const ONBOARDING_DISMISSED_KEY = "pf_onboarding_dismissed";

	const QUICK_START_TEMPLATES = [
		{
			label: "Code Review",
			icon: "terminal" as const,
			color: "cyan",
			prompt: "Review this Python function for correctness, performance issues, and adherence to best practices. Suggest specific refactors with code examples and explain the reasoning behind each change.",
		},
		{
			label: "Marketing Email",
			icon: "edit" as const,
			color: "purple",
			prompt: "Write a compelling product launch email for a B2B SaaS audience. Include a subject line, preview text, hero section, three benefit-driven paragraphs, social proof, and a clear call-to-action.",
		},
		{
			label: "Technical Docs",
			icon: "layers" as const,
			color: "green",
			prompt: "Create comprehensive API documentation for a REST endpoint including description, authentication requirements, request/response schemas with examples, error codes, and rate limiting details.",
		},
		{
			label: "Error Messages",
			icon: "alert-circle" as const,
			color: "red",
			prompt: "Design user-friendly error messages for a web application covering validation failures, network errors, authentication issues, and permission denials. Each message should explain what went wrong and how to fix it.",
		},
	] as const;

	const COLOR_CLASSES = {
		cyan: {
			text: "text-neon-cyan",
			bgLight: "bg-neon-cyan/10",
			bgHover: "hover:bg-neon-cyan/15",
			border: "border-neon-cyan/20",
			shadow: "hover:shadow-[0_0_20px_rgba(0,229,255,0.08)]",
		},
		purple: {
			text: "text-neon-purple",
			bgLight: "bg-neon-purple/10",
			bgHover: "hover:bg-neon-purple/15",
			border: "border-neon-purple/20",
			shadow: "hover:shadow-[0_0_20px_rgba(168,85,247,0.08)]",
		},
		green: {
			text: "text-neon-green",
			bgLight: "bg-neon-green/10",
			bgHover: "hover:bg-neon-green/15",
			border: "border-neon-green/20",
			shadow: "hover:shadow-[0_0_20px_rgba(34,255,136,0.08)]",
		},
		red: {
			text: "text-neon-red",
			bgLight: "bg-neon-red/10",
			bgHover: "hover:bg-neon-red/15",
			border: "border-neon-red/20",
			shadow: "hover:shadow-[0_0_20px_rgba(255,51,102,0.08)]",
		},
	} as const;

	// Clear stale optimization state when navigating to home
	// (e.g., after viewing a detail page via breadcrumb)
	if (!optimizationState.isRunning) {
		optimizationState.result = null;
		optimizationState.currentRun = null;
		optimizationState.error = null;
	}

	let onboardingDismissed = $state(false);
	try {
		onboardingDismissed =
			typeof window !== "undefined" &&
			localStorage.getItem(ONBOARDING_DISMISSED_KEY) === "true";
	} catch {
		/* ignore */
	}

	let showOnboarding = $derived.by(() => {
		if (onboardingDismissed) return false;
		if (!historyState.hasLoaded) return false;
		return historyState.total < 5;
	});

	function handleDismissOnboarding() {
		onboardingDismissed = true;
		try {
			localStorage.setItem(ONBOARDING_DISMISSED_KEY, "true");
		} catch {
			/* ignore */
		}
	}

	function handleStrategySelect(strategy: string) {
		forgeSession.updateDraft({ strategy });
		forgeSession.activate();
		forgeSession.focusTextarea();
	}

	function handleTemplateClick(text: string) {
		forgeSession.updateDraft({ text });
		forgeSession.focusTextarea();
	}

	function handleNewForge() {
		forgeSession.activate();
		forgeSession.focusTextarea();
	}
</script>

<div class="flex flex-col gap-3">
	<div class="relative overflow-visible">
		<!-- Logo: absolutely positioned, paints behind everything below -->
		<div
			class="pointer-events-none absolute inset-x-0 top-0 z-0 flex justify-center pt-5"
		>
			<div class="w-full max-w-sm">
				<BrandLogo />
			</div>
		</div>
		<!-- Spacer: shorter than full SVG height so bottom bleeds behind cards -->
		<div class="h-[260px] sm:h-[280px]" aria-hidden="true"></div>
	</div>

	{#if showOnboarding}
		<OnboardingHero onDismiss={handleDismissOnboarding} />
	{/if}

	<!-- Template cards (new users) or Strategy Explorer (returning users) -->
	{#if !optimizationState.currentRun && !optimizationState.error && historyState.hasLoaded}
		{#if historyState.total === 0}
			<div class="group/templates">
				<p
					class="section-heading-dim mb-1 px-1 transition-colors duration-200 group-hover/templates:text-neon-cyan"
				>
					Try a template
				</p>
				<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
					{#each QUICK_START_TEMPLATES as template, i}
						{@const colors = COLOR_CLASSES[template.color]}
						<button
							type="button"
							onclick={() => handleTemplateClick(template.prompt)}
							class="group flex flex-col items-center gap-2 rounded-lg border {colors.border} bg-bg-card/50 p-2.5 text-center transition-all duration-200 {colors.bgHover} {colors.shadow} hover:border-opacity-40 animate-fade-in"
							style="animation-delay: {200 +
								i * 75}ms; animation-fill-mode: backwards;"
						>
							<div
								class="flex h-7 w-7 items-center justify-center rounded-full {colors.bgLight} transition-transform duration-200 group-hover:scale-110"
							>
								<Icon
									name={template.icon}
									size={16}
									class={colors.text}
								/>
							</div>
							<span
								class="text-xs font-medium text-text-secondary group-hover:text-text-primary transition-colors"
								>{template.label}</span
							>
						</button>
					{/each}
				</div>
			</div>
		{:else if historyState.items.length > 0}
			<!-- New Forge entry point for returning users -->
			<div class="flex justify-center">
				<button
					type="button"
					onclick={handleNewForge}
					class="group flex items-center gap-2.5 rounded-lg border border-neon-cyan/20 bg-bg-card/50 px-5 py-2.5 text-sm font-medium text-neon-cyan transition-all duration-200 hover:bg-neon-cyan/10 hover:border-neon-cyan/40"
				>
					<Icon name="plus" size={16} class="transition-transform duration-200 group-hover:scale-110" />
					New Forge
					<span class="text-[10px] font-normal text-text-dim ml-1 border border-text-dim/30 rounded px-1 py-0.5">/</span>
				</button>
			</div>
			<RecentForges />
			<RecentProjects />
			{#if statsState.stats}
				<StrategyInsights
					stats={statsState.stats}
					lastPrompt={forgeSession.draft.text}
					onStrategySelect={handleStrategySelect}
				/>
			{/if}
		{/if}
	{/if}

</div>
