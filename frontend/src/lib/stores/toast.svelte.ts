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

	show(message: string, type: 'success' | 'error' | 'info' = 'info', duration = 4000) {
		const id = nextId++;
		this.toasts = [...this.toasts, { id, message, type, duration, dismissing: false }];

		setTimeout(() => {
			this.dismiss(id);
		}, duration);
	}

	dismiss(id: number) {
		const toast = this.toasts.find(t => t.id === id);
		if (!toast || toast.dismissing) return;
		this.toasts = this.toasts.map(t =>
			t.id === id ? { ...t, dismissing: true } : t
		);
		setTimeout(() => {
			this.toasts = this.toasts.filter(t => t.id !== id);
		}, 300);
	}
}

export const toastState = new ToastState();
