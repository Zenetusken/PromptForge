import { fetchProject } from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	const project = await fetchProject(params.id, fetch);
	if (!project) {
		throw error(404, 'Project not found');
	}
	return { project };
};
