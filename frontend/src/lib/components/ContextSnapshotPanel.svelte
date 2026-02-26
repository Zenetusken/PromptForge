<script lang="ts">
	import type { CodebaseContext } from '$lib/api/client';
	import Icon from './Icon.svelte';

	interface Props {
		context: CodebaseContext;
	}

	let { context }: Props = $props();
	let expanded = $state(false);

	let fieldCount = $derived.by(() => {
		const fields = [
			context.language, context.framework, context.description,
			context.conventions?.length, context.patterns?.length,
			context.code_snippets?.length, context.documentation,
			context.test_framework, context.test_patterns?.length,
		];
		return fields.filter(Boolean).length;
	});
</script>

<div class="border-t border-white/[0.06]">
	<button
		onclick={() => (expanded = !expanded)}
		class="flex w-full items-center gap-1.5 px-2 py-1 text-[10px] text-text-dim hover:text-text-secondary transition-colors"
	>
		<Icon name={expanded ? 'chevron-down' : 'chevron-right'} size={10} />
		<span class="font-medium">Codebase Context</span>
		<span class="ml-auto font-mono text-[9px] text-neon-cyan/60">{fieldCount}/9 fields</span>
	</button>

	{#if expanded}
		<div class="px-2 pb-2 space-y-1.5">
			<!-- Scalar badges -->
			{#if context.language || context.framework || context.test_framework}
				<div class="flex flex-wrap gap-1">
					{#if context.language}
						<span class="inline-flex items-center rounded-sm px-1.5 py-0.5 text-[9px] font-mono text-neon-cyan bg-neon-cyan/8 border border-neon-cyan/20">
							{context.language}
						</span>
					{/if}
					{#if context.framework}
						<span class="inline-flex items-center rounded-sm px-1.5 py-0.5 text-[9px] font-mono text-neon-cyan bg-neon-cyan/8 border border-neon-cyan/20">
							{context.framework}
						</span>
					{/if}
					{#if context.test_framework}
						<span class="inline-flex items-center rounded-sm px-1.5 py-0.5 text-[9px] font-mono text-neon-green/80 bg-neon-green/8 border border-neon-green/20">
							{context.test_framework}
						</span>
					{/if}
				</div>
			{/if}

			<!-- Description -->
			{#if context.description}
				<p class="text-[10px] text-text-secondary leading-snug">{context.description}</p>
			{/if}

			<!-- Conventions -->
			{#if context.conventions?.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Conventions</span>
					<div class="flex flex-wrap gap-1 mt-0.5">
						{#each context.conventions as conv}
							<span class="rounded-sm px-1 py-0.5 text-[9px] text-text-secondary bg-bg-hover border border-white/[0.06]">
								{conv}
							</span>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Patterns -->
			{#if context.patterns?.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Patterns</span>
					<div class="flex flex-wrap gap-1 mt-0.5">
						{#each context.patterns as pattern}
							<span class="rounded-sm px-1 py-0.5 text-[9px] text-text-secondary bg-bg-hover border border-white/[0.06]">
								{pattern}
							</span>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Test patterns -->
			{#if context.test_patterns?.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Test Patterns</span>
					<div class="flex flex-wrap gap-1 mt-0.5">
						{#each context.test_patterns as tp}
							<span class="rounded-sm px-1 py-0.5 text-[9px] text-text-secondary bg-bg-hover border border-white/[0.06]">
								{tp}
							</span>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Code snippets -->
			{#if context.code_snippets?.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Code Snippets</span>
					{#each context.code_snippets as snippet}
						<pre class="mt-0.5 rounded-sm bg-bg-primary p-1.5 text-[9px] font-mono text-text-secondary leading-tight overflow-x-auto border border-white/[0.06]">{snippet}</pre>
					{/each}
				</div>
			{/if}

			<!-- Documentation -->
			{#if context.documentation}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Documentation</span>
					<pre class="mt-0.5 rounded-sm bg-bg-primary p-1.5 text-[9px] font-mono text-text-secondary leading-tight overflow-x-auto max-h-24 border border-white/[0.06]">{context.documentation.slice(0, 500)}{context.documentation.length > 500 ? '...' : ''}</pre>
				</div>
			{/if}
		</div>
	{/if}
</div>
