<script lang="ts">
	import { API_BASE } from '$lib/api/client';
	import Icon from '$lib/components/Icon.svelte';
	import { InlineProgress, EmptyState } from '$lib/components/ui';
	import { processScheduler } from '$lib/stores/processScheduler.svelte';
	import { systemBus } from '$lib/services/systemBus.svelte';
	import { appSettings } from '$lib/kernel/services/appSettings.svelte';

	const TRANSFORM_TYPES = [
		{ id: 'summarize', label: 'Summarize', icon: 'minimize-2' },
		{ id: 'expand', label: 'Expand', icon: 'maximize-2' },
		{ id: 'rewrite', label: 'Rewrite', icon: 'edit' },
		{ id: 'simplify', label: 'Simplify', icon: 'layers' },
		{ id: 'translate', label: 'Translate', icon: 'code' },
		{ id: 'extract_keywords', label: 'Extract Keywords', icon: 'search' },
		{ id: 'fix_grammar', label: 'Fix Grammar', icon: 'check-circle' },
	];

	let inputText = $state('');
	let outputText = $state('');
	let selectedType = $state('summarize');
	let tone = $state('professional');
	let language = $state('English');
	let isTransforming = $state(false);
	let transformProgress = $state(0);
	let error = $state('');
	let activeProcessId = $state<string | null>(null);

	// Load default transform from settings
	$effect(() => {
		const settings = appSettings.get('textforge');
		if (settings.defaultTransform && typeof settings.defaultTransform === 'string') {
			selectedType = settings.defaultTransform;
		}
	});

	async function runTransform() {
		if (!inputText.trim() || isTransforming) return;
		isTransforming = true;
		transformProgress = 0;
		error = '';
		outputText = '';

		// Capture values before spawn to avoid closure issues
		const capturedInput = inputText;
		const capturedType = selectedType;
		const capturedTone = tone;
		const capturedLanguage = language;

		const proc = processScheduler.spawn({
			title: `Transform: ${capturedType}`,
			processType: 'transform',
			onExecute: (p) => executeTransform(p.id, capturedInput, capturedType, capturedTone, capturedLanguage),
		});
		activeProcessId = proc.id;
	}

	async function executeTransform(
		procId: string,
		input: string,
		transformType: string,
		transformTone: string,
		transformLanguage: string,
	) {
		try {
			transformProgress = 10;
			processScheduler.updateProgress(procId, 'analyze', 0.1);

			const res = await fetch(`${API_BASE}/api/apps/textforge/transform`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					input_text: input,
					transform_type: transformType,
					tone: transformTone,
					language: transformLanguage,
				}),
			});

			transformProgress = 60;
			processScheduler.updateProgress(procId, 'transform', 0.6);

			if (!res.ok) {
				const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
				throw new Error(errData.detail || `HTTP ${res.status}`);
			}

			const data = await res.json();
			outputText = data.output_text;

			transformProgress = 100;
			processScheduler.updateProgress(procId, 'validate', 1.0);
			processScheduler.complete(procId, {});

			systemBus.emit('transform:completed', 'textforge', {
				transform_type: transformType,
				id: data.id,
			});
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Transform failed';
			error = msg;
			processScheduler.fail(procId, msg);
			systemBus.emit('transform:failed', 'textforge', { error: msg });
		} finally {
			isTransforming = false;
			transformProgress = 0;
			activeProcessId = null;
		}
	}

	function clearAll() {
		inputText = '';
		outputText = '';
		error = '';
	}

	let charCount = $derived(inputText.length);
	let wordCount = $derived(inputText.trim() ? inputText.trim().split(/\s+/).length : 0);
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<!-- Header bar -->
	<div class="flex items-center gap-3 border-b border-neon-orange/10 px-3 py-2">
		<Icon name="zap" size={14} class="text-neon-orange" />
		<span class="text-xs font-display font-bold uppercase tracking-widest text-neon-orange">TextForge</span>
		<span class="text-[10px] text-text-dim ml-auto">{charCount} chars / {wordCount} words</span>
	</div>

	<!-- Transform type selector -->
	<div class="flex items-center gap-1.5 border-b border-neon-orange/5 px-3 py-1.5 overflow-x-auto">
		{#each TRANSFORM_TYPES as t (t.id)}
			<button
				class="flex items-center gap-1 px-2 py-1 text-[10px] border transition-colors shrink-0
					{selectedType === t.id
						? 'border-neon-orange/30 bg-neon-orange/8 text-neon-orange'
						: 'border-transparent text-text-dim hover:text-text-secondary hover:border-neon-orange/10'}"
				onclick={() => selectedType = t.id}
			>
				<Icon name={t.icon as any} size={10} />
				{t.label}
			</button>
		{/each}
	</div>

	<!-- Extra options for rewrite/translate -->
	{#if selectedType === 'rewrite'}
		<div class="flex items-center gap-2 border-b border-neon-orange/5 px-3 py-1.5">
			<span class="text-[10px] text-text-dim">Tone:</span>
			<select
				class="bg-bg-input border border-neon-orange/10 text-[10px] text-text-primary px-2 py-0.5 outline-none focus:border-neon-orange/30"
				bind:value={tone}
			>
				<option value="professional">Professional</option>
				<option value="casual">Casual</option>
				<option value="formal">Formal</option>
				<option value="friendly">Friendly</option>
				<option value="technical">Technical</option>
				<option value="academic">Academic</option>
			</select>
		</div>
	{:else if selectedType === 'translate'}
		<div class="flex items-center gap-2 border-b border-neon-orange/5 px-3 py-1.5">
			<span class="text-[10px] text-text-dim">Language:</span>
			<select
				class="bg-bg-input border border-neon-orange/10 text-[10px] text-text-primary px-2 py-0.5 outline-none focus:border-neon-orange/30"
				bind:value={language}
			>
				<option value="English">English</option>
				<option value="Spanish">Spanish</option>
				<option value="French">French</option>
				<option value="German">German</option>
				<option value="Japanese">Japanese</option>
				<option value="Chinese">Chinese</option>
				<option value="Korean">Korean</option>
				<option value="Portuguese">Portuguese</option>
			</select>
		</div>
	{/if}

	<!-- Main content: input + output split -->
	<div class="flex-1 flex min-h-0">
		<!-- Input panel -->
		<div class="flex-1 flex flex-col border-r border-neon-orange/5">
			<div class="flex items-center px-3 py-1">
				<span class="text-[10px] text-text-dim uppercase tracking-wider">Input</span>
			</div>
			<textarea
				class="flex-1 resize-none bg-bg-input px-3 py-2 text-xs text-text-primary outline-none placeholder:text-text-dim/50 font-mono"
				placeholder="Paste or type your text here..."
				bind:value={inputText}
			></textarea>
		</div>

		<!-- Output panel -->
		<div class="flex-1 flex flex-col">
			<div class="flex items-center px-3 py-1">
				<span class="text-[10px] text-text-dim uppercase tracking-wider">Output</span>
				{#if outputText}
					<button
						class="ml-auto text-[10px] text-text-dim hover:text-neon-orange transition-colors"
						onclick={() => {
							navigator.clipboard.writeText(outputText);
						}}
					>
						<Icon name="copy" size={10} />
					</button>
				{/if}
			</div>
			<div class="flex-1 overflow-y-auto px-3 py-2">
				{#if isTransforming}
					<div class="flex flex-col items-center justify-center h-full gap-3">
						<InlineProgress percent={transformProgress} color="cyan" class="w-32" />
						<span class="text-[10px] text-neon-orange animate-pulse">Transforming... {transformProgress}%</span>
					</div>
				{:else if error}
					<div class="flex items-start gap-2 p-2 border border-neon-red/20 bg-neon-red/5">
						<Icon name="alert-circle" size={12} class="text-neon-red shrink-0 mt-0.5" />
						<span class="text-xs text-neon-red">{error}</span>
					</div>
				{:else if outputText}
					<pre class="text-xs text-text-primary whitespace-pre-wrap font-mono">{outputText}</pre>
				{:else}
					<EmptyState icon="zap" message="Output will appear here" />
				{/if}
			</div>
		</div>
	</div>

	<!-- Action bar -->
	<div class="flex items-center gap-2 border-t border-neon-orange/10 px-3 py-2">
		<button
			class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] border border-neon-orange/20 text-neon-orange
				hover:bg-neon-orange/10 hover:border-neon-orange/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
			onclick={runTransform}
			disabled={!inputText.trim() || isTransforming}
		>
			<Icon name="zap" size={12} />
			Transform
		</button>
		<button
			class="px-3 py-1.5 text-[11px] border border-border-subtle text-text-dim hover:text-text-secondary hover:border-border-accent transition-colors"
			onclick={clearAll}
		>
			Clear
		</button>
		<span class="ml-auto text-[10px] text-text-dim">
			{selectedType.replace('_', ' ')}
		</span>
	</div>
</div>
