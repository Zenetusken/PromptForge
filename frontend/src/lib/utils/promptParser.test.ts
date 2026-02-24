import { describe, it, expect } from 'vitest';
import { extractVariables, detectSections } from './promptParser';

describe('extractVariables', () => {
	it('returns empty for empty text', () => {
		expect(extractVariables('')).toEqual([]);
	});

	it('extracts double-brace variables', () => {
		const result = extractVariables('Hello {{name}}, welcome to {{place}}!');
		expect(result).toHaveLength(2);
		expect(result.map((v) => v.name)).toContain('name');
		expect(result.map((v) => v.name)).toContain('place');
	});

	it('extracts single-brace variables', () => {
		const result = extractVariables('The {topic} is about {subject}.');
		expect(result).toHaveLength(2);
		expect(result.map((v) => v.name)).toContain('topic');
		expect(result.map((v) => v.name)).toContain('subject');
	});

	it('deduplicates repeated variables', () => {
		const result = extractVariables('{{name}} and {{name}} again');
		expect(result).toHaveLength(1);
		expect(result[0].name).toBe('name');
		expect(result[0].positions).toHaveLength(2);
	});

	it('handles variables with dots and dashes', () => {
		const result = extractVariables('Use {{user.name}} and {{api-key}}');
		expect(result).toHaveLength(2);
		expect(result.map((v) => v.name)).toContain('user.name');
		expect(result.map((v) => v.name)).toContain('api-key');
	});

	it('trims whitespace in variable names', () => {
		const result = extractVariables('{{ name }}');
		expect(result).toHaveLength(1);
		expect(result[0].name).toBe('name');
	});

	it('returns positions for each occurrence', () => {
		const text = '{{x}} then {{x}}';
		const result = extractVariables(text);
		expect(result).toHaveLength(1);
		expect(result[0].positions).toHaveLength(2);
		expect(result[0].positions[0]).toBe(0);
	});

	// --- Edge cases for robust business logic ---

	it('skips JS template literals ${var}', () => {
		const result = extractVariables('Use ${name} and ${count} in template');
		expect(result).toHaveLength(0);
	});

	it('extracts {var} but skips ${var} in same text', () => {
		const result = extractVariables('{real_var} and ${template_var}');
		expect(result).toHaveLength(1);
		expect(result[0].name).toBe('real_var');
	});

	it('skips empty braces {}', () => {
		const result = extractVariables('An object {} and empty {{}}');
		expect(result).toHaveLength(0);
	});

	it('tracks correct matchLength for double-brace variables', () => {
		const result = extractVariables('{{name}}');
		expect(result).toHaveLength(1);
		expect(result[0].occurrences).toHaveLength(1);
		expect(result[0].occurrences[0].position).toBe(0);
		expect(result[0].occurrences[0].matchLength).toBe(8); // "{{name}}" = 8 chars
	});

	it('tracks correct matchLength for single-brace variables', () => {
		const result = extractVariables('{name}');
		expect(result).toHaveLength(1);
		expect(result[0].occurrences).toHaveLength(1);
		expect(result[0].occurrences[0].position).toBe(0);
		expect(result[0].occurrences[0].matchLength).toBe(6); // "{name}" = 6 chars
	});

	it('tracks correct matchLength for whitespace-padded variables', () => {
		const result = extractVariables('{{ name }}');
		expect(result).toHaveLength(1);
		expect(result[0].occurrences[0].matchLength).toBe(10); // "{{ name }}" = 10 chars
	});

	it('handles mixed single and double braces in same text', () => {
		const text = '{{system_prompt}} with {user_input} and {{system_prompt}}';
		const result = extractVariables(text);
		expect(result).toHaveLength(2);

		const sys = result.find((v) => v.name === 'system_prompt')!;
		expect(sys.occurrences).toHaveLength(2);
		expect(sys.occurrences[0].matchLength).toBe(17); // "{{system_prompt}}"

		const usr = result.find((v) => v.name === 'user_input')!;
		expect(usr.occurrences).toHaveLength(1);
		expect(usr.occurrences[0].matchLength).toBe(12); // "{user_input}"
	});

	it('occurrence positions allow accurate text selection', () => {
		const text = 'Hello {{ name }}, your role is {role}.';
		const result = extractVariables(text);

		const nameVar = result.find((v) => v.name === 'name')!;
		const occ = nameVar.occurrences[0];
		const extracted = text.slice(occ.position, occ.position + occ.matchLength);
		expect(extracted).toBe('{{ name }}');

		const roleVar = result.find((v) => v.name === 'role')!;
		const roleOcc = roleVar.occurrences[0];
		const roleExtracted = text.slice(roleOcc.position, roleOcc.position + roleOcc.matchLength);
		expect(roleExtracted).toBe('{role}');
	});

	it('returns empty for null/undefined input', () => {
		expect(extractVariables(null as any)).toEqual([]);
		expect(extractVariables(undefined as any)).toEqual([]);
	});
});

