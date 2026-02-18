class PromptState {
	text: string = $state('');
	projectName: string = $state('');
	promptId: string = $state('');

	set(value: string, projectName?: string, promptId?: string) {
		this.text = value;
		this.projectName = projectName ?? '';
		this.promptId = promptId ?? '';
	}

	clear() {
		this.text = '';
		this.projectName = '';
		this.promptId = '';
	}
}

export const promptState = new PromptState();
