export interface ToastMessage {
	id: number;
	message: string;
	type: 'success' | 'error' | 'info';
	duration: number;
	dismissing: boolean;
}

let nextId = 0;

class ToastState {
	toasts: ToastMessage[] = $state([]);
	private _timers = new Map<number, ReturnType<typeof setTimeout>>();

	show(message: string, type: 'success' | 'error' | 'info' = 'info', duration = 4000) {
		const id = nextId++;
		this.toasts = [...this.toasts, { id, message, type, duration, dismissing: false }];

		const timer = setTimeout(() => {
			this._timers.delete(id);
			this.dismiss(id);
		}, duration);
		this._timers.set(id, timer);
	}

	dismiss(id: number) {
		const toast = this.toasts.find(t => t.id === id);
		if (!toast || toast.dismissing) return;
		// Clear the auto-dismiss timer if still pending
		const timer = this._timers.get(id);
		if (timer) {
			clearTimeout(timer);
			this._timers.delete(id);
		}
		this.toasts = this.toasts.map(t =>
			t.id === id ? { ...t, dismissing: true } : t
		);
		setTimeout(() => {
			this.toasts = this.toasts.filter(t => t.id !== id);
		}, 300);
	}
}

export const toastState = new ToastState();
