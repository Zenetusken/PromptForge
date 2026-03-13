<script lang="ts">
  import { refinement } from '$lib/stores/refinement.svelte';
  import type { Branch } from '$lib/stores/refinement.svelte';
  import { forge } from '$lib/stores/forge.svelte';

  // Build a simple tree: trunk = branches with no parent, forks = children
  let tree = $derived.by(() => {
    const roots = refinement.branches.filter((b) => b.parentBranchId === null);
    return roots.map((root) => ({
      branch: root,
      children: refinement.branches.filter((b) => b.parentBranchId === root.id),
    }));
  });

  function getStatusClasses(status: Branch['status']): string {
    switch (status) {
      case 'active': return 'border-neon-green text-neon-green';
      case 'selected': return 'border-neon-cyan text-neon-cyan';
      case 'abandoned': return 'border-text-dim text-text-dim';
    }
  }

  function getStatusLabel(status: Branch['status']): string {
    switch (status) {
      case 'active': return 'active';
      case 'selected': return 'selected';
      case 'abandoned': return 'abandoned';
    }
  }

  function getOverallScore(branch: Branch): number | null {
    if (!branch.scores) return null;
    return typeof branch.scores['overall_score'] === 'number'
      ? branch.scores['overall_score']
      : null;
  }

  function handleFork(branch: Branch) {
    // Opens the refinement input in fork mode — delegate to refinement store
    refinement.activeBranchId = branch.id;
    refinement.openRefinement();
  }

  function handleCompare(branch: Branch) {
    const active = refinement.activeBranchId;
    if (active && active !== branch.id) {
      refinement.comparingBranches = [active, branch.id];
    }
  }

  function handleSelect(branch: Branch) {
    const optId = forge.optimizationId;
    if (optId) refinement.selectWinner(optId, branch.id);
  }
</script>

<div class="space-y-3">
  <h3 class="font-display text-[12px] font-bold uppercase text-text-dim">Branches</h3>

  {#if tree.length === 0}
    <p class="text-xs text-text-dim">No branches yet.</p>
  {:else}
    <div class="space-y-0">
      {#each tree as node}
        <!-- Trunk branch -->
        <div class="space-y-0">
          <div class="flex items-start gap-2 p-1.5 bg-bg-card border border-border-subtle">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-mono text-[10px] text-text-primary truncate">{node.branch.label}</span>
                <span class="border text-[9px] font-mono uppercase px-1 py-0 {getStatusClasses(node.branch.status)}">
                  {getStatusLabel(node.branch.status)}
                </span>
              </div>
              <div class="flex gap-2 mt-0.5 text-[9px] text-text-dim font-mono">
                <span>{node.branch.turnCount} turns</span>
                {#if getOverallScore(node.branch) !== null}
                  <span>{getOverallScore(node.branch)}/10</span>
                {/if}
              </div>
            </div>
            <div class="flex gap-1 shrink-0">
              <button
                class="border border-neon-purple/60 text-neon-purple text-[9px] font-mono uppercase px-1.5 py-0.5 hover:bg-neon-purple/10 transition-colors"
                onclick={() => handleFork(node.branch)}
              >Fork</button>
              <button
                class="border border-neon-blue/60 text-neon-blue text-[9px] font-mono uppercase px-1.5 py-0.5 hover:bg-neon-blue/10 transition-colors"
                onclick={() => handleCompare(node.branch)}
              >Cmp</button>
              <button
                class="border border-neon-cyan text-neon-cyan text-[9px] font-mono uppercase px-1.5 py-0.5 hover:bg-neon-cyan/10 transition-colors"
                onclick={() => handleSelect(node.branch)}
              >Sel</button>
            </div>
          </div>

          <!-- Fork children — indented with connector line -->
          {#each node.children as child}
            <div class="flex ml-4">
              <!-- 1px neon-purple connector -->
              <div class="w-px self-stretch bg-neon-purple opacity-50"></div>
              <div class="flex-1 flex items-start gap-2 p-1.5 bg-bg-card border border-border-subtle border-l-0 ml-1">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="font-mono text-[10px] text-text-primary truncate">{child.label}</span>
                    <span class="border text-[9px] font-mono uppercase px-1 py-0 {getStatusClasses(child.status)}">
                      {getStatusLabel(child.status)}
                    </span>
                  </div>
                  <div class="flex gap-2 mt-0.5 text-[9px] text-text-dim font-mono">
                    <span>{child.turnCount} turns</span>
                    {#if getOverallScore(child) !== null}
                      <span>{getOverallScore(child)}/10</span>
                    {/if}
                  </div>
                </div>
                <div class="flex gap-1 shrink-0">
                  <button
                    class="border border-neon-purple/60 text-neon-purple text-[9px] font-mono uppercase px-1.5 py-0.5 hover:bg-neon-purple/10 transition-colors"
                    onclick={() => handleFork(child)}
                  >Fork</button>
                  <button
                    class="border border-neon-blue/60 text-neon-blue text-[9px] font-mono uppercase px-1.5 py-0.5 hover:bg-neon-blue/10 transition-colors"
                    onclick={() => handleCompare(child)}
                  >Cmp</button>
                  <button
                    class="border border-neon-cyan text-neon-cyan text-[9px] font-mono uppercase px-1.5 py-0.5 hover:bg-neon-cyan/10 transition-colors"
                    onclick={() => handleSelect(child)}
                  >Sel</button>
                </div>
              </div>
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}
</div>
