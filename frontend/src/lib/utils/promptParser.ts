/**
 * Prompt text parser — extracts variables and detects structural sections.
 * Pure functions, no dependencies.
 */

export interface VariableOccurrence {
	position: number;
	/** Full match length including braces and whitespace (e.g. `{{ name }}` = 10). */
	matchLength: number;
}

export interface ExtractedVariable {
	name: string;
	/** Character offsets in the original text where this variable appears. */
	positions: number[];
	/** Detailed occurrence data with match lengths for accurate selection. */
	occurrences: VariableOccurrence[];
}

export interface DetectedSection {
	label: string;
	lineNumber: number;
	type: SectionType;
}

export type SectionType = 'role' | 'context' | 'steps' | 'constraints' | 'examples' | 'output' | 'task' | 'other';

/** Regex patterns for variable extraction. Matches {{var}} and {var} patterns. */
const DOUBLE_BRACE_RE = /\{\{\s*(\w[\w\s.-]*?)\s*\}\}/g;
const SINGLE_BRACE_RE = /\{\s*(\w[\w\s.-]*?)\s*\}/g;

/**
 * Extract all template variables from prompt text.
 * Recognizes `{{variable_name}}` and `{variable_name}` patterns.
 * Skips `${var}` (JS template literals) and empty braces `{}`.
 * Returns unique variables with all occurrence positions and match lengths.
 */
export function extractVariables(text: string): ExtractedVariable[] {
	if (!text) return [];

	const variableMap = new Map<string, VariableOccurrence[]>();

	// Double-brace variables (higher priority)
	for (const match of text.matchAll(DOUBLE_BRACE_RE)) {
		const name = match[1].trim();
		if (!name) continue;
		const occs = variableMap.get(name) ?? [];
		occs.push({ position: match.index!, matchLength: match[0].length });
		variableMap.set(name, occs);
	}

	// Single-brace variables (only if not already captured by double-brace)
	for (const match of text.matchAll(SINGLE_BRACE_RE)) {
		const name = match[1].trim();
		if (!name) continue;
		const idx = match.index!;
		// Skip if inside a double brace (already captured)
		if (idx > 0 && text[idx - 1] === '{') continue;
		if (idx + match[0].length < text.length && text[idx + match[0].length] === '}') continue;
		// Skip JS template literals: ${var}
		if (idx > 0 && text[idx - 1] === '$') continue;

		const occs = variableMap.get(name) ?? [];
		occs.push({ position: idx, matchLength: match[0].length });
		variableMap.set(name, occs);
	}

	return Array.from(variableMap.entries()).map(([name, occs]) => ({
		name,
		positions: occs.map((o) => o.position),
		occurrences: occs,
	}));
}

/** Section header patterns mapped to section types. */
const SECTION_PATTERNS: [RegExp, SectionType][] = [
	[/^#{1,3}\s*role\b/i, 'role'],
	[/^role\s*:/i, 'role'],
	[/^you\s+are\b/i, 'role'],
	[/^act\s+as\b/i, 'role'],
	[/^#{1,3}\s*context\b/i, 'context'],
	[/^context\s*:/i, 'context'],
	[/^background\s*:/i, 'context'],
	[/^#{1,3}\s*(?:steps|instructions|procedure)\b/i, 'steps'],
	[/^steps\s*:/i, 'steps'],
	[/^instructions\s*:/i, 'steps'],
	[/^#{1,3}\s*(?:constraints?|rules?|requirements?)\b/i, 'constraints'],
	[/^constraints?\s*:/i, 'constraints'],
	[/^rules?\s*:/i, 'constraints'],
	[/^do\s+not\b/i, 'constraints'],
	[/^#{1,3}\s*(?:examples?|sample)\b/i, 'examples'],
	[/^examples?\s*:/i, 'examples'],
	[/^#{1,3}\s*(?:output|response|format)\b/i, 'output'],
	[/^output\s*(?:format)?\s*:/i, 'output'],
	[/^response\s*(?:format)?\s*:/i, 'output'],
	[/^#{1,3}\s*(?:task|objective|goal)\b/i, 'task'],
	[/^task\s*:/i, 'task'],
	[/^objective\s*:/i, 'task'],
];

/**
 * Detect structural sections in prompt text.
 * Returns detected sections with their line numbers and types.
 * Lines immediately following a heading/colon section (before the next blank line)
 * are treated as body text and not matched as new sections.
 */
export function detectSections(text: string): DetectedSection[] {
	if (!text) return [];

	const lines = text.split('\n');
	const sections: DetectedSection[] = [];
	let inSectionBody = false;

	for (let i = 0; i < lines.length; i++) {
		const line = lines[i].trim();

		// Blank lines reset "in body" state — next non-blank line can start a new section
		if (!line) {
			inSectionBody = false;
			continue;
		}

		// If we're in a section body, skip implicit pattern matches (like "You are...")
		// but still detect explicit heading/colon patterns that start new sections
		const isExplicitHeader = /^#{1,3}\s/.test(line) || /^\w[\w\s]*:\s*/.test(line);

		if (inSectionBody && !isExplicitHeader) continue;

		for (const [pattern, type] of SECTION_PATTERNS) {
			if (pattern.test(line)) {
				sections.push({
					label: line.replace(/^#{1,3}\s*/, '').replace(/:\s*$/, ''),
					lineNumber: i + 1,
					type,
				});
				inSectionBody = true;
				break; // Only match the first pattern per line
			}
		}
	}

	return sections;
}

/** Color for each section type, matching the neon palette. */
export const SECTION_COLORS: Record<SectionType, string> = {
	role: 'neon-purple',
	context: 'neon-cyan',
	steps: 'neon-green',
	constraints: 'neon-red',
	examples: 'neon-yellow',
	output: 'neon-blue',
	task: 'neon-orange',
	other: 'text-dim',
};
