<script lang="ts">
	import {
		optimizationState,
		type OptimizationResultState,
	} from "$lib/stores/optimization.svelte";
	import { toastState } from "$lib/stores/toast.svelte";
	import { forgeSession } from "$lib/stores/forgeSession.svelte";
	import { useCopyFeedback } from "$lib/utils/useCopyFeedback.svelte";
	import {
		generateExportMarkdown,
		downloadMarkdown,
	} from "$lib/utils/export";
	import Icon from "./Icon.svelte";
	import { Tooltip } from "./ui";

	let { result }: { result: OptimizationResultState } = $props();

	const copyFeedback = useCopyFeedback();

	function copyOptimized() {
		copyFeedback.copy(result.optimized);
		toastState.show("Copied to clipboard!", "success", 3000);
	}

	function handleReforge() {
		if (result.id) {
			optimizationState.retryOptimization(result.id, result.original);
		} else {
			optimizationState.startOptimization(result.original);
		}
		forgeSession.activate();
	}

	function handleEditReforge() {
		const isArchived = result.project_status === "archived";
		forgeSession.loadRequest({
			text: result.optimized,
			project: isArchived ? "" : result.project || "",
			promptId: isArchived ? "" : result.prompt_id || "",
		});
		forgeSession.activate();
	}

	function handleExportMd() {
		const content = generateExportMarkdown(result);
		downloadMarkdown(content, result.title || "Optimized Prompt");
	}
</script>

<div
	class="flex flex-wrap items-center gap-2 border-t border-border-subtle px-2.5 py-2"
	data-testid="result-actions"
>
	<Tooltip text="Copy optimized prompt to clipboard">
		<button
			class="btn-ghost flex items-center gap-1.5 transition-[background-color,color] duration-200 {copyFeedback.copied
				? 'copy-flash bg-neon-green/15 text-neon-green'
				: 'bg-neon-cyan/8 text-neon-cyan hover:bg-neon-cyan/15'}"
			onclick={copyOptimized}
			data-testid="copy-optimized-btn"
		>
			{#if copyFeedback.copied}
				<Icon name="check" size={12} />
				Copied!
			{:else}
				<Icon name="copy" size={12} />
				Copy
			{/if}
		</button>
	</Tooltip>
	<Tooltip text="Optimize the original prompt again">
		<button
			class="btn-ghost flex items-center gap-1.5 border border-neon-cyan/20 bg-neon-cyan/8 text-neon-cyan hover:bg-neon-cyan/15"
			onclick={handleReforge}
			data-testid="reforge-result-btn"
		>
			<Icon name="refresh" size={12} />
			Re-forge
		</button>
	</Tooltip>
	<Tooltip text="Use optimized result as new input">
		<button
			class="btn-ghost flex items-center gap-1.5 bg-neon-purple/8 text-neon-purple hover:bg-neon-purple/15"
			onclick={handleEditReforge}
			data-testid="iterate-result-btn"
		>
			<Icon name="edit" size={12} />
			Iterate
		</button>
	</Tooltip>
	{#if result.project_id && result.project}
		<Tooltip text="Open project containing this prompt">
			<a
				href="/projects/{result.project_id}"
				class="btn-ghost flex items-center gap-1.5 bg-neon-yellow/8 text-neon-yellow hover:bg-neon-yellow/15"
				data-testid="view-project-btn"
			>
				<Icon name="folder-open" size={12} />
				View Project
			</a>
		</Tooltip>
	{/if}
	<Tooltip text="Download as Markdown" class="ml-auto">
		<button
			class="btn-ghost flex items-center gap-1.5 bg-text-dim/8 text-text-dim hover:bg-text-dim/15 hover:text-text-secondary"
			onclick={handleExportMd}
			data-testid="export-md-btn"
		>
			<Icon name="download" size={12} />
			Export
		</button>
	</Tooltip>
</div>
