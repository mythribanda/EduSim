"""
observable_events.py
=====================
Observable State Reactive Signals Generator for EduSim.

This module maps changes in calculated variables (speeds, momentum spikes, 
conservation law violations, aggregate totals) into event signals. 

Subscribers can filter by specific target observable IDs.
"""


from __future__ import annotations
from typing import Dict, List, Optional
from app.src.modules.sandbox.events.event_types import ObservableEvents
from app.src.modules.sandbox.events.event_context import EventContext
from app.src.modules.sandbox.events.event_bus import EventBus


def emit_observable_updated(
    event_bus: EventBus,
    frame_count: int,
    observable_id: str,
    value: float,
    unit: str = ""
) -> None:
    """Emits a signal whenever an educational variable is recalculated."""
    context = EventContext.create(
        event_type=ObservableEvents.OBSERVABLE_UPDATED.value,
        frame_count=frame_count,
        source_system="observable",
        observable_ids=[observable_id],
        metadata={
            "value": float(value),
            "unit": unit
        }
    )
    event_bus.emit(context)


def emit_threshold_exceeded(
    event_bus: EventBus,
    frame_count: int,
    observable_id: str,
    value: float,
    threshold_limit: float,
    comparison_operator: str,
    tutor_questions: Optional[List[str]] = None
) -> None:
    """
    Emits a signal when an educational variable crosses a defined limit 
    (e.g., speed exceeds 15 m/s or conservation of energy fails).
    """
    context = EventContext.create(
        event_type=ObservableEvents.THRESHOLD_EXCEEDED.value,
        frame_count=frame_count,
        source_system="observable",
        observable_ids=[observable_id],
        priority=4, # High priority threshold event
        metadata={
            "value": float(value),
            "threshold_limit": float(threshold_limit),
            "comparison_operator": comparison_operator,
            "tutor_questions": tutor_questions or []
        }
    )
    event_bus.emit(context)


def emit_formula_recomputed(
    event_bus: EventBus,
    frame_count: int,
    relationship_id: str,
    inputs: Dict[str, float],
    output_value: float,
    formula_latex: str = ""
) -> None:
    """Emits a signal when an educational relationship is re-solved conceptually."""
    context = EventContext.create(
        event_type=ObservableEvents.FORMULA_RECOMPUTED.value,
        frame_count=frame_count,
        source_system="relationship",
        metadata={
            "relationship_id": relationship_id,
            "inputs": inputs,
            "output_value": float(output_value),
            "formula_latex": formula_latex
        }
    )
    event_bus.emit(context)
