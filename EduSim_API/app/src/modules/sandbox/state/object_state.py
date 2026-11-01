"""
object_state.py
===============
Runtime physics body state representation for EduSim objects.

This module acts as the authoritative backend runtime database for each object's 
live physical attributes (positions, velocities, accelerations, forces) and 
interactive properties (selection, hover, collision lists).

It computes derived attributes (such as linear momentum or kinetic energy) directly 
on demand to support educational formulas.
"""


from __future__ import annotations
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class StateVector2D(BaseModel):
    """Simple 2D coordinate or physics vector representation."""
    x: float = 0.0
    y: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}


class ObjectRuntimeState(BaseModel):
    """
    Live runtime state parameters tracking physical state changes, 
    forces, and UI markers.
    """
    id: str = Field(..., description="Target SandboxObject ID reference")
    
    # Position and Motion vectors
    position: StateVector2D = Field(default_factory=StateVector2D)
    velocity: StateVector2D = Field(default_factory=StateVector2D)
    acceleration: StateVector2D = Field(default_factory=StateVector2D)
    
    # Rotational parameters
    angle: float = Field(default=0.0, description="Rotation in radians")
    angular_velocity: float = Field(default=0.0, description="Angular speed rad/s")
    angular_acceleration: float = Field(default=0.0, description="Angular accel rad/s^2")
    
    # Active forces & torque
    net_force: StateVector2D = Field(default_factory=StateVector2D)
    torque: float = Field(default=0.0, description="Rotational force (N*m)")
    
    # Inertial / constant parameters loaded/synchronized from body definition
    mass: float = Field(default=1.0, description="Live mass in kg")
    inertia: float = Field(default=1.0, description="Moment of inertia")
    
    # Simulation / engine states
    is_static: bool = Field(default=False)
    is_sleeping: bool = Field(default=False)
    is_sensor: bool = Field(default=False)
    
    # Visual / UI states
    is_visible: bool = Field(default=True)
    is_selected: bool = Field(default=False)
    is_hovered: bool = Field(default=False)
    
    # Collision contacts list (other body IDs currently in contact)
    colliding_with: List[str] = Field(default_factory=list)

    # --- Derived Physics Calculations ---

    def get_kinetic_energy(self) -> float:
        """Returns translational kinetic energy: KE = 0.5 * m * v^2."""
        if self.is_static:
            return 0.0
        v_sq = (self.velocity.x ** 2) + (self.velocity.y ** 2)
        return 0.5 * self.mass * v_sq

    def get_rotational_energy(self) -> float:
        """Returns rotational kinetic energy: RE = 0.5 * I * omega^2."""
        if self.is_static:
            return 0.0
        return 0.5 * self.inertia * (self.angular_velocity ** 2)

    def get_momentum_vector(self) -> StateVector2D:
        """Returns translational momentum vector: p = m * v."""
        if self.is_static:
            return StateVector2D(x=0.0, y=0.0)
        return StateVector2D(
            x=self.mass * self.velocity.x,
            y=self.mass * self.velocity.y
        )

    def get_potential_energy(self, gravity_y: float, reference_y: float = 720.0) -> float:
        """
        Returns gravitational potential energy: PE = m * g * h.
        h is calculated as distance above the baseline canvas height reference_y.
        In canvas space, positive Y points downwards, so height is (reference_y - position.y).
        """
        if self.is_static:
            return 0.0
        # h (meters) = (reference_y - position.y) / 100.0 (where 100 px = 1 m)
        h = max(0.0, (reference_y - self.position.y) / 100.0)
        return self.mass * abs(gravity_y) * h

    def sync_from_physics_engine(
        self,
        pos_x: float, pos_y: float,
        vel_x: float, vel_y: float,
        accel_x: float, accel_y: float,
        angle: float,
        ang_vel: float,
        ang_accel: float = 0.0,
        force_x: float = 0.0, force_y: float = 0.0,
        torque: float = 0.0,
        is_sleeping: bool = False,
        colliding_with: Optional[List[str]] = None
    ) -> None:
        """
        Hydrates live runtime values from Matter.js frame sync payload.
        """
        self.position.x = pos_x
        self.position.y = pos_y
        self.velocity.x = vel_x
        self.velocity.y = vel_y
        self.acceleration.x = accel_x
        self.acceleration.y = accel_y
        
        self.angle = angle
        self.angular_velocity = ang_vel
        self.angular_acceleration = ang_accel
        
        self.net_force.x = force_x
        self.net_force.y = force_y
        self.torque = torque
        
        self.is_sleeping = is_sleeping
        if colliding_with is not None:
            self.colliding_with = colliding_with
