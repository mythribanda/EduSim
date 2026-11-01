"""
dependency_graph.py
===================
Conceptual Dependency Graph for EduSim.

This module models the educational physics variables and their causal, mathematical
relationships as a directed dependency graph. It is the intelligence layer 
that allows the Tutor AI to trace why things happen, sequence curriculum topics, 
and explain causal chains to students.

Example:
  - 'acceleration' depends on 'net force' and 'mass' (Newton's 2nd Law)
  - 'kinetic_energy' depends on 'mass' and 'velocity' (Kinetic Energy formula)
  - 'pendulum_period' depends on 'length' and 'gravity' (Simple Pendulum Period)

GRAPH ARCHITECTURE & TRAVERSAL
------------------------------
1. Nodes: Represent physical quantities (variables, property paths, or observables) 
   and relationship entities (formulas).
2. Directed Edges: Represent dependency direction (from consumer/derived quantity 
   to its direct input ingredients).
3. Traversal Strategy:
   - Upstream Trace (Backwards Causal Chain): "What physical factors determine the 
     value of kinetic energy?" Traces backward to find ['mass', 'velocity'].
   - Downstream Trace (Forwards Influence Chain): "If I increase the mass of this 
     pendulum bob, what other observables or educational properties will be affected?" 
     Traces forward to find ['kinetic_energy', 'momentum'].
   - Socratic Path Generation: Translates raw dependency tracks into a step-by-step
     causal sequencing for the Tutor.

BEST PRACTICES
--------------
- Do not store stateful frame values in the graph. Nodes represent the schema properties 
  and conceptual quantities, not their current numeric value.
- Support deep chains (e.g. thrust -> force -> acceleration -> velocity -> kinetic_energy).
- Keep graph lookups highly performant through standard native adjacency maps.
"""


from __future__ import annotations
from typing import Dict, List, Set, Optional
from app.src.modules.sandbox.schemas.sandbox_schema import SandboxSchema


class DependencyNode:
    """
    Represents a variable, property, or formula node within the conceptual physics graph.
    """
    def __init__(self, id: str, name: str, node_type: str, metadata: Optional[Dict] = None) -> None:
        self.id = id                    # e.g., 'bob_1.physics.mass' or 'vel_bob_1' or 'rel_newtons_second_law'
        self.name = name                # e.g., 'Bob Mass'
        self.node_type = node_type      # 'property', 'observable', 'relationship'
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"Node({self.id}, type={self.node_type})"


