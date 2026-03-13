<script lang="ts">
  interface ChainStep {
    id: string;
    promptName: string;
    prompt: string;
    strategy: string;
    score: number | null;
  }

  const strategies = ['auto', 'CO-STAR', 'RISEN', 'chain-of-thought', 'role-task-format', 'context-enrichment', 'persona-assignment'];

  let steps = $state<ChainStep[]>([
    { id: 'step-1', promptName: 'Step 1', prompt: '', strategy: 'auto', score: null }
  ]);

  function addStep() {
    const num = steps.length + 1;
    steps = [...steps, { id: `step-${Date.now()}`, promptName: `Step ${num}`, prompt: '', strategy: 'auto', score: null }];
  }

  function removeStep(id: string) {
    steps = steps.filter(s => s.id !== id);
  }
</script>

<div class="p-4 space-y-4 animate-fade-in">
  <div class="flex items-center justify-between">
    <h2 class="section-heading">Chain Composer</h2>
    <button
      class="btn-outline-subtle px-3 py-1 text-xs"
      onclick={addStep}
    >
      + Add Step
    </button>
  </div>

  <p class="text-xs text-text-dim">
    Build multi-step prompt chains. Each step's output feeds into the next.
  </p>

  <div class="space-y-3">
    {#each steps as step, i (step.id)}
      <div class="bg-bg-card border border-border-subtle p-3 animate-stagger-fade-in">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-text-secondary">{step.promptName}</span>
            <!-- Strategy badge -->
            <span class="text-[9px] px-1.5 py-0.5 badge-strategy">
              {step.strategy}
            </span>
            <!-- Score indicator -->
            {#if step.score != null}
              <span class="text-[9px] px-1.5 py-0.5 badge-score">
                {step.score}/10
              </span>
            {:else}
              <span class="text-[9px] px-1.5 py-0.5 badge-neutral">
                No score
              </span>
            {/if}
          </div>
          {#if steps.length > 1}
            <button
              class="btn-icon-danger text-[10px]"
              onclick={() => removeStep(step.id)}
            >
              Remove
            </button>
          {/if}
        </div>

        <!-- Strategy selector -->
        <div class="mb-2">
          <select
            id="step-strategy-{i}"
            name="step-strategy-{i}"
            class="w-full bg-bg-input border border-border-subtle px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-neon-cyan/30"
            bind:value={step.strategy}
          >
            {#each strategies as s}
              <option value={s}>{s}</option>
            {/each}
          </select>
        </div>

        <textarea
          id="step-prompt-{i}"
          name="step-prompt-{i}"
          class="w-full bg-bg-input border border-border-subtle px-3 py-2 text-sm text-text-primary font-mono resize-none focus:outline-none focus:border-neon-cyan/30 h-20"
          placeholder="Enter prompt for {step.promptName}..."
          bind:value={step.prompt}
        ></textarea>
        {#if i < steps.length - 1}
          <div class="flex justify-center mt-2">
            <svg class="w-4 h-4 text-neon-cyan/40" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3"></path>
            </svg>
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <button
    class="btn-forge w-full py-2 text-xs font-semibold transition-all duration-200 hover:-translate-y-px active:translate-y-0"
  >
    Forge Chain
  </button>
</div>
