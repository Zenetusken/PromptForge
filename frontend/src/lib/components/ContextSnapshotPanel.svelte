<script lang="ts">
	import type { CodebaseContext } from '$lib/api/client';
	import Icon from './Icon.svelte';

	interface Props {
		context: CodebaseContext;
	}

	let { context }: Props = $props();
	let expanded = $state(false);

	/** Safely normalize a field that may arrive as string or string[]. */
	function asArray(val: string | string[] | undefined | null): string[] {
		if (!val) return [];
		if (typeof val === 'string') return [val];
		return val;
	}

	let conventions = $derived(asArray(context.conventions));
	let patterns = $derived(asArray(context.patterns));
	let testPatterns = $derived(asArray(context.test_patterns));
	let codeSnippets = $derived(asArray(context.code_snippets));

	let fieldCount = $derived.by(() => {
		const fields = [
			context.language, context.framework, context.description,
			conventions.length, patterns.length,
			codeSnippets.length, context.documentation,
			context.test_framework, testPatterns.length,
			sourcesList?.length,
		];
		return fields.filter(Boolean).length;
	});

	let sourcesList = $derived(context.sources);
</script>

<div class="border-t border-white/[0.06]">
	<button
		onclick={() => (expanded = !expanded)}
		class="flex w-full items-center gap-1.5 px-2 py-1 text-[10px] text-text-dim hover:text-text-secondary transition-colors"
	>
		<Icon name={expanded ? 'chevron-down' : 'chevron-right'} size={10} />
		<span class="font-medium">Project Context</span>
		<span class="ml-auto font-mono text-[9px] text-neon-cyan/60">{fieldCount} fields</span>
	</button>

	{#if expanded}
		<div class="px-2 pb-2 space-y-1.5">
			<!-- Scalar badges -->
			{#if context.language || context.framework || context.test_framework}
				<div class="flex flex-wrap gap-1">
					{#if context.language}
						<span class="min-w-0 rounded-sm px-1.5 py-0.5 text-[9px] font-mono text-neon-cyan bg-neon-cyan/8 border border-neon-cyan/20 max-w-full truncate" title={context.language}>
							{context.language}
						</span>
					{/if}
					{#if context.framework}
						<span class="min-w-0 rounded-sm px-1.5 py-0.5 text-[9px] font-mono text-neon-cyan bg-neon-cyan/8 border border-neon-cyan/20 max-w-full truncate" title={context.framework}>
							{context.framework}
						</span>
					{/if}
					{#if context.test_framework}
						<span class="min-w-0 rounded-sm px-1.5 py-0.5 text-[9px] font-mono text-neon-green/80 bg-neon-green/8 border border-neon-green/20 max-w-full truncate" title={context.test_framework}>
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
			{#if conventions.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Conventions</span>
					<div class="mt-0.5 space-y-0.5">
						{#each conventions as conv, i (i)}
							<p class="text-[9px] text-text-secondary leading-snug">{conv}</p>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Patterns -->
			{#if patterns.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Patterns</span>
					<div class="mt-0.5 space-y-0.5">
						{#each patterns as pattern, i (i)}
							<p class="text-[9px] text-text-secondary leading-snug">{pattern}</p>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Test patterns -->
			{#if testPatterns.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Test Patterns</span>
					<div class="mt-0.5 space-y-0.5">
						{#each testPatterns as tp, i (i)}
							<p class="text-[9px] text-text-secondary leading-snug">{tp}</p>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Code snippets -->
			{#if codeSnippets.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Code Snippets</span>
					{#each codeSnippets as snippet, i (i)}
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

			<!-- Knowledge Sources -->
			{#if sourcesList?.length}
				<div>
					<span class="text-[9px] font-medium text-text-dim uppercase tracking-wider">Knowledge Sources</span>
					<div class="flex flex-wrap gap-1 mt-0.5">
						{#each sourcesList as src, i (i)}
							<span class="rounded-sm px-1 py-0.5 text-[9px] text-neon-cyan bg-neon-cyan/8 border border-neon-cyan/20">
								{src.title}
							</span>
						{/each}
					</div>
					{#each sourcesList as src, i (i)}
						{#if src.content}
							<details class="mt-1">
								<summary class="text-[9px] text-text-dim cursor-pointer hover:text-text-secondary">{src.title}</summary>
								<pre class="mt-0.5 rounded-sm bg-bg-primary p-1.5 text-[9px] font-mono text-text-secondary leading-tight overflow-x-auto max-h-24 border border-white/[0.06]">{src.content.slice(0, 500)}{src.content.length > 500 ? '...' : ''}</pre>
							</details>
						{/if}
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
