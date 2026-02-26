<script lang="ts">
	import { Dialog } from 'bits-ui';
	import Icon from './Icon.svelte';
	import { clipboardService } from '$lib/services/clipboardService.svelte';
	import { useCopyFeedback } from '$lib/utils/useCopyFeedback.svelte';
	import { providerState } from '$lib/stores/provider.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { Tooltip } from './ui';

	let { open = $bindable(false) }: { open: boolean } = $props();

	// ── Constants ──
	const SSE_ENDPOINT = 'http://localhost:8001/sse';
	const MCP_PORT = ':8001';
	const QUICK_START_CMD = 'python -m app.mcp_server';
	const TOOL_COPY_FLASH_MS = 1500;

	const configSnippet = `{
  "mcpServers": {
    "promptforge": {
      "type": "sse",
      "url": "${SSE_ENDPOINT}"
    }
  }
}`;

	// ── Copy feedback ──
	let copiedToolName: string | null = $state(null);
	let copiedToolTimer: ReturnType<typeof setTimeout> | null = null;
	const sseCopy = useCopyFeedback();
	const quickStartCopy = useCopyFeedback();
	const configCopy = useCopyFeedback();

	// ── Search ──
	let searchQuery = $state('');

	// Reset search when dialog closes
	$effect(() => {
		if (!open) searchQuery = '';
	});

	// Cleanup timers on destroy
	$effect(() => {
		return () => {
			if (copiedToolTimer) clearTimeout(copiedToolTimer);
		};
	});

	// ── MCP status ──
	let mcpStatus = $derived<'connected' | 'disconnected' | 'checking'>(
		providerState.healthChecking
			? 'checking'
			: providerState.health?.mcp_connected
				? 'connected'
				: 'disconnected'
	);

	const statusColors: Record<string, string> = {
		connected: 'var(--color-neon-green)',
		disconnected: 'var(--color-neon-orange)',
		checking: 'var(--color-neon-yellow)',
	};

	const statusLabels: Record<string, string> = {
		connected: 'MCP Connected',
		disconnected: 'MCP Disconnected',
		checking: 'Checking...',
	};

	// ── Tool data ──

	type ToolCategory = {
		label: string;
		color: string;
		borderColor: string;
		tools: { name: string; desc: string }[];
	};

	const categories: ToolCategory[] = [
		{
			label: 'Pipeline',
			color: 'var(--color-neon-cyan)',
			borderColor: 'rgba(0, 229, 255, 0.2)',
			tools: [
				{ name: 'optimize', desc: 'Run the full 4-stage pipeline on a prompt' },
				{ name: 'retry', desc: 'Re-run with optional strategy override' },
				{ name: 'batch', desc: 'Optimize multiple prompts in one call (1\u201320)' },
				{ name: 'cancel', desc: 'Cancel a running optimization' },
			],
		},
		{
			label: 'Query',
			color: 'var(--color-neon-blue)',
			borderColor: 'rgba(77, 142, 255, 0.2)',
			tools: [
				{ name: 'get', desc: 'Retrieve an optimization by ID' },
				{ name: 'list', desc: 'List with filtering, sorting, pagination' },
				{ name: 'get_by_project', desc: 'Get all optimizations for a project' },
				{ name: 'search', desc: 'Full-text search across prompts, titles, tags' },
			],
		},
		{
			label: 'Organize',
			color: 'var(--color-neon-purple)',
			borderColor: 'rgba(168, 85, 247, 0.2)',
			tools: [
				{ name: 'tag', desc: 'Add/remove tags, set title or project' },
				{ name: 'stats', desc: 'Usage statistics, optionally scoped to a project' },
				{ name: 'strategies', desc: 'List all available optimization strategies' },
			],
		},
		{
			label: 'Projects',
			color: 'var(--color-neon-green)',
			borderColor: 'rgba(34, 255, 136, 0.2)',
			tools: [
				{ name: 'list_projects', desc: 'List projects with filtering and pagination' },
				{ name: 'get_project', desc: 'Retrieve a project with its prompts' },
				{ name: 'create_project', desc: 'Create a new project for grouping prompts' },
				{ name: 'add_prompt', desc: 'Add a prompt to a project' },
				{ name: 'update_prompt', desc: 'Update prompt content with auto-versioning' },
				{ name: 'set_project_context', desc: 'Set or clear codebase context profile' },
			],
		},
		{
			label: 'Destructive',
			color: 'var(--color-neon-red)',
			borderColor: 'rgba(255, 51, 102, 0.2)',
			tools: [
				{ name: 'delete', desc: 'Permanently delete an optimization record' },
				{ name: 'bulk_delete', desc: 'Delete multiple records by ID (1\u2013100)' },
			],
		},
	];

	const totalTools = categories.reduce((sum, c) => sum + c.tools.length, 0);

	// ── Filtered categories ──
	let filteredCategories = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		if (!q) return categories;
		return categories
			.map((cat) => ({
				...cat,
				tools: cat.tools.filter(
					(t) => t.name.toLowerCase().includes(q) || t.desc.toLowerCase().includes(q)
				),
			}))
			.filter((cat) => cat.tools.length > 0);
	});

	let filteredToolCount = $derived(
		filteredCategories.reduce((sum, c) => sum + c.tools.length, 0)
	);

	let isFiltering = $derived(searchQuery.trim().length > 0);

	// ── Actions ──

	function copyToolName(name: string) {
		clipboardService.copy(name, `Tool: ${name}`, 'mcp-info');
		copiedToolName = name;
		if (copiedToolTimer) clearTimeout(copiedToolTimer);
		copiedToolTimer = setTimeout(() => {
			copiedToolName = null;
			copiedToolTimer = null;
		}, TOOL_COPY_FLASH_MS);
	}

	function copySSE() {
		sseCopy.copy(SSE_ENDPOINT);
		clipboardService.copy(SSE_ENDPOINT, 'SSE Endpoint', 'mcp-info');
	}

	function copyQuickStart() {
		quickStartCopy.copy(QUICK_START_CMD);
		clipboardService.copy(QUICK_START_CMD, 'Quick Start command', 'mcp-info');
	}

	function copyConfig() {
		configCopy.copy(configSnippet);
		clipboardService.copy(configSnippet, 'MCP config JSON', 'mcp-info');
	}

	function openTerminal() {
		open = false;
		windowManager.openTerminal();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay class="!bg-black/70 !backdrop-blur-md" data-testid="mcp-info-backdrop" />
		<Dialog.Content
			class="!max-w-[540px] !p-0 !overflow-hidden"
			data-testid="mcp-info-panel"
		>
			<!-- Title bar — window chrome style -->
			<div
				class="flex items-center gap-2 px-3 py-2 border-b"
				style="background: var(--color-bg-secondary); border-color: var(--color-border-subtle);"
			>
				<div
					class="flex h-6 w-6 items-center justify-center rounded-md"
					style="background: rgba(0, 229, 255, 0.08); border: 1px solid rgba(0, 229, 255, 0.15);"
				>
					<Icon name="terminal" size={12} class="text-neon-cyan" />
				</div>
				<Dialog.Title class="font-display text-xs font-bold uppercase tracking-widest text-text-primary">
					MCP Integration
				</Dialog.Title>
				<span
					class="rounded-full px-1.5 py-px font-mono text-[9px] font-bold"
					style="color: var(--color-neon-cyan); background: rgba(0, 229, 255, 0.08); border: 1px solid rgba(0, 229, 255, 0.15);"
				>
					{#if isFiltering}{filteredToolCount}/{/if}{totalTools}
				</span>

				<!-- Live status dot -->
				<Tooltip text={statusLabels[mcpStatus]}>
					<div
						class="h-2 w-2 rounded-full shrink-0"
						style="background: {statusColors[mcpStatus]};"
					></div>
				</Tooltip>

				<Dialog.Close
					class="wc-btn wc-close ml-auto"
					aria-label="Close"
				>
					<Icon name="x" size={12} />
				</Dialog.Close>
			</div>

			<!-- Scrollable body -->
			<div class="mcp-body overflow-y-auto" style="max-height: calc(85vh - 80px); padding: 10px 12px;">
				<Dialog.Description class="mb-2 text-[11px] leading-relaxed text-text-secondary">
					PromptForge exposes a <span class="text-neon-cyan font-semibold">Model Context Protocol</span> server.
					Claude Code and other MCP clients can forge prompts directly from the terminal.
				</Dialog.Description>

				<!-- SSE Endpoint chip -->
				<button
					class="mcp-sse-chip flex items-center gap-1.5 px-2 py-1 mb-3 rounded-md text-[10px] font-mono transition-colors duration-150"
					onclick={copySSE}
					aria-label="Copy SSE endpoint URL"
				>
					<Icon name="server" size={10} class="shrink-0" />
					<span>{SSE_ENDPOINT}</span>
					{#if sseCopy.copied}
						<Icon name="check" size={10} class="shrink-0" style="color: var(--color-neon-green);" />
					{:else}
						<Icon name="copy" size={10} class="shrink-0 opacity-40" />
					{/if}
				</button>

				<!-- Search filter -->
				<div class="relative mb-2">
					<Icon name="search" size={10} class="absolute left-2 top-1/2 -translate-y-1/2 text-text-dim pointer-events-none" />
					<input
						type="text"
						class="input-field w-full pl-6 pr-6 py-1 text-[10px]"
						placeholder="Filter tools..."
						bind:value={searchQuery}
					/>
					{#if searchQuery}
						<button
							class="mcp-inline-copy absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 text-text-dim hover:text-text-primary transition-colors"
							onclick={() => (searchQuery = '')}
							aria-label="Clear search"
						>
							<Icon name="x" size={10} />
						</button>
					{/if}
				</div>

				<!-- Categorized tools -->
				<div class="space-y-2">
					{#each filteredCategories as cat}
						<div class="mcp-category" style="--cat-color: {cat.color}; --cat-border: {cat.borderColor};">
							<!-- Category header -->
							<div class="flex items-center gap-1.5 mb-1">
								<div
									class="h-1.5 w-1.5 rounded-full shrink-0"
									style="background: {cat.color};"
								></div>
								<span class="section-heading-dim !text-[9px]" style="color: {cat.color}; opacity: 0.7;">
									{cat.label}
								</span>
								<div class="flex-1 h-px" style="background: linear-gradient(90deg, {cat.borderColor}, transparent 80%);"></div>
							</div>

							<!-- Tool rows -->
							<div>
								{#each cat.tools as tool}
									<button
										class="mcp-tool-row flex items-center gap-2 py-[3px] w-full text-left"
										onclick={() => copyToolName(tool.name)}
									>
										<code
											class="mcp-tool-name font-mono text-[11px] font-semibold shrink-0 transition-colors duration-150"
											style={copiedToolName === tool.name ? 'color: var(--color-neon-green);' : ''}
										>{tool.name}</code>
										<span class="text-[10px] leading-snug text-text-dim">{tool.desc}</span>
										<span
											class="mcp-copy-hint ml-auto shrink-0"
											class:mcp-copy-visible={copiedToolName === tool.name}
										>
											{#if copiedToolName === tool.name}
												<Icon name="check" size={10} style="color: var(--color-neon-green);" />
											{:else}
												<Icon name="copy" size={10} />
											{/if}
										</span>
									</button>
								{/each}
							</div>
						</div>
					{/each}

					{#if filteredCategories.length === 0}
						<div class="text-center py-4 text-[10px] text-text-dim">
							No tools matching "{searchQuery}"
						</div>
					{/if}
				</div>

				<!-- Divider -->
				<div class="divider-glow my-3"></div>

				<!-- Setup section — stacked -->
				<div class="space-y-2">
					<div>
						<h3 class="section-heading-dim !text-[9px] mb-1">Quick Start</h3>
						<div class="mcp-code-block flex items-center gap-1.5 px-2 py-1.5">
							<Icon name="terminal" size={10} class="text-text-dim shrink-0" />
							<code class="font-mono text-[10px] text-neon-green flex-1">{QUICK_START_CMD}</code>
							<button
								class="mcp-inline-copy shrink-0 p-0.5 transition-colors duration-150"
								onclick={copyQuickStart}
								aria-label="Copy command"
							>
								{#if quickStartCopy.copied}
									<Icon name="check" size={10} style="color: var(--color-neon-green);" />
								{:else}
									<Icon name="copy" size={10} class="text-text-dim" />
								{/if}
							</button>
						</div>
					</div>

					<div>
						<h3 class="section-heading-dim !text-[9px] mb-1">Claude Code Config<span class="ml-1.5 font-mono text-[9px] font-normal normal-case tracking-normal text-text-dim">.mcp.json</span></h3>
						<div class="mcp-code-block relative px-2 py-1.5">
							<button
								class="mcp-inline-copy absolute top-1.5 right-1.5 p-0.5 transition-colors duration-150"
								onclick={copyConfig}
								aria-label="Copy config"
							>
								{#if configCopy.copied}
									<Icon name="check" size={10} style="color: var(--color-neon-green);" />
								{:else}
									<Icon name="copy" size={10} class="text-text-dim" />
								{/if}
							</button>
							<pre class="font-mono text-[9px] leading-[1.6] text-text-dim whitespace-pre">{configSnippet}</pre>
						</div>
					</div>
				</div>
			</div>

			<!-- Footer actions -->
			<div
				class="flex items-center px-3 py-1.5 border-t"
				style="background: var(--color-bg-secondary); border-color: var(--color-border-subtle);"
			>
				<button class="btn-ghost flex items-center gap-1.5 text-[10px]" onclick={openTerminal}>
					<Icon name="terminal" size={10} />
					Open Terminal
				</button>
				<div class="ml-auto flex items-center gap-1.5 text-[9px] text-text-dim font-mono">
					<div
						class="h-1.5 w-1.5 rounded-full shrink-0"
						style="background: {statusColors[mcpStatus]};"
					></div>
					{MCP_PORT}
				</div>
			</div>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>

<style>
	/* Tool row — button reset + sharp left accent on hover */
	.mcp-tool-row {
		background: none;
		border: none;
		border-left: 2px solid transparent;
		padding: 3px 8px;
		cursor: pointer;
		font: inherit;
		color: inherit;
		transition: border-color 150ms, background-color 150ms;
	}

	.mcp-tool-row:hover {
		border-left-color: var(--cat-color);
		background: rgba(255, 255, 255, 0.02);
	}

	/* Copy hint — hidden until row hover or active copy flash */
	.mcp-copy-hint {
		opacity: 0;
		color: var(--color-text-dim);
		transition: opacity 150ms;
	}

	.mcp-tool-row:hover .mcp-copy-hint {
		opacity: 0.5;
	}

	.mcp-copy-visible {
		opacity: 1 !important;
	}

	/* Tool name inherits category color */
	.mcp-tool-name {
		color: var(--cat-color);
	}

	/* Code blocks */
	.mcp-code-block {
		background: var(--color-bg-secondary);
		border: 1px solid var(--color-border-subtle);
		border-radius: 6px;
	}

	/* SSE endpoint chip */
	.mcp-sse-chip {
		background: var(--color-bg-input);
		border: 1px solid var(--color-border-subtle);
		color: var(--color-neon-cyan);
		cursor: pointer;
	}

	.mcp-sse-chip:hover {
		border-color: var(--color-neon-cyan);
		background: rgba(0, 229, 255, 0.04);
	}

	/* Inline copy / clear buttons — shared reset */
	.mcp-inline-copy {
		background: none;
		border: none;
		cursor: pointer;
		line-height: 1;
	}

	.mcp-inline-copy:hover {
		opacity: 1;
	}
</style>
