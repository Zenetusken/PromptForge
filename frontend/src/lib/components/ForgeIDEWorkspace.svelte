<script lang="ts">
    import { onDestroy, onMount } from "svelte";
    import { forgeSession } from "$lib/stores/forgeSession.svelte";
    import { optimizationState } from "$lib/stores/optimization.svelte";
    import { forgeMachine } from "$lib/stores/forgeMachine.svelte";
    import { promptAnalysis } from "$lib/stores/promptAnalysis.svelte";
    import { projectsState } from "$lib/stores/projects.svelte";
    import { restoreTabState } from "$lib/stores/tabCoherence";
    import ForgeIDEExplorer from "./ForgeIDEExplorer.svelte";
    import ForgeIDEEditor from "./ForgeIDEEditor.svelte";
    import ForgeIDEInspector from "./ForgeIDEInspector.svelte";

    // Cancel any pending analysis debounce timer on teardown
    onDestroy(() => promptAnalysis.destroy());

    // Hydration recovery: restore result for active tab on page reload
    onMount(() => {
        const tab = forgeSession.activeTab;
        if (tab?.resultId && tab.mode === 'review' && !optimizationState.forgeResult) {
            restoreTabState(tab);
        } else if (forgeMachine.mode === 'review' && !optimizationState.forgeResult) {
            forgeMachine.back();
        }
    });

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
    class="flex h-full w-full bg-bg-primary overflow-hidden"
>
    <ForgeIDEExplorer />
    <ForgeIDEEditor />
    <ForgeIDEInspector />
</div>
