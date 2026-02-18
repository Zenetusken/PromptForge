/**
 * Navigation state for contextual back buttons.
 *
 * Uses a small stack instead of a single previousPath to prevent circular
 * navigation. When the destination matches the stack top, it's a "back"
 * navigation (pop); otherwise it's a "forward" navigation (push).
 */

export interface BackDestination {
	url: string;
	label: string;
}

export interface OptimizeData {
	project_id?: string | null;
	project?: string | null;
	project_status?: string | null;
}

const MAX_STACK_DEPTH = 10;

/** Append " (archived)" when the project status warrants it. */
export function projectLabel(name: string, status?: string | null): string {
	return status === 'archived' ? `${name} (archived)` : name;
}

function labelForPath(path: string, data?: OptimizeData | null): string {
	if (path === '/') return 'Back to Home';
	if (path.startsWith('/projects/') && data?.project) {
		return `Back to ${projectLabel(data.project, data.project_status)}`;
	}
	return 'Back';
}

class NavigationState {
	// Reactive so $derived expressions that call getBack* re-evaluate on changes.
	// In practice the stack only mutates during beforeNavigate (before the new
	// page renders), but keeping it reactive is correct and cheap.
	_stack = $state<string[]>([]);

	/** Call from beforeNavigate in the root layout. */
	recordNavigation(fromPath: string, toPath: string) {
		// Only care about navigations TO detail pages
		if (!toPath.startsWith('/optimize/') && !toPath.startsWith('/projects/')) {
			return;
		}

		// If the destination matches the stack top, the user is going "back" — pop
		if (this._stack.length > 0 && this._stack[this._stack.length - 1] === toPath) {
			this._stack.pop();
			return;
		}

		// Forward navigation — push the page we're leaving
		this._stack.push(fromPath);
		if (this._stack.length > MAX_STACK_DEPTH) {
			this._stack.shift();
		}
	}

	/** Reset all state (useful for tests). */
	reset() {
		this._stack = [];
	}

	/** Peek at the top of the navigation stack without modifying it. */
	private get _top(): string {
		return this._stack.length > 0 ? this._stack[this._stack.length - 1] : '';
	}

	getBackForOptimize(data?: OptimizeData | null): BackDestination {
		const prev = this._top;
		if (prev) {
			return { url: prev, label: labelForPath(prev, data) };
		}

		// Fallback: derive from page data when stack is empty (direct link / refresh)
		if (data?.project_id && data?.project) {
			return {
				url: `/projects/${data.project_id}`,
				label: `Back to ${projectLabel(data.project, data.project_status)}`,
			};
		}

		return { url: '/', label: 'Back to Home' };
	}

	getBackForProject(): BackDestination {
		const prev = this._top;
		if (prev) {
			return { url: prev, label: labelForPath(prev) };
		}
		return { url: '/', label: 'Back to Home' };
	}
}

export const navigationState = new NavigationState();
