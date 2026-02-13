"""MCP (Model Context Protocol) server for PromptForge.

Exposes prompt optimization capabilities as MCP tools that can be used
by Claude and other MCP-compatible clients.
"""

import json
from dataclasses import asdict

from app.services.analyzer import PromptAnalyzer
from app.services.claude_client import ClaudeClient
from app.services.optimizer import PromptOptimizer
from app.services.pipeline import run_pipeline
from app.services.strategy_selector import StrategySelector
from app.services.validator import PromptValidator


# MCP tool definitions for the PromptForge server
MCP_TOOLS = [
    {
        "name": "optimize_prompt",
        "description": (
            "Optimize a given prompt using the PromptForge pipeline. "
            "Analyzes the prompt, selects a strategy, optimizes it, "
            "and validates the result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The raw prompt to optimize",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "analyze_prompt",
        "description": (
            "Analyze a prompt to identify its task type, complexity, "
            "strengths, and weaknesses without optimizing it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt to analyze",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "validate_prompt",
        "description": (
            "Compare an original prompt with an optimized version and "
            "score the optimization quality."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "original": {
                    "type": "string",
                    "description": "The original prompt",
                },
                "optimized": {
                    "type": "string",
                    "description": "The optimized prompt to validate",
                },
            },
            "required": ["original", "optimized"],
        },
    },
]


async def handle_tool_call(tool_name: str, arguments: dict) -> dict:
    """Handle an MCP tool call and return the result.

    Args:
        tool_name: The name of the tool to execute.
        arguments: The tool arguments as a dictionary.

    Returns:
        A dictionary containing the tool result.

    Raises:
        ValueError: If the tool name is not recognized.
    """
    client = ClaudeClient()

    if tool_name == "optimize_prompt":
        result = await run_pipeline(arguments["prompt"], client)
        return asdict(result)

    elif tool_name == "analyze_prompt":
        analyzer = PromptAnalyzer(client)
        result = await analyzer.analyze(arguments["prompt"])
        return asdict(result)

    elif tool_name == "validate_prompt":
        validator = PromptValidator(client)
        result = await validator.validate(
            arguments["original"], arguments["optimized"]
        )
        return asdict(result)

    else:
        raise ValueError(f"Unknown tool: {tool_name}")
