<script lang="ts">
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
		class="fixed inset-0 z-50 flex cursor-default items-center justify-center bg-black/60 backdrop-blur-sm"
		onclick={handleBackdropClick}
		onkeydown={(e) => { if (e.key === 'Escape') open = false; }}
		role="button"
		tabindex="-1"
		aria-label="Close MCP info"
		data-testid="mcp-info-backdrop"
	>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="relative mx-4 max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-neon-cyan/20 bg-bg-card p-6 text-left shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			data-testid="mcp-info-panel"
		>
			<!-- Close button -->
			<button
				class="absolute right-3 top-3 rounded-lg p-1 text-text-dim transition-colors hover:bg-text-dim/10 hover:text-text-primary"
				onclick={() => (open = false)}
				aria-label="Close"
			>
				<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</button>

			<!-- Header -->
			<div class="mb-4 flex items-center gap-2">
				<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-neon-cyan">
					<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
				</svg>
				<h2 class="font-mono text-lg font-semibold text-text-primary">MCP Integration</h2>
			</div>

			<p class="mb-4 text-sm text-text-secondary">
				PromptForge exposes a <span class="font-mono text-neon-cyan">Model Context Protocol</span> (MCP) server,
				allowing Claude Code and other MCP-compatible clients to optimize prompts directly from the command line.
			</p>

			<!-- Tools list -->
			<div class="mb-4">
				<h3 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">Available Tools</h3>
				<div class="space-y-1.5">
					{#each tools as tool}
						<div class="rounded-lg bg-bg-secondary px-3 py-2">
							<span class="font-mono text-xs text-neon-cyan">{tool.name}</span>
							<p class="text-xs text-text-dim">{tool.desc}</p>
						</div>
					{/each}
				</div>
			</div>

			<!-- Setup instructions -->
			<div class="mb-4">
				<h3 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">Quick Start</h3>
				<p class="mb-2 text-xs text-text-secondary">Run the MCP server directly:</p>
				<div class="rounded-lg bg-bg-secondary p-3">
					<code class="font-mono text-xs text-neon-green">python -m app.mcp_server</code>
				</div>
			</div>

			<div>
				<h3 class="mb-2 font-mono text-xs font-semibold uppercase tracking-wider text-text-secondary">Claude Code Config</h3>
				<p class="mb-2 text-xs text-text-secondary">Add to your Claude Code MCP settings:</p>
				<pre class="overflow-x-auto rounded-lg bg-bg-secondary p-3 font-mono text-xs text-text-secondary">{configSnippet}</pre>
			</div>
		</div>
	</div>
{/if}
