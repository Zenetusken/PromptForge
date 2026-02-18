<script lang="ts">
	import { projectsState } from '$lib/stores/projects.svelte';
	import { toastState } from '$lib/stores/toast.svelte';

	let { onclose }: { onclose: () => void } = $props();

	let name = $state('');
	let description = $state('');
	let isSubmitting = $state(false);

	async function handleCreate() {
		const trimmedName = name.trim();
		if (!trimmedName || isSubmitting) return;

		isSubmitting = true;
		try {
			const project = await projectsState.create(trimmedName, description.trim() || undefined);
			if (project) {
				toastState.show(`Project "${trimmedName}" created`, 'success');
				onclose();
			} else {
				toastState.show('Failed to create project — name may already exist', 'error');
			}
		} finally {
			isSubmitting = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
			e.preventDefault();
			handleCreate();
		} else if (e.key === 'Escape') {
			onclose();
		}
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="animate-fade-in mx-3 mb-2 rounded-xl border border-neon-cyan/15 bg-bg-card p-3" onkeydown={handleKeydown} data-testid="create-project-dialog">
	<p class="mb-2 text-xs font-medium text-neon-cyan">New Project</p>
	<div class="space-y-2">
		<input
			type="text"
			bind:value={name}
			placeholder="Project name"
			aria-label="Project name"
			data-testid="project-name-input"
			class="input-field w-full py-2 text-sm"
		/>
		<textarea
			bind:value={description}
			placeholder="Description (optional)"
			aria-label="Project description"
			data-testid="project-description-input"
			rows="2"
			class="input-field w-full resize-none py-2 text-sm"
		></textarea>
	</div>
	<div class="mt-2.5 flex gap-2">
		<button
			onclick={handleCreate}
			disabled={!name.trim() || isSubmitting}
			class="flex-1 rounded-lg bg-neon-cyan/15 py-1.5 text-xs font-medium text-neon-cyan transition-colors hover:bg-neon-cyan/25 disabled:opacity-40"
			data-testid="create-project-submit"
		>
			{isSubmitting ? 'Creating...' : 'Create'}
		</button>
		<button
			onclick={onclose}
			class="flex-1 rounded-lg bg-bg-hover py-1.5 text-xs text-text-dim transition-colors hover:bg-bg-hover/80"
			data-testid="create-project-cancel"
		>
			Cancel
		</button>
	</div>
</div>
