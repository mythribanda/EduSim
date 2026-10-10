export interface PhysicsObject {
  id?: string;
  type: string;
  position: number[];
  velocity?: number[];
  mass?: number;
  radius?: number;
  width?: number;
  height?: number;
  length?: number;
  angle?: number;
  angularVelocity?: number;
  rotation?: number;
  rotationVelocity?: number;
  orbitRadius?: number;
  orbitSpeed?: number;
  restLength?: number;
  springConstant?: number;
  damping?: number;
  physics?: {
    static?: boolean;
    restitution?: number;
    bounce?: boolean;
  };
  [key: string]: any;
}

export interface SimulationConfig {
  title: string;
  description: string;
  environment: {
    width: number;
    height: number;
    gravity: number;
    airResistance?: number;
    timeScale?: number;
  };
  objects: PhysicsObject[];
}

export function validateSimulationConfig(config: any): config is SimulationConfig {
  return (
    config &&
    typeof config.title === "string" &&
    Array.isArray(config.objects) &&
    config.environment &&
    typeof config.environment.gravity === "number"
  );
}

export type Vector = {
  x: number;
  y: number;
};

export type SimulationObject = {
  /** Unique identifier */
  id: string;
  /** Primitive type, e.g., "projectile", "pendulum", "ball" */
  type: string;
  /** Current position */
  position: Vector;
  /** Current velocity */
  velocity: Vector;
  /** Mass (kg) – optional, used for force calculations */
  mass?: number;
  /** Additional properties specific to the primitive */
  props?: Record<string, any>;
};

export type Environment = {
  /** Width and height of the canvas (pixels) */
  width: number;
  height: number;
  /** Gravity acceleration (m/s²) – defaults to 9.81 */
  gravity?: number;
  /** Global damping factor (0‑1) to simulate friction/air resistance */
  damping?: number;
};

export type SimulationState = {
  objects: SimulationObject[];
  env: Environment;
  time?: number;
  paused?: boolean;
  gravity?: number;
  timeScale?: number;
};

export interface SimulationMeta {
  id: string;
  title: string;
  topic: string;
  difficulty: "beginner" | "intermediate" | "advanced";
}

export interface SimulationEnvironment {
  gravity: { x: number; y: number };
  friction: number;
  air_resistance: number;
  background?: string;
}

export interface SimulationDSL {
  meta: SimulationMeta;
  environment: SimulationEnvironment;
  objects: any[];
  interactions: any[];
  equations?: string[];
}

export interface DSLEntity {
  id: string;
  type: string;
  mass: number | null;
}

export interface DSLInteraction {
  type: string;
  target: string;
  parameters: Record<string, any>;
}

export interface DSLVisualization {
  type: string;
}

export interface PhysicsDSL {
  simulation_type: string;
  topic: string;
  environment: {
    gravity: number;
    friction: number;
  };
  entities: DSLEntity[];
  interactions: DSLInteraction[];
  visualizations: DSLVisualization[];
  equations: string[];
}


