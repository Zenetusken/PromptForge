import { fetchOptimization } from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	const item = await fetchOptimization(params.id, fetch);
	if (!item) {
		throw error(404, 'Optimization not found');
	}
	return { item };
};
