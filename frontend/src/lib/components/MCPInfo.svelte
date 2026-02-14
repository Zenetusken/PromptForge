<script lang="ts">
	import Icon from './Icon.svelte';

	let { open = $bindable(false) }: { open: boolean } = $props();

	const tools = [
		{ name: 'promptforge_optimize', desc: 'Run the full optimization pipeline on a prompt' },
		{ name: 'promptforge_get', desc: 'Retrieve an optimization by ID' },
		{ name: 'promptforge_list', desc: 'List optimizations with filtering, sorting, pagination' },
		{ name: 'promptforge_get_by_project', desc: 'Get all optimizations for a project' },
		{ name: 'promptforge_search', desc: 'Full-text search across prompts' },
		{ name: 'promptforge_tag', desc: 'Add/remove tags, set project on an optimization' },
		{ name: 'promptforge_stats', desc: 'Get usage statistics' },
		{ name: 'promptforge_delete', desc: 'Delete an optimization record' },
	];

	const configSnippet = `{
  "mcpServers": {
    "promptforge": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/path/to/promptforge/backend"
    }
  }
}`;

	function handleBackdropClick() {
		open = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (open && e.key === 'Escape') open = false;
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex cursor-default items-center justify-center bg-black/70 backdrop-blur-md"
		onclick={handleBackdropClick}
		onkeydown={(e) => { if (e.key === 'Escape' || e.key === 'Enter') open = false; }}
		role="button"
		tabindex="-1"
		aria-label="Close MCP info"
		data-testid="mcp-info-backdrop"
	>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="animate-scale-in relative mx-4 max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border-subtle bg-bg-card p-6 text-left shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			data-testid="mcp-info-panel"
		>
			<!-- Close button -->
			<button
				class="btn-icon absolute right-3 top-3"
				onclick={() => (open = false)}
				aria-label="Close"
			>
				<Icon name="x" size={14} />
			</button>

			<!-- Header -->
			<div class="mb-5 flex items-center gap-2.5">
				<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-neon-cyan/10">
					<Icon name="terminal" size={16} class="text-neon-cyan" />
				</div>
				<h2 class="font-display text-lg font-bold text-text-primary">MCP Integration</h2>
			</div>

			<p class="mb-5 text-sm leading-relaxed text-text-secondary">
				PromptForge exposes a <span class="text-neon-cyan">Model Context Protocol</span> (MCP) server,
				allowing Claude Code and other MCP-compatible clients to optimize prompts directly from the command line.
			</p>

			<!-- Tools list -->
			<div class="mb-5">
				<h3 class="mb-3 section-heading-dim text-[10px]">Available Tools</h3>
				<div class="space-y-1.5">
					{#each tools as tool}
						<div class="rounded-xl bg-bg-secondary/80 px-3 py-2.5">
							<span class="font-mono text-xs text-neon-cyan">{tool.name}</span>
							<p class="mt-0.5 text-[11px] leading-relaxed text-text-dim">{tool.desc}</p>
						</div>
					{/each}
				</div>
			</div>

			<!-- Setup instructions -->
			<div class="mb-5">
				<h3 class="mb-2 section-heading-dim text-[10px]">Quick Start</h3>
				<p class="mb-2 text-xs text-text-secondary">Run the MCP server directly:</p>
				<div class="rounded-xl bg-bg-secondary/80 p-3">
					<code class="font-mono text-xs text-neon-green">python -m app.mcp_server</code>
				</div>
			</div>

			<div>
				<h3 class="mb-2 section-heading-dim text-[10px]">Claude Code Config</h3>
				<p class="mb-2 text-xs text-text-secondary">Add to your Claude Code MCP settings:</p>
				<pre class="overflow-x-auto rounded-xl bg-bg-secondary/80 p-3 font-mono text-xs leading-relaxed text-text-secondary">{configSnippet}</pre>
			</div>
		</div>
	</div>
{/if}
