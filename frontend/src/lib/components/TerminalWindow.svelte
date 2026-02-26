<script lang="ts">
	import { commandPalette } from '$lib/services/commandPalette.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { processScheduler } from '$lib/stores/processScheduler.svelte';
	import { historyState } from '$lib/stores/history.svelte';
	import { statsState } from '$lib/stores/stats.svelte';
	import { windowManager } from '$lib/stores/windowManager.svelte';
	import { normalizeScore } from '$lib/utils/format';
	import Icon from './Icon.svelte';
	import { onMount, tick } from 'svelte';

	interface TermLine {
		type: 'input' | 'output' | 'error' | 'system';
		text: string;
		timestamp: number;
	}

	let lines: TermLine[] = $state([
		{ type: 'system', text: 'PromptForge OS Terminal v1.0', timestamp: Date.now() },
		{ type: 'system', text: 'Type "help" for available commands.', timestamp: Date.now() },
	]);
	let inputValue = $state('');
	let commandHistory: string[] = $state([]);
	let historyIndex = $state(-1);
	let inputRef: HTMLInputElement;
	let scrollRef: HTMLDivElement;

	const COMMANDS: Record<string, { desc: string; handler: (args: string) => Promise<string | string[]> }> = {
		help: {
			desc: 'Show available commands',
			handler: async () => [
				'Available commands:',
				'  help              Show this help message',
				'  stats             Show optimization statistics',
				'  processes         List active processes',
				'  history [n]       Show recent history (default: 5)',
				'  commands          List registered commands',
				'  events [n]        Show recent bus events (default: 10)',
				'  clear             Clear terminal',
				'  forge "text"      Load a prompt into the IDE',
				'  forge! "text"     Forge a prompt immediately',
				'  tournament "text" s1 s2...  Multi-strategy tournament',
				'  chain             Chain forge from last result',
				'  mcp               Show MCP activity status',
				'  mcp-log [n]       Show recent MCP events (default: 10)',
				'  netmon            Open Network Monitor',
				'  open <window>     Open a window (ide, projects, history, etc)',
				'  close <window>    Close a window',
				'  version           Show system version',
			],
		},
		stats: {
			desc: 'Show optimization statistics',
			handler: async () => {
				const s = statsState.activeStats;
				if (!s) return 'No stats available. Run some forges first.';
				return [
					`Total optimizations: ${s.total_optimizations}`,
					`Average score: ${s.average_overall_score != null ? normalizeScore(s.average_overall_score) : 'N/A'}`,
					`Projects: ${s.total_projects}`,
					`Today: ${s.optimizations_today}`,
					`Most common type: ${s.most_common_task_type ?? 'N/A'}`,
				];
			},
		},
		processes: {
			desc: 'List active processes',
			handler: async () => {
				const procs = processScheduler.processes;
				if (procs.length === 0) return 'No processes.';
				return procs.map(p =>
					`  PID ${p.pid}  ${p.status.padEnd(10)} ${p.title.slice(0, 40)}`
				);
			},
		},
		history: {
			desc: 'Show recent history',
			handler: async (args) => {
				const n = parseInt(args) || 5;
				const items = historyState.items.slice(0, n);
				if (items.length === 0) return 'No history.';
				return items.map(item =>
					`  ${item.id.slice(0, 8)} ${item.status.padEnd(10)} ${normalizeScore(item.overall_score ?? 0)}/10 ${item.raw_prompt.slice(0, 40)}...`
				);
			},
		},
		commands: {
			desc: 'List registered commands',
			handler: async () => {
				const cmds = commandPalette.commands;
				if (cmds.length === 0) return 'No commands registered.';
				return cmds.map(c =>
					`  ${c.id.padEnd(25)} ${c.shortcut ?? ''.padEnd(12)} ${c.label}`
				);
			},
		},
		events: {
			desc: 'Show recent bus events',
			handler: async (args) => {
				const n = parseInt(args) || 10;
				const events = systemBus.recentEvents.slice(0, n);
				if (events.length === 0) return 'No recent events.';
				return events.map(e => {
					const time = new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
					return `  [${time}] ${e.type} from ${e.source}`;
				});
			},
		},
		clear: {
			desc: 'Clear terminal',
			handler: async () => {
				lines = [];
				return '';
			},
		},
		forge: {
			desc: 'Start a forge with the given prompt',
			handler: async (args) => {
				const prompt = args.replace(/^["']|["']$/g, '').trim();
				if (!prompt) return 'Usage: forge "your prompt text here"';

				const { forgeMachine } = await import('$lib/stores/forgeMachine.svelte');
				const { forgeSession } = await import('$lib/stores/forgeSession.svelte');
				forgeMachine.restore();
				forgeSession.updateDraft({ text: prompt });
				forgeSession.activate();
				windowManager.openIDE();

				return `Forge loaded: "${prompt.slice(0, 60)}${prompt.length > 60 ? '...' : ''}"`;
			},
		},
		'forge!': {
			desc: 'Forge a prompt immediately',
			handler: async (args) => {
				const prompt = args.replace(/^["']|["']$/g, '').trim();
				if (!prompt) return 'Usage: forge! "your prompt text here"';

				const { optimizationState } = await import('$lib/stores/optimization.svelte');
				const { forgeMachine } = await import('$lib/stores/forgeMachine.svelte');
				forgeMachine.forge();
				windowManager.openIDE();
				optimizationState.startOptimization(prompt);

				return `Forging: "${prompt.slice(0, 60)}${prompt.length > 60 ? '...' : ''}"`;
			},
		},
		tournament: {
			desc: 'Tournament: tournament "prompt" strategy1 strategy2...',
			handler: async (args) => {
				// Parse: first quoted string is prompt, rest are strategy names
				const quoteMatch = args.match(/^["'](.+?)["']\s*(.*)/s);
				if (!quoteMatch) return 'Usage: tournament "your prompt" strategy1 strategy2 ...';
				const prompt = quoteMatch[1].trim();
				const strategies = quoteMatch[2].trim().split(/\s+/).filter(Boolean);
				if (strategies.length < 2) return 'Need at least 2 strategies. Example: tournament "prompt" co-star chain-of-thought few-shot-scaffolding';

				const { optimizationState } = await import('$lib/stores/optimization.svelte');
				optimizationState.startTournament(prompt, strategies);
				windowManager.openIDE();

				return `Tournament started with ${strategies.length} strategies: ${strategies.join(', ')}`;
			},
		},
		chain: {
			desc: 'Chain forge from last result',
			handler: async () => {
				const { optimizationState } = await import('$lib/stores/optimization.svelte');
				const result = optimizationState.result;
				if (!result) return 'No result to chain from. Run a forge first.';

				optimizationState.chainForge(result);
				windowManager.openIDE();

				return `Chaining from: "${result.optimized.slice(0, 60)}${result.optimized.length > 60 ? '...' : ''}"`;
			},
		},
		open: {
			desc: 'Open a window',
			handler: async (args) => {
				const target = args.trim().toLowerCase();
				const windows: Record<string, () => void> = {
					ide: () => windowManager.openIDE(),
					projects: () => windowManager.openProjectsWindow(),
					history: () => windowManager.openHistoryWindow(),
					'control-panel': () => windowManager.openControlPanel(),
					'task-manager': () => windowManager.openTaskManager(),
					'network-monitor': () => windowManager.openNetworkMonitor(),
				};
				if (windows[target]) {
					windows[target]();
					return `Opened ${target}`;
				}
				return `Unknown window: ${target}. Available: ${Object.keys(windows).join(', ')}`;
			},
		},
		close: {
			desc: 'Close a window',
			handler: async (args) => {
				const target = args.trim().toLowerCase();
				windowManager.closeWindow(target);
				return `Closed ${target}`;
			},
		},
		mcp: {
			desc: 'Show MCP activity status',
			handler: async () => {
				const { mcpActivityFeed } = await import('$lib/services/mcpActivityFeed.svelte');
				return [
					`MCP Activity Feed: ${mcpActivityFeed.connected ? 'Connected' : 'Disconnected'}`,
					`  Active calls: ${mcpActivityFeed.activeCalls.length}`,
					`  Sessions: ${mcpActivityFeed.sessionCount}`,
					`  Total events: ${mcpActivityFeed.totalEventsReceived}`,
					`  Buffered: ${mcpActivityFeed.events.length}`,
				];
			},
		},
		'mcp-log': {
			desc: 'Show recent MCP events',
			handler: async (args) => {
				const n = parseInt(args) || 10;
				const { mcpActivityFeed } = await import('$lib/services/mcpActivityFeed.svelte');
				const events = mcpActivityFeed.events.slice(0, n);
				if (events.length === 0) return 'No MCP events.';
				return events.map(e => {
					const time = new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
					const dur = e.duration_ms != null ? ` (${e.duration_ms}ms)` : '';
					return `  [${time}] ${e.event_type.padEnd(14)} ${(e.tool_name ?? '-').padEnd(18)} ${e.error ?? e.message ?? ''}${dur}`;
				});
			},
		},
		netmon: {
			desc: 'Open Network Monitor',
			handler: async () => {
				windowManager.openNetworkMonitor();
				return 'Opened Network Monitor';
			},
		},
		version: {
			desc: 'Show system version',
			handler: async () => {
				const { providerState } = await import('$lib/stores/provider.svelte');
				return [
					'PromptForge OS',
					`  Backend: ${providerState.health?.version || 'Unknown'}`,
					`  Provider: ${providerState.health?.llm_provider || 'Auto-detect'}`,
					`  Model: ${providerState.health?.llm_model || 'Default'}`,
				];
			},
		},
	};

	async function executeCommand(input: string) {
		const trimmed = input.trim();
		if (!trimmed) return;

		lines = [...lines, { type: 'input', text: `$ ${trimmed}`, timestamp: Date.now() }];
		commandHistory = [trimmed, ...commandHistory.slice(0, 50)];
		historyIndex = -1;

		const [cmd, ...argParts] = trimmed.split(/\s+/);
		const args = argParts.join(' ');
		const handler = COMMANDS[cmd.toLowerCase()];

		if (!handler) {
			lines = [...lines, { type: 'error', text: `Unknown command: ${cmd}. Type "help" for available commands.`, timestamp: Date.now() }];
		} else {
			try {
				const result = await handler.handler(args);
				if (Array.isArray(result)) {
					for (const line of result) {
						if (line) lines = [...lines, { type: 'output', text: line, timestamp: Date.now() }];
					}
				} else if (result) {
					lines = [...lines, { type: 'output', text: result, timestamp: Date.now() }];
				}
			} catch (err: any) {
				lines = [...lines, { type: 'error', text: `Error: ${err?.message ?? 'Unknown error'}`, timestamp: Date.now() }];
			}
		}

		await tick();
		scrollRef?.scrollTo({ top: scrollRef.scrollHeight, behavior: 'smooth' });
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			executeCommand(inputValue);
			inputValue = '';
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			if (historyIndex < commandHistory.length - 1) {
				historyIndex++;
				inputValue = commandHistory[historyIndex];
			}
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			if (historyIndex > 0) {
				historyIndex--;
				inputValue = commandHistory[historyIndex];
			} else {
				historyIndex = -1;
				inputValue = '';
			}
		}
	}

	const LINE_COLORS: Record<TermLine['type'], string> = {
		input: 'text-neon-cyan',
		output: 'text-text-primary',
		error: 'text-neon-red',
		system: 'text-text-dim',
	};

	onMount(() => {
		inputRef?.focus();
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="flex h-full flex-col bg-bg-primary text-text-primary font-mono"
	onclick={() => inputRef?.focus()}
	onkeydown={() => inputRef?.focus()}
>
	<!-- Output area -->
	<div class="flex-1 overflow-y-auto p-3 space-y-0.5" bind:this={scrollRef}>
		{#each lines as line (line.timestamp + line.text)}
			<div class="text-[11px] {LINE_COLORS[line.type]} whitespace-pre-wrap break-words leading-relaxed">
				{line.text}
			</div>
		{/each}
	</div>

	<!-- Input line -->
	<div class="flex items-center gap-2 border-t border-neon-cyan/10 px-3 py-2">
		<span class="text-[11px] text-neon-cyan shrink-0">$</span>
		<input
			bind:this={inputRef}
			bind:value={inputValue}
			type="text"
			class="flex-1 bg-transparent text-[11px] text-text-primary outline-none caret-neon-cyan"
			placeholder="Type a command..."
			onkeydown={handleKeydown}
			spellcheck="false"
			autocomplete="off"
		/>
	</div>
</div>
