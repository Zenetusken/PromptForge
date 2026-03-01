<script lang="ts">
	import { knowledge } from "$lib/kernel/services/knowledge.svelte";
	import type { KnowledgeSource } from "$lib/kernel/types";
	import Icon from "./Icon.svelte";

	interface Props {
		appId: string;
		entityId: string;
		projectStatus?: string;
	}

	let { appId, entityId, projectStatus = "active" }: Props = $props();

	let sources = $state<KnowledgeSource[]>([]);
	let totalChars = $state(0);
	let loading = $state(false);
	let error = $state("");

	// Add form state
	let showAddForm = $state(false);
	let addTitle = $state("");
	let addContent = $state("");
	let addType = $state("document");
	let saving = $state(false);

	// Edit state
	let editingId = $state<string | null>(null);
	let editTitle = $state("");
	let editContent = $state("");

	// Preview state
	let previewId = $state<string | null>(null);

	const isReadOnly = $derived(projectStatus !== "active");
	const maxChars = 100_000;
	const budgetPercent = $derived(Math.min(100, Math.round((totalChars / maxChars) * 100)));

	async function loadSources() {
		loading = true;
		error = "";
		try {
			const items = await knowledge.getSources(appId, entityId);
			sources = items;
			totalChars = items.reduce((sum, s) => sum + s.char_count, 0);
		} catch {
			error = "Failed to load sources";
		} finally {
			loading = false;
		}
	}

	async function handleAdd() {
		if (!addTitle.trim() || !addContent.trim()) return;
		saving = true;
		try {
			const result = await knowledge.addSource(appId, entityId, {
				title: addTitle.trim(),
				content: addContent,
				source_type: addType,
			});
			if (result) {
				sources = [...sources, result];
				totalChars += result.char_count;
				addTitle = "";
				addContent = "";
				addType = "document";
				showAddForm = false;
			}
		} catch {
			error = "Failed to add source";
		} finally {
			saving = false;
		}
	}

	async function handleDelete(id: string) {
		const src = sources.find((s) => s.id === id);
		if (!src) return;
		try {
			await knowledge.deleteSource(id);
			totalChars -= src.char_count;
			sources = sources.filter((s) => s.id !== id);
		} catch {
			error = "Failed to delete source";
		}
	}

	async function handleToggle(id: string) {
		try {
			const result = await knowledge.toggleSource(id);
			if (result) {
				sources = sources.map((s) => (s.id === id ? result : s));
			}
		} catch {
			error = "Failed to toggle source";
		}
	}

	function startEdit(src: KnowledgeSource) {
		editingId = src.id;
		editTitle = src.title;
		editContent = src.content;
	}

	async function saveEdit() {
		if (!editingId || !editTitle.trim()) return;
		saving = true;
		try {
			const result = await knowledge.updateSource(editingId, {
				title: editTitle.trim(),
				content: editContent,
			});
			if (result) {
				const oldSrc = sources.find((s) => s.id === editingId);
				const charDiff = result.char_count - (oldSrc?.char_count ?? 0);
				totalChars += charDiff;
				sources = sources.map((s) => (s.id === editingId ? result : s));
				editingId = null;
			}
		} catch {
			error = "Failed to update source";
		} finally {
			saving = false;
		}
	}

	function cancelEdit() {
		editingId = null;
	}

	const TYPE_LABELS: Record<string, string> = {
		document: "Doc",
		paste: "Paste",
		api_reference: "API",
		specification: "Spec",
		notes: "Notes",
	};

	function formatChars(n: number): string {
		if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
		return String(n);
	}

	$effect(() => {
		if (entityId) loadSources();
	});
</script>

