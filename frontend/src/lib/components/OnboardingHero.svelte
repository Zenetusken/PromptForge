<script lang="ts">
	import { forgeSession } from '$lib/stores/forgeSession.svelte';

	let { onDismiss }: { onDismiss?: () => void } = $props();

	const STEPS = [
		{
			title: 'Write',
			description: 'Type any prompt',
			color: 'neon-cyan',
			iconPath: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
		},
		{
			title: 'Forge',
			description: 'AI pipeline optimizes it',
			color: 'neon-purple',
			iconPath: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
		},
		{
			title: 'Iterate',
			description: 'Score, compare, refine',
			color: 'neon-green',
			iconPath: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
		},
	] as const;

	const COLOR_MAP: Record<string, { circle: string; text: string; glow: string }> = {
		'neon-cyan': {
			circle: 'bg-neon-cyan/10 border-neon-cyan/20',
			text: 'text-neon-cyan',
			glow: 'shadow-[0_0_12px_rgba(0,229,255,0.08)]',
		},
		'neon-purple': {
			circle: 'bg-neon-purple/10 border-neon-purple/20',
			text: 'text-neon-purple',
			glow: 'shadow-[0_0_12px_rgba(168,85,247,0.08)]',
		},
		'neon-green': {
			circle: 'bg-neon-green/10 border-neon-green/20',
			text: 'text-neon-green',
			glow: 'shadow-[0_0_12px_rgba(34,255,136,0.08)]',
		},
	};

	function handleStepClick() {
		forgeSession.focusTextarea();
	}
</script>

<div class="relative py-3">
	<!-- Dismiss button -->
	{#if onDismiss}
		<button
			type="button"
			onclick={onDismiss}
			class="absolute right-0 top-4 rounded px-1.5 py-0.5 text-[10px] text-text-dim/50 transition-colors hover:text-text-dim"
			aria-label="Dismiss onboarding"
		>
			dismiss
		</button>
	{/if}

	<!-- Steps row -->
	<div class="flex items-start justify-center gap-0">
		{#each STEPS as step, i}
			{@const colors = COLOR_MAP[step.color]}

			{#if i > 0}
				<!-- Connector line -->
				<div
					class="mt-4 h-px w-10 shrink-0 sm:w-14 animate-fade-in"
					style="
						background: linear-gradient(90deg,
							{i === 1 ? 'rgba(0,229,255,0.3)' : 'rgba(168,85,247,0.3)'},
							{i === 1 ? 'rgba(168,85,247,0.3)' : 'rgba(34,255,136,0.3)'}
						);
						animation-delay: {75 + i * 100}ms;
						animation-fill-mode: backwards;
					"
				></div>
			{/if}

			<button
				type="button"
				onclick={handleStepClick}
				class="group flex w-24 flex-col items-center gap-1.5 rounded-lg p-2 text-center transition-all duration-200 hover:bg-bg-hover/40 animate-fade-in"
				style="animation-delay: {50 + i * 100}ms; animation-fill-mode: backwards;"
			>
				<!-- Icon circle -->
				<div class="flex h-8 w-8 items-center justify-center rounded-full border {colors.circle} {colors.glow} transition-transform duration-200 group-hover:scale-110">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" class={colors.text}>
						{#if step.color === 'neon-purple'}
							<path d={step.iconPath} fill="currentColor" />
						{:else}
							<path d={step.iconPath} stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
						{/if}
					</svg>
				</div>

				<!-- Title -->
				<span class="font-display text-xs font-bold uppercase tracking-wider {colors.text}">
					{step.title}
				</span>

				<!-- Description -->
				<span class="text-[11px] leading-snug text-text-dim">
					{step.description}
				</span>
			</button>
		{/each}
	</div>
</div>
