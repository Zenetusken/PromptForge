<script lang="ts">
  let { original = '', modified = '' }: { original?: string; modified?: string } = $props();

  let viewMode = $state<'side-by-side' | 'inline'>('side-by-side');
  let showDiffsOnly = $state(false);

  // Simple word-level diff for inline highlighting
  interface DiffLine {
    type: 'same' | 'added' | 'removed';
    lineNum: number;
    text: string;
  }

  // LCS-based line diff
  let diffLines = $derived.by(() => {
    const origLines = original.split('\n');
    const modLines = modified.split('\n');
    const result: DiffLine[] = [];

    // Simple LCS diff algorithm
    const m = origLines.length;
    const n = modLines.length;

    // Build LCS table
    const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        if (origLines[i - 1] === modLines[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }

    // Backtrack to find diff
    const diffs: Array<{ type: 'same' | 'added' | 'removed'; text: string }> = [];
    let i = m, j = n;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && origLines[i - 1] === modLines[j - 1]) {
        diffs.unshift({ type: 'same', text: origLines[i - 1] });
        i--;
        j--;
      } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
        diffs.unshift({ type: 'added', text: modLines[j - 1] });
        j--;
      } else {
        diffs.unshift({ type: 'removed', text: origLines[i - 1] });
        i--;
      }
    }

    let lineNum = 0;
    for (const d of diffs) {
      lineNum++;
      result.push({ ...d, lineNum });
    }

    return result;
  });

  // Side-by-side pairs
  interface SidePair {
    left: { type: 'same' | 'removed' | 'empty'; text: string; lineNum: number } | null;
    right: { type: 'same' | 'added' | 'empty'; text: string; lineNum: number } | null;
  }

  let sidePairs = $derived.by(() => {
    const origLines = original.split('\n');
    const modLines = modified.split('\n');
    const pairs: SidePair[] = [];

    // Use the same LCS approach
    const m = origLines.length;
    const n = modLines.length;
    const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        if (origLines[i - 1] === modLines[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }

    // Backtrack
    const actions: Array<{ type: 'same' | 'added' | 'removed'; origIdx?: number; modIdx?: number }> = [];
    let i = m, j = n;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && origLines[i - 1] === modLines[j - 1]) {
        actions.unshift({ type: 'same', origIdx: i - 1, modIdx: j - 1 });
        i--;
        j--;
      } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
        actions.unshift({ type: 'added', modIdx: j - 1 });
        j--;
      } else {
        actions.unshift({ type: 'removed', origIdx: i - 1 });
        i--;
      }
    }

    let leftNum = 0;
    let rightNum = 0;
    for (const a of actions) {
      if (a.type === 'same') {
        leftNum++;
        rightNum++;
        pairs.push({
          left: { type: 'same', text: origLines[a.origIdx!], lineNum: leftNum },
          right: { type: 'same', text: modLines[a.modIdx!], lineNum: rightNum }
        });
      } else if (a.type === 'removed') {
        leftNum++;
        pairs.push({
          left: { type: 'removed', text: origLines[a.origIdx!], lineNum: leftNum },
          right: null
        });
      } else {
        rightNum++;
        pairs.push({
          left: null,
          right: { type: 'added', text: modLines[a.modIdx!], lineNum: rightNum }
        });
      }
    }

    return pairs;
  });

  let filteredDiffLines = $derived(
    showDiffsOnly ? diffLines.filter(d => d.type !== 'same') : diffLines
  );

  let filteredSidePairs = $derived(
    showDiffsOnly ? sidePairs.filter(p => (p.left?.type !== 'same') || (p.right?.type !== 'same')) : sidePairs
  );

  function lineClass(type: string): string {
    switch (type) {
      case 'added': return 'bg-neon-green/10 text-neon-green';
      case 'removed': return 'bg-neon-red/10 text-neon-red';
      default: return 'text-text-secondary';
    }
  }

  function linePrefix(type: string): string {
    switch (type) {
      case 'added': return '+';
      case 'removed': return '-';
      default: return ' ';
    }
  }
</script>

<div class="font-mono text-xs">
  <!-- Toolbar -->
  <div class="flex items-center justify-between px-3 py-1.5 bg-bg-secondary/50 border-b border-border-subtle">
    <div class="flex items-center gap-2">
      <button
        class="text-[10px] px-2 py-0.5 rounded border transition-colors
          {viewMode === 'side-by-side'
            ? 'text-neon-cyan border-neon-cyan/30 bg-neon-cyan/10'
            : 'text-text-dim border-border-subtle hover:border-neon-cyan/20'}"
        onclick={() => viewMode = 'side-by-side'}
      >
        Side-by-side
      </button>
      <button
        class="text-[10px] px-2 py-0.5 rounded border transition-colors
          {viewMode === 'inline'
            ? 'text-neon-cyan border-neon-cyan/30 bg-neon-cyan/10'
            : 'text-text-dim border-border-subtle hover:border-neon-cyan/20'}"
        onclick={() => viewMode = 'inline'}
      >
        Inline
      </button>
    </div>
    <label class="flex items-center gap-1.5 cursor-pointer">
      <input
        type="checkbox"
        bind:checked={showDiffsOnly}
        class="w-3 h-3 rounded border-border-subtle accent-neon-cyan"
      />
      <span class="text-[10px] text-text-dim">Show differences only</span>
    </label>
  </div>

  <!-- Side-by-side view -->
  {#if viewMode === 'side-by-side'}
    <div class="grid grid-cols-2 gap-px bg-border-subtle">
      <!-- Original -->
      <div class="bg-bg-card p-2">
        <div class="text-[10px] text-neon-red/60 uppercase tracking-wider font-semibold mb-2">Original</div>
        {#each filteredSidePairs as pair}
          {#if pair.left}
            <div class="py-0.5 px-1 flex gap-2 {lineClass(pair.left.type)}">
              <span class="text-text-dim/40 select-none w-4 text-right shrink-0">{pair.left.lineNum}</span>
              <span class="whitespace-pre-wrap break-all">{pair.left.text}</span>
            </div>
          {:else}
            <div class="py-0.5 px-1 flex gap-2 opacity-30">
              <span class="w-4 shrink-0"></span>
              <span class="whitespace-pre-wrap"> </span>
            </div>
          {/if}
        {/each}
      </div>

      <!-- Modified -->
      <div class="bg-bg-card p-2">
        <div class="text-[10px] text-neon-green/60 uppercase tracking-wider font-semibold mb-2">Modified</div>
        {#each filteredSidePairs as pair}
          {#if pair.right}
            <div class="py-0.5 px-1 flex gap-2 {lineClass(pair.right.type)}">
              <span class="text-text-dim/40 select-none w-4 text-right shrink-0">{pair.right.lineNum}</span>
              <span class="whitespace-pre-wrap break-all">{pair.right.text}</span>
            </div>
          {:else}
            <div class="py-0.5 px-1 flex gap-2 opacity-30">
              <span class="w-4 shrink-0"></span>
              <span class="whitespace-pre-wrap"> </span>
            </div>
          {/if}
        {/each}
      </div>
    </div>

  <!-- Inline view -->
  {:else}
    <div class="bg-bg-card p-2">
      {#each filteredDiffLines as line}
        <div class="py-0.5 px-1 flex gap-2 {lineClass(line.type)}">
          <span class="text-text-dim/40 select-none w-3 shrink-0">{linePrefix(line.type)}</span>
          <span class="text-text-dim/40 select-none w-4 text-right shrink-0">{line.lineNum}</span>
          <span class="whitespace-pre-wrap break-all">{line.text}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>
