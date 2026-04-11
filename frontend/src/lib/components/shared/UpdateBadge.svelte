<script lang="ts">
  import { updateStore } from '$lib/stores/update.svelte';
  import { tooltip } from '$lib/actions/tooltip';

  let dialogEl = $state<HTMLDivElement | null>(null);
  let badgeEl = $state<HTMLButtonElement | null>(null);
  let dialogStyle = $state('');

  function toggleDialog(e: MouseEvent) {
    if (updateStore.updating) return;
    e.stopPropagation();
    updateStore.dialogOpen = !updateStore.dialogOpen;
    if (updateStore.dialogOpen && badgeEl) {
      const rect = badgeEl.getBoundingClientRect();
      dialogStyle = `position:fixed;bottom:${window.innerHeight - rect.top + 4}px;right:${window.innerWidth - rect.right}px;`;
    }
  }

  function handleUpdate(e: MouseEvent) {
    e.stopPropagation();
    updateStore.startUpdate();
  }

  function handleClickOutside(e: MouseEvent) {
    const target = e.target as Node;
    if (dialogEl && !dialogEl.contains(target) && badgeEl && !badgeEl.contains(target)) {
      updateStore.dialogOpen = false;
    }
  }

  $effect(() => {
    if (updateStore.dialogOpen) {
      // Defer listener to next tick so the opening click doesn't
      // immediately trigger close via the capture-phase handler.
      const timer = setTimeout(() => {
        document.addEventListener('click', handleClickOutside);
      }, 0);
      return () => {
        clearTimeout(timer);
        document.removeEventListener('click', handleClickOutside);
      };
    }
  });

  const categoryColor: Record<string, string> = {
    Added: 'var(--color-neon-green)',
    Changed: 'var(--color-neon-yellow)',
    Fixed: 'var(--color-neon-red)',
    Removed: 'var(--color-neon-red)',
    Deprecated: 'var(--color-text-dim)',
  };
</script>

