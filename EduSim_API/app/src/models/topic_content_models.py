from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class TutorScript(BaseModel):
    """Stage 1: AI Tutor Script with conceptual explanation and follow-ups."""
    model_config = ConfigDict(populate_by_name=True)

    explanation: str = Field(
        ...,
        description="Clear, age-appropriate conceptual breakdown of the topic"
    )
    keyPoints: List[str] = Field(
        ...,
        alias="keyPoints",
        description="Key takeaways and principles"
    )
    followUpPrompts: List[str] = Field(
        default_factory=list,
        alias="followUpPrompts",
        description="Socratic discussion and follow-up reflection questions"
    )


class FormulaItem(BaseModel):
    expression: str = Field(..., description="Mathematical formula expression, e.g. 'F = m * a'")
    description: str = Field(..., description="Description of what this equation calculates")


class FormulaVariable(BaseModel):
    name: str = Field(..., description="Variable symbol or name (e.g. 'm', 'g')")
    unit: str = Field("", description="Standard SI or relevant unit (e.g. 'kg', 'm/s^2')")
    min: float = Field(..., description="Minimum slider range value")
    max: float = Field(..., description="Maximum slider range value")
    default: float = Field(..., description="Default slider value")


class FormulaLab(BaseModel):
    """Stage 2: Formula Lab for quantitative simulation and computation."""
    model_config = ConfigDict(populate_by_name=True)

    formulas: List[FormulaItem] = Field(
        ...,
        description="List of relevant formulas and expressions"
    )
    variables: List[FormulaVariable] = Field(
        ...,
        description="Interactive variables with ranges and units"
    )
    computeExpression: str = Field(
        ...,
        alias="computeExpression",
        description="Evaluable math expression for frontend calculation"
    )


class SimulationEntity(BaseModel):
    name: str = Field(..., description="Name of the physical entity or actor")
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of visual and physical properties (e.g., mass, position, color)"
    )
    adjustable: bool = Field(
        True,
        description="Whether user can interact with or adjust this entity in the canvas"
    )


class SimulationConfig(BaseModel):
    """Stage 3: Interactive Visual Simulation Specification."""
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["static", "dynamic"] = Field(
        "dynamic",
        description="Simulation execution mode: 'static' for fixed diagrams or 'dynamic' for physics tick engine"
    )
    rendererType: str = Field(
        "mechanics-2d",
        alias="rendererType",
        description="Renderer engine type: 'mechanics-2d', 'chart', 'circuit', 'chemical-reaction', 'bio-process', etc."
    )
    entities: List[SimulationEntity] = Field(
        default_factory=list,
        description="Entities and objects rendered in the simulation scene"
    )
    rules: List[str] = Field(
        default_factory=list,
        description="Physical laws, boundary constraints, and collision rules"
    )


class TopicContent(BaseModel):
    """Combined 3-stage topic content payload."""
    model_config = ConfigDict(populate_by_name=True)

    topic_id: Optional[str] = Field(None, alias="topicId")
    topic_name: Optional[str] = Field(None, alias="topicName")
    tutorScript: TutorScript = Field(..., alias="tutorScript")
    formulaLab: Optional[FormulaLab] = Field(None, alias="formulaLab")
    simulationConfig: SimulationConfig = Field(..., alias="simulationConfig")
