<script lang="ts">
  import { github, type GitHubRepo } from '$lib/stores/github.svelte';
  import RepoBadge from './RepoBadge.svelte';

  let {
    open = false,
    onclose,
    onselectrepo
  }: {
    open?: boolean;
    onclose?: () => void;
    onselectrepo?: (name: string, branch: string) => void;
  } = $props();

  let search = $state('');
  let expandedRepo = $state<string | null>(null);
  let branchInput = $state('');

  let filtered = $derived(
    github.repos.filter(r =>
      r.full_name.toLowerCase().includes(search.toLowerCase()) ||
      r.description.toLowerCase().includes(search.toLowerCase())
    )
  );

  // Collapse expansion when search changes
  $effect(() => {
    search;
    expandedRepo = null;
  });

  function toggleExpand(repo: GitHubRepo) {
    if (expandedRepo === repo.full_name) {
      expandedRepo = null;
    } else {
      expandedRepo = repo.full_name;
      branchInput = repo.default_branch;
    }
  }

  function confirmLink() {
    if (!expandedRepo || !branchInput.trim()) return;
    if (onselectrepo) {
      onselectrepo(expandedRepo, branchInput.trim());
    } else {
      github.selectRepo(expandedRepo);
    }
    expandedRepo = null;
    onclose?.();
  }
</script>

{#if open}
  <div class="fixed inset-0 bg-black/50 z-[700]" onclick={() => onclose?.()} role="presentation"></div>

  <div class="fixed top-[20%] left-1/2 -translate-x-1/2 w-[440px] max-w-[90vw] bg-bg-card border border-border-subtle rounded-xl z-[700] overflow-hidden animate-dialog-in">
    <div class="px-4 py-3 border-b border-border-subtle">
      <h2 class="text-sm font-semibold text-text-primary mb-2">Select Repository</h2>
      <input
        type="text"
        placeholder="Search repositories..."
        class="w-full bg-bg-input border border-border-subtle rounded px-2 py-1.5 text-xs text-text-primary placeholder:text-text-dim focus:outline-none focus:border-neon-cyan/30"
        bind:value={search}
      />
    </div>

    <div class="max-h-[360px] overflow-y-auto py-1">
      {#each filtered as repo (repo.full_name)}
        <!-- Main row — click to expand/collapse -->
        <button
          class="w-full text-left px-4 py-2 hover:bg-bg-hover transition-colors"
          onclick={() => toggleExpand(repo)}
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 min-w-0">
              <RepoBadge name={repo.full_name} isPrivate={repo.private} />
              {#if repo.language}
                <span class="text-[10px] text-text-dim bg-bg-hover px-1.5 py-0.5 rounded shrink-0">
                  {repo.language}
                </span>
              {/if}
              {#if repo.size_kb != null}
                <span class="text-[10px] text-text-dim/60 shrink-0">
                  {repo.size_kb >= 1000
                    ? `${(repo.size_kb / 1024).toFixed(1)} MB`
                    : `${repo.size_kb} KB`}
                </span>
              {/if}
            </div>
            {#if github.selectedRepo === repo.full_name}
              <svg class="w-4 h-4 text-neon-cyan shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"></path>
              </svg>
            {/if}
          </div>
          {#if repo.description}
            <p class="text-[10px] text-text-dim mt-0.5 ml-1 truncate">{repo.description}</p>
          {/if}
        </button>

        <!-- Inline branch expansion -->
        {#if expandedRepo === repo.full_name}
          <div class="px-4 pt-2 pb-3 flex items-center gap-2 bg-bg-hover/40 border-t border-border-subtle/50">
            <span class="text-[10px] text-text-dim shrink-0">Branch</span>
            <input
              class="flex-1 bg-bg-input border border-border-subtle rounded px-2 py-1
                     text-xs text-text-primary font-mono focus:outline-none
                     focus:border-neon-cyan/30"
              bind:value={branchInput}
              onkeydown={(e) => { if (e.key === 'Enter') confirmLink(); if (e.key === 'Escape') { expandedRepo = null; } }}
              autofocus
            />
            <button
              class="px-2 py-1 rounded text-xs font-medium bg-neon-cyan/10 text-neon-cyan
                     border border-neon-cyan/20 hover:bg-neon-cyan/20 transition-colors shrink-0"
              onclick={confirmLink}
            >
              Link →
            </button>
          </div>
        {/if}
      {/each}

      {#if filtered.length === 0}
        <p class="text-xs text-text-dim text-center py-6">No repositories match your search.</p>
      {/if}
    </div>
  </div>
{/if}
