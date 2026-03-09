import { context } from './context.svelte';

export interface PaletteCommand {
  id: string;
  label: string;
  shortcut?: string;
  description?: string;
  category: string;
  action: () => void;
}

export interface Command {
  id: string;
  label: string;
  description?: string;
  shortcut?: string;
  action: () => void;
  group: string;
}

class CommandPaletteStore {
  isOpen = $state(false);
  query = $state('');
  commands = $state<PaletteCommand[]>([]);
  selectedIndex = $state(0);

  get filteredCommands(): PaletteCommand[] {
    if (!this.query) return this.commands;
    let q = this.query;
    // Prefix scoping: '>' shows only command items
    if (q.startsWith('>')) {
      const term = q.slice(1).trim().toLowerCase();
      if (!term) return this.commands;
      return this.commands.filter(
        c => c.label.toLowerCase().includes(term) || c.category.toLowerCase().includes(term)
      );
    }
    // Prefix scoping: '@' shows context source commands
    if (q.startsWith('@')) {
      const term = q.slice(1).trim().toLowerCase();
      const contextCommands: PaletteCommand[] = [
        { id: 'ctx-file', label: 'Add context: File', category: 'context', action: () => context.addChip('file') },
        { id: 'ctx-repo', label: 'Add context: Repository', category: 'context', action: () => context.addChip('repo') },
        { id: 'ctx-url', label: 'Add context: URL', category: 'context', action: () => context.addChip('url') },
        { id: 'ctx-template', label: 'Add context: Template', category: 'context', action: () => context.addChip('template') },
        { id: 'ctx-instruction', label: 'Add context: Instruction', category: 'context', action: () => context.addChip('instruction') },
      ];
      if (!term) return contextCommands;
      return contextCommands.filter(c => c.label.toLowerCase().includes(term));
    }
    // Prefix scoping: '#' shows history-related items
    if (q.startsWith('#')) {
      const term = q.slice(1).trim().toLowerCase();
      const historyCommands = this.commands.filter(c =>
        c.category.toLowerCase() === 'view' && c.label.toLowerCase().includes('history')
      );
      if (!term) return historyCommands.length > 0 ? historyCommands : this.commands;
      return this.commands.filter(
        c => (c.label.toLowerCase().includes(term) || c.label.toLowerCase().includes('history'))
      );
    }
    const lower = q.toLowerCase();
    return this.commands.filter(
      c => c.label.toLowerCase().includes(lower) || c.category.toLowerCase().includes(lower)
    );
  }

  open() {
    this.isOpen = true;
    this.query = '';
    this.selectedIndex = 0;
  }

  close() {
    this.isOpen = false;
    this.query = '';
    this.selectedIndex = 0;
  }

  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  }

  setQuery(q: string) {
    this.query = q;
    this.selectedIndex = 0;
  }

  moveUp() {
    if (this.selectedIndex > 0) {
      this.selectedIndex--;
    }
  }

  moveDown() {
    const max = this.filteredCommands.length - 1;
    if (this.selectedIndex < max) {
      this.selectedIndex++;
    }
  }

  executeSelected() {
    const cmds = this.filteredCommands;
    if (cmds.length > 0 && this.selectedIndex < cmds.length) {
      cmds[this.selectedIndex].action();
      this.close();
    }
  }

  registerCommands(cmds: PaletteCommand[]) {
    this.commands = cmds;
  }

  registerCommand(cmd: Command): void {
    if (!this.commands.find(c => c.id === cmd.id)) {
      this.commands.push({
        id: cmd.id,
        label: cmd.label,
        description: cmd.description,
        shortcut: cmd.shortcut,
        category: cmd.group,
        action: cmd.action,
      });
    }
  }
}

export const commandPalette = new CommandPaletteStore();
