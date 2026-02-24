<script lang="ts">
	import { onMount } from "svelte";
	import { projectsState } from "$lib/stores/projects.svelte";
	import { sidebarState } from "$lib/stores/sidebar.svelte";
	import Icon from "./Icon.svelte";

	let activeProjects = $derived(
		projectsState.items.filter((p) => p.status === "active").slice(0, 4),
	);

	// Load projects once on mount if not yet loaded (onMount prevents
	// infinite retry loops if the fetch fails — unlike $effect which
	// would re-fire when isLoading resets to false after an error).
	onMount(() => {
		if (!projectsState.hasLoaded && !projectsState.isLoading) {
			projectsState.loadProjects();
		}
	});
</script>

{#if activeProjects.length > 0}
	<div class="group/projects">
		<div class="mb-1 flex items-center justify-between px-1">
			<p
				class="section-heading-dim transition-colors duration-200 group-hover/projects:text-neon-cyan"
			>
				Projects
			</p>
			<button
				type="button"
				onclick={() => sidebarState.openTo("projects")}
				class="text-[11px] font-medium text-text-dim transition-colors duration-300 hover:text-neon-cyan"
			>
				View all &rarr;
			</button>
		</div>

		<div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
			{#each activeProjects as project, i}
				<a
					href="/projects/{project.id}"
					class="group flex flex-col justify-between gap-0.5 rounded-md p-1.5 no-underline animate-fade-in glass-panel-bleed card-hover-bleed"
					style="animation-delay: {i *
						75}ms; animation-fill-mode: both;"
				>
					<!-- Top Row: Icon + Name -->
					<div class="flex items-center gap-1.5 min-w-0">
						<!-- Folder Icon with sharp border contour -->
						<div
							class="relative flex h-5 w-5 shrink-0 items-center justify-center rounded bg-black/40 border border-neon-cyan/10 transition-colors duration-300 group-hover:border-neon-cyan/60 group-hover:bg-neon-cyan/5"
						>
							<Icon
								name="folder"
								size={12}
								class="relative z-10 text-neon-cyan/60 transition-colors duration-300 group-hover:text-neon-cyan"
							/>
						</div>

						<span
							class="truncate text-[12px] font-display font-bold tracking-tight text-text-primary/90 group-hover:text-white transition-colors"
						>
							{project.name}
						</span>
					</div>

					<!-- Bottom Row: Stats & Desc -->
					<div class="flex flex-col gap-1 mt-0">
						<!-- Description -->
						<span
							class="truncate text-[10px] text-text-dim/70 group-hover:text-text-dim transition-colors"
						>
							{project.description || "No description"}
						</span>

						<!-- Progress Track-like Stats -->
						<div
							class="flex items-center justify-between rounded bg-black/40 border border-white/5 px-1.5 py-0.5 mt-0 group-hover:border-neon-cyan/40 transition-colors duration-300"
						>
							<div
								class="flex items-center gap-1.5 font-mono text-[10px] text-text-dim group-hover:text-neon-cyan/80 transition-colors"
							>
								<span
									class="font-bold text-text-primary group-hover:text-neon-cyan transition-colors"
									>{project.prompt_count}</span
								>
								<span class="uppercase tracking-wide"
									>{project.prompt_count === 1
										? "prompt"
										: "prompts"}</span
								>
							</div>

							{#if project.has_context}
								<div
									class="flex items-center gap-1.5"
									title="Has context profile"
								>
									<span
										class="font-mono text-[9px] uppercase tracking-wider text-neon-green/60 group-hover:text-neon-green transition-colors"
										>CTX</span
									>
									<span
										class="inline-block h-1.5 w-1.5 rounded-full bg-neon-green/70 group-hover:bg-neon-green transition-colors"
									></span>
								</div>
							{:else}
								<div
									class="h-1.5 w-1.5 rounded-full bg-border-subtle/50"
								></div>
							{/if}
						</div>
					</div>
				</a>
			{/each}
		</div>
	</div>
{/if}
