import JSZip from 'jszip';
import { fetchOptimization, fetchPromptForges, type ProjectDetail, type HistoryItem } from '$lib/api/client';
import { mapToResultState } from '$lib/stores/optimization.svelte';
import { generateExportMarkdown, slugifyTitle, downloadBlob } from '$lib/utils/export';

export interface ProjectExportProgress {
	total: number;
	fetched: number;
	status: 'fetching' | 'generating' | 'done';
}

/**
 * Produce a unique filename by slugifying the desired name and appending
 * a numeric suffix (-2, -3, ...) when collisions occur.
 */
export function deduplicateFilename(
	desired: string,
	fallbackId: string,
	usedNames: Set<string>,
): string {
	let base = slugifyTitle(desired);
	if (!base) base = fallbackId;

	let name = base;
	let counter = 2;
	while (usedNames.has(name)) {
		name = `${base}-${counter}`;
		counter++;
	}
	usedNames.add(name);
	return name;
}

/**
 * Export all forge results in a project as a zip of markdown files.
 * Returns the number of successfully exported files.
 */
export async function exportProjectAsZip(
	project: ProjectDetail,
	onProgress?: (progress: ProjectExportProgress) => void,
): Promise<number> {
	// Phase 1 — Collect forge IDs from all prompts
	const forgeIds: string[] = [];

	for (const prompt of project.prompts) {
		if (prompt.forge_count === 0) continue;

		if (prompt.forge_count === 1 && prompt.latest_forge) {
			forgeIds.push(prompt.latest_forge.id);
		} else if (prompt.forge_count > 1) {
			const result = await fetchPromptForges(project.id, prompt.id, { limit: 100 });
			for (const forge of result.items) {
				forgeIds.push(forge.id);
			}
		}
	}

	if (forgeIds.length === 0) return 0;

	const total = forgeIds.length;
	let fetched = 0;
	onProgress?.({ total, fetched, status: 'fetching' });

	// Phase 2 — Batch-fetch full details (batches of 5)
	const BATCH_SIZE = 5;
	const items: HistoryItem[] = [];

	for (let i = 0; i < forgeIds.length; i += BATCH_SIZE) {
		const batch = forgeIds.slice(i, i + BATCH_SIZE);
		const settled = await Promise.allSettled(
			batch.map((id) => fetchOptimization(id)),
		);

		for (const result of settled) {
			if (result.status === 'fulfilled' && result.value) {
				items.push(result.value);
			}
			fetched++;
		}
		onProgress?.({ total, fetched, status: 'fetching' });
	}

	if (items.length === 0) {
		throw new Error('All forge results failed to load');
	}

	// Phase 3 — Generate markdown files
	onProgress?.({ total, fetched, status: 'generating' });

	const usedNames = new Set<string>();
	const files: Array<{ filename: string; content: string }> = [];

	for (const item of items) {
		const state = mapToResultState({ ...item }, item.raw_prompt);
		const markdown = generateExportMarkdown(state);
		const filename = deduplicateFilename(
			state.title || 'optimized-prompt',
			state.id,
			usedNames,
		);
		files.push({ filename: `${filename}.md`, content: markdown });
	}

	// Phase 4 — Build zip and download
	const zip = new JSZip();
	const folderName = slugifyTitle(project.name) || 'project-export';
	const folder = zip.folder(folderName)!;

	for (const file of files) {
		folder.file(file.filename, file.content);
	}

	const blob = await zip.generateAsync({ type: 'blob' });
	downloadBlob(blob, `${folderName}-export.zip`);

	onProgress?.({ total, fetched, status: 'done' });
	return files.length;
}
