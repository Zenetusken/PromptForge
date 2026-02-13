class PromptState {
	text: string = $state('');

	set(value: string) {
		this.text = value;
	}

	clear() {
		this.text = '';
	}
}

export const promptState = new PromptState();
