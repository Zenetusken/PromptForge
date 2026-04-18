"""Task 26 regression — Compat: legacy state='template' activity events render verbatim.

Spec §Compat:
  - Activity events with context['new_state']='template' must NOT be remapped.
  - A diagnostic counter (legacy_state_observed) increments each time such
    an event surfaces through GET /api/clusters/activity.
"""
from __future__ import annotations

import pytest

from app.services.taxonomy.event_logger import (
    TaxonomyEventLogger,
    get_event_logger,
    reset_event_logger,
    set_event_logger,
)


@pytest.fixture(autouse=True)
def isolated_event_logger(tmp_path):
    """Give each test its own fresh TaxonomyEventLogger singleton."""
    inst = TaxonomyEventLogger(events_dir=tmp_path, publish_to_bus=False)
    set_event_logger(inst)
    yield inst
    reset_event_logger()


class TestActivityLegacyTemplateState:
    @pytest.mark.asyncio
    async def test_activity_endpoint_returns_legacy_template_state_verbatim(
        self, app_client, isolated_event_logger
    ):
        """Spec §Compat: historical activity entries with state='template' render verbatim.

        The activity feed is a debug/history surface — it MUST show events
        as-they-happened. A read-side remap from 'template' to any other
        state would silently rewrite history, which the spec forbids.
        """
        logger = get_event_logger()
        logger.log_decision(
            path="warm",
            op="lifecycle_transition",
            decision="demoted",
            cluster_id="c_legacy_tpl",
            context={"old_state": "mature", "new_state": "template", "reason": "legacy"},
        )

        r = await app_client.get("/api/clusters/activity?limit=10")
        assert r.status_code == 200, r.text
        events = r.json()["events"]
        legacy = [e for e in events if e.get("context", {}).get("new_state") == "template"]
        assert len(legacy) == 1, (
            f"legacy template event lost or remapped — got {[e.get('context') for e in events]}"
        )
        # Belt-and-suspenders: no silent rewrite to any other state.
        assert legacy[0]["context"]["new_state"] != "mature"
        assert legacy[0]["context"]["old_state"] == "mature"

    @pytest.mark.asyncio
    async def test_legacy_state_observed_counter_increments_on_template_read(
        self, app_client, isolated_event_logger
    ):
        """Diagnostic counter: each read of a pre-migration template event ticks."""
        logger = get_event_logger()
        before = logger.legacy_state_observed  # new attribute

        logger.log_decision(
            path="warm",
            op="lifecycle_transition",
            decision="demoted",
            cluster_id="c_legacy_count",
            context={"new_state": "template"},
        )

        # Reading the event triggers the observer in the ring-buffer reader path.
        r = await app_client.get("/api/clusters/activity?limit=10")
        assert r.status_code == 200

        after = logger.legacy_state_observed
        assert after >= before + 1, f"counter did not increment: {before} → {after}"
        # Bounded — must never exceed an internal cap.
        assert after < 10_000_000

    @pytest.mark.asyncio
    async def test_non_legacy_events_do_not_increment_counter(
        self, app_client, isolated_event_logger
    ):
        """Counter only ticks for 'template' values — not for 'active', 'mature', etc."""
        logger = get_event_logger()

        logger.log_decision(
            path="warm",
            op="lifecycle_transition",
            decision="promoted",
            cluster_id="c_modern",
            context={"old_state": "candidate", "new_state": "active"},
        )

        r = await app_client.get("/api/clusters/activity?limit=10")
        assert r.status_code == 200

        assert logger.legacy_state_observed == 0, (
            f"counter should not have incremented for modern states, got {logger.legacy_state_observed}"
        )