class ConceptualDependencyGraph:
    """
    Direct graph modeling and tracing of causal and mathematical dependencies 
    across sandbox components.
    """
    def __init__(self) -> None:
        self.nodes: Dict[str, DependencyNode] = {}
        self.adj_list: Dict[str, Set[str]] = {}      # child -> parents (depends on)
        self.rev_adj_list: Dict[str, Set[str]] = {}  # parent -> children (influences)

    def add_node(self, node: DependencyNode) -> None:
        """Add a conceptual node to the graph."""
        if node.id not in self.nodes:
            self.nodes[node.id] = node
            self.adj_list[node.id] = set()
            self.rev_adj_list[node.id] = set()

    def add_dependency(self, target_id: str, depends_on_id: str) -> None:
        """
        Declares that target_id depends on depends_on_id.
        Creates a directed edge: target_id -> depends_on_id.
        """
        if target_id not in self.nodes or depends_on_id not in self.nodes:
            raise ValueError(f"Both nodes must exist in graph. Missing {target_id} or {depends_on_id}")
        
        self.adj_list[target_id].add(depends_on_id)
        self.rev_adj_list[depends_on_id].add(target_id)

    def trace_upstream(self, node_id: str, visited: Optional[Set[str]] = None) -> List[str]:
        """
        Backwards trace (DFS): find all direct and indirect factors that this node depends on.
        Answers: 'What determines the value of X?'
        """
        if visited is None:
            visited = set()

        if node_id not in self.nodes:
            return []

        dependencies = []
        for dep in self.adj_list.get(node_id, set()):
            if dep not in visited:
                visited.add(dep)
                dependencies.append(dep)
                dependencies.extend(self.trace_upstream(dep, visited))
        
        return list(dict.fromkeys(dependencies)) # Preserve order, remove duplicates

    def trace_downstream(self, node_id: str, visited: Optional[Set[str]] = None) -> List[str]:
        """
        Forwards trace (DFS): find all nodes that are influenced by changes in this node.
        Answers: 'If I change Y, what else is affected?'
        """
        if visited is None:
            visited = set()

        if node_id not in self.nodes:
            return []

        influences = []
        for infl in self.rev_adj_list.get(node_id, set()):
            if infl not in visited:
                visited.add(infl)
                influences.append(infl)
                influences.extend(self.trace_downstream(infl, visited))
        
        return list(dict.fromkeys(influences)) # Preserve order, remove duplicates

    def explain_causal_path(self, start_id: str, end_id: str) -> List[str]:
        """
        Finds a direct pathway from start_id to end_id to explain a causal relationship.
        Answers: 'Why does changing mass affect kinetic energy?'
        Returns an ordered list of node IDs showing the chain of dependency.
        """
        # Standard BFS pathfinding
        if start_id not in self.nodes or end_id not in self.nodes:
            return []

        queue: List[List[str]] = [[start_id]]
        visited = {start_id}

        while queue:
            path = queue.pop(0)
            node = path[-1]

            if node == end_id:
                return path

            # We search along the influences (reverse adjacency list because start influences end)
            for neighbor in self.rev_adj_list.get(node, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = list(path)
                    new_path.append(neighbor)
                    queue.append(new_path)
        
        return []

    @classmethod
    def build_from_sandbox(cls, sandbox: SandboxSchema) -> ConceptualDependencyGraph:
        """
        Factory method to automatically construct a conceptual dependency graph from 
        a hydrated SandboxSchema.
        """
        graph = cls()

        # 1. Register Objects and their properties
        for obj in sandbox.objects:
            # Base mass property
            mass_id = f"{obj.id}.physics.mass"
            graph.add_node(DependencyNode(id=mass_id, name=f"{obj.name} Mass", node_type="property"))
            
            # Area/cross-section if relevant
            if obj.width and obj.height:
                area_id = f"{obj.id}.geometry.area"
                graph.add_node(DependencyNode(id=area_id, name=f"{obj.name} Area", node_type="property"))

        # 2. Register Environment properties
        # Gravity
        gravity_id = "environment.gravity.y"
        graph.add_node(DependencyNode(id=gravity_id, name="Gravity Acceleration", node_type="property"))
        
        # Wind/Atmosphere if active
        if sandbox.environment.atmosphere.air_density > 0:
            density_id = "environment.atmosphere.air_density"
            graph.add_node(DependencyNode(id=density_id, name="Air Density", node_type="property"))

        # 3. Register Observables
        for obs in sandbox.observables:
            graph.add_node(DependencyNode(
                id=obs.id,
                name=obs.display.label,
                node_type="observable",
                metadata={"formula": obs.derivation_formula}
            ))

        # 4. Register Relationships and link dependencies
        for rel in sandbox.relationships:
            rel_node_id = f"relationship.{rel.id}"
            graph.add_node(DependencyNode(
                id=rel_node_id,
                name=rel.name,
                node_type="relationship",
                metadata={"formula": rel.formula_latex}
            ))

            # Bind variables in the relationship to their targets
            independent_symbols = []
            
            # Map bindings to graph connections
            for binding in rel.variable_map:
                source_id = None
                if binding.observable_id:
                    source_id = binding.observable_id
                elif binding.property_path:
                    obj_part = binding.object_id if binding.object_id else "environment"
                    source_id = f"{obj_part}.{binding.property_path}"

                if source_id:
                    # Make sure source is added
                    if source_id not in graph.nodes:
                        graph.add_node(DependencyNode(id=source_id, name=binding.description, node_type="property"))
                    
                    # Connect: Relationship Node depends on Source bindings
                    graph.add_dependency(target_id=rel_node_id, depends_on_id=source_id)
                    independent_symbols.append(source_id)

            # Connect dependencies between observables if specified via the relationship
            # Typically, an observable (like 'acceleration') is explained by the relationship (like 'newtons_second_law')
            # So the observable depends on the relationship itself.
            for binding in rel.variable_map:
                if binding.observable_id:
                    obs_id = binding.observable_id
                    # Standard assumption: an observable's physical value is governed/explained by the relationship
                    # e.g., acceleration observable depends on F=ma relationship
                    graph.add_dependency(target_id=obs_id, depends_on_id=rel_node_id)

            # Handle cross-relationship dependencies (e.g. kinetic energy relationship depends on motion relationship)
            for parent_rel_id in rel.depends_on:
                parent_node_id = f"relationship.{parent_rel_id}"
                if parent_node_id in graph.nodes:
                    graph.add_dependency(target_id=rel_node_id, depends_on_id=parent_node_id)

        # 5. Connect observables governed by formulas/derivations
        for obs in sandbox.observables:
            for source in obs.source_bindings:
                source_id = None
                if source.observable_id:
                    source_id = source.observable_id
                elif source.property_path:
                    obj_part = source.object_id if source.object_id else "environment"
                    source_id = f"{obj_part}.{source.property_path}"

                if source_id and source_id in graph.nodes:
                    graph.add_dependency(target_id=obs.id, depends_on_id=source_id)

        return graph
