import { getPreferences, patchPreferences } from '$lib/api/client';

export interface ModelPrefs {
  analyzer: string;
  optimizer: string;
  scorer: string;
}

export interface PipelinePrefs {
  enable_explore: boolean;
  enable_scoring: boolean;
  enable_adaptation: boolean;
  force_sampling: boolean;
}

export interface Preferences {
  schema_version: number;
  models: ModelPrefs;
  pipeline: PipelinePrefs;
  defaults: { strategy: string };
}

const DEFAULTS: Preferences = {
  schema_version: 1,
  models: { analyzer: 'sonnet', optimizer: 'opus', scorer: 'sonnet' },
  pipeline: { enable_explore: true, enable_scoring: true, enable_adaptation: true, force_sampling: false },
  defaults: { strategy: 'auto' },
};

class PreferencesStore {
  prefs = $state<Preferences>(structuredClone(DEFAULTS));
  loading = $state(false);
  error = $state<string | null>(null);

  get models(): ModelPrefs { return this.prefs.models; }
  get pipeline(): PipelinePrefs { return this.prefs.pipeline; }
  get defaultStrategy(): string { return this.prefs.defaults.strategy; }

  get isLeanMode(): boolean {
    return !this.prefs.pipeline.enable_explore && !this.prefs.pipeline.enable_scoring;
  }

  async init(): Promise<void> {
    this.loading = true;
    this.error = null;
    try {
      const data = await getPreferences();
      this.prefs = data as Preferences;
    } catch {
      // Backend offline — use defaults
    } finally {
      this.loading = false;
    }
  }

  async update(patch: Record<string, any>): Promise<void> {
    this.error = null;
    try {
      const updated = await patchPreferences(patch);
      this.prefs = updated as Preferences;
    } catch (err: any) {
      this.error = err.message || 'Failed to save';
    }
  }

  async setModel(phase: string, model: string): Promise<void> {
    await this.update({ models: { [phase]: model } });
  }

  async setPipelineToggle(key: string, value: boolean): Promise<void> {
    await this.update({ pipeline: { [key]: value } });
  }

  async setDefaultStrategy(strategy: string): Promise<void> {
    await this.update({ defaults: { strategy } });
  }
}

export const preferencesStore = new PreferencesStore();
