<script lang="ts">
  import { workbench } from "$lib/stores/workbench.svelte";
  import { editor } from "$lib/stores/editor.svelte";
  import { forge } from "$lib/stores/forge.svelte";
  import { history } from "$lib/stores/history.svelte";
  import { feedback } from "$lib/stores/feedback.svelte";
  import { refinement } from "$lib/stores/refinement.svelte";
  import { getStrategyHex } from "$lib/utils/strategy";
  import ScoreCircle from "$lib/components/shared/ScoreCircle.svelte";
  import { getScoreColor } from "$lib/utils/colors";
  import Tip from "$lib/components/shared/Tip.svelte";
  import InspectorFeedback from "$lib/components/layout/InspectorFeedback.svelte";
  import InspectorRefinement from "$lib/components/layout/InspectorRefinement.svelte";
  import InspectorBranches from "$lib/components/layout/InspectorBranches.svelte";
  import InspectorAdaptation from "$lib/components/layout/InspectorAdaptation.svelte";

  // ── Drag-resize state ───────────────────────────────────────────────
  let _resizing = $state(false);
  let _startX = 0;
  let _startW = 0;

  function _onResizeStart(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    _resizing = true;
    _startX = e.clientX;
    _startW = workbench.inspectorWidth;

    function onMove(ev: MouseEvent) {
      // Inspector is on the right — dragging left increases width
      const delta = _startX - ev.clientX;
      workbench.setInspectorWidth(_startW + delta);
    }

    function onUp() {
      _resizing = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }

    // Use window mouse events for reliable tracking outside the handle
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    // Prevent text selection and set cursor during drag
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  let strategyRecommendations = $derived.by(() => {
    // Prefer real forge strategy result when available
    const strategyResult = forge.stageResults['strategy']?.data as Record<string, unknown> | undefined;
    if (strategyResult?.primary_framework) {
      const primary = strategyResult.primary_framework as string;
      const secondary = (strategyResult.secondary_frameworks as string[] | undefined) || [];
      const rationale = (strategyResult.rationale as string | undefined) || '';
      const recs = [
        { name: primary, confidence: 0.95, desc: rationale.slice(0, 60) + (rationale.length > 60 ? '…' : '') },
        ...secondary.slice(0, 2).map((fw: string, i: number) => ({
          name: fw,
          confidence: 0.75 - i * 0.1,
          desc: `Secondary framework`,
        })),
      ];
      return recs;
    }
    // Fall back to prompt-length heuristics when no forge has run
    const promptLen = (editor.activeTab?.promptText || "").length;
    if (promptLen > 200) {
      return [
        {
          name: "CO-STAR",
          confidence: 0.85,
          desc: "Best for detailed task prompts",
        },
        {
          name: "chain-of-thought",
          confidence: 0.72,
          desc: "Great for reasoning tasks",
        },
        {
          name: "RISEN",
          confidence: 0.65,
          desc: "Good for role-based prompts",
        },
      ];
    } else if (promptLen > 50) {
      return [
        {
          name: "role-task-format",
          confidence: 0.78,
          desc: "Simple and effective",
        },
        {
          name: "step-by-step",
          confidence: 0.71,
          desc: "Breaks down complex tasks",
        },
        {
          name: "few-shot-scaffolding",
          confidence: 0.6,
          desc: "Learn by example",
        },
      ];
    }
    return [
      { name: "auto", confidence: 0.9, desc: "Let Project Synthesis choose" },
      {
        name: "context-enrichment",
        confidence: 0.65,
        desc: "Add more context",
      },
      {
        name: "persona-assignment",
        confidence: 0.55,
        desc: "Assign expert role",
      },
    ];
  });
</script>

<aside
  class="h-full bg-bg-secondary border-l border-border-subtle flex overflow-hidden"
  class:w-0={workbench.inspectorCollapsed}
  class:opacity-0={workbench.inspectorCollapsed}
  class:transition-all={!_resizing}
  class:duration-200={!_resizing}
  style="width: {workbench.inspectorCssWidth}"
  aria-label="Inspector"
  data-tour="inspector"
>
  {#if !workbench.inspectorCollapsed}
    <!-- Drag-resize handle — 6px hit zone on the left edge, 2px visible line on hover -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="resize-handle shrink-0 cursor-col-resize relative select-none"
      style="width: 6px;"
      onmousedown={_onResizeStart}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize inspector panel"
      title="Drag to resize"
    >
      <div class="absolute inset-y-0 left-0 w-[2px] bg-transparent transition-colors duration-150 resize-line"></div>
    </div>

    <div class="flex-1 flex flex-col overflow-hidden min-w-0">
    <div
      class="h-8 flex items-center px-2 border-b border-border-subtle shrink-0"
    >
      <span class="font-display text-[11px] font-bold uppercase text-text-dim"
        >Inspector</span
      >
    </div>

    <div class="flex-1 overflow-y-auto p-2 space-y-2" style="overscroll-behavior: contain;">
      {#if forge.isForging || forge.overallScore != null}
        <!-- Pipeline status — compact horizontal layout -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between">
            <h3 class="section-heading">Pipeline</h3>
            {#if forge.overallScore != null}
              <div class="flex items-center gap-1.5">
                <ScoreCircle score={forge.overallScore} size={20} />
                <span class="text-[10px] font-mono text-text-dim">
                  {forge.completedStages}/{forge.visibleStages.length}
                </span>
              </div>
            {/if}
          </div>

          <div class="flex flex-wrap gap-x-3 gap-y-0.5">
            {#each forge.stages.filter((s) => !(s === "explore" && forge.stageStatuses[s] === "idle")) as stage}
              {@const status = forge.stageStatuses[stage]}
              <div class="flex items-center gap-1 text-[10px]">
                <span
                  class="w-1.5 h-1.5 rounded-full shrink-0 {status === 'done'
                    ? 'bg-neon-green'
                    : status === 'running'
                      ? 'bg-neon-cyan animate-status-pulse'
                      : status === 'error'
                        ? 'bg-neon-red'
                        : status === 'timed_out'
                          ? 'bg-neon-yellow'
                          : 'bg-text-dim/20'}"
                ></span>
                <span
                  class="capitalize {status === 'running'
                    ? 'text-neon-cyan'
                    : status === 'done'
                      ? 'text-text-primary'
                      : status === 'error'
                        ? 'text-neon-red'
                        : status === 'timed_out'
                          ? 'text-neon-yellow'
                          : 'text-text-dim'}"
                >{stage}</span>
              </div>
            {/each}
          </div>
        </div>

        <!-- Scores — compact inline rows with thin bars -->
        {#if forge.stageResults["validate"]}
          {@const validation =
            (forge.stageResults["validate"]?.data as Record<string, unknown>) ||
            {}}
          {@const scores = (validation.scores || {}) as Record<string, number>}
          {#key forge.overallScore}
            <div
              class="space-y-1"
              style="animation: fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;"
            >
              <h3 class="section-heading">Scores</h3>
              {#each Object.entries(scores).filter(([k]) => k !== "overall_score") as [key, val]}
                {@const scoreVal = typeof val === "number" ? val : 0}
                {@const scoreLabel = key.replace(/_score$/, "").replace(/_/g, " ")}
                <div class="flex items-center gap-1.5 h-5">
                  <span class="text-[10px] text-text-secondary capitalize w-20 shrink-0 truncate"
                    >{scoreLabel}</span
                  >
                  <div class="flex-1 h-1 bg-bg-primary overflow-hidden">
                    <div
                      class="h-full"
                      style="width: {scoreVal * 10}%; background-color: {getScoreColor(scoreVal)};"
                    ></div>
                  </div>
                  <span class="font-mono text-[10px] text-text-primary w-7 text-right shrink-0"
                    >{scoreVal}/10</span
                  >
                </div>
              {/each}
            </div>
          {/key}
        {/if}

        <!-- Feedback panel — merged with score overrides -->
        {#if forge.overallScore != null}
          <InspectorFeedback />
        {/if}

        <!-- Refinement turn history -->
        {#if refinement.branches.length > 0}
          <InspectorRefinement />
        {/if}

        <!-- Branch tree -->
        {#if refinement.branchCount > 1}
          <InspectorBranches />
        {/if}

        <!-- Adaptation transparency -->
        {#if feedback.adaptationSummary !== null || feedback.showAdaptationPanel}
          <InspectorAdaptation />
        {/if}

        <!-- Original Prompt — compact -->
        {#if forge.rawPrompt}
          <div class="space-y-1">
            <h3 class="section-heading">Original Prompt</h3>
            <div
              class="text-[10px] text-text-secondary bg-bg-card border border-border-subtle p-1.5 max-h-20 overflow-y-auto whitespace-pre-wrap break-words leading-snug"
            >
              {forge.rawPrompt}
            </div>
          </div>
        {/if}
      {:else if editor.activeTab}
        <!-- Strategy Recommendations (when Edit sub-tab is active) -->
        {#if editor.activeSubTab === "edit"}
          <div class="space-y-2">
            <h3 class="section-heading">Strategy Recommendations</h3>
            <div class="space-y-2">
              {#each strategyRecommendations as rec, i}
                <div class="space-y-1">
                  <div class="flex justify-between text-xs">
                    <span class="text-text-secondary">{rec.name}</span>
                    <span class="text-text-dim"
                      >{Math.round(rec.confidence * 100)}%</span
                    >
                  </div>
                  <div
                    class="relative h-1.5 bg-bg-card overflow-hidden rounded-none"
                    style="--bar-accent: {getStrategyHex(rec.name)}55;"
                  >
                    <div
                      class="absolute inset-0 origin-left"
                      style="width: {rec.confidence *
                        100}%; background: {getStrategyHex(
                        rec.name,
                      )}; animation: progress-fill 0.6s cubic-bezier(0.16, 1, 0.3, 1) {i *
                        80}ms both;"
                    ></div>
                    <div
                      class="bar-glass absolute inset-0 pointer-events-none"
                    ></div>
                  </div>
                  <p class="text-[10px] text-text-secondary">{rec.desc}</p>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- History sub-tab: run statistics -->
        {#if editor.activeSubTab === "history"}
          <div class="space-y-2">
            <h3 class="section-heading">Run Statistics</h3>
            {#if history.entries.length > 0}
              {@const scoredEntries = history.entries.filter(
                (e) => e.overall_score != null,
              )}
              {@const avgScore =
                scoredEntries.length > 0
                  ? (
                      scoredEntries.reduce(
                        (s, e) => s + (e.overall_score ?? 0),
                        0,
                      ) / scoredEntries.length
                    ).toFixed(1)
                  : null}
              {@const bestEntry =
                scoredEntries.length > 0
                  ? scoredEntries.reduce((a, b) =>
                      (b.overall_score ?? 0) > (a.overall_score ?? 0) ? b : a,
                    )
                  : null}
              {@const strategyCounts = history.entries.reduce(
                (acc: Record<string, number>, e) => {
                  if (e.primary_framework) acc[e.primary_framework] = (acc[e.primary_framework] || 0) + 1;
                  return acc;
                },
                {},
              )}
              {@const mostUsedStrategy = Object.keys(strategyCounts).sort(
                (a, b) => strategyCounts[b] - strategyCounts[a],
              )[0]}
              <div class="space-y-0.5">
                <div class="flex items-center justify-between h-5 text-[10px]">
                  <span class="text-text-dim">Total runs</span>
                  <span class="font-mono text-text-primary"
                    >{history.unfilteredTotal || history.entries.length}</span
                  >
                </div>
                {#if avgScore}
                  <div class="flex items-center justify-between h-5 text-[10px]">
                    <span class="text-text-dim">Avg score</span>
                    <span class="font-mono text-text-primary"
                      >{avgScore}/10</span
                    >
                  </div>
                {/if}
                {#if mostUsedStrategy}
                  <div class="flex items-center justify-between h-5 text-[10px]">
                    <span class="text-text-dim">Top strategy</span>
                    <span class="font-mono text-text-primary capitalize"
                      >{mostUsedStrategy}</span
                    >
                  </div>
                {/if}
                {#if bestEntry}
                  <div class="flex items-center justify-between h-5 text-[10px]">
                    <span class="text-text-dim">Best run</span>
                    <span class="font-mono text-text-primary"
                      >{bestEntry.overall_score}/10</span
                    >
                  </div>
                {/if}
              </div>
            {:else}
              <p class="text-xs text-text-dim">No runs yet</p>
            {/if}
          </div>
        {/if}

        <!-- Document Info -->
        <div class="space-y-2">
          <h3 class="section-heading">Document Info</h3>
          <div class="space-y-0.5">
            <div class="flex items-center justify-between h-5 text-[10px]">
              <span class="text-text-dim">Type</span>
              <span class="font-mono text-text-primary capitalize"
                >{editor.activeTab.type}</span
              >
            </div>
            <div class="flex items-center justify-between h-5 text-[10px]">
              <span class="text-text-dim">Characters</span>
              <span class="font-mono text-text-primary"
                >{(editor.activeTab.promptText || "").length}</span
              >
            </div>
            <div class="flex items-center justify-between h-5 text-[10px]">
              <span class="text-text-dim">Words</span>
              <span class="font-mono text-text-primary"
                >{(editor.activeTab.promptText || "")
                  .split(/\s+/)
                  .filter(Boolean).length}</span
              >
            </div>
            <div class="flex items-center justify-between h-5 text-[10px]">
              <span class="text-text-dim">Status</span>
              <span class="font-mono text-text-primary"
                >{editor.activeTab.dirty ? "Modified" : "Clean"}</span
              >
            </div>
          </div>
        </div>
      {:else}
        <div
          class="flex flex-col items-center justify-center text-center py-8"
        >
          <svg
            class="w-10 h-10 mb-3 opacity-30"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            stroke-width="1"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            ></path>
          </svg>
          <p class="text-xs text-text-dim">Open a prompt to see metadata</p>
          <div class="mt-2">
            <Tip id="inspector-scores" text="Scores and details appear here after synthesis" />
          </div>
        </div>
      {/if}
    </div>
    </div><!-- close flex-1 wrapper -->
  {/if}
</aside>

<style>
  .resize-handle:hover .resize-line,
  .resize-handle:active .resize-line {
    background-color: rgba(0, 229, 255, 0.4);
  }
  .resize-handle:active .resize-line {
    background-color: rgba(0, 229, 255, 0.6);
  }
</style>
