<script lang="ts">
	import { API_BASE } from '$lib/api/client';
	import Icon from '$lib/components/Icon.svelte';

	let greeting = $state('Hello, World!');
	let name = $state('');
	let loading = $state(false);

	async function fetchGreeting() {
		if (!name.trim()) return;
		loading = true;
		try {
			const resp = await fetch(
				`${API_BASE}/api/apps/hello-world/greet?name=${encodeURIComponent(name)}`,
			);
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data = await resp.json();
			greeting = data.message;
		} catch {
			greeting = 'Failed to fetch greeting';
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex h-full flex-col bg-bg-primary text-text-primary font-mono">
	<!-- Header -->
	<div class="flex items-center gap-2 border-b border-neon-green/10 px-3 py-2">
		<Icon name="sparkles" size={14} class="text-neon-green" />
		<span class="text-xs font-display font-bold uppercase tracking-widest text-neon-green">Hello World</span>
		<span class="text-[10px] text-text-dim ml-auto">Example App</span>
	</div>

	<!-- Content -->
	<div class="flex-1 flex flex-col items-center justify-center gap-4 p-4">
		<!-- Greeting display -->
		<div class="text-center">
			<div class="text-lg text-text-primary mb-1">{greeting}</div>
			<div class="h-px w-24 mx-auto" style="background: linear-gradient(90deg, transparent, rgba(34, 255, 136, 0.3), transparent)"></div>
		</div>

		<!-- Input row -->
		<div class="flex items-center gap-2">
			<input
				bind:value={name}
				class="bg-bg-input border border-neon-green/10 text-xs text-text-primary px-3 py-1.5 w-48 outline-none
					focus:border-neon-green/30 transition-colors placeholder:text-text-dim/50"
				placeholder="Enter a name..."
				onkeydown={(e) => e.key === 'Enter' && fetchGreeting()}
			/>
			<button
				class="flex items-center gap-1.5 px-3 py-1.5 text-[11px] border border-neon-green/20 text-neon-green
					hover:bg-neon-green/10 hover:border-neon-green/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
				onclick={fetchGreeting}
				disabled={loading || !name.trim()}
			>
				<Icon name="arrow-up-right" size={10} />
				{loading ? '...' : 'Greet'}
			</button>
		</div>

		<!-- Footer info -->
		<p class="text-[10px] text-text-dim text-center max-w-[240px]">
			Minimal example app running on the PromptForge kernel. Demonstrates window registration, commands, and API integration.
		</p>
	</div>
</div>
