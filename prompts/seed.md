## Project Context

{{project_description}}

## Workspace Profile

{{workspace_profile}}

## Codebase Context

{{codebase_context}}

## Your Role

You are generating prompts that a developer working on this project would bring to an AI assistant. These prompts will be optimized by a prompt engineering pipeline that adds structure, constraints, examples, and specificity.

Generate {{prompts_per_run}} prompts covering {{task_types}} work in the {{phase_context}} phase of this project.

Each prompt should:
- Represent a real task the developer needs to accomplish
- Be at the natural level of detail the developer would have
- Cover a different aspect of the project
- Be self-contained (no dependencies on other prompts)

Return a JSON array of prompt strings. Each string is a complete prompt.
