export type SourceAction = 'optimize' | 'reiterate' | null;

class PromptState {
	text: string = $state('');
	projectName: string = $state('');
	promptId: string = $state('');
	title: string = $state('');
	tags: string[] = $state([]);
	version: string = $state('');
	sourceAction: SourceAction = $state(null);
	strategy: string = $state('');

	set(value: string, projectName?: string, promptId?: string, metadata?: {
		title?: string;
		tags?: string[];
		version?: string;
		sourceAction?: SourceAction;
		strategy?: string;
	}) {
		this.text = value;
		this.projectName = projectName ?? '';
		this.promptId = promptId ?? '';
		this.title = metadata?.title ?? '';
		this.tags = metadata?.tags ?? [];
		this.version = metadata?.version ?? '';
		this.sourceAction = metadata?.sourceAction ?? null;
		this.strategy = metadata?.strategy ?? '';
	}

	clear() {
		this.text = '';
		this.projectName = '';
		this.promptId = '';
		this.title = '';
		this.tags = [];
		this.version = '';
		this.sourceAction = null;
		this.strategy = '';
	}
}

export const promptState = new PromptState();
