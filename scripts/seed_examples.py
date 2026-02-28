#!/usr/bin/env python3
"""Seed the database with example optimization records for development and testing."""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add the backend directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import async_session_factory, init_db
from app import config
from apps.promptforge.models.optimization import Optimization


EXAMPLE_OPTIMIZATIONS = [
    {
        "raw_prompt": "Write me a Python function that sorts a list.",
        "optimized_prompt": (
            "You are a senior Python developer with expertise in algorithms and "
            "data structures.\n\n"
            "Write a Python function that sorts a list of elements. Please include:\n"
            "1. Type hints for parameters and return value\n"
            "2. A docstring explaining the algorithm, time complexity, and space complexity\n"
            "3. Handle edge cases (empty list, single element, already sorted)\n"
            "4. Use an efficient sorting algorithm (e.g., merge sort or quicksort)\n\n"
            "Return the function with example usage demonstrating different input cases."
        ),
        "task_type": "coding",
        "complexity": "medium",
        "weaknesses": json.dumps(["No language version specified", "No complexity requirements"]),
        "strengths": json.dumps(["Clear task", "Specific language"]),
        "changes_made": json.dumps([
            "Added role definition",
            "Specified type hints requirement",
            "Added docstring requirement",
            "Listed edge cases to handle",
            "Specified algorithm preference",
        ]),
        "framework_applied": "role-task-format",
        "optimization_notes": "Enhanced with structured requirements and role-task-format context.",
        "clarity_score": 0.92,
        "specificity_score": 0.88,
        "structure_score": 0.95,
        "faithfulness_score": 0.97,
        "overall_score": 0.93,
        "is_improvement": True,
        "verdict": "Excellent optimization with clear structure and specific requirements.",
        "duration_ms": 2150,
        "model_used": config.CLAUDE_MODEL,
        "status": "completed",
        "project": "python-tutorials",
        "tags": json.dumps(["coding", "python", "algorithms"]),
        "title": "Python Sorting Function",
    },
    {
        "raw_prompt": "Explain machine learning to me.",
        "optimized_prompt": (
            "You are a university professor specializing in machine learning and "
            "artificial intelligence, known for making complex topics accessible.\n\n"
            "Explain machine learning to someone with a basic understanding of "
            "programming but no prior ML experience. Your explanation should:\n\n"
            "1. **Definition**: Start with a clear, concise definition\n"
            "2. **Analogy**: Use a real-world analogy to illustrate the concept\n"
            "3. **Types**: Briefly describe the three main types (supervised, "
            "unsupervised, reinforcement learning) with one example each\n"
            "4. **Process**: Outline the typical ML workflow in 4-5 steps\n"
            "5. **Applications**: Give 3 practical, everyday examples\n\n"
            "Keep the explanation under 500 words. Avoid jargon or define it "
            "when first used."
        ),
        "task_type": "education",
        "complexity": "low",
        "weaknesses": json.dumps(["Too broad", "No target audience", "No depth specified"]),
        "strengths": json.dumps(["Clear topic"]),
        "changes_made": json.dumps([
            "Added expert role",
            "Specified target audience",
            "Defined output structure",
            "Added word limit",
            "Included jargon guideline",
        ]),
        "framework_applied": "persona-assignment",
        "optimization_notes": "Applied persona-assignment framework with structured output sections.",
        "clarity_score": 0.90,
        "specificity_score": 0.85,
        "structure_score": 0.93,
        "faithfulness_score": 0.92,
        "overall_score": 0.90,
        "is_improvement": True,
        "verdict": "Strong improvement with clear structure and defined audience.",
        "duration_ms": 1890,
        "model_used": config.CLAUDE_MODEL,
        "status": "completed",
        "project": "education",
        "tags": json.dumps(["education", "machine-learning", "explanation"]),
        "title": "ML Explanation for Beginners",
    },
    {
        "raw_prompt": "Review this code and find bugs.",
        "optimized_prompt": (
            "You are a senior software engineer conducting a thorough code review.\n\n"
            "Review the provided code and identify any bugs, issues, or improvements. "
            "For each finding, provide:\n\n"
            "1. **Location**: File name and line number (if applicable)\n"
            "2. **Severity**: Critical / High / Medium / Low\n"
            "3. **Category**: Bug / Security / Performance / Style / Logic Error\n"
            "4. **Description**: What the issue is and why it matters\n"
            "5. **Fix**: Suggested code change or approach to resolve it\n\n"
            "After listing all findings, provide a summary with:\n"
            "- Total issues found by severity\n"
            "- Overall code quality assessment (1-10)\n"
            "- Top 3 priority items to address first\n\n"
            "If no code is provided in the next message, ask for it."
        ),
        "task_type": "coding",
        "complexity": "high",
        "weaknesses": json.dumps([
            "No code provided",
            "No review criteria",
            "No output format",
        ]),
        "strengths": json.dumps(["Clear intent"]),
        "changes_made": json.dumps([
            "Added reviewer role",
            "Defined finding format",
            "Added severity levels",
            "Included summary section",
            "Added fallback for missing code",
        ]),
        "framework_applied": "structured-output",
        "optimization_notes": "Structured the review process with clear categorization.",
        "clarity_score": 0.88,
        "specificity_score": 0.92,
        "structure_score": 0.95,
        "faithfulness_score": 0.90,
        "overall_score": 0.91,
        "is_improvement": True,
        "verdict": "Well-structured code review prompt with clear output expectations.",
        "duration_ms": 2340,
        "model_used": config.CLAUDE_MODEL,
        "status": "completed",
        "project": "dev-tools",
        "tags": json.dumps(["coding", "code-review", "debugging"]),
        "title": "Code Review Template",
    },
]


async def seed():
    """Insert example optimizations into the database."""
    await init_db()

    async with async_session_factory() as session:
        for i, example in enumerate(EXAMPLE_OPTIMIZATIONS):
            # Stagger creation times
            created_at = datetime.now(timezone.utc) - timedelta(hours=len(EXAMPLE_OPTIMIZATIONS) - i)
            optimization = Optimization(
                id=str(uuid.uuid4()),
                created_at=created_at,
                **example,
            )
            session.add(optimization)

        await session.commit()
        print(f"Seeded {len(EXAMPLE_OPTIMIZATIONS)} example optimizations.")


if __name__ == "__main__":
    asyncio.run(seed())
