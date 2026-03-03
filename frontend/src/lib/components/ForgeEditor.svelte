<script lang="ts">
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { promptAnalysis } from '$lib/stores/promptAnalysis.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { ALL_STRATEGIES } from '$lib/utils/strategies';
	import { SECTION_COLORS, type DetectedSection } from '$lib/utils/promptParser';
	import Icon from './Icon.svelte';

	let {
		variant = 'collapsed',
		onsubmit,
		onexitfocus,
		oncursorchange,
		onselectionchange,
	}: {
		variant?: 'collapsed' | 'focus';
		onsubmit?: () => boolean;
		onexitfocus?: () => void;
		oncursorchange?: (line: number, col: number) => void;
		onselectionchange?: (selectedChars: number) => void;
	} = $props();

	let textareaEl: HTMLTextAreaElement | undefined = $state();
	let gutterEl: HTMLDivElement | undefined = $state();
	let mirrorEl: HTMLDivElement | undefined = $state();
	let isFocused = $state(false);

	// Cursor position tracking (visual lines)
	let cursorLine = $state(1);
	let cursorCol = $state(1);

	// Visual line measurement state
	let visualLineCount = $state(1);
	let lineVisualRows: number[] = $state([]);
	const LINE_HEIGHT = 21;

	// Starting visual line number for each logical line (1-indexed)
	let logicalToVisualStart = $derived.by(() => {
		const starts: number[] = [];
		let visual = 1;
		for (const rows of lineVisualRows) {
			starts.push(visual);
			visual += rows;
		}
		return starts;
	});

	// Slash command state
	let showSlashMenu = $state(false);
	let slashQuery = $state('');
	let slashSelectedIndex = $state(0);

	let filteredStrategies = $derived(
		ALL_STRATEGIES.filter((s) => s.toLowerCase().includes(slashQuery.toLowerCase()))
	);

	let isCollapsed = $derived(variant === 'collapsed');

	// Prompt structure analysis (from centralized store)
	let variables = $derived(promptAnalysis.variables);
	let sections = $derived(promptAnalysis.sections);

	// Show structure dots only in focus mode with enough visual lines
	let showStructureDots = $derived(
		!isCollapsed &&
		sections.length > 0 &&
		visualLineCount > 5
	);

	// Map section logical lines to their starting visual line numbers
	let sectionsByLine = $derived(
		showStructureDots
			? new Map(sections.map(s => [
				logicalToVisualStart[s.lineNumber - 1] ?? s.lineNumber,
				s
			]))
			: new Map<number, DetectedSection>()
	);

	export function focus() {
		textareaEl?.focus();
	}

	// --- Visual line measurement via mirror element ---

	function measureLines() {
		if (!mirrorEl || !textareaEl || isCollapsed) return;

		// Match mirror width to textarea content area (excludes scrollbar)
		mirrorEl.style.width = textareaEl.clientWidth + 'px';

		const lines = forgeSession.draft.text.split('\n');
		mirrorEl.innerHTML = '';
		const frag = document.createDocumentFragment();
		for (const line of lines) {
			const div = document.createElement('div');
			div.textContent = line || '\u200b';
			frag.appendChild(div);
		}
		mirrorEl.appendChild(frag);

		// Single reflow: measure all child heights
		const rows: number[] = [];
		let total = 0;
		for (const child of mirrorEl.children) {
			const r = Math.max(1, Math.round((child as HTMLElement).offsetHeight / LINE_HEIGHT));
			rows.push(r);
			total += r;
		}

		lineVisualRows = rows;
		visualLineCount = Math.max(1, total);
	}

	// Re-measure when text changes
	$effect(() => {
		if (isCollapsed) return;
		const _ = forgeSession.draft.text;
		queueMicrotask(measureLines);
	});

	// Re-measure on textarea resize (panel drag, window resize, scrollbar appear/disappear)
	$effect(() => {
		if (!textareaEl || isCollapsed) return;
		const ro = new ResizeObserver(() => measureLines());
		ro.observe(textareaEl);
		return () => ro.disconnect();
	});

	// --- Cursor tracking ---

	function updateCursorPosition() {
		if (!textareaEl) return;
		const pos = textareaEl.selectionStart;
		const textBefore = forgeSession.draft.text.slice(0, pos);
		const logicalLines = textBefore.split('\n');
		const logicalLine = logicalLines.length;
		const colInLine = logicalLines[logicalLines.length - 1].length;

		// Convert logical line + column to visual line
		const startVisual = logicalToVisualStart[logicalLine - 1] ?? 1;
		const visualRowsForLine = lineVisualRows[logicalLine - 1] ?? 1;
		const fullLineText = forgeSession.draft.text.split('\n')[logicalLine - 1] ?? '';

		let visualOffset = 0;
		if (visualRowsForLine > 1 && fullLineText.length > 0) {
			const charsPerRow = Math.ceil(fullLineText.length / visualRowsForLine);
			visualOffset = Math.min(
				Math.floor(colInLine / charsPerRow),
				visualRowsForLine - 1
			);
		}

		cursorLine = startVisual + visualOffset;
		cursorCol = colInLine + 1;
		oncursorchange?.(cursorLine, cursorCol);
		onselectionchange?.(Math.abs(textareaEl.selectionEnd - textareaEl.selectionStart));
	}

	// --- Scroll helpers ---

	function scrollToVisualLine(visualLine: number) {
		if (!textareaEl) return;
		textareaEl.scrollTop = Math.max(0, (visualLine - 3) * LINE_HEIGHT);
	}

	function syncGutterScroll() {
		if (gutterEl && textareaEl) {
			gutterEl.scrollTop = textareaEl.scrollTop;
		}
	}

	// --- Slash commands ---

	function applySlashStrategy(strategy: string) {
		if (!strategy) return;
		forgeSession.updateDraft({ strategy });

		if (!textareaEl) return;
		const text = forgeSession.draft.text;
		const cursor = textareaEl.selectionStart;
		const textBeforeCursor = text.slice(0, cursor);
		const match = textBeforeCursor.match(/(?:^|\s)\/([\w-]*)$/);
		if (match) {
			const replaceStart =
				cursor - match[0].length + (match[0].startsWith(' ') || match[0].startsWith('\n') ? 1 : 0);
			forgeSession.updateDraft({ text: text.slice(0, replaceStart) + text.slice(cursor) });
			setTimeout(() => {
				if (textareaEl) textareaEl.setSelectionRange(replaceStart, replaceStart);
			}, 0);
		}
		showSlashMenu = false;
		toastState.show(`Strategy set to ${strategy}`, 'success');
	}

	function handleInput() {
		if (!textareaEl) return;
		const text = forgeSession.draft.text;
		const cursor = textareaEl.selectionStart;
		const textBeforeCursor = text.slice(0, cursor);

		const match = textBeforeCursor.match(/(?:^|\s)\/([\w-]*)$/);
		if (match) {
			showSlashMenu = true;
			slashQuery = match[1];
			slashSelectedIndex = 0;
		} else {
			showSlashMenu = false;
		}

		updateCursorPosition();
		if (isCollapsed) autoResize();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (showSlashMenu) {
			if (e.key === 'ArrowDown') {
				e.preventDefault();
				slashSelectedIndex = (slashSelectedIndex + 1) % filteredStrategies.length;
				return;
			} else if (e.key === 'ArrowUp') {
				e.preventDefault();
				slashSelectedIndex = (slashSelectedIndex - 1 + filteredStrategies.length) % filteredStrategies.length;
				return;
			} else if (e.key === 'Escape') {
				e.preventDefault();
				showSlashMenu = false;
				return;
			} else if (e.key === 'Enter' || e.key === 'Tab') {
				e.preventDefault();
				if (filteredStrategies.length > 0) {
					applySlashStrategy(filteredStrategies[slashSelectedIndex]);
				}
				return;
			}
		}

		if (e.key === 'Escape' && !isCollapsed) {
			onexitfocus?.();
		}

		if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
			e.preventDefault();
			onsubmit?.();
		}
	}

	function autoResize() {
		if (!textareaEl || !isCollapsed) return;
		textareaEl.style.height = 'auto';
		textareaEl.style.height = Math.min(textareaEl.scrollHeight, 250) + 'px';
	}

	$effect(() => {
		if (forgeSession.draft.text !== undefined && textareaEl && isCollapsed) {
			queueMicrotask(autoResize);
		}
	});

	// §6: Track which occurrence index each variable is at for cycling.
	// Must be $state so template reads (via .get()) re-render on .set().
	let variableOccIdx: Map<string, number> = $state(new Map());

	// Reset occurrence tracking when variables change (text edits invalidate positions)
	$effect(() => {
		const _ = promptAnalysis.variables;
		variableOccIdx = new Map();
	});

	/** Cycle through all occurrences of a variable in the textarea. */
	function selectVariable(variable: typeof variables[0]) {
		if (!textareaEl || variable.occurrences.length === 0) return;
		const prev = variableOccIdx.get(variable.name) ?? -1;
		const next = (prev + 1) % variable.occurrences.length;
		variableOccIdx.set(variable.name, next);

		const occ = variable.occurrences[next];
		textareaEl.focus();
		textareaEl.setSelectionRange(occ.position, occ.position + occ.matchLength);
		// Scroll to the visual line of this occurrence
		const linesBefore = forgeSession.draft.text.slice(0, occ.position).split('\n');
		const logicalLine = linesBefore.length;
		const visualLine = logicalToVisualStart[logicalLine - 1] ?? logicalLine;
		scrollToVisualLine(visualLine);
		updateCursorPosition();
	}

	/** Jump the textarea cursor to a specific logical line number. */
	export function jumpToLine(lineNumber: number) {
		if (!textareaEl) return;
		const lines = forgeSession.draft.text.split('\n');
		let charOffset = 0;
		for (let i = 0; i < lineNumber - 1 && i < lines.length; i++) {
			charOffset += lines[i].length + 1; // +1 for \n
		}
		textareaEl.focus();
		textareaEl.setSelectionRange(charOffset, charOffset);
		const visualLine = logicalToVisualStart[lineNumber - 1] ?? lineNumber;
		scrollToVisualLine(visualLine);
	}
