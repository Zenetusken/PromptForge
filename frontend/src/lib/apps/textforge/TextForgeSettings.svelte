<script lang="ts">
	import { appSettings } from '$lib/kernel/services/appSettings.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';

	const APP_ID = 'textforge';

	const TRANSFORM_OPTIONS = [
		{ id: 'summarize', label: 'Summarize' },
		{ id: 'expand', label: 'Expand' },
		{ id: 'rewrite', label: 'Rewrite' },
		{ id: 'simplify', label: 'Simplify' },
		{ id: 'translate', label: 'Translate' },
		{ id: 'extract_keywords', label: 'Extract Keywords' },
		{ id: 'fix_grammar', label: 'Fix Grammar' },
	];

	const FORMAT_OPTIONS = [
		{ id: 'plain', label: 'Plain Text' },
		{ id: 'markdown', label: 'Markdown' },
	];

	let settings = $derived(appSettings.get(APP_ID));
	let loading = $derived(appSettings.isLoading(APP_ID));
	let error = $state('');

	let defaultTransform = $derived((settings.defaultTransform as string) ?? 'summarize');
	let outputFormat = $derived((settings.outputFormat as string) ?? 'plain');
	let preserveFormatting = $derived((settings.preserveFormatting as boolean) ?? true);

	onMount(() => {
		appSettings.load(APP_ID).catch((e: Error) => {
			error = e.message || 'Failed to load settings';
		});
	});

	async function updateSetting(key: string, value: unknown) {
		error = '';
		try {
			await appSettings.save(APP_ID, { [key]: value });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save setting';
		}
	}

	async function resetAll() {
		error = '';
		try {
			await appSettings.reset(APP_ID);
			await appSettings.load(APP_ID);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to reset settings';
		}
	}
</script>

<div class="space-y-3">
	<h3 class="section-heading">
		<Icon name="zap" size={12} class="inline -mt-px mr-1 text-neon-orange" />TextForge Settings
	</h3>

	{#if error}
		<div class="flex items-center gap-2 p-2 border border-neon-red/20 bg-neon-red/5">
			<Icon name="alert-circle" size={10} class="text-neon-red shrink-0" />
			<span class="text-[10px] text-neon-red">{error}</span>
		</div>
	{/if}

	{#if loading}
		<p class="text-[10px] text-text-dim">Loading...</p>
	{:else}
		<div class="space-y-2">
			<label class="flex items-center justify-between">
				<span class="text-xs text-text-secondary">Default Transform</span>
				<select
					class="bg-bg-input border border-neon-orange/10 text-xs text-text-primary px-2 py-1 outline-none focus:border-neon-orange/30"
					value={defaultTransform}
					onchange={(e) => updateSetting('defaultTransform', (e.target as HTMLSelectElement).value)}
				>
					{#each TRANSFORM_OPTIONS as opt (opt.id)}
						<option value={opt.id}>{opt.label}</option>
					{/each}
				</select>
			</label>

			<label class="flex items-center justify-between">
				<span class="text-xs text-text-secondary">Output Format</span>
				<select
					class="bg-bg-input border border-neon-orange/10 text-xs text-text-primary px-2 py-1 outline-none focus:border-neon-orange/30"
					value={outputFormat}
					onchange={(e) => updateSetting('outputFormat', (e.target as HTMLSelectElement).value)}
				>
					{#each FORMAT_OPTIONS as opt (opt.id)}
						<option value={opt.id}>{opt.label}</option>
					{/each}
				</select>
			</label>

			<label class="flex items-center justify-between">
				<span class="text-xs text-text-secondary">Preserve Formatting</span>
				<input
					type="checkbox"
					class="accent-neon-orange"
					checked={preserveFormatting}
					onchange={(e) => updateSetting('preserveFormatting', (e.target as HTMLInputElement).checked)}
				/>
			</label>
		</div>

		<button
			class="mt-2 border border-neon-red/20 px-3 py-1.5 text-[11px] text-neon-red hover:bg-neon-red/10 transition-colors"
			onclick={resetAll}
		>
			Reset TextForge Settings
		</button>
	{/if}
</div>
