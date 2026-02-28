<script lang="ts">
	let greeting = $state("Hello, World!");
	let name = $state("");
	let loading = $state(false);

	async function fetchGreeting() {
		if (!name.trim()) return;
		loading = true;
		try {
			const resp = await fetch(
				`/api/apps/hello-world/greet?name=${encodeURIComponent(name)}`,
			);
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data = await resp.json();
			greeting = data.message;
		} catch {
			greeting = "Failed to fetch greeting";
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex h-full flex-col items-center justify-center gap-6 p-8">
	<div class="text-4xl">{greeting}</div>

	<div class="flex items-center gap-3">
		<input
			bind:value={name}
			class="input-field w-48"
			placeholder="Enter a name..."
			onkeydown={(e) => e.key === "Enter" && fetchGreeting()}
		/>
		<button
			class="btn-primary"
			onclick={fetchGreeting}
			disabled={loading || !name.trim()}
		>
			{loading ? "..." : "Greet"}
		</button>
	</div>

	<p class="text-sm text-text-dim">
		This is a minimal example app running on the PromptForge kernel.
	</p>
</div>
