import { fetchProject, type ProjectDetail, type ProjectPrompt } from '$lib/api/client';
import { optimizationState } from '$lib/stores/optimization.svelte';
import { forgeSession } from '$lib/stores/forgeSession.svelte';
import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
import { toastState } from '$lib/stores/toast.svelte';

export interface PromptOpenerContext {
	promptId: string;
	projectId: string;
	projectData?: ProjectDetail;
	prompt?: ProjectPrompt;
}

/**
 * Open a project prompt in the IDE.
 * - If the prompt has forges, opens the latest forge in review mode.
 * - If the prompt has no forges, opens in compose mode with the prompt text.
 */
export async function openPromptInIDE(ctx: PromptOpenerContext): Promise<void> {
	// Resolve project data
	const projectData = ctx.projectData ?? (await fetchProject(ctx.projectId));
	if (!projectData) { toastState.show('Could not load project', 'error'); return; }

	// Resolve prompt
	const prompt = ctx.prompt ?? projectData.prompts.find((p) => p.id === ctx.promptId);
	if (!prompt) { toastState.show('Prompt not found in project', 'error'); return; }

	// Derive a meaningful tab title
	const tabTitle = prompt.latest_forge?.title || projectData.name;

	if (prompt.forge_count > 0 && prompt.latest_forge) {
		// Open latest forge result in IDE review mode
		await optimizationState.openInIDEFromHistory(prompt.latest_forge.id);
		// Populate the left pane with the prompt text for reiteration
		forgeSession.loadRequest({
			text: prompt.content,
			title: tabTitle,
			project: projectData.name,
			promptId: prompt.id,
			sourceAction: 'reiterate',
			contextProfile: projectData.context_profile,
		});
		// Re-assert review mode after loadRequest (which may switch to compose)
		forgeMachine.enterReview();
	} else {
		// No forges — open in compose mode with the prompt text
		forgeMachine.restore();
		// loadRequest sets isActive, opens IDE, and populates the draft
		forgeSession.loadRequest({
			text: prompt.content,
			title: tabTitle,
			project: projectData.name,
			promptId: prompt.id,
			sourceAction: 'optimize',
			contextProfile: projectData.context_profile,
		});
	}
}
