type SidebarTab = 'history' | 'projects';

const STORAGE_KEY = 'pf_sidebar_tab';

function loadTab(): SidebarTab {
	if (typeof localStorage === 'undefined') return 'history';
	const stored = localStorage.getItem(STORAGE_KEY);
	if (stored === 'history' || stored === 'projects') return stored;
	return 'history';
}

class SidebarState {
	activeTab: SidebarTab = $state(loadTab());

	setTab(tab: SidebarTab) {
		this.activeTab = tab;
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem(STORAGE_KEY, tab);
		}
	}
}

export const sidebarState = new SidebarState();
