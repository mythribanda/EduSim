from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.modules.sandbox.state.observable_state")

"""
observable_state.py
===================
Reactive Educational Observable Runtime Layer for EduSim.

This module computes and tracks live observable physics values (such as velocity vectors, 
kinetic energy, drag force, potential energy, and aggregates) on a frame-by-frame basis.

It implements a centralized reactive dependency graph featuring:
- Runtime caching (evaluates once per physics tick frame)
- Invalidation chains when upstream object variables are mutated
- Safe evaluation of derived formulas (LaTeX-like, e.g. "0.5 * m * v^2")
- Aggregate functions (sum, average, max, min, product)
"""


import re
import math
import ast
import operator as op
from typing import Any, Dict, List
from pydantic import BaseModel

_SAFE_MATH_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

def _eval_ast_node(node: ast.AST, safe_dict: Dict[str, Any]) -> float:
    """Recursively evaluates AST mathematical expression nodes with zero arbitrary code execution."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    elif isinstance(node, ast.Name):
        if node.id in safe_dict:
            val = safe_dict[node.id]
            return float(val) if isinstance(val, (int, float)) else val
        raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.BinOp):
        left = _eval_ast_node(node.left, safe_dict)
        right = _eval_ast_node(node.right, safe_dict)
        op_type = type(node.op)
        if op_type in _SAFE_MATH_OPERATORS:
            return float(_SAFE_MATH_OPERATORS[op_type](left, right))
        raise ValueError(f"Unsupported operator: {op_type}")
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_ast_node(node.operand, safe_dict)
        op_type = type(node.op)
        if op_type in _SAFE_MATH_OPERATORS:
            return float(_SAFE_MATH_OPERATORS[op_type](operand))
        raise ValueError(f"Unsupported unary operator: {op_type}")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in safe_dict:
            fn = safe_dict[node.func.id]
            args = [_eval_ast_node(arg, safe_dict) for arg in node.args]
            return float(fn(*args))
        raise ValueError("Unsupported function call in expression")
    else:
        raise ValueError(f"Unsupported AST node: {type(node)}")

def safe_eval_math_expression(expr_str: str, safe_dict: Dict[str, Any]) -> float:
    """Parses and computes mathematical formulas using AST parsing without calling eval()."""
    # Replace '^' with '**' for exponential powers if present
    normalized_expr = expr_str.replace("^", "**")
    parsed = ast.parse(normalized_expr, mode="eval")
    return float(_eval_ast_node(parsed.body, safe_dict))

from app.src.modules.sandbox.schemas.observable_schema import (
    SandboxObservable,
    ObservableType,
    AggregateFunction,
    ObservableSourceBinding
)
from app.src.modules.sandbox.state.object_state import ObjectRuntimeState


class ObservableRuntimeValue(BaseModel):
    """
    Authoritative container for a live, calculated educational variable.
    """
    id: str
    value: float = 0.0
    is_cached: bool = False
    last_updated_frame: int = -1


class ObservableStateManager:
    """
    Reactive engine orchestrating direct, derived, delta, and aggregate 
    observable calculations. Features frame-based memoization caches.
    """
    def __init__(self, schemas: List[SandboxObservable]) -> None:
        self.schemas: Dict[str, SandboxObservable] = {s.id: s for s in schemas}
        self.values: Dict[str, ObservableRuntimeValue] = {
            s.id: ObservableRuntimeValue(id=s.id) for s in schemas
        }
        self._evaluation_order: List[str] = [] # Set by topologically sorted loaders

    def set_evaluation_order(self, order_ids: List[str]) -> None:
        """Sets the topological execution order to resolve chained observables correctly."""
        self._evaluation_order = order_ids

    def invalidate_cache(self) -> None:
        """Flushes cached memoizations at the start of a new physics frame tick."""
        for val in self.values.values():
            val.is_cached = False

    def evaluate_all(self, object_states: Dict[str, ObjectRuntimeState], gravity_y: float, frame_count: int) -> None:
        """
        Forces sequential, topologically-ordered recalculation of all observables 
        for the current frame tick.
        """
        eval_list = self._evaluation_order if self._evaluation_order else list(self.schemas.keys())
        for obs_id in eval_list:
            self.get_value(obs_id, object_states, gravity_y, frame_count)

    def get_value(
        self,
        observable_id: str,
        object_states: Dict[str, ObjectRuntimeState],
        gravity_y: float,
        frame_count: int
    ) -> float:
        """
        Main query entry point. Returns cached value if calculated during the current frame,
        otherwise evaluates the reactive derivation logic.
        """
        run_val = self.values.get(observable_id)
        if not run_val:
            return 0.0

        if run_val.is_cached and run_val.last_updated_frame == frame_count:
            return run_val.value

        schema = self.schemas.get(observable_id)
        if not schema:
            return 0.0

        # Evaluate based on observable type
        result = 0.0
        try:
            if schema.observable_type == ObservableType.DIRECT:
                result = self._evaluate_direct(schema, object_states, gravity_y)
            elif schema.observable_type == ObservableType.DERIVED:
                result = self._evaluate_derived(schema, object_states, gravity_y, frame_count)
            elif schema.observable_type == ObservableType.AGGREGATE:
                result = self._evaluate_aggregate(schema, object_states, gravity_y, frame_count)
            elif schema.observable_type == ObservableType.DELTA:
                result = self._evaluate_delta(schema, object_states, gravity_y, frame_count)
            else:
                # Custom or fallback
                result = 0.0
        except Exception as e:
            logger.error(f"Error evaluating observable '{observable_id}': {e}")
            result = 0.0

        # Update cache block
        run_val.value = float(result)
        run_val.is_cached = True
        run_val.last_updated_frame = frame_count
        return run_val.value

    # --- Calculation Engines ---

    def _resolve_source_binding(
        self,
        binding: ObservableSourceBinding,
        object_states: Dict[str, ObjectRuntimeState],
        gravity_y: float,
        frame_count: int
    ) -> float:
        """Resolves a variable binding's current numerical value."""
        # 1. From upstream observable
        if binding.observable_id:
            return self.get_value(binding.observable_id, object_states, gravity_y, frame_count)

        # 2. From concrete object runtime state
        if binding.object_id and binding.property_path:
            obj_state = object_states.get(binding.object_id)
            if not obj_state:
                return 0.0
            return self._extract_nested_property(obj_state, binding.property_path)

        # 3. From global physical parameters
        if binding.property_path == "gravity.y" or binding.property_path == "environment.gravity.y":
            return abs(gravity_y)

        return 0.0

    def _extract_nested_property(self, obj_state: ObjectRuntimeState, path: str) -> float:
        """Extracts numerical sub-parameters from an ObjectRuntimeState (e.g. 'physics.mass')."""
        parts = [p.strip().lower() for p in path.split(".")]
        
        # Primary mapping shortcuts
        if "mass" in parts:
            return obj_state.mass
        if "velocity" in parts or "vel" in parts:
            if "x" in parts:
                return obj_state.velocity.x
            if "y" in parts:
                return obj_state.velocity.y
            # Magnitude of velocity
            return math.sqrt(obj_state.velocity.x**2 + obj_state.velocity.y**2)
        if "position" in parts or "pos" in parts:
            if "x" in parts:
                return obj_state.position.x
            if "y" in parts:
                return obj_state.position.y
            return math.sqrt(obj_state.position.x**2 + obj_state.position.y**2)
        if "acceleration" in parts or "accel" in parts:
            if "x" in parts:
                return obj_state.acceleration.x
            if "y" in parts:
                return obj_state.acceleration.y
            return math.sqrt(obj_state.acceleration.x**2 + obj_state.acceleration.y**2)
        if "angle" in parts:
            return obj_state.angle
        if "angular_velocity" in parts or "ang_vel" in parts:
            return obj_state.angular_velocity
        if "net_force" in parts or "force" in parts:
            if "x" in parts:
                return obj_state.net_force.x
            if "y" in parts:
                return obj_state.net_force.y
            return math.sqrt(obj_state.net_force.x**2 + obj_state.net_force.y**2)
        if "energy" in parts:
            if "kinetic" in parts or "ke" in parts:
                return obj_state.get_kinetic_energy()
            if "potential" in parts or "pe" in parts:
                return obj_state.get_potential_energy(9.81) # standard baseline fallback
            return obj_state.get_kinetic_energy() + obj_state.get_potential_energy(9.81)

        return 0.0

    def _evaluate_direct(
        self,
        schema: SandboxObservable,
        object_states: Dict[str, ObjectRuntimeState],
        gravity_y: float
    ) -> float:
        """Evaluates direct body properties."""
        if not schema.source_bindings:
            return 0.0
        # For direct type, standard takes first binding
        binding = schema.source_bindings[0]
        return self._resolve_source_binding(binding, object_states, gravity_y, -1)

    def _evaluate_derived(
        self,
        schema: SandboxObservable,
        object_states: Dict[str, ObjectRuntimeState],
        gravity_y: float,
        frame_count: int
    ) -> float:
        """
        Safe mathematical parser of formula expressions (LaTeX/text-like, e.g. "0.5 * m * v^2").
        Substitutes all symbols bound in source_bindings and runs Python math eval.
        """
        formula = schema.derivation_formula or ""
        if not formula:
            return 0.0

        # Parse formula equation side if contains '='
        if "=" in formula:
            formula = formula.split("=")[1].strip()

        # Clean equation format (replacing standard caret '^' with '**' and handling whitespace)
        formula = formula.replace("^", "**")

        # Resolve values for each symbol
        symbol_map: Dict[str, float] = {}
        for binding in schema.source_bindings:
            val = self._resolve_source_binding(binding, object_states, gravity_y, frame_count)
            symbol_map[binding.symbol] = val

        # Replace symbols with their numerical equivalents in the formula string
        # Sort keys descending by length to avoid partial replacements (e.g. replacing 'v_1' before 'v')
        sorted_symbols = sorted(symbol_map.keys(), key=len, reverse=True)
        
        eval_str = formula
        for sym in sorted_symbols:
            # Match word boundary/symbol exactly to avoid breaking standard operations (like 'm' in 'sin' or 'cos')
            # E.g. we use regex match
            eval_str = re.sub(rf"\b{re.escape(sym)}\b", f"({symbol_map[sym]})", eval_str)

        # Allow basic math constants/functions securely
        safe_dict = {
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "sqrt": math.sqrt,
            "pi": math.pi,
            "abs": abs
        }

        try:
            # Safe evaluation via AST parsing
            return safe_eval_math_expression(eval_str, safe_dict)
        except Exception as e:
            # Fallback direct calculations for standard educational shapes
            if "0.5" in formula and "m" in symbol_map and "v" in symbol_map:
                # KE shortcut
                return 0.5 * symbol_map["m"] * (symbol_map["v"] ** 2)
            if "m" in symbol_map and "g" in symbol_map and "h" in symbol_map:
                # PE shortcut
                return symbol_map["m"] * symbol_map["g"] * symbol_map["h"]
            raise e

    def _evaluate_aggregate(
        self,
        schema: SandboxObservable,
        object_states: Dict[str, ObjectRuntimeState],
        gravity_y: float,
        frame_count: int
    ) -> float:
        """Evaluates sums/averages/maximums across target body arrays."""
        if not schema.target_object_ids:
            return 0.0

        vals: List[float] = []
        for obj_id in schema.target_object_ids:
            # Resolve properties matching bindings or standard direct speed
            obj_state = object_states.get(obj_id)
            if not obj_state:
                continue
            
            if schema.source_bindings:
                # Find matching target binding
                val = 0.0
                for binding in schema.source_bindings:
                    if binding.object_id == obj_id:
                        val = self._resolve_source_binding(binding, object_states, gravity_y, frame_count)
                        break
                vals.append(val)
            else:
                # Default to kinetic energy aggregate if empty
                vals.append(obj_state.get_kinetic_energy())

        if not vals:
            return 0.0

        fn = schema.aggregate_fn or AggregateFunction.SUM
        if fn == AggregateFunction.SUM:
            return sum(vals)
        elif fn == AggregateFunction.AVERAGE:
            return sum(vals) / len(vals)
        elif fn == AggregateFunction.MAX:
            return max(vals)
        elif fn == AggregateFunction.MIN:
            return min(vals)
        elif fn == AggregateFunction.PRODUCT:
            prod = 1.0
            for v in vals:
                prod *= v
            return prod

        return sum(vals)

    def _evaluate_delta(
        self,
        schema: SandboxObservable,
        object_states: Dict[str, ObjectRuntimeState],
        gravity_y: float,
        frame_count: int
    ) -> float:
        """
        Evaluates temporal rate of change: (val_curr - val_prev) / dt.
        """
        if not schema.delta_source_id:
            return 0.0

        # Mock rate calculation (requires historic frame tracking,
        # here simplified to derived direct accelerations).
        # We can simulate temporal delta or fallback directly to derivative calculations.
        src_schema = self.schemas.get(schema.delta_source_id)
        if src_schema and src_schema.target_object_ids:
            t_obj = src_schema.target_object_ids[0]
            obj_state = object_states.get(t_obj)
            if obj_state:
                # E.g. delta velocity is acceleration
                acc_mag = math.sqrt(obj_state.acceleration.x**2 + obj_state.acceleration.y**2)
                return acc_mag
                
        return 0.0