<div class="update-badge-wrapper">
  {#if updateStore.updating}
    <span class="update-badge updating">&#8635; Restarting...</span>
  {:else}
    <button
      class="update-badge available"
      bind:this={badgeEl}
      onclick={toggleDialog}
      use:tooltip={'Update available — click for details'}
    >
      <span class="badge-dot"></span>
      &#8593; v{updateStore.latestVersion}
    </button>
  {/if}

  {#if updateStore.dialogOpen}
    <div class="update-dialog" bind:this={dialogEl} style={dialogStyle}>
      <div class="dialog-header">
        <div>
          <div class="dialog-title">Update Available</div>
          <div class="dialog-subtitle">
            v{updateStore.currentVersion} &rarr; v{updateStore.latestVersion}
          </div>
        </div>
        <span class="dialog-new-badge">NEW</span>
      </div>

      {#if updateStore.changelogEntries && updateStore.changelogEntries.length > 0}
        <div class="dialog-changelog">
          <div class="changelog-label">What's New</div>
          {#each updateStore.changelogEntries as entry}
            <div class="changelog-entry">
              <span style="color: {categoryColor[entry.category] ?? 'var(--color-text-dim)'}">{entry.category}</span>
              &mdash; {entry.text}
            </div>
          {/each}
        </div>
      {/if}

      {#if !updateStore.hideDetachedWarning}
        <details class="dialog-warning">
          <summary>This will detach from your current branch</summary>
          <p>
            If you've made local commits or customizations, they won't be lost but
            will no longer be on an active branch. You can recover them later with
            <code>git checkout main &amp;&amp; git merge HEAD@{'{'}1{'}'}</code>.
          </p>
          <p class="warning-who">
            This matters if you've committed changes to strategies, prompts, or code.
            If you only use the app as-is, you can safely dismiss this warning.
          </p>
          <label class="warning-dismiss">
            <input
              type="checkbox"
              checked={updateStore.hideDetachedWarning}
              onchange={(e) => updateStore.dismissWarning((e.target as HTMLInputElement).checked)}
            />
            Don't show this warning again
          </label>
        </details>
      {/if}

      <div class="dialog-actions">
        <button class="btn-update" onclick={handleUpdate}>Update &amp; Restart</button>
        <button class="btn-later" onclick={() => updateStore.dialogOpen = false}>Later</button>
      </div>

      <div class="dialog-footer">
        Your data (database, preferences, embeddings) is preserved.
      </div>
    </div>
  {/if}
</div>

<style>
  .update-badge-wrapper {
    position: relative;
  }
  .update-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 6px;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    border: none;
    background: transparent;
    cursor: pointer;
    line-height: 18px;
  }
  .update-badge.available {
    color: var(--color-neon-green);
    border: 1px solid var(--color-neon-green);
    border-radius: 0;
    position: relative;
  }
  .badge-dot {
    position: absolute;
    top: -3px;
    right: -3px;
    width: 7px;
    height: 7px;
    background: var(--color-neon-green);
    border: 1px solid var(--color-bg-primary);
    animation: pulse-dot 2s ease-in-out infinite;
  }
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  .update-badge.updating {
    color: var(--color-neon-yellow);
    cursor: default;
    animation: pulse 1.5s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  .update-dialog {
    width: 360px;
    border: 1px solid var(--color-border-subtle, #1a1a2e);
    background: var(--color-bg-secondary, #0d0d14);
    font-family: var(--font-mono);
    z-index: 100;
  }
  .dialog-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--color-border-subtle, #1a1a2e);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .dialog-title {
    color: var(--color-text, #e0e0e0);
    font-size: 13px;
    font-weight: 600;
  }
  .dialog-subtitle {
    color: var(--color-text-dim, #4a4a6e);
    font-size: 11px;
    margin-top: 2px;
  }
  .dialog-new-badge {
    color: var(--color-neon-green);
    font-size: 10px;
    border: 1px solid var(--color-neon-green);
    padding: 2px 6px;
    letter-spacing: 0.5px;
    border-radius: 0;
  }
  .dialog-changelog {
    padding: 12px 16px;
    border-bottom: 1px solid var(--color-border-subtle, #1a1a2e);
    max-height: 160px;
    overflow-y: auto;
  }
  .changelog-label {
    color: var(--color-text-dim, #7a7a9e);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
  }
  .changelog-entry {
    color: var(--color-text-secondary, #c0c0d0);
    font-size: 11px;
    line-height: 1.6;
    margin-bottom: 4px;
  }
  .dialog-warning {
    padding: 12px 16px;
    border-bottom: 1px solid var(--color-border-subtle, #1a1a2e);
    color: var(--color-text-dim, #7a7a9e);
    font-size: 10px;
    line-height: 1.5;
  }
  .dialog-warning summary {
    cursor: pointer;
    color: var(--color-neon-yellow);
    font-size: 11px;
  }
  .dialog-warning p {
    margin: 8px 0 0;
  }
  .dialog-warning code {
    background: color-mix(in srgb, var(--color-text-primary) 5%, transparent);
    padding: 1px 4px;
  }
  .warning-who {
    color: var(--color-text-dim, #4a4a6e);
    font-style: italic;
  }
  .warning-dismiss {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
    cursor: pointer;
  }
  .warning-dismiss input {
    accent-color: var(--color-neon-green);
    border-radius: 0;
    -webkit-appearance: none;
    appearance: none;
    width: 12px;
    height: 12px;
    border: 1px solid var(--color-border-subtle);
    background: transparent;
    cursor: pointer;
    position: relative;
  }
  .warning-dismiss input:checked {
    border-color: var(--color-neon-green);
    background: var(--color-neon-green);
  }
  .warning-dismiss input:checked::after {
    content: '';
    position: absolute;
    top: 1px;
    left: 3px;
    width: 4px;
    height: 7px;
    border: solid var(--color-bg-primary);
    border-width: 0 1.5px 1.5px 0;
    transform: rotate(45deg);
  }
  .dialog-actions {
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .btn-update {
    flex: 1;
    padding: 8px 0;
    text-align: center;
    border: 1px solid var(--color-neon-green);
    color: var(--color-neon-green);
    background: transparent;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    border-radius: 0;
  }
  .btn-update:hover {
    background: color-mix(in srgb, var(--color-neon-green) 10%, transparent);
  }
  .btn-later {
    padding: 8px 12px;
    text-align: center;
    border: 1px solid var(--color-border-subtle, #2a2a3e);
    color: var(--color-text-dim, #7a7a9e);
    background: transparent;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
    border-radius: 0;
  }
  .dialog-footer {
    padding: 8px 16px 12px;
    color: var(--color-text-dim, #4a4a6e);
    font-size: 10px;
    line-height: 1.4;
  }
</style>
