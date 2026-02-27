import type { ProjectDetail, ProjectPrompt } from '$lib/api/client';
import { createPromptDescriptor } from '$lib/utils/fileDescriptor';
import { openDocument } from '$lib/utils/documentOpener';
import { toFilename } from '$lib/utils/fileTypes';

export interface PromptOpenerContext {
	promptId: string;
	projectId: string;
	projectData?: ProjectDetail;
	prompt?: ProjectPrompt;
}

/**
 * Open a project prompt in the IDE.
 * @deprecated Use `openDocument(createPromptDescriptor(...))` directly.
 * Delegates to the unified document opener.
 */
export async function openPromptInIDE(ctx: PromptOpenerContext): Promise<void> {
	const name = ctx.prompt
		? toFilename(ctx.prompt.content, ctx.prompt.latest_forge?.title)
		: 'Prompt';

	const descriptor = createPromptDescriptor(
		ctx.promptId,
		ctx.projectId,
		name,
	);
	await openDocument(descriptor);
}
