<script lang="ts">
	type IconName =
		| "bolt"
		| "sidebar"
		| "menu"
		| "chevron-down"
		| "chevron-right"
		| "chevron-left"
		| "chevron-up"
		| "spinner"
		| "check"
		| "x"
		| "copy"
		| "clipboard"
		| "download"
		| "refresh"
		| "search"
		| "layers"
		| "terminal"
		| "sparkles"
		| "arrow-up-right"
		| "edit"
		| "alert-circle"
		| "info"
		| "server"
		| "key"
		| "eye"
		| "eye-off"
		| "folder"
		| "folder-open"
		| "plus"
		| "grip-vertical"
		| "archive"
		| "trash-2"
		| "clock"
		| "arrow-up"
		| "maximize-2"
		| "chevrons-right"
		| "chevrons-left"
		| "code"
		| "box"
		| "file-text"
		| "zap"
		| "minimize-2"
		| "sliders"
		| "check-circle"
		| "loader"
		| "circle"
		| "award"
		| "alert-triangle"
		| "file-code"
		| "minus"
		| "upload-cloud"
		| "cpu"
		| "git-branch"
		| "monitor"
		| "settings"
		| "mail"
		| "users"
		| "x-circle"
		| "bar-chart"
		| "check-square"
		| "activity";

	let {
		name,
		size = 16,
		class: className = "",
		style: styleAttr = "",
	}: {
		name: IconName;
		size?: number;
		class?: string;
		style?: string;
	} = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="2"
	stroke-linecap="round"
	stroke-linejoin="round"
	class={className}
	style={styleAttr || undefined}
	aria-hidden="true"
