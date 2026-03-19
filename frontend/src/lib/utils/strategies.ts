/**
 * Shared strategy list transformation for dropdown rendering.
 */

import type { StrategyInfo } from '$lib/api/client';

export interface StrategyOption {
  value: string;
  label: string;
}

/**
 * Transform a strategy list from the API into dropdown options.
 * Filters out the 'auto' entry and prepends it as the default '' value.
 */
export function strategyListToOptions(list: StrategyInfo[]): StrategyOption[] {
  const rest = list.filter((s) => s.name !== 'auto');
  return [
    { value: '', label: 'auto' },
    ...rest.map((s) => ({
      value: s.name,
      label: s.tagline ? `${s.name} — ${s.tagline}` : s.name,
    })),
  ];
}
