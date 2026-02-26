import { describe, it, expect, beforeEach, vi } from 'vitest';
import { commandPalette, type Command } from './commandPalette.svelte';

function makeCmd(overrides: Partial<Command> = {}): Command {
	return {
		id: overrides.id ?? 'test-cmd',
		label: overrides.label ?? 'Test Command',
		category: overrides.category ?? 'forge',
		execute: overrides.execute ?? vi.fn(),
		...overrides,
	};
}

describe('CommandPalette', () => {
	beforeEach(() => {
		commandPalette.reset();
	});

	describe('register', () => {
		it('adds a command to the registry', () => {
			commandPalette.register(makeCmd({ id: 'cmd-1' }));
			expect(commandPalette.commands).toHaveLength(1);
			expect(commandPalette.commands[0].id).toBe('cmd-1');
		});

		it('replaces an existing command with the same ID', () => {
			commandPalette.register(makeCmd({ id: 'cmd-1', label: 'V1' }));
			commandPalette.register(makeCmd({ id: 'cmd-1', label: 'V2' }));
			expect(commandPalette.commands).toHaveLength(1);
			expect(commandPalette.commands[0].label).toBe('V2');
		});
	});

	describe('registerAll', () => {
		it('registers multiple commands', () => {
			commandPalette.registerAll([
				makeCmd({ id: 'a' }),
				makeCmd({ id: 'b' }),
				makeCmd({ id: 'c' }),
			]);
			expect(commandPalette.commands).toHaveLength(3);
		});
	});

	describe('unregister', () => {
		it('removes a command by ID', () => {
			commandPalette.register(makeCmd({ id: 'cmd-1' }));
			commandPalette.unregister('cmd-1');
			expect(commandPalette.commands).toHaveLength(0);
		});

		it('no-ops for unknown ID', () => {
			commandPalette.register(makeCmd({ id: 'cmd-1' }));
			commandPalette.unregister('nonexistent');
			expect(commandPalette.commands).toHaveLength(1);
		});
	});

	describe('execute', () => {
		it('calls the command execute function', () => {
			const exec = vi.fn();
			commandPalette.register(makeCmd({ id: 'cmd-1', execute: exec }));
			const result = commandPalette.execute('cmd-1');
			expect(result).toBe(true);
			expect(exec).toHaveBeenCalledOnce();
		});

		it('returns false for unknown command', () => {
			expect(commandPalette.execute('nonexistent')).toBe(false);
		});

		it('returns false if command is unavailable', () => {
			const exec = vi.fn();
			commandPalette.register(makeCmd({
				id: 'cmd-1',
				execute: exec,
				available: () => false,
			}));
			expect(commandPalette.execute('cmd-1')).toBe(false);
			expect(exec).not.toHaveBeenCalled();
		});

		it('closes the palette after execution', () => {
			commandPalette.register(makeCmd({ id: 'cmd-1' }));
			commandPalette.open();
			commandPalette.execute('cmd-1');
			expect(commandPalette.isOpen).toBe(false);
		});
	});

	describe('filteredCommands', () => {
		beforeEach(() => {
			commandPalette.registerAll([
				makeCmd({ id: 'forge-new', label: 'New Forge', category: 'forge' }),
				makeCmd({ id: 'win-close', label: 'Close Window', category: 'window', shortcut: 'Ctrl+W' }),
				makeCmd({ id: 'nav-home', label: 'Go Home', category: 'navigation' }),
				makeCmd({ id: 'hidden', label: 'Hidden', category: 'settings', available: () => false }),
			]);
		});

		it('returns all available commands when no query', () => {
			expect(commandPalette.filteredCommands).toHaveLength(3); // hidden excluded
		});

		it('filters by label', () => {
			commandPalette.searchQuery = 'forge';
			expect(commandPalette.filteredCommands).toHaveLength(1);
			expect(commandPalette.filteredCommands[0].id).toBe('forge-new');
		});

		it('filters by category', () => {
			commandPalette.searchQuery = 'window';
			expect(commandPalette.filteredCommands).toHaveLength(1);
			expect(commandPalette.filteredCommands[0].id).toBe('win-close');
		});

		it('filters by shortcut', () => {
			commandPalette.searchQuery = 'ctrl+w';
			expect(commandPalette.filteredCommands).toHaveLength(1);
		});

		it('is case-insensitive', () => {
			commandPalette.searchQuery = 'NEW FORGE';
			expect(commandPalette.filteredCommands).toHaveLength(1);
		});

		it('excludes unavailable commands', () => {
			commandPalette.searchQuery = 'hidden';
			expect(commandPalette.filteredCommands).toHaveLength(0);
		});
	});

	describe('groupedCommands', () => {
		it('groups by category', () => {
			commandPalette.registerAll([
				makeCmd({ id: 'a', category: 'forge' }),
				makeCmd({ id: 'b', category: 'forge' }),
				makeCmd({ id: 'c', category: 'window' }),
			]);

			const groups = commandPalette.groupedCommands;
			expect(groups.get('forge')).toHaveLength(2);
			expect(groups.get('window')).toHaveLength(1);
			expect(groups.has('navigation')).toBe(false);
		});
	});

	describe('open/close/toggle', () => {
		it('open sets isOpen and clears query', () => {
			commandPalette.searchQuery = 'stale';
			commandPalette.open();
			expect(commandPalette.isOpen).toBe(true);
			expect(commandPalette.searchQuery).toBe('');
		});

		it('close sets isOpen false and clears query', () => {
			commandPalette.open();
			commandPalette.searchQuery = 'test';
			commandPalette.close();
			expect(commandPalette.isOpen).toBe(false);
			expect(commandPalette.searchQuery).toBe('');
		});

		it('toggle flips state', () => {
			commandPalette.toggle();
			expect(commandPalette.isOpen).toBe(true);
			commandPalette.toggle();
			expect(commandPalette.isOpen).toBe(false);
		});
	});
});
