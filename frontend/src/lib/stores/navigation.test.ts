import { describe, it, expect, beforeEach } from 'vitest';
import { navigationState, projectLabel } from './navigation.svelte';

describe('projectLabel', () => {
	it('returns name as-is for active projects', () => {
		expect(projectLabel('My Project', 'active')).toBe('My Project');
	});

	it('appends (archived) for archived projects', () => {
		expect(projectLabel('Old', 'archived')).toBe('Old (archived)');
	});

	it('returns name as-is for null status', () => {
		expect(projectLabel('Proj', null)).toBe('Proj');
	});

	it('returns name as-is for undefined status', () => {
		expect(projectLabel('Proj')).toBe('Proj');
	});
});

describe('NavigationState', () => {
	beforeEach(() => {
		navigationState.reset();
	});

	// ---------------------------------------------------------------
	// recordNavigation
	// ---------------------------------------------------------------
	describe('recordNavigation', () => {
		it('pushes source when navigating to an optimize page', () => {
			navigationState.recordNavigation('/', '/optimize/abc');
			expect(navigationState._stack).toEqual(['/']);
		});

		it('pushes source when navigating to a project page', () => {
			navigationState.recordNavigation('/optimize/abc', '/projects/xyz');
			expect(navigationState._stack).toEqual(['/optimize/abc']);
		});

		it('does not record navigations to non-detail pages', () => {
			navigationState.recordNavigation('/optimize/abc', '/');
			expect(navigationState._stack).toEqual([]);
		});

		it('pushes on forward navigation, building a stack', () => {
			navigationState.recordNavigation('/', '/optimize/aaa');
			navigationState.recordNavigation('/optimize/aaa', '/optimize/bbb');
			expect(navigationState._stack).toEqual(['/', '/optimize/aaa']);
		});

		it('pops when destination matches stack top (back navigation)', () => {
			// Forward: Home → A → B   stack: ['/', '/optimize/aaa']
			navigationState.recordNavigation('/', '/optimize/aaa');
			navigationState.recordNavigation('/optimize/aaa', '/optimize/bbb');
			// Back: B → A (top is '/optimize/aaa')
			navigationState.recordNavigation('/optimize/bbb', '/optimize/aaa');
			expect(navigationState._stack).toEqual(['/']);
		});

		it('handles navigating between project pages', () => {
			navigationState.recordNavigation('/', '/projects/a');
			navigationState.recordNavigation('/projects/a', '/projects/b');
			expect(navigationState._stack).toEqual(['/', '/projects/a']);
		});

		it('caps stack at max depth', () => {
			// Push 12 entries (exceeds the 10-entry cap)
			for (let i = 0; i < 12; i++) {
				navigationState.recordNavigation(`/page/${i}`, `/optimize/target-${i}`);
			}
			expect(navigationState._stack.length).toBe(10);
			// Oldest entries should have been shifted off
			expect(navigationState._stack[0]).toBe('/page/2');
			expect(navigationState._stack[9]).toBe('/page/11');
		});
	});

	// ---------------------------------------------------------------
	// Circular navigation prevention (the main bug)
	// ---------------------------------------------------------------
	describe('circular navigation prevention', () => {
		it('prevents ping-pong between two optimize pages', () => {
			// Home → A → B
			navigationState.recordNavigation('/', '/optimize/aaa');
			navigationState.recordNavigation('/optimize/aaa', '/optimize/bbb');

			// On B, back should point to A
			expect(navigationState.getBackForOptimize(null)).toEqual({
				url: '/optimize/aaa',
				label: 'Back',
			});

			// User clicks back: B → A (pops A off stack, leaving ['/'])
			navigationState.recordNavigation('/optimize/bbb', '/optimize/aaa');

			// On A, back should point to Home, NOT back to B
			expect(navigationState.getBackForOptimize(null)).toEqual({
				url: '/',
				label: 'Back to Home',
			});

			// User clicks back: A → Home (not recorded, non-detail dest)
			navigationState.recordNavigation('/optimize/aaa', '/');
			expect(navigationState._stack).toEqual(['/']);
		});

		it('prevents loop between optimize and project pages', () => {
			// Home → Project → Forge
			navigationState.recordNavigation('/', '/projects/xyz');
			navigationState.recordNavigation('/projects/xyz', '/optimize/abc');

			// On Forge, back = Project
			expect(navigationState.getBackForOptimize({
				project: 'My Project',
				project_status: 'active',
			})).toEqual({
				url: '/projects/xyz',
				label: 'Back to My Project',
			});

			// Back: Forge → Project (pops)
			navigationState.recordNavigation('/optimize/abc', '/projects/xyz');

			// On Project, back = Home, NOT back to Forge
			expect(navigationState.getBackForProject()).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('correctly unwinds a 4-page deep chain', () => {
			// Home → Project → Forge A → Forge B
			navigationState.recordNavigation('/', '/projects/xyz');
			navigationState.recordNavigation('/projects/xyz', '/optimize/aaa');
			navigationState.recordNavigation('/optimize/aaa', '/optimize/bbb');
			expect(navigationState._stack).toEqual(['/', '/projects/xyz', '/optimize/aaa']);

			// Back: B → A (pop)
			navigationState.recordNavigation('/optimize/bbb', '/optimize/aaa');
			expect(navigationState._stack).toEqual(['/', '/projects/xyz']);

			// Back: A → Project (pop)
			navigationState.recordNavigation('/optimize/aaa', '/projects/xyz');
			expect(navigationState._stack).toEqual(['/']);

			// Back: Project → Home
			expect(navigationState.getBackForProject()).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('handles 3 sibling forges with prev/next navigation', () => {
			// Home → Forge A → (Next) Forge B → (Next) Forge C
			navigationState.recordNavigation('/', '/optimize/a');
			navigationState.recordNavigation('/optimize/a', '/optimize/b');
			navigationState.recordNavigation('/optimize/b', '/optimize/c');
			expect(navigationState._stack).toEqual(['/', '/optimize/a', '/optimize/b']);

			// Back from C → B (pop)
			navigationState.recordNavigation('/optimize/c', '/optimize/b');
			expect(navigationState._stack).toEqual(['/', '/optimize/a']);

			// Back from B → A (pop)
			navigationState.recordNavigation('/optimize/b', '/optimize/a');
			expect(navigationState._stack).toEqual(['/']);

			// Back from A → Home
			expect(navigationState.getBackForOptimize(null)).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});
	});

	// ---------------------------------------------------------------
	// getBackForOptimize
	// ---------------------------------------------------------------
	describe('getBackForOptimize', () => {
		it('returns home when stack is empty and no project data', () => {
			expect(navigationState.getBackForOptimize(null)).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('returns home when called with undefined', () => {
			expect(navigationState.getBackForOptimize(undefined)).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('returns home when called with no args', () => {
			expect(navigationState.getBackForOptimize()).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('returns home when stack top is /', () => {
			navigationState.recordNavigation('/', '/optimize/abc');
			expect(navigationState.getBackForOptimize(null)).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('returns project page with name when stack top is a project page', () => {
			navigationState.recordNavigation('/projects/xyz', '/optimize/abc');
			expect(navigationState.getBackForOptimize({
				project: 'My Project',
				project_status: 'active',
			})).toEqual({
				url: '/projects/xyz',
				label: 'Back to My Project',
			});
		});

		it('appends (archived) suffix for archived projects', () => {
			navigationState.recordNavigation('/projects/xyz', '/optimize/abc');
			expect(navigationState.getBackForOptimize({
				project: 'Old Project',
				project_status: 'archived',
			})).toEqual({
				url: '/projects/xyz',
				label: 'Back to Old Project (archived)',
			});
		});

		it('returns generic label when stack top is project but data has no name', () => {
			navigationState.recordNavigation('/projects/xyz', '/optimize/abc');
			expect(navigationState.getBackForOptimize({ project: null })).toEqual({
				url: '/projects/xyz',
				label: 'Back',
			});
		});

		it('falls back to project from data when stack is empty', () => {
			expect(navigationState.getBackForOptimize({
				project_id: 'abc',
				project: 'Data Project',
				project_status: 'active',
			})).toEqual({
				url: '/projects/abc',
				label: 'Back to Data Project',
			});
		});

		it('falls back to project from data with archived suffix', () => {
			expect(navigationState.getBackForOptimize({
				project_id: 'abc',
				project: 'Archived',
				project_status: 'archived',
			})).toEqual({
				url: '/projects/abc',
				label: 'Back to Archived (archived)',
			});
		});

		it('falls back to home when data has no project', () => {
			expect(navigationState.getBackForOptimize({
				project_id: null,
				project: null,
			})).toEqual({ url: '/', label: 'Back to Home' });
		});

		it('falls back to home when data has project_id but no name', () => {
			expect(navigationState.getBackForOptimize({
				project_id: 'abc',
				project: null,
			})).toEqual({ url: '/', label: 'Back to Home' });
		});

		it('falls back to home when data has project name but no id', () => {
			expect(navigationState.getBackForOptimize({
				project_id: null,
				project: 'Orphan',
			})).toEqual({ url: '/', label: 'Back to Home' });
		});

		it('returns generic back for optimize-page stack top', () => {
			navigationState.recordNavigation('/optimize/aaa', '/optimize/bbb');
			expect(navigationState.getBackForOptimize(null)).toEqual({
				url: '/optimize/aaa',
				label: 'Back',
			});
		});

		it('stack top takes priority over data-derived project', () => {
			navigationState.recordNavigation('/', '/optimize/abc');
			expect(navigationState.getBackForOptimize({
				project_id: 'xyz',
				project: 'Project',
				project_status: 'active',
			})).toEqual({ url: '/', label: 'Back to Home' });
		});

		it('uses data-derived project with empty string project_status', () => {
			expect(navigationState.getBackForOptimize({
				project_id: 'abc',
				project: 'Project',
				project_status: '',
			})).toEqual({
				url: '/projects/abc',
				label: 'Back to Project',
			});
		});
	});

	// ---------------------------------------------------------------
	// getBackForProject
	// ---------------------------------------------------------------
	describe('getBackForProject', () => {
		it('returns home when stack is empty', () => {
			expect(navigationState.getBackForProject()).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('returns home when stack top is /', () => {
			navigationState.recordNavigation('/', '/projects/xyz');
			expect(navigationState.getBackForProject()).toEqual({
				url: '/',
				label: 'Back to Home',
			});
		});

		it('returns optimize page when stack top is an optimize page', () => {
			navigationState.recordNavigation('/optimize/abc', '/projects/xyz');
			expect(navigationState.getBackForProject()).toEqual({
				url: '/optimize/abc',
				label: 'Back',
			});
		});
	});
});
