<script lang="ts">
	import { forgeSession } from '$lib/stores/forgeSession.svelte';
	import { optimizationState } from '$lib/stores/optimization.svelte';
	import { toastState } from '$lib/stores/toast.svelte';
	import { ALL_STRATEGIES } from '$lib/utils/strategies';
	import { extractVariables, detectSections, SECTION_COLORS, type ExtractedVariable, type DetectedSection, type VariableOccurrence } from '$lib/utils/promptParser';
	import Icon from './Icon.svelte';

	let {
		variant = 'collapsed',
		onsubmit,
		onexitfocus,
	}: {
		variant?: 'collapsed' | 'focus';
		onsubmit?: () => boolean;
		onexitfocus?: () => void;
	} = $props();

	let textareaEl: HTMLTextAreaElement | undefined = $state();
	let isFocused = $state(false);

	// Slash command state
	let showSlashMenu = $state(false);
	let slashQuery = $state('');
	let slashSelectedIndex = $state(0);

	let filteredStrategies = $derived(
		ALL_STRATEGIES.filter((s) => s.toLowerCase().includes(slashQuery.toLowerCase()))
	);

	let isCollapsed = $derived(variant === 'collapsed');

	// Prompt structure analysis (debounced via $derived)
	let variables: ExtractedVariable[] = $derived(extractVariables(forgeSession.draft.text));
	let sections: DetectedSection[] = $derived(detectSections(forgeSession.draft.text));

	// Show structure gutter only in focus mode with content > 5 lines
	let showGutter = $derived(
		!isCollapsed &&
		sections.length > 0 &&
		forgeSession.draft.text.split('\n').length > 5
	);

	export function focus() {
		textareaEl?.focus();
	}

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

	/** Select a variable occurrence in the textarea. */
	function selectVariable(occ: VariableOccurrence) {
		if (!textareaEl) return;
		textareaEl.focus();
		textareaEl.setSelectionRange(occ.position, occ.position + occ.matchLength);
	}

	/** Jump the textarea cursor to a specific line number. */
	function jumpToLine(lineNumber: number) {
		if (!textareaEl) return;
		const lines = forgeSession.draft.text.split('\n');
		let charOffset = 0;
		for (let i = 0; i < lineNumber - 1 && i < lines.length; i++) {
			charOffset += lines[i].length + 1; // +1 for \n
		}
		textareaEl.focus();
		textareaEl.setSelectionRange(charOffset, charOffset);
		// Scroll the textarea to bring the line into view
		const lineHeight = textareaEl.scrollHeight / Math.max(lines.length, 1);
		textareaEl.scrollTop = Math.max(0, (lineNumber - 3) * lineHeight);
	}
</script>

<div class="relative {isCollapsed ? '' : 'flex-1 flex'}">
	{#if showSlashMenu && filteredStrategies.length > 0}
		<div
			class="absolute {isCollapsed ? 'bottom-full left-0 mb-2 w-full sm:w-64' : 'top-[100px] left-6 ml-1 w-64'} rounded-md border border-neon-cyan/20 bg-bg-secondary/95 shadow-xl backdrop-blur-md overflow-hidden z-[50]"
		>
			<div class="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-text-dim border-b border-neon-cyan/10">
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

	<!-- Structure gutter (focus mode only) -->
	{#if showGutter}
		<div class="shrink-0 w-5 pt-6 flex flex-col relative">
			{#each sections as section}
				{@const color = SECTION_COLORS[section.type]}
				<button
					class="absolute left-1 w-2 h-2 rounded-full cursor-pointer transition-transform hover:scale-125 border-0 p-0"
					style="top: calc({section.lineNumber} * 1.625em); background-color: var(--color-{color})"
					title="{section.label} ({section.type})"
					onclick={() => jumpToLine(section.lineNumber)}
					aria-label="Jump to {section.label}"
				></button>
			{/each}
		</div>
	{/if}

	<div class="relative flex-1">
		<textarea
			bind:this={textareaEl}
			bind:value={forgeSession.draft.text}
			onkeydown={handleKeydown}
			oninput={handleInput}
			onfocus={() => (isFocused = true)}
			onblur={() => (isFocused = false)}
			placeholder=""
			rows={isCollapsed ? 2 : undefined}
			disabled={optimizationState.isRunning}
			class={isCollapsed
				? 'w-full resize-none bg-transparent px-2 pt-2 pb-0 text-[12px] leading-relaxed text-text-primary outline-none disabled:opacity-50'
				: 'h-full w-full resize-none bg-transparent p-6 text-[15px] leading-relaxed text-text-primary outline-none disabled:opacity-50 font-mono'}
			style={isCollapsed ? 'max-height: 250px; overflow-y: auto;' : ''}
			data-testid={isCollapsed ? 'forge-panel-textarea' : 'focus-mode-textarea'}
		></textarea>
		{#if !forgeSession.draft.text && !isFocused}
			<span
				class="shimmer-placeholder pointer-events-none absolute {isCollapsed ? 'left-2 top-2 text-[12px]' : 'left-6 top-6 text-[15px]'} leading-relaxed opacity-70 transition-opacity {isCollapsed ? 'group-focus-within:opacity-30' : ''}"
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
	<div class="flex flex-wrap gap-1 {isCollapsed ? 'px-2 pb-1 pt-0.5' : 'px-6 pb-2 pt-1.5'} border-t border-neon-teal/10">
		<span class="text-[8px] uppercase tracking-wider text-text-dim/50 font-bold self-center mr-0.5">Vars</span>
		{#each variables as variable}
			<button
				class="inline-flex items-center gap-0.5 rounded-sm bg-neon-teal/8 border border-neon-teal/20 {isCollapsed ? 'px-1 py-0 text-[8px]' : 'px-1.5 py-0.5 text-[9px]'} font-mono text-neon-teal transition-colors hover:bg-neon-teal/15"
				onclick={() => {
					if (variable.occurrences.length > 0) selectVariable(variable.occurrences[0]);
				}}
			>
				{'{{'}{variable.name}{'}}'}
				{#if variable.occurrences.length > 1}
					<span class="text-[7px] text-neon-teal/50">x{variable.occurrences.length}</span>
				{/if}
			</button>
		{/each}
	</div>
{/if}
