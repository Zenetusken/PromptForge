# Prompt Templates

All prompts for the optimization pipeline are stored as Markdown files in this directory.
Templates use `{{variable}}` syntax for dynamic substitution and XML tags for structured sections.

## Template Syntax

- `{{variable_name}}` — replaced at runtime by prompt_loader.py
- Variables with no value are omitted entirely, including surrounding XML tags
- Data goes at the TOP of the template, instructions at the BOTTOM

## Editing Templates

Templates are hot-reloaded — edit any file and the next optimization uses the updated version.
No app restart needed.

## Variable Reference

See `manifest.json` for required and optional variables per template.
See the spec for the full variable reference table.

## Strategy Files

Strategy templates in `strategies/` are static content (no variables).
Their full text is loaded by strategy_loader.py and injected as `{{strategy_instructions}}`.
