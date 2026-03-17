export interface HeroSection {
  type: 'hero';
  heading: string;
  subheading: string;
  cta?: { label: string; href: string };
}

export interface ProseSection {
  type: 'prose';
  blocks: Array<{ heading?: string; content: string }>;
}

export interface CardGridSection {
  type: 'card-grid';
  columns: 2 | 3 | 5;
  cards: Array<{
    icon?: string;
    color: string;
    title: string;
    description: string;
  }>;
}

export interface TimelineSection {
  type: 'timeline';
  versions: Array<{
    version: string;
    date: string;
    categories: Array<{
      label: 'ADDED' | 'CHANGED' | 'FIXED' | 'REMOVED';
      color: string;
      items: string[];
    }>;
  }>;
}

export interface StepFlowSection {
  type: 'step-flow';
  steps: Array<{ title: string; description: string }>;
}

export interface CodeBlockSection {
  type: 'code-block';
  language: string;
  code: string;
  filename?: string;
}

export interface MetricBarSection {
  type: 'metric-bar';
  dimensions: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

export type Section =
  | HeroSection
  | ProseSection
  | CardGridSection
  | TimelineSection
  | StepFlowSection
  | CodeBlockSection
  | MetricBarSection;

export interface ContentPage {
  slug: string;
  title: string;
  description: string;
  sections: Section[];
}
