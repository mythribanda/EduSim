// ============================================================================
// Stage 1: TutorScript
// ============================================================================
export interface TutorScript {
  /** Clear, age-appropriate conceptual explanation */
  explanation: string;
  /** Bullet points highlighting core principles and takeaways */
  keyPoints: string[];
  /** Socratic questions or prompts to test comprehension and encourage exploration */
  followUpPrompts: string[];
}

// ============================================================================
// Stage 2: FormulaLab (Omitted if the topic has no quantitative formula)
// ============================================================================
export interface FormulaItem {
  /** Mathematical notation / LaTeX / formula string (e.g. "F = m * a") */
  expression: string;
  /** Plain English explanation of what this equation calculates */
  description: string;
}

export interface FormulaVariable {
  /** Variable symbol or identifier (e.g. "m", "v", "r") */
  name: string;
  /** Standard measurement unit (e.g. "kg", "m/s", "N", "rad/s") */
  unit: string;
  /** Lower bound for interactive slider/input */
  min: number;
  /** Upper bound for interactive slider/input */
  max: number;
  /** Initial/default value */
  default: number;
}

export interface FormulaLab {
  /** Primary formula and derived or related expressions */
  formulas: FormulaItem[];
  /** Configurable parameters and variables */
  variables: FormulaVariable[];
  /** Evaluable JS/Python math expression for live numerical calculation (e.g. "(m * v**2) / r") */
  computeExpression: string;
}

// ============================================================================
// Stage 3: SimulationConfig
// ============================================================================
export type SimulationMode = "static" | "dynamic";

export interface SimulationEntity {
  /** Human-readable identifier for the entity (e.g., "cart", "pendulum_bob", "inclined_plane") */
  name: string;
  /** Initial physical/visual properties (e.g., { mass: 5, x: 100, y: 250, color: "#3B82F6" }) */
  properties: Record<string, any>;
  /** Whether the user can drag, scale, or tweak this entity in the canvas */
  adjustable: boolean;
}

export interface SimulationConfig {
  /** "static" (diagram/step-based) or "dynamic" (physics tick loop) */
  mode: SimulationMode;
  /** Target rendering engine: "mechanics-2d" | "chart" | "circuit" | "chemical-reaction" | "bio-process" | string */
  rendererType: string;
  /** Interactive objects and actors in the scene */
  entities: SimulationEntity[];
  /** Governing physical rules, boundary conditions, or constraints */
  rules: string[];
}

// ============================================================================
// Unified Topic Content Wrapper
// ============================================================================
export interface TopicContent {
  topicId?: string;
  topicName?: string;
  tutorScript: TutorScript;
  formulaLab?: FormulaLab | null;
  simulationConfig: SimulationConfig;
}
