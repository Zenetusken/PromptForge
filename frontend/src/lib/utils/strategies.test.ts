import { describe, it, expect } from 'vitest';
import { strategyListToOptions } from './strategies';

describe('strategyListToOptions', () => {
  it('transforms strategy list and prepends auto', () => {
    const list = [
      { name: 'chain-of-thought', tagline: 'Step-by-step', description: '' },
      { name: 'few-shot', tagline: 'Examples', description: '' },
    ];
    const options = strategyListToOptions(list);
    expect(options[0]).toEqual({ value: '', label: 'auto' });
    expect(options).toHaveLength(3);
    expect(options[1].value).toBe('chain-of-thought');
    expect(options[2].value).toBe('few-shot');
  });

  it('handles empty list', () => {
    const options = strategyListToOptions([]);
    expect(options).toHaveLength(1);
    expect(options[0]).toEqual({ value: '', label: 'auto' });
  });
});
