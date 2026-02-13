export interface ToastMessage {
	id: number;
	message: string;
	type: 'success' | 'error' | 'info';
	duration: number;
}

let nextId = 0;

class ToastState {
	toasts: ToastMessage[] = $state([]);

	show(message: string, type: 'success' | 'error' | 'info' = 'info', duration = 4000) {
		const id = nextId++;
		this.toasts = [...this.toasts, { id, message, type, duration }];

		setTimeout(() => {
			this.dismiss(id);
		}, duration);
	}

	dismiss(id: number) {
		this.toasts = this.toasts.filter(t => t.id !== id);
	}
}

export const toastState = new ToastState();
