<script lang="ts">
  import { forge } from '$lib/stores/forge.svelte';

  let result = $derived(forge.stageResults['explore']);
  let data = $derived((result?.data || {}) as Record<string, unknown>);
  let techStack = $derived((data.tech_stack || []) as string[]);
  let keyFiles = $derived((data.key_files_read || []) as string[]);
  let observations = $derived((data.observations || []) as string[]);
  let groundingNotes = $derived((data.grounding_notes || []) as string[]);
  let filesReadCount = $derived((data.files_read_count as number) || keyFiles.length);
  let coveragePct = $derived((data.coverage_pct as number) || 0);
  let branchFallback = $derived((data.branch_fallback as boolean) || false);
  let originalBranch = $derived((data.original_branch as string) || '');
  let usedBranch = $derived((data.used_branch as string) || '');
</script>

<div class="space-y-2 text-xs">
  {#if forge.stageStatuses['explore'] === 'running'}
    <div class="flex items-center gap-2 text-neon-purple">
      <span class="w-3 h-3 rounded-full animate-spin" style="border: 1px solid transparent; border-top-color: #a855f7;"></span>
      <span>Exploring prompt context...</span>
    </div>
  {:else if forge.stageStatuses['explore'] === 'error'}
    <div class="space-y-1">
      <div class="flex items-center gap-2 text-neon-red text-[11px]">
        <span>Exploration failed — pipeline continues without codebase context.</span>
      </div>
      {#if observations.length > 0}
        {#each observations as obs}
          <p class="text-text-dim font-mono text-[10px] truncate" title={obs}>· {obs}</p>
        {/each}
      {:else if forge.error}
        <p class="text-text-dim font-mono text-[10px] truncate" title={forge.error}>· {forge.error}</p>
      {/if}
    </div>
  {:else if result}
    <!-- Branch fallback warning -->
    {#if branchFallback}
      <div
        class="px-2 py-1.5 text-[11px] text-text-secondary font-mono"
        style="border: 1px solid var(--color-neon-yellow, #fbbf24); background: rgba(251,191,36,0.04);"
      >
        ⚠ Branch "{originalBranch}" not found — using "{usedBranch}" instead
      </div>
    {/if}

    <!-- Terminal-style key files feed -->
    {#if keyFiles.length > 0}
      <div class="bg-bg-input rounded-md p-2 space-y-1">
        {#each keyFiles as file, i}
          <div
            class="font-mono text-[11px] text-text-secondary"
            style="animation: list-item-in 0.15s cubic-bezier(0.16,1,0.3,1) {i*30}ms both;"
          >
            <span class="text-neon-purple/80">▸</span> {file}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Tech stack badges -->
    {#if techStack.length > 0}
      <div class="flex flex-wrap gap-1">
        {#each techStack as tech}
          <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-neon-purple/10 border border-neon-purple/20 text-neon-purple/80">{tech}</span>
        {/each}
      </div>
    {/if}

    <!-- Observations -->
    {#if observations.length > 0}
      <div class="space-y-1">
        {#each observations as obs}
          <p class="text-text-secondary text-[11px]">· {obs}</p>
        {/each}
      </div>
    {/if}

    <!-- Grounding notes -->
    {#if groundingNotes.length > 0}
      <div class="border-t border-border-subtle pt-1.5 space-y-1">
        {#each groundingNotes as note}
          <p class="text-text-dim italic text-[10px]">{note}</p>
        {/each}
      </div>
    {/if}

    {#if filesReadCount > 0}
      <div class="text-text-secondary font-mono text-[10px] flex items-center gap-2">
        <span class="text-neon-purple/80">Files: {filesReadCount}</span>
        {#if coveragePct > 0}
          <span class="text-text-dim">·</span>
          <span>Coverage: <span style="color: var(--color-neon-teal, #00e5ff);">{coveragePct}% of repo</span></span>
        {/if}
      </div>
    {/if}
  {:else}
    <p class="text-text-secondary">Waiting to start...</p>
  {/if}
</div>