</script>

<div class="relative {isCollapsed ? '' : 'flex-1 min-h-0 flex'}">
	{#if showSlashMenu && filteredStrategies.length > 0}
		<div
			class="absolute {isCollapsed ? 'bottom-full left-0 mb-2 w-full sm:w-64' : 'top-[100px] left-12 w-64'} rounded-md border border-neon-cyan/20 bg-bg-secondary/95 overflow-hidden z-[50]"
		>
			<div class="px-2 py-1.5 text-[10px] font-bold uppercase tracking-wider text-text-dim border-b border-neon-cyan/10">
				Strategies
			</div>
			<ul class="max-h-48 overflow-y-auto p-1">
				{#each filteredStrategies as strategy, i}
					<li>
						<button
							onclick={() => applySlashStrategy(strategy)}
							class="w-full text-left px-2 py-1.5 text-[12px] rounded-sm transition-colors {i === slashSelectedIndex ? 'bg-neon-cyan/20 text-neon-cyan' : 'text-text-primary hover:bg-bg-hover'}"
						>
							<div class="flex items-center gap-2">
								<Icon name="zap" size={10} class={i === slashSelectedIndex ? 'text-neon-cyan' : 'text-text-dim'} />
								{strategy}
							</div>
						</button>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- Line numbers gutter (focus mode only) -->
	{#if !isCollapsed}
		<div
			bind:this={gutterEl}
			class="shrink-0 w-10 select-none overflow-hidden pt-3 flex flex-col items-end font-mono text-[13px] leading-[21px]"
			aria-hidden="true"
		>
			{#each { length: visualLineCount } as _, i}
				{@const lineNum = i + 1}
				{@const section = sectionsByLine.get(lineNum)}
				<div
					class="w-full text-right pr-2 text-[11px] {cursorLine === lineNum ? 'text-text-dim' : 'text-text-dim/40'}"
					style={section ? `border-left: 2px solid var(--color-${SECTION_COLORS[section.type]})` : ''}
				>
					{#if section}
						<button
							class="w-full text-right cursor-pointer hover:text-text-secondary transition-colors border-0 bg-transparent p-0 font-mono text-[11px] leading-[inherit] {cursorLine === lineNum ? 'text-text-dim' : 'text-text-dim/40'}"
							title="{section.label} ({section.type})"
							onclick={() => jumpToLine(section.lineNumber)}
							aria-label="Jump to {section.label}"
						>{lineNum}</button>
					{:else}
						{lineNum}
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	<div class="relative flex-1">
		<!-- Hidden mirror for visual line measurement -->
		{#if !isCollapsed}
			<div
				bind:this={mirrorEl}
				class="absolute top-0 left-0 pointer-events-none font-mono text-[13px] leading-[21px] whitespace-pre-wrap break-words py-3 pr-3 pl-1"
				style="visibility: hidden; height: auto; z-index: -1;"
				aria-hidden="true"
			></div>
		{/if}
		<textarea
			id="forge-editor-prompt"
			aria-label="Prompt editor"
			bind:this={textareaEl}
			bind:value={forgeSession.draft.text}
			onkeydown={handleKeydown}
			oninput={handleInput}
			onclick={updateCursorPosition}
			onkeyup={updateCursorPosition}
			onscroll={syncGutterScroll}
			onfocus={() => (isFocused = true)}
			onblur={() => (isFocused = false)}
			placeholder=""
			rows={isCollapsed ? 2 : undefined}
			disabled={optimizationState.isRunning}
			class={isCollapsed
				? 'w-full resize-none bg-transparent px-2 pt-2 pb-0 text-[12px] leading-relaxed text-text-primary outline-none disabled:opacity-50'
				: 'h-full w-full resize-none bg-transparent py-3 pr-3 pl-1 text-[13px] leading-[21px] text-text-primary outline-none disabled:opacity-50 font-mono whitespace-pre-wrap break-words overflow-y-auto'}
			style={isCollapsed ? 'max-height: 250px; overflow-y: auto;' : ''}
			data-testid={isCollapsed ? 'forge-panel-textarea' : 'focus-mode-textarea'}
		></textarea>
		{#if !forgeSession.draft.text && !isFocused}
			<span
				class="shimmer-placeholder pointer-events-none absolute {isCollapsed ? 'left-2 top-2 text-[12px]' : 'left-1 top-3 text-[13px]'} {isCollapsed ? 'leading-relaxed' : 'leading-[21px]'} opacity-70 transition-opacity {isCollapsed ? 'group-focus-within:opacity-30' : ''}"
			>
				{isCollapsed ? 'What should your prompt do...' : 'Write your system prompt or instructions here...\nTake all the space you need.'}
				<br />
				<span class="text-{isCollapsed ? '[10px]' : '[12px]'} uppercase tracking-wider text-neon-cyan/50 font-bold mt-{isCollapsed ? '1' : '2'} inline-block">
					Drag & drop files here to inject context
				</span>
			</span>
		{/if}
	</div>
</div>

<!-- Variable chips (shown in both collapsed and focus modes) -->
{#if variables.length > 0}
	<div class="flex flex-wrap gap-1 {isCollapsed ? 'px-2 pb-1 pt-0.5' : 'px-3 pb-1 pt-1'} border-t border-neon-teal/10">
		<span class="text-[8px] uppercase tracking-wider text-text-dim/50 font-bold self-center mr-0.5">Vars</span>
		{#each variables as variable}
			{@const occTotal = variable.occurrences.length}
			{@const occCurrent = (variableOccIdx.get(variable.name) ?? -1) + 1}
			<button
				class="inline-flex items-center gap-0.5 rounded-sm bg-neon-teal/8 border border-neon-teal/20 {isCollapsed ? 'px-1 py-0 text-[8px]' : 'px-1.5 py-0.5 text-[9px]'} font-mono text-neon-teal transition-colors hover:bg-neon-teal/15"
				onclick={() => selectVariable(variable)}
				title={occTotal > 1 ? `Click to cycle (${Math.min(occCurrent + 1, occTotal)}/${occTotal})` : `Go to occurrence`}
			>
				{'{{'}{variable.name}{'}}'}
				{#if occTotal > 1}
					<span class="text-[7px] text-neon-teal/50">{occCurrent > 0 ? `${occCurrent}/` : 'x'}{occTotal}</span>
				{/if}
			</button>
		{/each}
	</div>
{/if}
