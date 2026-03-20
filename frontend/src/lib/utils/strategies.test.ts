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

  it('filters out auto strategy from input list', () => {
    const list = [
      { name: 'auto', tagline: 'Automatic', description: '' },
      { name: 'chain-of-thought', tagline: 'Step-by-step', description: '' },
    ];
    const options = strategyListToOptions(list);
    // auto is prepended as { value: '', label: 'auto' }, not duplicated
    expect(options).toHaveLength(2);
    expect(options[0]).toEqual({ value: '', label: 'auto' });
    expect(options[1].value).toBe('chain-of-thought');
  });

  it('uses name only as label when tagline is empty', () => {
    const list = [
      { name: 'few-shot', tagline: '', description: '' },
    ];
    const options = strategyListToOptions(list);
    expect(options[1].label).toBe('few-shot');
  });

  it('uses name only as label when tagline is null', () => {
    const list = [
      { name: 'few-shot', tagline: null as any, description: '' },
    ];
    const options = strategyListToOptions(list);
    expect(options[1].label).toBe('few-shot');
  });

  it('formats label with tagline when present', () => {
    const list = [
      { name: 'chain-of-thought', tagline: 'Step-by-step', description: '' },
    ];
    const options = strategyListToOptions(list);
    expect(options[1].label).toBe('chain-of-thought \u2014 Step-by-step');
  });
});