>
	{#if name === "bolt"}
		<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
	{:else if name === "sidebar"}
		<rect x="3" y="3" width="18" height="18" rx="2" />
		<line x1="9" y1="3" x2="9" y2="21" />
	{:else if name === "menu"}
		<line x1="3" y1="6" x2="21" y2="6" />
		<line x1="3" y1="12" x2="21" y2="12" />
		<line x1="3" y1="18" x2="21" y2="18" />
	{:else if name === "chevron-down"}
		<polyline points="6 9 12 15 18 9" />
	{:else if name === "chevron-right"}
		<polyline points="9 18 15 12 9 6" />
	{:else if name === "chevron-left"}
		<polyline points="15 18 9 12 15 6" />
	{:else if name === "spinner"}
		<circle
			class="opacity-25"
			cx="12"
			cy="12"
			r="10"
			stroke="currentColor"
			stroke-width="4"
			fill="none"
		/>
		<path
			class="opacity-75"
			fill="currentColor"
			stroke="none"
			d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
		/>
	{:else if name === "check"}
		<polyline points="20 6 9 17 4 12" />
	{:else if name === "x"}
		<line x1="18" y1="6" x2="6" y2="18" />
		<line x1="6" y1="6" x2="18" y2="18" />
	{:else if name === "copy"}
		<rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
		<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
	{:else if name === "clipboard"}
		<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
		<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
	{:else if name === "download"}
		<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
		<polyline points="7 10 12 15 17 10" />
		<line x1="12" y1="15" x2="12" y2="3" />
	{:else if name === "refresh"}
		<polyline points="23 4 23 10 17 10" />
		<polyline points="1 20 1 14 7 14" />
		<path
			d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"
		/>
	{:else if name === "search"}
		<circle cx="11" cy="11" r="8" />
		<line x1="21" y1="21" x2="16.65" y2="16.65" />
	{:else if name === "layers"}
		<path d="M12 2L2 7l10 5 10-5-10-5z" />
		<path d="M2 17l10 5 10-5" />
		<path d="M2 12l10 5 10-5" />
	{:else if name === "terminal"}
		<polyline points="4 17 10 11 4 5" />
		<line x1="12" y1="19" x2="20" y2="19" />
	{:else if name === "sparkles"}
		<path
			d="M12 3v3M12 18v3M3 12h3M18 12h3M5.636 5.636l2.121 2.121M16.243 16.243l2.121 2.121M5.636 18.364l2.121-2.121M16.243 7.757l2.121-2.121"
		/>
	{:else if name === "arrow-up-right"}
		<line x1="7" y1="17" x2="17" y2="7" />
		<polyline points="7 7 17 7 17 17" />
	{:else if name === "edit"}
		<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
		<path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
	{:else if name === "alert-circle"}
		<circle cx="12" cy="12" r="10" />
		<line x1="12" y1="8" x2="12" y2="12" />
		<line x1="12" y1="16" x2="12.01" y2="16" />
	{:else if name === "info"}
		<circle cx="12" cy="12" r="10" />
		<line x1="12" y1="16" x2="12" y2="12" />
		<line x1="12" y1="8" x2="12.01" y2="8" />
	{:else if name === "server"}
		<rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
		<rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
		<line x1="6" y1="6" x2="6.01" y2="6" />
		<line x1="6" y1="18" x2="6.01" y2="18" />
	{:else if name === "key"}
		<path
			d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"
		/>
	{:else if name === "eye"}
		<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
		<circle cx="12" cy="12" r="3" />
	{:else if name === "eye-off"}
		<path
			d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"
		/>
		<line x1="1" y1="1" x2="23" y2="23" />
	{:else if name === "chevron-up"}
		<polyline points="18 15 12 9 6 15" />
	{:else if name === "folder"}
		<path
			d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"
		/>
	{:else if name === "folder-open"}
		<path d="M2 19V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2v1" />
		<path
			d="M2 19l2.56-7.68A2 2 0 016.46 10h15.08a2 2 0 011.9 2.63L20.87 20a2 2 0 01-1.9 1.37H4a2 2 0 01-2-2z"
		/>
	{:else if name === "plus"}
		<line x1="12" y1="5" x2="12" y2="19" />
		<line x1="5" y1="12" x2="19" y2="12" />
	{:else if name === "grip-vertical"}
		<circle cx="9" cy="5" r="1" fill="currentColor" stroke="none" />
		<circle cx="9" cy="12" r="1" fill="currentColor" stroke="none" />
		<circle cx="9" cy="19" r="1" fill="currentColor" stroke="none" />
		<circle cx="15" cy="5" r="1" fill="currentColor" stroke="none" />
		<circle cx="15" cy="12" r="1" fill="currentColor" stroke="none" />
		<circle cx="15" cy="19" r="1" fill="currentColor" stroke="none" />
	{:else if name === "archive"}
		<polyline points="21 8 21 21 3 21 3 8" />
		<rect x="1" y="3" width="22" height="5" />
		<line x1="10" y1="12" x2="14" y2="12" />
	{:else if name === "trash-2"}
		<polyline points="3 6 5 6 21 6" />
		<path
			d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"
		/>
		<line x1="10" y1="11" x2="10" y2="17" />
		<line x1="14" y1="11" x2="14" y2="17" />
	{:else if name === "clock"}
		<circle cx="12" cy="12" r="10" />
		<polyline points="12 6 12 12 16 14" />
	{:else if name === "arrow-up"}
		<line x1="12" y1="19" x2="12" y2="5" />
		<polyline points="5 12 12 5 19 12" />
	{:else if name === "maximize-2"}
		<polyline points="15 3 21 3 21 9" />
		<polyline points="9 21 3 21 3 15" />
		<line x1="21" y1="3" x2="14" y2="10" />
		<line x1="3" y1="21" x2="10" y2="14" />
	{:else if name === "minimize-2"}
		<polyline points="4 14 10 14 10 20" />
		<polyline points="20 10 14 10 14 4" />
		<line x1="14" y1="10" x2="21" y2="3" />
		<line x1="3" y1="21" x2="10" y2="14" />
	{:else if name === "code"}
		<polyline points="16 18 22 12 16 6" />
		<polyline points="8 6 2 12 8 18" />
	{:else if name === "box"}
		<path
			d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"
		/>
		<polyline points="3.27 6.96 12 12.01 20.73 6.96" />
		<line x1="12" y1="22.08" x2="12" y2="12" />
	{:else if name === "file-text"}
		<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
		<polyline points="14 2 14 8 20 8" />
		<line x1="16" y1="13" x2="8" y2="13" />
		<line x1="16" y1="17" x2="8" y2="17" />
		<polyline points="10 9 9 9 8 9" />
	{:else if name === "zap"}
		<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
	{:else if name === "chevrons-right"}
		<polyline points="13 17 18 12 13 7" />
		<polyline points="6 17 11 12 6 7" />
	{:else if name === "chevrons-left"}
		<polyline points="11 17 6 12 11 7" />
		<polyline points="18 17 13 12 18 7" />
	{:else if name === "sliders"}
		<line x1="4" y1="21" x2="4" y2="14" />
		<line x1="4" y1="10" x2="4" y2="3" />
		<line x1="12" y1="21" x2="12" y2="12" />
		<line x1="12" y1="8" x2="12" y2="3" />
		<line x1="20" y1="21" x2="20" y2="16" />
		<line x1="20" y1="12" x2="20" y2="3" />
		<line x1="1" y1="14" x2="7" y2="14" />
		<line x1="9" y1="8" x2="15" y2="8" />
		<line x1="17" y1="16" x2="23" y2="16" />
	{:else if name === "check-circle"}
		<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
		<polyline points="22 4 12 14.01 9 11.01" />
	{:else if name === "loader"}
		<line x1="12" y1="2" x2="12" y2="6" />
		<line x1="12" y1="18" x2="12" y2="22" />
		<line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
		<line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
		<line x1="2" y1="12" x2="6" y2="12" />
		<line x1="18" y1="12" x2="22" y2="12" />
		<line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
		<line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
	{:else if name === "circle"}
		<circle cx="12" cy="12" r="10" />
	{:else if name === "award"}
		<circle cx="12" cy="8" r="7" />
		<polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88" />
	{:else if name === "alert-triangle"}
		<path
			d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
		/>
		<line x1="12" y1="9" x2="12" y2="13" />
		<line x1="12" y1="17" x2="12.01" y2="17" />
	{:else if name === "file-code"}
		<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
		<polyline points="14 2 14 8 20 8" />
		<polyline points="10 13 8 15 10 17" />
		<polyline points="14 13 16 15 14 17" />
	{:else if name === "minus"}
		<line x1="5" y1="12" x2="19" y2="12" />
	{:else if name === "upload-cloud"}
		<polyline points="16 16 12 12 8 16" />
		<line x1="12" y1="12" x2="12" y2="21" />
		<path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
	{:else if name === "cpu"}
		<rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
		<rect x="9" y="9" width="6" height="6" />
		<line x1="9" y1="1" x2="9" y2="4" />
		<line x1="15" y1="1" x2="15" y2="4" />
		<line x1="9" y1="20" x2="9" y2="23" />
		<line x1="15" y1="20" x2="15" y2="23" />
		<line x1="20" y1="9" x2="23" y2="9" />
		<line x1="20" y1="14" x2="23" y2="14" />
		<line x1="1" y1="9" x2="4" y2="9" />
		<line x1="1" y1="14" x2="4" y2="14" />
	{:else if name === "git-branch"}
		<line x1="6" y1="3" x2="6" y2="15" />
		<circle cx="18" cy="6" r="3" />
		<circle cx="6" cy="18" r="3" />
		<path d="M18 9a9 9 0 0 1-9 9" />
	{:else if name === "monitor"}
		<rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
		<line x1="8" y1="21" x2="16" y2="21" />
		<line x1="12" y1="17" x2="12" y2="21" />
	{:else if name === "settings"}
		<circle cx="12" cy="12" r="3" />
		<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
	{:else if name === "mail"}
		<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
		<polyline points="22,6 12,13 2,6" />
	{:else if name === "users"}
		<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
		<circle cx="9" cy="7" r="4" />
		<path d="M23 21v-2a4 4 0 0 0-3-3.87" />
		<path d="M16 3.13a4 4 0 0 1 0 7.75" />
	{:else if name === "x-circle"}
		<circle cx="12" cy="12" r="10" />
		<line x1="15" y1="9" x2="9" y2="15" />
		<line x1="9" y1="9" x2="15" y2="15" />
	{:else if name === "bar-chart"}
		<line x1="12" y1="20" x2="12" y2="10" />
		<line x1="18" y1="20" x2="18" y2="4" />
		<line x1="6" y1="20" x2="6" y2="16" />
	{:else if name === "check-square"}
		<polyline points="9 11 12 14 22 4" />
		<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
	{:else if name === "activity"}
		<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
	{/if}
</svg>
