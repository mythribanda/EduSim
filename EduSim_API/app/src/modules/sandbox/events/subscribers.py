from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.modules.sandbox.events.subscribers")

"""
subscribers.py
==============
Standard Reusable Event Subscribers for EduSim.

This module provides plug-and-play concrete subscriber handlers for logging, 
analytics metrics, timeline replay recorders, simulated WebSockets, and 
conversational Socratic tutor responses.
"""


from typing import Any, Callable, Dict, List, Optional
from app.src.modules.sandbox.events.event_context import EventContext


class LoggingSubscriber:
    """
    Diagnostic logger subscriber. Prints nicely formatted logs to stdout.
    """
    def __init__(self, name: str = "EduSimLogger") -> None:
        self.name: str = name

    def on_event(self, context: EventContext) -> None:
        """Standard callback listener."""
        logger.info(f"[{self.name}] [F:{context.frame_count}] [{context.source_system.upper()}] "
                    f"Event: '{context.event_type}' (ID: {context.event_id[:8]})")


class ReplayRecorderSubscriber:
    """
    Timeline replay recorder. Captures every serializable event context 
    chronologically. Can export full simulation history files.
    """
    def __init__(self) -> None:
        self.timeline: List[Dict[str, Any]] = []

    def on_event(self, context: EventContext) -> None:
        """Captures a deep copy dictionary of the context."""
        # Standard system events can be skipped in replay logs
        if "snapshot" in context.event_type:
            return
        self.timeline.append(context.serialize())

    def export_history(self) -> List[Dict[str, Any]]:
        """Returns the chronological array of recorded event dicts."""
        return list(self.timeline)

    def clear(self) -> None:
        """Flushes history logs."""
        self.timeline.clear()


class AnalyticsSubscriber:
    """
    Analytics aggregator tracking user interactions, misconceptions, 
    and collision counts for tutor metrics.
    """
    def __init__(self) -> None:
        self.counters: Dict[str, int] = {
            "total_events": 0,
            "clicks": 0,
            "drags": 0,
            "collisions": 0,
            "misconceptions": 0
        }

    def on_event(self, context: EventContext) -> None:
        """Increments matching metric counters."""
        self.counters["total_events"] += 1
        
        et = context.event_type
        if "pointer_down" in et or "pointer_up" in et:
            self.counters["clicks"] += 1
        elif "object_dragged" in et:
            self.counters["drags"] += 1
        elif "collision.start" in et:
            self.counters["collisions"] += 1
        elif "misconception_detected" in et:
            self.counters["misconceptions"] += 1

    def get_report(self) -> Dict[str, int]:
        """Returns collected interaction metrics."""
        return dict(self.counters)


class WebSocketSubscriber:
    """
    Network interface emulator. Buffers events to be pulled/flushed 
    over WebSocket channels.
    """
    def __init__(self) -> None:
        self.outbox: List[Dict[str, Any]] = []
        self._network_sender: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_sender(self, sender_callback: Callable[[Dict[str, Any]], None]) -> None:
        """Links an active connection callback."""
        self._network_sender = sender_callback

    def on_event(self, context: EventContext) -> None:
        """Dispatches event to linked connection or buffers in outbox."""
        serialized = context.serialize()
        if self._network_sender is not None:
            try:
                self._network_sender(serialized)
            except Exception:
                self.outbox.append(serialized)
        else:
            self.outbox.append(serialized)

    def flush_outbox(self) -> List[Dict[str, Any]]:
        """Pulls and clears buffered outbox events."""
        buffered = list(self.outbox)
        self.outbox.clear()
        return buffered


class TutorSubscriber:
    """
    Pedagogical listener. Automatically analyzes physical alerts 
    and formulates Socratic dialogue states.
    """
    def __init__(self, dialogue_handler: Callable[[str, Dict[str, Any]], None]) -> None:
        self.dialogue_handler: Callable[[str, Dict[str, Any]], None] = dialogue_handler

    def on_event(self, context: EventContext) -> None:
        """Launches tutor responses based on active events."""
        et = context.event_type
        
        # 1. Handle threshold speeds
        if et == "observable.threshold_exceeded":
            questions = context.metadata.get("tutor_questions", [])
            val = context.metadata.get("value", 0.0)
            self.dialogue_handler("threshold_dialogue", {
                "message": f"Whoa, velocity has spike to {val:.2f} m/s! Let's pause and think.",
                "questions": questions
            })

        # 2. Handle collisions
        elif et == "collision.start":
            self.dialogue_handler("collision_dialogue", {
                "message": "An impact occurred! How was momentum conserved?",
                "bodies": context.affected_objects
            })
