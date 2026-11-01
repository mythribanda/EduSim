from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Any, Optional

class Vector2D(BaseModel):
    x: float
    y: float

class Meta(BaseModel):
    id: str
    title: str
    topic: str
    simulationType: str
    difficulty: str
    version: str = "2.0"

class Units(BaseModel):
    length: str = "m"
    mass: str = "kg"
    time: str = "s"
    force: str = "N"
    energy: str = "J"

class Boundaries(BaseModel):
    enabled: bool = True
    type: str = "solid"

class CameraConfig(BaseModel):
    mode: str = "auto-fit"
    padding: float = 0.15
    allowZoom: bool = True
    allowPan: bool = True

class WorldConfig(BaseModel):
    width: float = 800
    height: float = 600
    unitSystem: str = "normalized"

class BackgroundConfig(BaseModel):
    color: str = "#0f172a"

class Environment(BaseModel):
    gravity: Vector2D
    airResistance: float = 0.005
    world: Optional[WorldConfig] = Field(default_factory=WorldConfig)
    background: Optional[BackgroundConfig] = Field(default_factory=BackgroundConfig)
    units: Optional[Units] = Field(default_factory=Units)
    camera: Optional[CameraConfig] = Field(default_factory=CameraConfig)
    boundaries: Optional[Boundaries] = Field(default_factory=Boundaries)

class Shape(BaseModel):
    type: str  # "rectangle", "circle"
    width: Optional[float] = None
    height: Optional[float] = None
    radius: Optional[float] = None

class PhysicsProps(BaseModel):
    mass: float = 1.0
    density: float = 1.0
    fixedRotation: bool = False
    affectedByGravity: bool = True
    isSensor: bool = False

class MaterialProps(BaseModel):
    friction: float = 0.5
    restitution: float = 0.5

class Collision(BaseModel):
    enabled: bool = True
    group: str = "default"

class AssetProps(BaseModel):
    enabled: bool = False
    assetId: str
    scale: float = 1.0
    rotationSync: bool = True
    anchor: Optional[Vector2D] = Field(default_factory=lambda: Vector2D(x=0.5, y=0.5))

class VisualProps(BaseModel):
    color: str
    label: Optional[str] = None
    showLabel: bool = True
    showVelocityVector: bool = False
    showTrail: bool = False
    asset: Optional[AssetProps] = None

class SimulationObject(BaseModel):
    id: str
    category: str = "physics-object"
    bodyType: str = "dynamic"
    shape: Shape
    position: Vector2D
    velocity: Optional[Vector2D] = None
    acceleration: Optional[Vector2D] = None
    rotation: float = 0.0
    initialState: Optional[Dict[str, Any]] = None
    physics: PhysicsProps = Field(default_factory=PhysicsProps)
    material: MaterialProps = Field(default_factory=MaterialProps)
    collision: Collision = Field(default_factory=Collision)
    visual: VisualProps

class Force(BaseModel):
    id: str
    type: str  # "constantForce", "drag", "friction"
    target: str
    vector: Optional[Vector2D] = None
    coefficient: Optional[float] = None
    active: bool = True

class ConstraintVisual(BaseModel):
    color: str = "#ffffff"
    lineWidth: int = 2

class Constraint(BaseModel):
    id: str
    type: str  # "rope", "spring", "link"
    bodyA: Optional[str] = None
    bodyB: Optional[str] = None
    anchor: Optional[Vector2D] = None
    length: float
    stiffness: float = 0.9
    visual: Optional[ConstraintVisual] = Field(default_factory=ConstraintVisual)

class Behavior(BaseModel):
    id: str
    type: str  # "drag", "brownian"
    targets: List[str]
    coefficient: Optional[float] = None
    active: bool = True

class FormulaVariable(BaseModel):
    path: str
    role: str # "independent", "dependent"

class FormulaBinding(BaseModel):
    id: str
    formula: str
    variables: Dict[str, FormulaVariable]

class ControlParameter(BaseModel):
    id: str
    type: str  # "slider", "toggle"
    label: str
    symbol: Optional[str] = None
    formulaReferences: List[str] = Field(default_factory=list)
    bind: str  # e.g. "objects[0].physics.mass"
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None

    @model_validator(mode='after')
    def check_type_constraints(self) -> 'ControlParameter':
        if self.type == "toggle":
            if self.min is not None or self.max is not None or self.step is not None:
                raise ValueError(f"{self.type.capitalize()}s cannot have min/max/step fields")
        elif self.type == "slider":
            if self.min is None or self.max is None:
                raise ValueError("Sliders must have min and max fields")
            if self.step is None:
                self.step = 0.1
        return self

class ControlAction(BaseModel):
    id: str
    type: str # "button"
    label: str
    action: str # "resetSimulation", "togglePause", "startSimulation"

class Controls(BaseModel):
    parameters: List[ControlParameter] = Field(default_factory=list)
    actions: List[ControlAction] = Field(default_factory=list)

class Observable(BaseModel):
    id: str
    label: str
    source: str
    precision: int = 2
    unit: Optional[str] = None

class Event(BaseModel):
    id: str
    type: str
    targets: List[str]
    response: Optional[Dict[str, Any]] = None

class Interaction(BaseModel):
    id: str
    type: str
    targets: List[str]

class ScalingConfig(BaseModel):
    mode: str = "dynamic-auto-fit"
    baseUnit: int = 50
    allowResponsiveResize: bool = True

class InteractionConfig(BaseModel):
    allowDragging: bool = True
    allowZoom: bool = True
    allowPan: bool = True

class RuntimeConfig(BaseModel):
    engine: str = "matter-js"
    renderer: str = "pixi-js"
    fps: int = 60
    scaling: ScalingConfig = Field(default_factory=ScalingConfig)
    paused: bool = False
    interaction: InteractionConfig = Field(default_factory=InteractionConfig)
    debug: bool = False
    calculated: Dict[str, float] = Field(default_factory=dict)

class SimulationDSL(BaseModel):
    meta: Meta
    environment: Environment
    objects: List[SimulationObject]
    forces: List[Force] = Field(default_factory=list)
    constraints: List[Constraint] = Field(default_factory=list)
    behaviors: List[Behavior] = Field(default_factory=list)
    interactions: List[Interaction] = Field(default_factory=list)
    formulaBindings: List[FormulaBinding] = Field(default_factory=list)
    controls: Controls = Field(default_factory=Controls)
    observables: List[Observable] = Field(default_factory=list)
    events: List[Event] = Field(default_factory=list)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    def dict(self, **kwargs):
        kwargs.update({"exclude_none": True})
        return super().dict(**kwargs)

class KnowledgeSection(BaseModel):
    relevant_formulas: List[str]
    related_concepts: List[str]
    learningObjectives: List[str] = Field(default_factory=list)

class MetadataSection(BaseModel):
    subject: str
    chapter: Optional[str] = None
    difficulty: str
    curriculum: Optional[str] = None
    simulationCategory: Optional[str] = None
    renderer: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    generated_at: Optional[str] = None

class EduSimResponse(BaseModel):
    dsl: SimulationDSL
    knowledge: KnowledgeSection
    metadata: MetadataSection

    def dict(self, **kwargs):
        kwargs.update({"exclude_none": True})
        return super().dict(**kwargs)