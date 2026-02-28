<script lang="ts">
	import Icon from './Icon.svelte';
	import { settingsState, NEON_COLORS, NEON_COLOR_HEX, type WallpaperMode } from '$lib/stores/settings.svelte';

	const PRESETS = [
		{ key: 'low' as const, label: 'Low', icon: 'minus' as const, desc: 'Static wallpaper' },
		{ key: 'balanced' as const, label: 'Balanced', icon: 'activity' as const, desc: 'Turbine spins' },
		{ key: 'high' as const, label: 'High', icon: 'zap' as const, desc: 'Full effects' },
	];

	const MODES: { key: WallpaperMode; label: string }[] = [
		{ key: 'static', label: 'Static' },
		{ key: 'subtle', label: 'Subtle' },
		{ key: 'dynamic', label: 'Dynamic' },
	];

	let opacityPercent = $derived(Math.round(settingsState.wallpaperOpacity * 100));

	function handleOpacity(e: Event) {
		const val = Number((e.target as HTMLInputElement).value);
		settingsState.update({ wallpaperOpacity: val / 100 });
	}
</script>

<div class="flex h-full overflow-y-auto bg-bg-primary">
	<div class="w-full max-w-xl mx-auto p-3 space-y-5 text-xs">
		<!-- Section 1: Performance Profile -->
		<section>
			<h3 class="section-heading mb-2">Performance Profile</h3>
			<div class="grid grid-cols-3 gap-2">
				{#each PRESETS as preset (preset.key)}
					{@const active = settingsState.performanceProfile === preset.key}
					<button
						class="flex flex-col items-center gap-1.5 py-3 px-2 border transition-colors
							{active
								? 'border-neon-cyan bg-neon-cyan/5'
								: 'border-border-subtle hover:border-white/15'}"
						onclick={() => settingsState.applyPreset(preset.key)}
					>
						<Icon name={preset.icon} size={14}
							class={active ? 'text-neon-cyan' : 'text-text-dim'} />
						<span class="font-semibold {active ? 'text-neon-cyan' : 'text-text-secondary'}">{preset.label}</span>
						<span class="text-[9px] text-text-dim">{preset.desc}</span>
					</button>
				{/each}
			</div>
			{#if settingsState.performanceProfile === 'custom'}
				<div class="flex items-center gap-1.5 mt-2 text-[10px] text-neon-orange">
					<Icon name="settings" size={10} />
					<span>Custom &mdash; settings don't match a preset</span>
				</div>
			{/if}
		</section>

		<hr class="border-border-subtle" />

		<!-- Section 2: Wallpaper -->
		<section class="space-y-3">
			<h3 class="section-heading">Wallpaper</h3>
			<!-- Animation segmented control -->
			<div>
				<span class="text-[10px] text-text-dim block mb-1">Animation</span>
				<div class="flex border border-border-subtle">
					{#each MODES as mode (mode.key)}
						{@const active = settingsState.wallpaperMode === mode.key}
						<button
							class="flex-1 py-1.5 text-center transition-colors
								{active
									? 'bg-neon-cyan/8 text-neon-cyan'
									: 'text-text-dim hover:text-text-secondary'}"
							style={active ? 'box-shadow: inset 0 0 0 1px var(--color-neon-cyan)' : ''}
							onclick={() => settingsState.update({ wallpaperMode: mode.key })}
						>
							{mode.label}
						</button>
					{/each}
				</div>
			</div>

			<!-- Opacity slider -->
			<label class="block">
				<div class="flex items-center justify-between mb-1">
					<span class="text-[10px] text-text-dim">Opacity</span>
					<span class="text-[10px] font-mono text-neon-cyan">{opacityPercent}%</span>
				</div>
				<input
					id="display-wallpaper-opacity"
					type="range"
					class="cyber-range"
					min="5"
					max="35"
					step="1"
					value={opacityPercent}
					oninput={handleOpacity}
				/>
			</label>
		</section>

		<hr class="border-border-subtle" />

		<!-- Section 3: Theme -->
		<section>
			<h3 class="section-heading mb-2">Theme</h3>
			<div>
				<span class="text-[10px] text-text-dim block mb-1.5">Accent Color</span>
				<div class="flex flex-wrap gap-2">
					{#each NEON_COLORS as color (color)}
						<button
							class="w-8 h-8 border transition-colors
								{settingsState.accentColor === color
									? 'border-white/60'
									: 'border-border-subtle hover:border-white/25'}"
							onclick={() => settingsState.update({ accentColor: color })}
							title={color.replace('neon-', '')}
							style="background-color: {NEON_COLOR_HEX[color]}"
						></button>
					{/each}
				</div>
			</div>
		</section>

		<hr class="border-border-subtle" />

		<!-- Section 4: Visual Effects -->
		<section>
			<h3 class="section-heading mb-2">Visual Effects</h3>
			<label class="flex items-center gap-2 cursor-pointer">
				<input
					id="display-enable-animations"
					type="checkbox"
					class="accent-neon-cyan"
					checked={settingsState.enableAnimations}
					onchange={() => settingsState.update({ enableAnimations: !settingsState.enableAnimations })}
				/>
				<span class="text-text-secondary">UI Animations</span>
			</label>
		</section>
	</div>
</div>
