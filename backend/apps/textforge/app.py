"""TextForge app — lifecycle hooks and kernel integration."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from kernel.registry.hooks import AppBase

if TYPE_CHECKING:
    from kernel.bus.contracts import EventContract
    from kernel.core import Kernel
    from kernel.services.job_queue import Job

logger = logging.getLogger(__name__)

# Optimization score threshold below which auto-simplify triggers
AUTO_SIMPLIFY_THRESHOLD = 7.0


class TextForgeApp(AppBase):
    """Text transformation app that exercises kernel services."""

    _kernel: Kernel | None = None

    @property
    def app_id(self) -> str:
        return "textforge"

    async def on_startup(self, kernel: Kernel | None) -> None:
        self._kernel = kernel
        if kernel and hasattr(kernel, "services"):
            missing = kernel.services.validate_requirements(["llm", "storage"])
            if missing:
                logger.warning("TextForge: missing services %s", missing)
            else:
                logger.info("TextForge: all required services available")
        logger.info("TextForge app started")

    async def on_shutdown(self, kernel: Kernel | None) -> None:
        self._kernel = None
        logger.info("TextForge app stopped")

    def get_event_contracts(self) -> list[EventContract]:
        from apps.textforge.events import TEXTFORGE_CONTRACTS
        return list(TEXTFORGE_CONTRACTS)

    def get_event_handlers(self) -> dict[str, Callable]:
        async def on_optimization_completed(data: dict, source_app: str) -> None:
            optimization_id = data.get("optimization_id")
            overall_score = data.get("overall_score")
            logger.info(
                "TextForge received optimization.completed from %s: id=%s score=%s",
                source_app, optimization_id, overall_score,
            )

            # Auto-simplify low-scoring optimizations via the job queue
            if overall_score is not None and float(overall_score) < AUTO_SIMPLIFY_THRESHOLD:
                await self._submit_auto_simplify(optimization_id, overall_score)

        return {
            "promptforge:optimization.completed": on_optimization_completed,
        }

    def get_job_handlers(self) -> dict[str, Callable]:
        return {
            "textforge:auto-simplify": self._auto_simplify_handler,
        }

    async def _submit_auto_simplify(
        self, optimization_id: str | None, score: Any
    ) -> None:
        """Submit an auto-simplify background job for a low-scoring optimization."""
        if not self._kernel or not self._kernel.services.has("jobs"):
            logger.debug("TextForge: job queue not available, skipping auto-simplify")
            return

        job_queue = self._kernel.services.get("jobs")
        try:
            job_id = await job_queue.submit(
                app_id="textforge",
                job_type="textforge:auto-simplify",
                payload={
                    "optimization_id": optimization_id,
                    "original_score": float(score) if score is not None else None,
                },
                priority=1,
            )
            logger.info(
                "TextForge: submitted auto-simplify job %s for optimization %s (score=%.1f)",
                job_id, optimization_id, float(score),
            )
        except Exception:
            logger.debug("TextForge: failed to submit auto-simplify job", exc_info=True)

    async def _auto_simplify_handler(self, job: Job) -> dict:
        """Job handler: fetch the optimized prompt and run a simplification transform."""
        optimization_id = job.payload.get("optimization_id")
        original_score = job.payload.get("original_score")

        if not self._kernel:
            return {"error": "kernel not available"}

        # Fetch the optimized prompt text from the database
        optimized_text = await self._fetch_optimized_prompt(optimization_id)
        if not optimized_text:
            return {"skipped": True, "reason": "optimization not found or no prompt text"}

        # Update progress
        if self._kernel.services.has("jobs"):
            await self._kernel.services.get("jobs").update_progress(job.id, 0.3)

        # Run simplification via the LLM
        simplified_text = await self._run_simplify(optimized_text)
        if not simplified_text:
            return {"skipped": True, "reason": "simplification produced no output"}

        # Update progress
        if self._kernel.services.has("jobs"):
            await self._kernel.services.get("jobs").update_progress(job.id, 0.7)

        # Store the result in TextForge's app storage
        transform_id = await self._store_simplification(
            optimization_id, optimized_text, simplified_text, original_score
        )

        # Compute improvement_delta as relative length reduction
        improvement_delta = 0.0
        if len(optimized_text) > 0:
            improvement_delta = round(
                (len(optimized_text) - len(simplified_text)) / len(optimized_text), 3
            )

        # Publish completion event
        from kernel.bus.helpers import publish_event
        publish_event("textforge:auto-simplify.completed", {
            "optimization_id": optimization_id or "",
            "transform_id": transform_id or "",
            "improvement_delta": improvement_delta,
        }, "textforge")

        return {
            "optimization_id": optimization_id,
            "transform_id": transform_id,
            "input_length": len(optimized_text),
            "output_length": len(simplified_text),
            "improvement_delta": improvement_delta,
        }

    async def _fetch_optimized_prompt(self, optimization_id: str | None) -> str | None:
        """Fetch the optimized prompt text from the PF database."""
        if not optimization_id or not self._kernel:
            return None
        try:
            async with self._kernel.db_session_factory() as session:
                from sqlalchemy import text
                result = await session.execute(
                    text("SELECT optimized_prompt FROM optimizations WHERE id = :id"),
                    {"id": optimization_id},
                )
                row = result.first()
                return row[0] if row else None
        except Exception:
            logger.debug(
                "TextForge: failed to fetch optimization %s",
                optimization_id, exc_info=True,
            )
            return None

    async def _run_simplify(self, text_input: str) -> str | None:
        """Run a simplification transform via the LLM."""
        if not self._kernel:
            return None
        try:
            from app.providers.types import CompletionRequest
            provider = self._kernel.get_provider()
            request = CompletionRequest(
                system_prompt=(
                    "You are a clarity expert. Simplify the following prompt for a "
                    "general audience using shorter sentences and simpler vocabulary. "
                    "Preserve all key instructions and intent."
                ),
                user_message=f"Simplify this prompt:\n\n{text_input}",
            )
            response = await provider.complete(request)
            return response.text if response.text and response.text.strip() else None
        except Exception:
            logger.debug("TextForge: LLM simplify failed", exc_info=True)
            return None

    async def _store_simplification(
        self,
        optimization_id: str | None,
        original_text: str,
        simplified_text: str,
        original_score: float | None,
    ) -> str | None:
        """Store the simplification result in TextForge's app storage."""
        if not self._kernel:
            return None
        try:
            from kernel.repositories.app_storage import AppStorageRepository
            async with self._kernel.db_session_factory() as session:
                repo = AppStorageRepository(session)
                # Ensure collection exists
                collections = await repo.list_collections("textforge")
                collection_id = None
                for c in collections:
                    if c["name"] == "auto-simplify":
                        collection_id = c["id"]
                        break
                if not collection_id:
                    created = await repo.create_collection("textforge", "auto-simplify")
                    collection_id = created["id"]

                now = datetime.now(timezone.utc)
                doc = await repo.create_document(
                    "textforge",
                    f"simplify-{now.strftime('%Y%m%d-%H%M%S')}",
                    json.dumps({
                        "optimization_id": optimization_id,
                        "original_text": original_text,
                        "simplified_text": simplified_text,
                        "original_score": original_score,
                    }),
                    collection_id=collection_id,
                    content_type="application/json",
                    metadata={"type": "auto-simplify", "optimization_id": optimization_id},
                )
                await session.commit()
                return doc["id"]
        except Exception:
            logger.debug("TextForge: failed to store simplification", exc_info=True)
            return None