<div class="space-y-2">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-1.5">
			<Icon name="file-text" size={12} class="text-neon-cyan" />
			<span class="text-[11px] font-medium text-text-primary">Knowledge Sources</span>
			<span class="text-[9px] text-text-dim">({sources.length})</span>
		</div>
		{#if !isReadOnly}
			<button
				type="button"
				class="flex items-center gap-1 rounded-sm border border-neon-cyan/20 px-1.5 py-0.5 text-[9px] text-neon-cyan hover:bg-neon-cyan/8 transition-colors"
				onclick={() => (showAddForm = !showAddForm)}
			>
				<Icon name={showAddForm ? "x" : "plus"} size={10} />
				{showAddForm ? "Cancel" : "Add Source"}
			</button>
		{/if}
	</div>

	<!-- Budget bar -->
	{#if sources.length > 0}
		<div class="flex items-center gap-2">
			<div class="h-1 flex-1 rounded-full bg-bg-hover border border-white/[0.04]">
				<div
					class="h-full rounded-full transition-all {budgetPercent > 80 ? 'bg-neon-orange' : 'bg-neon-cyan/60'}"
					style="width: {budgetPercent}%"
				></div>
			</div>
			<span class="text-[9px] font-mono text-text-dim">{formatChars(totalChars)} / {formatChars(maxChars)}</span>
		</div>
	{/if}

	<!-- Add form -->
	{#if showAddForm}
		<div class="rounded-sm border border-neon-cyan/15 bg-bg-secondary p-2 space-y-1.5">
			<input
				type="text"
				bind:value={addTitle}
				placeholder="Source title (e.g. Architecture Doc)"
				maxlength="200"
				class="w-full rounded-sm border border-white/[0.08] bg-bg-input px-2 py-1 text-[11px] text-text-primary placeholder:text-text-dim/50 focus:border-neon-cyan/30 focus:outline-none"
			/>
			<select
				bind:value={addType}
				class="rounded-sm border border-white/[0.08] bg-bg-input px-1.5 py-0.5 text-[10px] text-text-secondary"
			>
				<option value="document">Document</option>
				<option value="paste">Paste</option>
				<option value="api_reference">API Reference</option>
				<option value="specification">Specification</option>
				<option value="notes">Notes</option>
			</select>
			<textarea
				bind:value={addContent}
				placeholder="Paste your reference document content here..."
				rows="6"
				class="w-full rounded-sm border border-white/[0.08] bg-bg-input px-2 py-1.5 font-mono text-[10px] text-text-primary placeholder:text-text-dim/50 focus:border-neon-cyan/30 focus:outline-none resize-y"
			></textarea>
			<div class="flex items-center justify-between">
				<span class="text-[9px] font-mono text-text-dim">{formatChars(addContent.length)} chars</span>
				<button
					type="button"
					disabled={saving || !addTitle.trim() || !addContent.trim()}
					onclick={handleAdd}
					class="rounded-sm border border-neon-cyan/30 bg-neon-cyan/10 px-2 py-0.5 text-[10px] text-neon-cyan hover:bg-neon-cyan/15 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
				>
					{saving ? "Adding..." : "Add Source"}
				</button>
			</div>
		</div>
	{/if}

	<!-- Error -->
	{#if error}
		<p class="text-[10px] text-neon-red">{error}</p>
	{/if}

	<!-- Loading -->
	{#if loading}
		<p class="text-[10px] text-text-dim">Loading sources...</p>
	{/if}

	<!-- Source list -->
	{#if sources.length === 0 && !loading}
		<p class="text-[10px] text-text-dim italic">
			No sources yet. Add reference documents to ground your prompts.
		</p>
	{:else}
		<div class="space-y-1">
			{#each sources as src (src.id)}
				{#if editingId === src.id}
					<!-- Edit mode -->
					<div class="rounded-sm border border-neon-cyan/20 bg-bg-secondary p-2 space-y-1.5">
						<input
							type="text"
							bind:value={editTitle}
							maxlength="200"
							class="w-full rounded-sm border border-white/[0.08] bg-bg-input px-2 py-1 text-[11px] text-text-primary focus:border-neon-cyan/30 focus:outline-none"
						/>
						<textarea
							bind:value={editContent}
							rows="6"
							class="w-full rounded-sm border border-white/[0.08] bg-bg-input px-2 py-1.5 font-mono text-[10px] text-text-primary focus:border-neon-cyan/30 focus:outline-none resize-y"
						></textarea>
						<div class="flex gap-1.5 justify-end">
							<button
								type="button"
								onclick={cancelEdit}
								class="rounded-sm border border-white/[0.08] px-2 py-0.5 text-[10px] text-text-secondary hover:text-text-primary transition-colors"
							>
								Cancel
							</button>
							<button
								type="button"
								disabled={saving}
								onclick={saveEdit}
								class="rounded-sm border border-neon-cyan/30 bg-neon-cyan/10 px-2 py-0.5 text-[10px] text-neon-cyan hover:bg-neon-cyan/15 disabled:opacity-30 transition-colors"
							>
								{saving ? "Saving..." : "Save"}
							</button>
						</div>
					</div>
				{:else}
					<!-- View mode -->
					<div
						class="rounded-sm border transition-colors {src.enabled
							? 'border-white/[0.06] bg-bg-card'
							: 'border-white/[0.03] bg-bg-card/50 opacity-50'}"
					>
						<div class="flex items-center gap-2 px-2 py-1.5">
							<!-- svelte-ignore a11y_click_events_have_key_events -->
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div
								class="min-w-0 flex-1 cursor-pointer"
								onclick={() => { previewId = previewId === src.id ? null : src.id; }}
							>
								<div class="flex items-center gap-1.5">
									<Icon name={previewId === src.id ? "chevron-down" : "chevron-right"} size={10} class="shrink-0 text-text-dim" />
									<span class="truncate text-[11px] text-text-primary">{src.title}</span>
									<span
										class="shrink-0 rounded-sm border border-neon-cyan/15 bg-neon-cyan/5 px-1 py-px text-[8px] font-mono text-neon-cyan/70"
									>
										{TYPE_LABELS[src.source_type] ?? src.source_type}
									</span>
								</div>
								<span class="text-[9px] font-mono text-text-dim ml-[22px]">{formatChars(src.char_count)} chars</span>
							</div>
							{#if !isReadOnly}
								<div class="flex shrink-0 items-center gap-1">
									<button
										type="button"
										title={src.enabled ? "Disable" : "Enable"}
										onclick={() => handleToggle(src.id)}
										class="p-0.5 text-text-dim hover:text-neon-green transition-colors"
									>
										<Icon name={src.enabled ? "eye" : "eye-off"} size={12} />
									</button>
									<button
										type="button"
										title="Edit"
										onclick={() => { previewId = null; startEdit(src); }}
										class="p-0.5 text-text-dim hover:text-neon-cyan transition-colors"
									>
										<Icon name="edit" size={12} />
									</button>
									<button
										type="button"
										title="Delete"
										onclick={() => handleDelete(src.id)}
										class="p-0.5 text-text-dim hover:text-neon-red transition-colors"
									>
										<Icon name="trash-2" size={12} />
									</button>
								</div>
							{/if}
						</div>
						{#if previewId === src.id}
							<div class="mx-2 mb-1.5 border-t border-white/[0.04] pt-1.5">
								<pre class="whitespace-pre-wrap font-mono text-[10px] text-text-secondary leading-snug max-h-48 overflow-y-auto">{src.content.slice(0, 2000)}{src.content.length > 2000 ? '\n... (truncated)' : ''}</pre>
							</div>
						{/if}
					</div>
				{/if}
			{/each}
		</div>
	{/if}
</div>
