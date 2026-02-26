/**
 * Command Registry — centralized action registry for keyboard shortcuts & command palette.
 *
 * Layer 3 (System Libraries) in the PromptForge OS stack.
 * All user-invocable actions register here. The Command Palette UI (Phase 2) queries this registry.
 */

export type CommandCategory = 'forge' | 'window' | 'navigation' | 'settings' | 'edit';

export interface Command {
	id: string;
	label: string;
	category: CommandCategory;
	shortcut?: string;
	icon?: string;
	execute: () => void;
	/** Return false to hide the command from the palette when unavailable. */
	available?: () => boolean;
}

class CommandPalette {
	commands: Command[] = $state([]);
	isOpen: boolean = $state(false);
	searchQuery: string = $state('');

	/**
	 * Register a command. Replaces if the same ID already exists.
	 */
	register(command: Command): void {
		const idx = this.commands.findIndex(c => c.id === command.id);
		if (idx >= 0) {
			this.commands[idx] = command;
			this.commands = [...this.commands];
		} else {
			this.commands = [...this.commands, command];
		}
	}

	/**
	 * Register multiple commands at once.
	 */
	registerAll(cmds: Command[]): void {
		for (const cmd of cmds) this.register(cmd);
	}

	/**
	 * Unregister a command by ID.
	 */
	unregister(id: string): void {
		this.commands = this.commands.filter(c => c.id !== id);
	}

	/**
	 * Execute a command by ID. Returns true if found and executed.
	 */
	execute(id: string): boolean {
		const cmd = this.commands.find(c => c.id === id);
		if (!cmd) return false;
		if (cmd.available && !cmd.available()) return false;
		cmd.execute();
		this.close();
		return true;
	}

	/**
	 * Commands filtered by search query and availability, grouped by category.
	 */
	get filteredCommands(): Command[] {
		const query = this.searchQuery.toLowerCase().trim();
		return this.commands.filter(cmd => {
			if (cmd.available && !cmd.available()) return false;
			if (!query) return true;
			return (
				cmd.label.toLowerCase().includes(query) ||
				cmd.category.toLowerCase().includes(query) ||
				(cmd.shortcut?.toLowerCase().includes(query) ?? false) ||
				cmd.id.toLowerCase().includes(query)
			);
		});
	}

	/**
	 * Commands grouped by category.
	 */
	get groupedCommands(): Map<CommandCategory, Command[]> {
		const groups = new Map<CommandCategory, Command[]>();
		for (const cmd of this.filteredCommands) {
			if (!groups.has(cmd.category)) groups.set(cmd.category, []);
			groups.get(cmd.category)!.push(cmd);
		}
		return groups;
	}

	toggle(): void {
		if (this.isOpen) {
			this.close();
		} else {
			this.open();
		}
	}

	open(): void {
		this.isOpen = true;
		this.searchQuery = '';
	}

	close(): void {
		this.isOpen = false;
		this.searchQuery = '';
	}

	/**
	 * Full reset for testing.
	 */
	reset(): void {
		this.commands = [];
		this.isOpen = false;
		this.searchQuery = '';
	}
}

export const commandPalette = new CommandPalette();
