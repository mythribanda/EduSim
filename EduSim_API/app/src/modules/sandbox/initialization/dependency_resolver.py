"""
dependency_resolver.py
=======================
Topological Dependency Resolver & Integrity Validator for EduSim.

This module validates and sequences all entities (objects, constraints, observables, 
relationships, and controls) within a sandbox schema to guarantee structural 
integrity, resolve references, and detect circular dependencies.

It contains:
- Topological sort for evaluating dependent Observables (e.g. velocity depends on position)
- Topological sort for sequencing Educational Relationships (e.g. kinetic energy depends on motion)
- Safe reference validation for constraints, controls, and bindings
- Dynamic DFS circular reference tracking with precise error messages
"""


from __future__ import annotations
from typing import List, Dict, Set
from app.src.modules.sandbox.schemas.sandbox_schema import SandboxSchema
from app.src.modules.sandbox.schemas.observable_schema import SandboxObservable
from app.src.modules.sandbox.schemas.relationship_schema import EducationalRelationship


class DependencyResolutionError(ValueError):
    """Raised when there is an unresolved reference or circular loop in sandbox dependencies."""


class DependencyResolver:
    """
    Orchestrates the resolution and ordering of cross-referenced simulation layers.
    """

    @staticmethod
    def validate_integrity(sandbox: SandboxSchema) -> None:
        """
        Performs strict verification of cross-reference integrity across the entire sandbox.
        Ensures all referenced objects, constraints, observables, and relationships exist.
        """
        object_ids = {obj.id for obj in sandbox.objects}
        constraint_ids = {c.id for c in sandbox.constraints}
        observable_ids = {o.id for o in sandbox.observables}
        {r.id for r in sandbox.relationships}
        valid_ids = object_ids.union(constraint_ids)

        # 1. Verify constraints
        for constraint in sandbox.constraints:
            for side, anchor in [("anchor_a", constraint.anchor_a), ("anchor_b", constraint.anchor_b)]:
                if anchor.body_id and anchor.body_id not in object_ids:
                    raise DependencyResolutionError(
                        f"Constraint '{constraint.id}' attaches to non-existent body_id '{anchor.body_id}' on {side}."
                    )

        # 2. Verify controls
        for control in sandbox.controls:
            # Check object target scope references
            if control.binding.scope == "object" and control.binding.object_id:
                if control.binding.object_id not in object_ids:
                    raise DependencyResolutionError(
                        f"Control '{control.id}' targets non-existent object '{control.binding.object_id}'."
                    )

        # 3. Verify relationships
        for rel in sandbox.relationships:
            # Check physical targets are valid
            for obj_id in rel.object_ids:
                if obj_id not in valid_ids and obj_id != "environment":
                    raise DependencyResolutionError(
                        f"Relationship '{rel.id}' binds to non-existent physical object or constraint '{obj_id}'."
                    )
            # Check variable bindings
            for binding in rel.variable_map:
                if binding.observable_id and binding.observable_id not in observable_ids:
                    raise DependencyResolutionError(
                        f"Relationship '{rel.id}' variable '{binding.symbol}' binds to missing observable '{binding.observable_id}'."
                    )
                if binding.object_id and binding.object_id not in valid_ids:
                    raise DependencyResolutionError(
                        f"Relationship '{rel.id}' variable '{binding.symbol}' binds to missing object/constraint '{binding.object_id}'."
                    )

        # 4. Verify observables
        for obs in sandbox.observables:
            # Verify direct targets
            for target_id in obs.target_object_ids:
                if target_id not in object_ids:
                    raise DependencyResolutionError(
                        f"Observable '{obs.id}' targets non-existent object '{target_id}'."
                    )
            # Verify nested source bindings
            for source in obs.source_bindings:
                if source.observable_id and source.observable_id not in observable_ids:
                    raise DependencyResolutionError(
                        f"Observable '{obs.id}' derives from non-existent observable '{source.observable_id}'."
                    )
                if source.object_id and source.object_id not in valid_ids:
                    raise DependencyResolutionError(
                        f"Observable '{obs.id}' derives from property on missing object '{source.object_id}'."
                    )

    @classmethod
    def sort_observables(cls, sandbox: SandboxSchema) -> List[SandboxObservable]:
        """
        Topologically sorts observables based on their source bindings to guarantee 
        an executable evaluation order (e.g. derivative/derived values processed after raw inputs).
        Raises DependencyResolutionError if a circular loop is detected.
        """
        # Create an adjacency map representing B -> A (B depends on A)
        adj_map: Dict[str, Set[str]] = {}
        obs_map: Dict[str, SandboxObservable] = {o.id: o for o in sandbox.observables}

        for obs in sandbox.observables:
            adj_map[obs.id] = set()
            for source in obs.source_bindings:
                if source.observable_id:
                    adj_map[obs.id].add(source.observable_id)

        # Detect circular references & compute topological sort via DFS
        sorted_ids: List[str] = []
        visited: Dict[str, int] = {oid: 0 for oid in obs_map} # 0=Unvisited, 1=Visiting, 2=Visited

        def dfs(node_id: str) -> None:
            visited[node_id] = 1 # Mark as visiting
            
            for dep in adj_map.get(node_id, set()):
                if visited.get(dep, 0) == 1:
                    raise DependencyResolutionError(
                        f"Circular dependency loop detected in observables: {node_id} <-> {dep}"
                    )
                if visited.get(dep, 0) == 0:
                    dfs(dep)
                    
            visited[node_id] = 2 # Mark as visited
            sorted_ids.append(node_id)

        for oid in obs_map:
            if visited[oid] == 0:
                dfs(oid)

        return [obs_map[oid] for oid in sorted_ids]

    @classmethod
    def sort_relationships(cls, sandbox: SandboxSchema) -> List[EducationalRelationship]:
        """
        Topologically sorts educational relationships by their `depends_on` chains.
        This orders concepts sequentially so that baseline physics concepts 
        are sequenced/explained before compound derivative topics.
        """
        adj_map: Dict[str, Set[str]] = {}
        rel_map: Dict[str, EducationalRelationship] = {r.id: r for r in sandbox.relationships}

        for rel in sandbox.relationships:
            adj_map[rel.id] = set()
            for dep in rel.depends_on:
                if dep in rel_map:
                    adj_map[rel.id].add(dep)

        sorted_ids: List[str] = []
        visited: Dict[str, int] = {rid: 0 for rid in rel_map} # 0=Unvisited, 1=Visiting, 2=Visited

        def dfs(node_id: str) -> None:
            visited[node_id] = 1
            
            for dep in adj_map.get(node_id, set()):
                if visited.get(dep, 0) == 1:
                    raise DependencyResolutionError(
                        f"Circular dependency loop detected in relationships: {node_id} <-> {dep}"
                    )
                if visited.get(dep, 0) == 0:
                    dfs(dep)
                    
            visited[node_id] = 2
            sorted_ids.append(node_id)

        for rid in rel_map:
            if visited[rid] == 0:
                dfs(rid)

        return [rel_map[rid] for rid in sorted_ids]
