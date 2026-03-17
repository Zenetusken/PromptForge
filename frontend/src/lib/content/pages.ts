import type { ContentPage } from './types';
import { changelog } from './pages/changelog';
import { privacy } from './pages/privacy';
import { terms } from './pages/terms';
import { security } from './pages/security';

const allPages: Record<string, ContentPage> = {
  changelog,
  privacy,
  terms,
  security,
};

export function getPage(slug: string): ContentPage | undefined {
  return allPages[slug];
}

export function getAllSlugs(): string[] {
  return Object.keys(allPages);
}
