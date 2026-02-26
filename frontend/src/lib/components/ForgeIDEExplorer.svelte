<script lang="ts">
	import { projectsState } from '$lib/stores/projects.svelte';
	import ForgeMetadataSection from './ForgeMetadataSection.svelte';
	import ForgeContextSection from './ForgeContextSection.svelte';
</script>

<div class="flex h-full w-56 shrink-0 flex-col overflow-y-auto border-r border-neon-cyan/10 bg-bg-secondary p-2 gap-1.5">
	<div class="text-[10px] font-bold uppercase tracking-widest text-text-dim">Workspace Explorer</div>

	<!-- Metadata (title, version, project, tags) — stacked in narrow pane -->
	<ForgeMetadataSection projectListId="ide-project-suggestions" compact />

	<!-- Context (stack templates, codebase fields) — stacked in narrow pane -->
	<ForgeContextSection compact />

	<!-- Project autocomplete datalist -->
	<datalist id="ide-project-suggestions">
		{#each projectsState.allItems as p}
			<option value={p.name}></option>
		{/each}
	</datalist>
</div>
