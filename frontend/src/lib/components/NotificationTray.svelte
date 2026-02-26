<script lang="ts">
	import { notificationService, type SystemNotification } from '$lib/services/notificationService.svelte';
	import Icon from './Icon.svelte';

	let open = $state(false);

	const TYPE_ICON: Record<SystemNotification['type'], string> = {
		info: 'info',
		success: 'check',
		warning: 'alert-triangle',
		error: 'alert-circle',
	};

	const TYPE_COLOR: Record<SystemNotification['type'], string> = {
		info: 'text-neon-blue',
		success: 'text-neon-green',
		warning: 'text-neon-yellow',
		error: 'text-neon-red',
	};

	function toggle() {
		open = !open;
	}

	function closePanel() {
		open = false;
	}

	function handleDismiss(e: MouseEvent, id: string) {
		e.stopPropagation();
		notificationService.dismiss(id);
	}

	function handleAction(notif: SystemNotification) {
		if (notif.actionCallback) {
			notif.actionCallback();
		}
		notificationService.markRead(notif.id);
		open = false;
	}

	function handleClickNotification(notif: SystemNotification) {
		if (!notif.read) {
			notificationService.markRead(notif.id);
		}
		if (notif.actionCallback) {
			notif.actionCallback();
			open = false;
		}
	}

	function formatTime(ts: number): string {
		const diff = Date.now() - ts;
		if (diff < 60_000) return 'now';
		if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
		if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
		return `${Math.floor(diff / 86_400_000)}d`;
	}
</script>

<!-- Escape key handler (only active when panel is open) -->
<svelte:window onkeydown={(e) => { if (open && e.key === 'Escape') { e.preventDefault(); closePanel(); }}} />

<div class="relative">
	<!-- Bell button — z-[101] keeps it clickable above the backdrop -->
	<button
		class="relative z-[101] flex items-center gap-0.5 text-[10px] transition-colors
			{open ? 'text-neon-cyan' : 'text-text-dim/70 hover:text-neon-cyan'}"
		onclick={toggle}
		aria-label="Notifications ({notificationService.unreadCount} unread)"
	>
		<Icon name="alert-circle" size={11} />
		{#if notificationService.unreadCount > 0}
			<span class="absolute -top-1 -right-1 flex h-3 w-3 items-center justify-center bg-neon-red text-[7px] text-white font-bold">
				{notificationService.unreadCount > 9 ? '9+' : notificationService.unreadCount}
			</span>
		{/if}
	</button>

	{#if open}
		<!-- Invisible backdrop — catches outside clicks. Fixed to viewport,
		     participates in taskbar's stacking context. -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="fixed inset-0 z-[99]"
			onclick={closePanel}
			onkeydown={() => {}}
			role="presentation"
		></div>

		<!-- Popup panel — above backdrop -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="absolute bottom-8 right-0 z-[100] w-72 border border-neon-cyan/20 bg-bg-card font-mono"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-neon-cyan/10 px-3 py-1.5">
				<span class="text-[11px] text-text-primary font-medium">Notifications</span>
				<div class="flex items-center gap-2">
					{#if notificationService.unreadCount > 0}
						<button
							class="text-[9px] text-neon-cyan hover:text-neon-cyan/80 transition-colors"
							onclick={() => notificationService.markAllRead()}
						>
							Mark all read
						</button>
					{/if}
					{#if notificationService.notifications.length > 0}
						<button
							class="text-[9px] text-text-dim hover:text-neon-red transition-colors"
							onclick={() => notificationService.clear()}
						>
							Clear
						</button>
					{/if}
				</div>
			</div>

			<!-- Notification list -->
			<div class="max-h-[300px] overflow-y-auto">
				{#if notificationService.notifications.length === 0}
					<div class="px-3 py-6 text-center text-xs text-text-dim">
						No notifications
					</div>
				{:else}
					{#each notificationService.notifications as notif (notif.id)}
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div
							class="flex items-start gap-2 px-3 py-2 border-b border-neon-cyan/5 cursor-pointer transition-colors
								{notif.read ? 'opacity-60' : ''} hover:bg-bg-hover"
							onclick={() => handleClickNotification(notif)}
							onkeydown={(e) => { if (e.key === 'Enter') handleClickNotification(notif); }}
						>
							<Icon name={TYPE_ICON[notif.type] as any} size={12} class="{TYPE_COLOR[notif.type]} shrink-0 mt-0.5" />
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-1">
									<span class="text-[11px] text-text-primary truncate">{notif.title}</span>
									{#if !notif.read}
										<span class="h-1 w-1 bg-neon-cyan shrink-0"></span>
									{/if}
								</div>
								{#if notif.body}
									<p class="text-[10px] text-text-dim truncate mt-0.5">{notif.body}</p>
								{/if}
								<div class="flex items-center gap-2 mt-1">
									<span class="text-[9px] text-text-dim/50">{formatTime(notif.timestamp)}</span>
									{#if notif.actionLabel}
										<button
											class="text-[9px] text-neon-cyan hover:text-neon-cyan/80 transition-colors"
											onclick={(e) => { e.stopPropagation(); handleAction(notif); }}
										>
											{notif.actionLabel}
										</button>
									{/if}
								</div>
							</div>
							<button
								class="shrink-0 p-0.5 text-text-dim/30 hover:text-text-dim transition-colors"
								onclick={(e) => handleDismiss(e, notif.id)}
								aria-label="Dismiss"
							>
								<Icon name="x" size={10} />
							</button>
						</div>
					{/each}
				{/if}
			</div>
		</div>
	{/if}
</div>
