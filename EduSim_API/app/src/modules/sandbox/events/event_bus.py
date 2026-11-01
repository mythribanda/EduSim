from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.modules.sandbox.events.event_bus")

"""
event_bus.py
============
Central Reactive Event Bus (Nervous System) for EduSim.

This module acts as the event dispatcher and propagation layer. 
It supports:
- Scoped subscriptions (e.g., matching exact types like "collision.start")
- Namespace wildcard prefix subscriptions (e.g., "collision.*" or "*")
- Priority-ordered callback executions
- Safe exception handling (exceptions in listeners do not crash the physics clock)
- Event queueing and batch flushing
- Propagation cancellation support
"""


import fnmatch
from typing import Dict, List, Callable, Optional

from app.src.modules.sandbox.events.event_context import EventContext


class SubscriptionListener:
    """
    Registry node tracking subscriber callbacks, priority ordering, 
    and custom filter constraints.
    """
    def __init__(
        self,
        sub_id: str,
        event_pattern: str,
        callback: Callable[[EventContext], None],
        priority: int = 3,
        filter_fn: Optional[Callable[[EventContext], bool]] = None
    ) -> None:
        self.sub_id: str = sub_id
        self.event_pattern: str = event_pattern
        self.callback: Callable[[EventContext], None] = callback
        self.priority: int = priority
        self.filter_fn: Optional[Callable[[EventContext], bool]] = filter_fn

    def matches(self, event_type: str) -> bool:
        """Evaluates wildcard patterns (e.g., 'collision.*' or '*' matches 'collision.start')."""
        return fnmatch.fnmatch(event_type, self.event_pattern)


class EventBus:
    """
    Central event dispatch and routing repository.
    """
    def __init__(self) -> None:
        # Map of sub_id -> SubscriptionListener
        self._registry: Dict[str, SubscriptionListener] = {}
        
        # Batch queue for high-frequency buffered dispatches
        self._queue: List[EventContext] = []

    # --- Listener Management ---

    def subscribe(
        self,
        event_pattern: str,
        callback: Callable[[EventContext], None],
        priority: int = 3,
        filter_fn: Optional[Callable[[EventContext], bool]] = None
    ) -> str:
        """
        Registers a callback subscription matching target event patterns.
        Priority: higher integers executed first (e.g., 5 runs before 1).
        Returns a unique subscription ID for subsequent unsubscribe calls.
        """
        import uuid
        sub_id = str(uuid.uuid4())
        
        listener = SubscriptionListener(
            sub_id=sub_id,
            event_pattern=event_pattern,
            callback=callback,
            priority=priority,
            filter_fn=filter_fn
        )
        self._registry[sub_id] = listener
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Deregisters an active subscriber callback."""
        if subscription_id in self._registry:
            del self._registry[subscription_id]

    # --- Dispatch Orchestrators ---

    def emit(self, context: EventContext) -> None:
        """
        Synchronously dispatches signals to all matching priority-ordered subscribers.
        Maintains defensive try-except blocks to insulate the physics engine.
        Supports propagation cancellation via metadata flag "_cancelled".
        """
        # Find all matching listeners
        matched_listeners: List[SubscriptionListener] = []
        for listener in self._registry.values():
            if listener.matches(context.event_type):
                # Evaluate filter functions if defined
                if listener.filter_fn is not None:
                    try:
                        if not listener.filter_fn(context):
                            continue
                    except Exception as e:
                        logger.error(f"Error evaluating filter function for listener {listener.sub_id}: {e}")
                        continue
                matched_listeners.append(listener)

        # Sort matching subscribers descending by callback priority
        matched_listeners.sort(key=lambda l: l.priority, reverse=True)

        # Execute dispatches sequentially
        for listener in matched_listeners:
            # Check for propagation cancellation
            if context.metadata.get("_cancelled", False):
                break

            try:
                listener.callback(context)
            except Exception as e:
                # Shield physics engine from failing listeners
                logger.info(f"Defensive catch: subscriber callback crashed for '{context.event_type}': {e}")

    # --- Batch Queue Systems ---

    def queue_event(self, context: EventContext) -> None:
        """Appends events to a buffer for batched end-of-tick processing."""
        self._queue.append(context)

    def flush_queue(self) -> None:
        """Sequentially flushes and dispatches all buffered signals."""
        current_queue = list(self._queue)
        self._queue.clear()
        
        for context in current_queue:
            self.emit(context)

    def cancel_propagation(self, context: EventContext) -> None:
        """Stops further subscription callbacks from receiving this signal."""
        context.metadata["_cancelled"] = True
