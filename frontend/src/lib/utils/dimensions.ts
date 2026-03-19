/**
 * Shared dimension labels and phase mappings for the scoring system.
 */

/** Human-readable labels for the 5 quality dimensions. */
export const DIMENSION_LABELS: Record<string, string> = {
  clarity: 'Clarity',
  specificity: 'Specificity',
  structure: 'Structure',
  faithfulness: 'Faithfulness',
  conciseness: 'Conciseness',
};

/** Pipeline phase display labels. */
export const PHASE_LABELS: Record<string, string> = {
  analyzing: 'Analyzing',
  optimizing: 'Optimizing',
  scoring: 'Scoring',
  passthrough: 'Passthrough',
};

/** Get phase display label, or null if status isn't a known phase. */
export function getPhaseLabel(status: string): string | null {
  return PHASE_LABELS[status] ?? null;
}
