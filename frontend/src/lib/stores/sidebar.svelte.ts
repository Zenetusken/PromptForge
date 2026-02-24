type SidebarTab = 'history' | 'projects';

const TAB_STORAGE_KEY = 'pf_sidebar_tab';
const OPEN_STORAGE_KEY = 'pf_sidebar_open';

function loadTab(): SidebarTab {
	if (typeof localStorage === 'undefined') return 'history';
	const stored = localStorage.getItem(TAB_STORAGE_KEY);
	if (stored === 'history' || stored === 'projects') return stored;
	return 'history';
}

function loadOpen(): boolean {
	if (typeof localStorage === 'undefined') return true;
	return localStorage.getItem(OPEN_STORAGE_KEY) !== 'false';
}

class SidebarState {
	activeTab: SidebarTab = $state(loadTab());

	// Private reactive backing field — the getter/setter on `isOpen` ensures
	// every mutation (including two-way binding from HistorySidebar/Header)
	// persists to localStorage automatically.
	#_isOpen: boolean = $state(loadOpen());

	get isOpen(): boolean {
		return this.#_isOpen;
	}

	set isOpen(value: boolean) {
		this.#_isOpen = value;
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem(OPEN_STORAGE_KEY, String(value));
		}
	}

	setTab(tab: SidebarTab) {
		this.activeTab = tab;
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem(TAB_STORAGE_KEY, tab);
		}
	}

	open() { this.isOpen = true; }
	close() { this.isOpen = false; }
	toggle() { this.isOpen = !this.isOpen; }

	/** Open sidebar and switch to a specific tab. */
	openTo(tab: SidebarTab) {
		this.setTab(tab);
		this.open();
	}
}

export const sidebarState = new SidebarState();
