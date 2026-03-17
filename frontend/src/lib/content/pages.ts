import type { ContentPage } from './types';

const pipeline: ContentPage = {
  slug: 'pipeline',
  title: 'Three Phases. One Pipeline. Zero Guesswork.',
  description: 'Analyze, optimize, and score prompts through independent LLM subagents.',
  sections: [
    {
      type: 'hero',
      heading: 'THREE PHASES. ONE PIPELINE. ZERO GUESSWORK.',
      subheading:
        'Each optimization runs through three independent LLM subagents — analyzer, optimizer, scorer — each with its own context window, rubric, and output contract.',
      cta: { label: 'Open the App', href: '/' },
    },
  ],
};

const allPages: Record<string, ContentPage> = { pipeline };

export function getPage(slug: string): ContentPage | undefined {
  return allPages[slug];
}

export function getAllSlugs(): string[] {
  return Object.keys(allPages);
}