describe('detectSections', () => {
	it('returns empty for empty text', () => {
		expect(detectSections('')).toEqual([]);
	});

	it('detects markdown heading sections', () => {
		const text = '# Role\nYou are an expert.\n\n## Context\nBackground info.\n\n## Steps\n1. Do this.';
		const sections = detectSections(text);
		expect(sections).toHaveLength(3);
		expect(sections[0].type).toBe('role');
		expect(sections[0].lineNumber).toBe(1);
		expect(sections[1].type).toBe('context');
		expect(sections[2].type).toBe('steps');
	});

	it('detects colon-delimited sections', () => {
		const text = 'Role: You are a teacher\nContext: Teaching math\nSteps:\n1. Explain\n2. Test';
		const sections = detectSections(text);
		expect(sections.length).toBeGreaterThanOrEqual(3);
		expect(sections[0].type).toBe('role');
		expect(sections[1].type).toBe('context');
		expect(sections[2].type).toBe('steps');
	});

	it('detects "You are" as role section', () => {
		const text = 'You are an expert data analyst.\nAnalyze the following data.';
		const sections = detectSections(text);
		expect(sections).toHaveLength(1);
		expect(sections[0].type).toBe('role');
	});

	it('detects constraint sections', () => {
		const text = '# Constraints\n- No swearing\n- Keep it professional\n\nDo not include personal opinions.';
		const sections = detectSections(text);
		expect(sections.some((s) => s.type === 'constraints')).toBe(true);
	});

	it('detects output format sections', () => {
		const text = 'Output Format:\nReturn as JSON with the following schema:\n```json\n{}\n```';
		const sections = detectSections(text);
		expect(sections.some((s) => s.type === 'output')).toBe(true);
	});

	it('detects example sections', () => {
		const text = '## Examples\nInput: hello\nOutput: HELLO';
		const sections = detectSections(text);
		expect(sections.some((s) => s.type === 'examples')).toBe(true);
	});

	it('handles mixed section styles', () => {
		const text = '# Role\nExpert coder\n\nTask: Build an API\n\nConstraints:\n- Use REST\n\n## Output\nJSON response';
		const sections = detectSections(text);
		expect(sections.length).toBeGreaterThanOrEqual(3);
	});

	// --- Edge cases for robust section detection ---

	it('does not false-positive body text after a section header', () => {
		const text = '# Role\nYou are a helpful assistant.\nAct as an expert.';
		const sections = detectSections(text);
		// "Act as an expert" would match 'role' pattern but is body text after "# Role"
		expect(sections).toHaveLength(1);
		expect(sections[0].type).toBe('role');
		expect(sections[0].lineNumber).toBe(1);
	});

	it('detects new section after a blank line resets body state', () => {
		const text = '# Role\nYou are a coder.\n\nYou are also a reviewer.';
		const sections = detectSections(text);
		// Blank line resets body state, "You are also..." should match as role
		expect(sections).toHaveLength(2);
		expect(sections[0].lineNumber).toBe(1);
		expect(sections[1].lineNumber).toBe(4);
	});

	it('detects "Do not" as constraint section', () => {
		const text = 'Do not include personal opinions or biases.';
		const sections = detectSections(text);
		expect(sections).toHaveLength(1);
		expect(sections[0].type).toBe('constraints');
	});

	it('detects task/objective sections', () => {
		const text = '# Task\nBuild a REST API\n\nObjective: Create endpoints';
		const sections = detectSections(text);
		expect(sections.filter((s) => s.type === 'task')).toHaveLength(2);
	});

	it('strips heading markers and colons from labels', () => {
		const text = '## Context:\nSome background.';
		const sections = detectSections(text);
		expect(sections).toHaveLength(1);
		expect(sections[0].label).toBe('Context');
	});

	it('returns empty for plain text with no structure', () => {
		const text = 'Just a simple sentence with no headings or labels.';
		expect(detectSections(text)).toEqual([]);
	});

	it('returns empty for null/undefined input', () => {
		expect(detectSections(null as any)).toEqual([]);
		expect(detectSections(undefined as any)).toEqual([]);
	});

	it('explicit header inside body overrides body state', () => {
		const text = 'Role: Expert coder\nYou are great.\n## Steps\n1. Plan\n2. Code';
		const sections = detectSections(text);
		// "Role:" starts body, "You are great" is body, "## Steps" is explicit header
		expect(sections).toHaveLength(2);
		expect(sections[0].type).toBe('role');
		expect(sections[1].type).toBe('steps');
	});
});
