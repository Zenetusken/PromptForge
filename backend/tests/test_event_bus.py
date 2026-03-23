"""Tests for the in-process event bus."""

import asyncio

import pytest

from app.services.event_bus import EventBus


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.mark.asyncio
async def test_publish_to_subscriber(bus: EventBus) -> None:
    """Subscribe, publish, verify the subscriber receives the event."""
    received: list[dict] = []

    async def consume():
        async for event in bus.subscribe():
            received.append(event)
            break  # stop after first event

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)  # let subscriber register

    bus.publish("test_event", {"key": "value"})
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 1
    assert received[0]["event"] == "test_event"
    assert received[0]["data"] == {"key": "value"}
    assert "timestamp" in received[0]


@pytest.mark.asyncio
async def test_multiple_subscribers(bus: EventBus) -> None:
    """Two subscribers should both receive the same event."""
    results_a: list[dict] = []
    results_b: list[dict] = []

    async def consume_a():
        async for event in bus.subscribe():
            results_a.append(event)
            break

    async def consume_b():
        async for event in bus.subscribe():
            results_b.append(event)
            break

    task_a = asyncio.create_task(consume_a())
    task_b = asyncio.create_task(consume_b())
    await asyncio.sleep(0.01)

    assert bus.subscriber_count == 2
    bus.publish("multi", {"n": 1})

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=2.0)

    assert len(results_a) == 1
    assert len(results_b) == 1
    assert results_a[0]["data"] == {"n": 1}
    assert results_b[0]["data"] == {"n": 1}


@pytest.mark.asyncio
async def test_no_subscribers(bus: EventBus) -> None:
    """Publishing with no subscribers should not raise."""
    bus.publish("orphan_event", {"x": 1})
    assert bus.subscriber_count == 0


@pytest.mark.asyncio
async def test_overflow_drops_oldest_not_subscriber(bus: EventBus) -> None:
    """When a subscriber's queue is full, drop oldest event (keep subscriber alive)."""
    # Manually add a full queue with maxsize=1
    full_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    full_queue.put_nowait({"event": "filler", "data": {}, "timestamp": 0, "seq": 0})
    bus._subscribers.add(full_queue)

    assert bus.subscriber_count == 1

    # This publish should drop the filler and insert the new event
    bus.publish("overflow", {"y": 2})

    # Subscriber is still connected (NOT removed)
    assert bus.subscriber_count == 1

    # The queue now holds the new event (filler was dropped)
    event = full_queue.get_nowait()
    assert event["event"] == "overflow"
    assert event["data"] == {"y": 2}


@pytest.mark.asyncio
async def test_subscriber_cleanup(bus: EventBus) -> None:
    """Subscriber count goes back to zero after the generator is closed."""
    assert bus.subscriber_count == 0

    gen = bus.subscribe()

    # Manually start the generator — registers the subscriber
    async def consume_one():
        return await gen.__anext__()

    task = asyncio.create_task(consume_one())
    await asyncio.sleep(0.01)
    assert bus.subscriber_count == 1

    bus.publish("cleanup_test", {})
    event = await asyncio.wait_for(task, timeout=2.0)
    assert event["event"] == "cleanup_test"

    # Explicitly close the generator to trigger finally
    await gen.aclose()
    assert bus.subscriber_count == 0


# ---------------------------------------------------------------------------
# Sequence number tests
# ---------------------------------------------------------------------------


def test_sequence_monotonically_increasing(bus: EventBus) -> None:
    """Each publish increments the sequence number."""
    assert bus.current_sequence == 0

    bus.publish("a", {"i": 1})
    assert bus.current_sequence == 1

    bus.publish("b", {"i": 2})
    assert bus.current_sequence == 2

    bus.publish("c", {"i": 3})
    assert bus.current_sequence == 3


@pytest.mark.asyncio
async def test_events_contain_seq(bus: EventBus) -> None:
    """Published events include a `seq` field."""
    received: list[dict] = []

    async def consume():
        async for event in bus.subscribe():
            received.append(event)
            if len(received) >= 2:
                break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)

    bus.publish("ev1", {})
    bus.publish("ev2", {})
    await asyncio.wait_for(task, timeout=2.0)

    assert received[0]["seq"] == 1
    assert received[1]["seq"] == 2


# ---------------------------------------------------------------------------
# Replay buffer tests
# ---------------------------------------------------------------------------


def test_replay_since_returns_missed_events(bus: EventBus) -> None:
    """replay_since returns all events with seq > given value."""
    bus.publish("a", {"i": 1})
    bus.publish("b", {"i": 2})
    bus.publish("c", {"i": 3})

    # Replay since seq=1 should return events 2 and 3
    missed = bus.replay_since(1)
    assert len(missed) == 2
    assert missed[0]["event"] == "b"
    assert missed[0]["seq"] == 2
    assert missed[1]["event"] == "c"
    assert missed[1]["seq"] == 3


def test_replay_since_zero_returns_all(bus: EventBus) -> None:
    """replay_since(0) returns all buffered events."""
    bus.publish("a", {})
    bus.publish("b", {})
    assert len(bus.replay_since(0)) == 2


def test_replay_since_future_returns_empty(bus: EventBus) -> None:
    """replay_since with a seq beyond current returns empty list."""
    bus.publish("a", {})
    assert len(bus.replay_since(999)) == 0


def test_replay_buffer_bounded() -> None:
    """Replay buffer respects maxlen — old events are evicted."""
    from app.services.event_bus import _REPLAY_BUFFER_SIZE

    bus = EventBus()
    for i in range(_REPLAY_BUFFER_SIZE + 50):
        bus.publish("x", {"i": i})

    # Buffer should hold exactly _REPLAY_BUFFER_SIZE events
    all_events = bus.replay_since(0)
    assert len(all_events) == _REPLAY_BUFFER_SIZE

    # Oldest retained event should be seq 51 (first 50 evicted)
    assert all_events[0]["seq"] == 51


def test_shutdown_suppresses_publish(bus: EventBus) -> None:
    """After shutdown, publish is a no-op."""
    bus.publish("before", {})
    assert bus.current_sequence == 1

    bus.shutdown()
    bus.publish("after", {})
    # Sequence should not advance
    assert bus.current_sequence == 1
