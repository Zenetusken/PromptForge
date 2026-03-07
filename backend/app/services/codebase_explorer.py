"""Stage 0: Codebase Explore

Agentic exploration of a linked GitHub repository.
Runs before the main pipeline when a repo is linked.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from typing import AsyncGenerator, Optional

from app.config import settings
from app.prompts.explore_prompt import get_explore_prompt
from app.providers.base import MODEL_ROUTING, LLMProvider, parse_json_robust
from app.services.codebase_tools import build_codebase_tools

logger = logging.getLogger(__name__)

# JSON Schema for the explore stage output.
# Passed to complete_agentic as output_schema so both providers use structured
# output (tool-as-output for AnthropicAPIProvider, output_format + submit_result
# MCP tool for ClaudeCLIProvider). No text parsing required when result.output
# is populated.
EXPLORE_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "tech_stack": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of technologies, frameworks, and languages used",
        },
        "key_files_read": {
            "type": "array",
            "items": {"type": "string"},
            "description": "File paths that were read during exploration",
        },
        "relevant_code_snippets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "lines": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["file", "context"],
            },
            "description": "Code snippets relevant to the user's prompt",
        },
        "codebase_observations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key observations about the codebase architecture and patterns",
        },
        "prompt_grounding_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notes on how the codebase relates to or corrects the user's prompt",
        },
    },
    "required": ["tech_stack", "key_files_read", "codebase_observations", "prompt_grounding_notes"],
}


@dataclass
class CodebaseContext:
    repo: str = ""
    branch: str = "main"
    tech_stack: list[str] = field(default_factory=list)
    key_files_read: list[str] = field(default_factory=list)
    relevant_snippets: list[dict] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    grounding_notes: list[str] = field(default_factory=list)
    files_read_count: int = 0
    duration_ms: int = 0


async def run_explore(
    provider: LLMProvider,
    raw_prompt: str,
    repo_full_name: str,
    repo_branch: str,
    session_id: Optional[str] = None,
    github_token: Optional[str] = None,
) -> AsyncGenerator[tuple[str, dict], None]:
    """Run Stage 0 codebase exploration.

    Token resolution order:
      1. ``github_token`` — passed directly (MCP path, no session needed)
      2. ``session_id``   — decrypt from DB (browser OAuth/PAT path)
    At least one must be provided; a ValueError is raised if neither is.

    Yields:
        ("tool_call", {...}) for each tool invocation in real time
        ("explore_result", CodebaseContext dict) when done
    """
    model = MODEL_ROUTING["explore"]
    system_prompt = get_explore_prompt(raw_prompt)

    # Resolve GitHub token and build tools up front; yield a fallback result if
    # setup fails so pipeline.py always receives an explore_result event.
    try:
        if github_token:
            token = github_token
        elif session_id:
            from app.services.github_client import _get_decrypted_token
            token = await _get_decrypted_token(session_id)
        else:
            raise ValueError(
                "run_explore requires either github_token or session_id to authenticate with GitHub"
            )
        tools = build_codebase_tools(
            token=token,
            repo_full_name=repo_full_name,
            repo_branch=repo_branch,
        )
    except Exception as e:
        logger.error(f"Stage 0 (Explore) setup error: {e}")
        context = CodebaseContext(repo=repo_full_name, branch=repo_branch)
        context.observations = [f"Exploration setup failed: {e}"]
        yield ("explore_result", asdict(context))
        return

    # Use asyncio.Queue to bridge the sync on_tool_call callback → async SSE stream.
    # This lets tool-call events reach the client in real time while the agent runs,
    # rather than buffering them all until completion.
    event_queue: asyncio.Queue = asyncio.Queue()

    def _on_tool_call(name: str, args: dict) -> None:
        """Sync callback; enqueues event for immediate SSE yield."""
        event_queue.put_nowait(("tool_call", {
            "tool": name,
            "input": args,
            "status": "running",
        }))

    # Run the agentic call as a background task so we can drain events while it runs.
    agent_task = asyncio.create_task(
        provider.complete_agentic(
            system=system_prompt,
            user=(
                f"Explore the repository {repo_full_name} (branch: {repo_branch}) "
                f"to build context for optimizing this prompt:\n\n{raw_prompt}"
            ),
            model=model,
            tools=tools,
            max_turns=25,
            on_tool_call=_on_tool_call,
            output_schema=EXPLORE_OUTPUT_SCHEMA,
        )
    )

    # Enforce timeout via call_later so the timeout also covers the drain loop.
    # Uses get_running_loop() — safe in async context (avoids Python 3.12 deprecation).
    timeout_secs = settings.EXPLORE_TIMEOUT_SECONDS
    timeout_handle = asyncio.get_running_loop().call_later(
        timeout_secs, lambda: agent_task.cancel() if not agent_task.done() else None
    )

    try:
        # Stream tool-call events in real time while the agent is running.
        while not agent_task.done():
            try:
                evt = event_queue.get_nowait()
                yield evt
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.05)  # 50ms poll — tight enough for real-time UX

        # Drain any events that arrived in the final moments before task completion.
        while not event_queue.empty():
            yield event_queue.get_nowait()

        # Re-raises CancelledError or any exception from the agent task.
        result = await agent_task

    except asyncio.CancelledError:
        logger.warning("Stage 0 (Explore) timed out after %ds", timeout_secs)
        while not event_queue.empty():
            yield event_queue.get_nowait()
        context = CodebaseContext(repo=repo_full_name, branch=repo_branch)
        context.observations = [
            f"Exploration timed out after {timeout_secs}s — partial context only"
        ]
        ctx_dict = asdict(context)
        ctx_dict["explore_failed"] = True
        ctx_dict["explore_error"] = f"Timed out after {timeout_secs}s"
        yield ("explore_result", ctx_dict)
        return

    except BaseException as e:
        # Catch BaseException (not just Exception) to handle anyio's BaseExceptionGroup
        # which is raised by TaskGroup failures in ClaudeCLIProvider.
        logger.error(f"Stage 0 (Explore) error: {type(e).__name__}: {e}")
        while not event_queue.empty():
            yield event_queue.get_nowait()
        context = CodebaseContext(repo=repo_full_name, branch=repo_branch)
        context.observations = [f"Exploration failed: {type(e).__name__}: {e}"]
        ctx_dict = asdict(context)
        ctx_dict["explore_failed"] = True
        ctx_dict["explore_error"] = f"{type(e).__name__}: {e}"
        yield ("explore_result", ctx_dict)
        return

    finally:
        timeout_handle.cancel()

    # Parse the agent's response into a CodebaseContext.
    context = CodebaseContext(repo=repo_full_name, branch=repo_branch)

    if result.output:
        # Structured output from submit_result tool or SDK output_format —
        # already a validated dict, no text parsing needed.
        parsed = result.output
        context.tech_stack = parsed.get("tech_stack", [])
        context.key_files_read = parsed.get("key_files_read", [])
        context.relevant_snippets = parsed.get("relevant_code_snippets", [])
        context.observations = parsed.get("codebase_observations", [])
        context.grounding_notes = parsed.get("prompt_grounding_notes", [])
        context.files_read_count = len(context.key_files_read)
    else:
        # Fallback: model produced free-form text instead of calling submit_result.
        # Use 3-strategy robust JSON parsing as a last resort.
        try:
            parsed = parse_json_robust(result.text)
            context.tech_stack = parsed.get("tech_stack", [])
            context.key_files_read = parsed.get("key_files_read", [])
            context.relevant_snippets = parsed.get("relevant_code_snippets", [])
            context.observations = parsed.get("codebase_observations", [])
            context.grounding_notes = parsed.get("prompt_grounding_notes", [])
            context.files_read_count = len(context.key_files_read)
        except (ValueError, TypeError):
            context.observations = [result.text[:500] if result.text else "No output from exploration"]

    yield ("explore_result", asdict(context))
