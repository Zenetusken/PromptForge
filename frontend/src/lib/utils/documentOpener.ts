import type { FileDescriptor, NodeDescriptor, PromptDescriptor, ArtifactDescriptor, SubArtifactDescriptor } from './fileDescriptor';
import { isFolderDescriptor } from './fileDescriptor';
import { toArtifactName } from './fileTypes';
import { fetchProject, fetchOptimization, fetchPromptDirect } from '$lib/api/client';
import { optimizationState, mapToResultState } from '$lib/stores/optimization.svelte';
import { forgeSession } from '$lib/stores/forgeSession.svelte';
import { forgeMachine } from '$lib/stores/forgeMachine.svelte';
import { windowManager } from '$lib/stores/windowManager.svelte';
import { saveActiveTabState, restoreTabState } from '$lib/stores/tabCoherence';
import { toastState } from '$lib/stores/toast.svelte';
import { appRegistry } from '$lib/kernel/services/appRegistry.svelte';
import type { GenericFileDescriptor } from '$lib/kernel/types';

/**
 * Single entry point for opening any document type in the IDE or a folder window.
 * Replaces the separate openPromptInIDE() and openInIDEFromHistory() paths.
 *
 * All entry points (HistoryWindow, ProjectsWindow, StartMenu, notifications,
 * TaskManager, drag-and-drop) should funnel through this function.
 */
export async function openDocument(descriptor: NodeDescriptor): Promise<void> {
	if (isFolderDescriptor(descriptor)) {
		windowManager.openFolderWindow(descriptor.id, descriptor.name);
		return;
	}
	return openFileDocument(descriptor);
}

/** Handle file descriptors (prompt/artifact/template) — opens in IDE. */
async function openFileDocument(descriptor: FileDescriptor): Promise<void> {
	// Dedup: if a tab already has this document, focus it instead of creating a new one
	const existingTab = forgeSession.findTabByDocument(descriptor);
	if (existingTab) {
		saveActiveTabState();
		forgeSession.activeTabId = existingTab.id;
		forgeSession.isActive = true;
		windowManager.openIDE();
		restoreTabState(existingTab);
		return;
	}

	switch (descriptor.kind) {
		case 'prompt':
			return openPrompt(descriptor);
		case 'artifact':
			return openArtifact(descriptor);
		case 'sub-artifact':
			return openSubArtifact(descriptor);
		case 'template':
			// Future extensibility — no-op for now
			return;
		default:
			// Fallback: route unknown file types through the app registry
			return openViaRegistry(descriptor);
	}
}

/**
 * Open a project prompt in the IDE with its document descriptor attached to the tab.
 * If the prompt has existing forges, opens the latest in review mode.
 * If no forges, opens in compose mode ready for optimization.
 * Handles desktop prompts (projectId is empty) via direct fetch.
 */
async function openPrompt(descriptor: PromptDescriptor): Promise<void> {
	// Desktop prompts (project_id=null) have empty projectId — fetch directly
	if (!descriptor.projectId) {
		return openDesktopPrompt(descriptor);
	}

	const projectData = await fetchProject(descriptor.projectId);
	if (!projectData) {
		toastState.show('Could not load project', 'error');
		return;
	}

	const prompt = projectData.prompts.find((p) => p.id === descriptor.id);
	if (!prompt) {
		toastState.show('Prompt not found in project', 'error');
		return;
	}

	const tabTitle = prompt.latest_forge?.title || projectData.name;

	if (prompt.forge_count > 0 && prompt.latest_forge) {
		// Fetch the forge result data (without triggering enterReview/openIDE yet)
		const item = await fetchOptimization(prompt.latest_forge.id);
		if (item) {
			const result = mapToResultState({ ...item }, item.raw_prompt);
			optimizationState.forgeResult = result;
		}
		// Create tab with prompt text for reiteration
		forgeSession.loadRequest({
			text: prompt.content,
			title: tabTitle,
			project: projectData.name,
			promptId: prompt.id,
			sourceAction: 'reiterate',
			contextProfile: projectData.context_profile,
		});
		forgeMachine.enterReview();
	} else {
		// No forges — open in compose mode
		forgeMachine.restore();
		forgeSession.loadRequest({
			text: prompt.content,
			title: tabTitle,
			project: projectData.name,
			promptId: prompt.id,
			sourceAction: 'optimize',
			contextProfile: projectData.context_profile,
		});
	}

	// Attach document descriptor to the tab (shared for both paths)
	forgeSession.activeTab.document = descriptor;
}

/**
 * Open a desktop prompt (project_id=null) via direct filesystem fetch.
 */
async function openDesktopPrompt(descriptor: PromptDescriptor): Promise<void> {
	const node = await fetchPromptDirect(descriptor.id);
	if (!node || !node.content) {
		toastState.show('Could not load prompt', 'error');
		return;
	}

	forgeMachine.restore();
	forgeSession.loadRequest({
		text: node.content,
		title: descriptor.name,
		project: '',
		promptId: descriptor.id,
		sourceAction: 'optimize',
	});

	forgeSession.activeTab.document = descriptor;
}

/**
 * Shared helper: fetch a forge result by ID, set it as the active result,
 * create a tab, attach the descriptor, and open IDE in review mode.
 * Used by both artifact and sub-artifact openers.
 */
async function openForgeResult(optimizationId: string, descriptor: ArtifactDescriptor | SubArtifactDescriptor): Promise<void> {
	const item = await fetchOptimization(optimizationId);
	if (!item) {
		toastState.show('Could not load forge result', 'error');
		return;
	}

	const result = mapToResultState({ ...item }, item.raw_prompt);
	optimizationState.forgeResult = result;

	forgeSession.loadRequest({
		text: item.raw_prompt,
		title: toArtifactName(item.title, item.overall_score),
		project: item.project ?? '',
		promptId: item.prompt_id ?? '',
		sourceAction: 'reiterate',
	});

	forgeSession.activeTab.document = descriptor;
	forgeSession.activeTab.resultId = result.id;

	forgeMachine.enterReview();
}

/** Open a forge result artifact in the IDE, creating a proper tab for it. */
async function openArtifact(descriptor: ArtifactDescriptor): Promise<void> {
	return openForgeResult(descriptor.id, descriptor);
}

/** Open a sub-artifact (analysis, scores, strategy) from a forge result. */
async function openSubArtifact(descriptor: SubArtifactDescriptor): Promise<void> {
	return openForgeResult(descriptor.parentForgeId, descriptor);
}

/**
 * Fallback: route unknown file types through the app registry.
 * Finds the app that registered the file extension and delegates to its openFile() method.
 */
async function openViaRegistry(descriptor: FileDescriptor): Promise<void> {
	// Future descriptor kinds may carry an extension property — check safely
	const raw = descriptor as unknown as Record<string, unknown>;
	const ext = typeof raw.extension === 'string' ? raw.extension : undefined;
	if (!ext) return;

	// Find which app registered this file type
	for (const record of appRegistry.all) {
		const hasType = record.manifest.file_types.some((ft) => ft.extension === ext);
		if (hasType && record.instance.openFile) {
			const generic: GenericFileDescriptor = {
				kind: descriptor.kind,
				id: descriptor.id,
				appId: record.manifest.id,
				name: descriptor.name,
				extension: ext,
			};
			await record.instance.openFile(generic);
			return;
		}
	}
}
