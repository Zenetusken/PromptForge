<script lang="ts">
	import { API_BASE } from '$lib/api/client';
	import Icon from '$lib/components/Icon.svelte';
	import { EmptyState } from '$lib/components/ui';
	import { onMount } from 'svelte';

	interface TransformEntry {
		id: string;
		transform_type: string;
		input_text: string;
		output_text: string;
		created_at: string;
	}

	let transforms = $state<TransformEntry[]>([]);
	let loading = $state(true);
	let error = $state('');
	let selectedId = $state<string | null>(null);
	let detail = $state<TransformEntry | null>(null);

	onMount(() => {
		loadTransforms();
	});

	async function loadTransforms() {
		loading = true;
		error = '';
		try {
			const res = await fetch(`${API_BASE}/api/apps/textforge/transforms`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			transforms = data.transforms;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load transforms';
		} finally {
			loading = false;
		}
	}

	async function loadDetail(id: string) {
		selectedId = id;
		try {
			const res = await fetch(`${API_BASE}/api/apps/textforge/transforms/${id}`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			detail = await res.json();
		} catch (e) {
			detail = null;
			error = e instanceof Error ? e.message : 'Failed to load details';
		}
	}

	async function deleteTransform(id: string) {
		try {
			const res = await fetch(`${API_BASE}/api/apps/textforge/transforms/${id}`, {
				method: 'DELETE',
			});
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			transforms = transforms.filter(t => t.id !== id);
			if (selectedId === id) {
				selectedId = null;
				detail = null;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete transform';
		}
	}

	function formatDate(iso: string): string {
		try {
			return new Date(iso).toLocaleString(undefined, {
				month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
			});
		} catch {
			return iso;
		}
	}

	const TYPE_COLORS: Record<string, string> = {
		summarize: 'text-neon-cyan',
		expand: 'text-neon-green',
		rewrite: 'text-neon-purple',
		simplify: 'text-neon-teal',
		translate: 'text-neon-blue',
		extract_keywords: 'text-neon-yellow',
		fix_grammar: 'text-neon-pink',
	};
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<!-- Header -->
	<div class="flex items-center gap-2 border-b border-neon-orange/10 px-3 py-2">
		<Icon name="clock" size={14} class="text-neon-orange" />
		<span class="text-xs font-display font-bold uppercase tracking-widest text-neon-orange">Transform History</span>
		<span class="text-[10px] text-text-dim ml-auto">{transforms.length} entries</span>
		<button
			class="text-[10px] text-text-dim hover:text-neon-orange transition-colors"
			onclick={loadTransforms}
			title="Refresh"
		>
			<Icon name="refresh" size={10} />
		</button>
	</div>

	{#if loading}
		<div class="flex-1 flex items-center justify-center">
			<span class="text-[10px] text-text-dim">Loading...</span>
		</div>
	{:else if error && transforms.length === 0}
		<div class="flex-1 flex flex-col items-center justify-center gap-2 p-4">
			<Icon name="alert-circle" size={16} class="text-neon-red" />
			<span class="text-xs text-neon-red text-center">{error}</span>
			<button
				class="text-[10px] text-text-dim hover:text-neon-orange transition-colors mt-1"
				onclick={loadTransforms}
			>
				Retry
			</button>
		</div>
	{:else if transforms.length === 0}
		<div class="flex-1">
			<EmptyState icon="zap" message="No transforms yet" />
		</div>
	{:else}
		{#if error}
			<div class="flex items-center gap-2 px-3 py-1.5 border-b border-neon-red/10 bg-neon-red/5">
				<Icon name="alert-circle" size={10} class="text-neon-red shrink-0" />
				<span class="text-[10px] text-neon-red flex-1 truncate">{error}</span>
				<button class="text-[10px] text-text-dim hover:text-text-secondary" onclick={() => error = ''}>dismiss</button>
			</div>
		{/if}
		<div class="flex flex-1 min-h-0">
			<!-- List -->
			<div class="w-2/5 border-r border-neon-orange/5 overflow-y-auto">
				{#each transforms as t (t.id)}
					<button
						class="w-full text-left px-3 py-2 border-b border-neon-orange/5 transition-colors
							{selectedId === t.id ? 'bg-bg-hover border-l-2 border-l-neon-orange' : 'hover:bg-bg-hover/40'}"
						onclick={() => loadDetail(t.id)}
					>
						<div class="flex items-center gap-1.5">
							<span class="text-[10px] font-mono uppercase tracking-wider {TYPE_COLORS[t.transform_type] ?? 'text-text-secondary'}">
								{t.transform_type.replace('_', ' ')}
							</span>
							<span class="text-[9px] text-text-dim ml-auto">{formatDate(t.created_at)}</span>
						</div>
						<div class="text-[10px] text-text-secondary mt-0.5 truncate">{t.input_text}</div>
					</button>
				{/each}
			</div>

			<!-- Detail -->
			<div class="flex-1 overflow-y-auto p-3">
				{#if detail}
					<div class="space-y-3">
						<div class="flex items-center justify-between">
							<span class="text-[10px] font-display font-bold uppercase tracking-wider {TYPE_COLORS[detail.transform_type] ?? 'text-text-secondary'}">
								{detail.transform_type.replace('_', ' ')}
							</span>
							<button
								class="text-[10px] text-text-dim hover:text-neon-red transition-colors"
								onclick={() => detail && deleteTransform(detail.id)}
								title="Delete"
							>
								<Icon name="trash-2" size={10} />
							</button>
						</div>

						<div>
							<div class="text-[10px] text-text-dim uppercase tracking-wider mb-1">Input</div>
							<pre class="text-xs text-text-secondary whitespace-pre-wrap bg-bg-input p-2 border border-border-subtle">{detail.input_text}</pre>
						</div>

						<div>
							<div class="text-[10px] text-text-dim uppercase tracking-wider mb-1">Output</div>
							<pre class="text-xs text-text-primary whitespace-pre-wrap bg-bg-input p-2 border border-neon-orange/10">{detail.output_text}</pre>
						</div>

						<div class="text-[9px] text-text-dim">{formatDate(detail.created_at)}</div>
					</div>
				{:else}
					<EmptyState icon="chevron-left" message="Select a transform to view details" />
				{/if}
			</div>
		</div>
	{/if}
</div>
