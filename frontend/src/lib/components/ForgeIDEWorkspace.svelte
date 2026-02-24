<script lang="ts">
    import { forgeSession } from "$lib/stores/forgeSession.svelte";
    import { promptAnalysis } from "$lib/stores/promptAnalysis.svelte";
    import { projectsState } from "$lib/stores/projects.svelte";
    import ForgeIDEExplorer from "./ForgeIDEExplorer.svelte";
    import ForgeIDEEditor from "./ForgeIDEEditor.svelte";
    import ForgeIDEInspector from "./ForgeIDEInspector.svelte";

    // Drive promptAnalysis from the current draft text
    $effect(() => {
        const text = forgeSession.draft.text;
        if (text.trim()) {
            promptAnalysis.analyzePrompt(text);
        } else {
            promptAnalysis.reset();
        }
    });

    // Ensure projects list is loaded for autocomplete
    $effect(() => {
        if (!projectsState.allItemsLoaded) {
            projectsState.loadAllProjects();
        }
    });
</script>

<div
    class="flex h-full w-full bg-bg-primary overflow-hidden border-t border-neon-cyan/10"
>
    <ForgeIDEExplorer />
    <ForgeIDEEditor />
    <ForgeIDEInspector />
</div>
