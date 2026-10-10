import { SimulationDSL } from "@/types/simulation";
import { getApiUrl } from "@/config/api";
import { joinUrl } from "@/utils/urlUtils";

/**
 * Default timeout for agent simulation requests
 * Autonomous AI Simulation Generation Agent Service
 *
 * Handles communication with the backend agent endpoints for:
 * - Prompt analysis and topic detection
 * - Context retrieval from RAG system
 * - AI-powered Physics DSL generation
 * - Streaming generation with progress updates
 */

// =========================================================
// Simulation Response Types
// =========================================================

export interface SimulationTopicInfo {
  topic: string;
  subject: "physics" | "chemistry" | "astronomy" | "biology" | "mathematics";
  subtopic?: string;
  complexity: "beginner" | "medium" | "advanced";
}

export interface SimulationContextInfo {
  topic: string;
  formulas: string[];
  constants: string[];
  laws: string[];
  definitions: string[];
  sources: Array<{
    source: string;
    page: string | number;
  }>;
}

export interface AgentGeneratedSimulation {
  id: string;
  title: string;
  description: string;
  topic: SimulationTopicInfo;
  /** Physics DSL JSON — the core output of the compiler pipeline */
  dsl: SimulationDSL;
  formula?: string;
  formula_explanation?: string;
  formulas: string[];
  learning_objectives: string[];
  related_concepts: string[];
  context: SimulationContextInfo;
  timestamp: string;
  generation_stages: string[];
  intent?: {
    simulation_type: string;
    label: string;
    confidence: number;
    keywords: string[];
  };
}

export interface AgentGenerateRequest {
  prompt: string;
  topic?: string;
  complexity?: "beginner" | "medium" | "advanced";
  include_answers?: boolean;
  streaming?: boolean;
}

export interface AgentStreamProgress {
  stage: string;
  progress?: number;
  message?: string;
  id?: string;
  error?: string;
  type?: string;
}

type AgentProgressCallback = (progress: AgentStreamProgress) => void;
type AgentCompleteCallback = (simulation: AgentGeneratedSimulation) => void;

const DEFAULT_TIMEOUT_MS = 60000;

function normalizeAgentSimulation(payload: any): AgentGeneratedSimulation {
  const dsl = payload?.dsl || payload?.simulation?.dsl || payload?.scene || payload?.simulation || {};
  const title =
    payload?.title ||
    payload?.simulation?.title ||
    dsl?.meta?.title ||
    payload?.metadata?.title ||
    "AI Generated Simulation";
  const description =
    payload?.description ||
    payload?.simulation?.description ||
    dsl?.meta?.description ||
    dsl?.meta?.explanation ||
    payload?.reasoning ||
    "";

  return {
    id: payload?.id || globalThis.crypto?.randomUUID?.() || `${Date.now()}`,
    title,
    description,
    topic: payload?.topic || {
      topic: payload?.simulation_type || dsl?.meta?.topic || title,
      subject: payload?.metadata?.subject || "physics",
      complexity: payload?.metadata?.difficulty || "medium",
    },
    dsl,
    formula: payload?.formula,
    formula_explanation: payload?.formula_explanation || payload?.reasoning || "",
    formulas: payload?.formulas || payload?.knowledge?.relevant_formulas || [],
    learning_objectives: payload?.learning_objectives || [],
    related_concepts: payload?.related_concepts || payload?.knowledge?.related_concepts || [],
    context: payload?.context || {
      topic: payload?.metadata?.topic || title,
      formulas: payload?.formulas || [],
      constants: [],
      laws: [],
      definitions: [],
      sources: [],
    },
    timestamp: payload?.timestamp || new Date().toISOString(),
    generation_stages: payload?.generation_stages || [],
    intent: payload?.intent,
  };
}

// =========================================================
// Service Class
// =========================================================

class AgentSimulationService {
  private apiBaseUrl: string;

  constructor() {
    this.apiBaseUrl = getApiUrl("");
  }

  /**
   * Generate a simulation using the autonomous agent (non-streaming).
   * Returns a Physics DSL JSON object — not HTML.
   */
  async generate(
    prompt: string,
    complexity?: string,
    topic?: string,
  ): Promise<AgentGeneratedSimulation> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    try {
      const response = await fetch(joinUrl(this.apiBaseUrl, "/api/simulations/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          topic,
          complexity,
          include_answers: true,
          streaming: false,
        } as AgentGenerateRequest),
        signal: controller.signal,
      });

      const data = (await response.json()) as AgentGeneratedSimulation | { detail?: string };
      if (!response.ok) {
        throw new Error((data as { detail?: string }).detail || "Agent generation failed");
      }

      return normalizeAgentSimulation(data);
    } finally {
      window.clearTimeout(timeout);
    }
  }

  /**
   * Generate a simulation with streaming progress updates.
   *
   * Emits SSE events at each stage:
   * - started:  Initial event with simulation ID
   * - progress: Stage updates
   * - complete: Final event with full simulation (DSL)
   * - error:    Error event if generation fails
   */
  async generateStream(
    prompt: string,
    onProgress: AgentProgressCallback,
    onComplete: AgentCompleteCallback,
    complexity?: string,
    topic?: string,
  ): Promise<void> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
    let completed = false;

    try {
      const response = await fetch(joinUrl(this.apiBaseUrl, "/api/simulations/generate-stream"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          topic,
          complexity,
          include_answers: true,
          streaming: true,
        } as AgentGenerateRequest),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error("Failed to start streaming generation");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines[lines.length - 1];

          for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            if (line.startsWith("event:")) {
              const eventType = line.replace("event:", "").trim();
              const dataLine = lines[++i];

              if (dataLine?.startsWith("data:")) {
                const dataStr = dataLine.replace("data:", "").trim();
                try {
                  const data = JSON.parse(dataStr);

                  if (eventType === "progress" || eventType === "started") {
                    onProgress(data as AgentStreamProgress);
                  } else if (eventType === "complete") {
                    completed = true;
                    onComplete(normalizeAgentSimulation(data));
                  } else if (eventType === "error") {
                    onProgress(data as AgentStreamProgress);
                  } else if (eventType === "done") {
                    break;
                  }
                } catch (e) {
                  console.error("Failed to parse SSE data:", dataStr, e);
                }
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      if (!completed) {
        throw new Error("Streaming generation finished without a completed simulation payload");
      }
    } finally {
      window.clearTimeout(timeout);
    }
  }

  /** Client-side subject detection for UI labelling */
  analyzePrompt(prompt: string): SimulationTopicInfo {
    const promptLower = prompt.toLowerCase();

    const subjects: Record<string, string[]> = {
      physics: [
        "motion",
        "force",
        "velocity",
        "gravity",
        "wave",
        "light",
        "projectile",
        "pendulum",
      ],
      chemistry: ["molecule", "atom", "bond", "reaction", "element"],
      astronomy: ["planet", "star", "galaxy", "orbit", "space"],
      biology: ["cell", "dna", "organism", "photosynthesis"],
      mathematics: ["function", "graph", "equation", "algebra"],
    };

    let subject: SimulationTopicInfo["subject"] = "physics";
    for (const [subj, keywords] of Object.entries(subjects)) {
      if (keywords.some((kw) => promptLower.includes(kw))) {
        subject = subj as SimulationTopicInfo["subject"];
        break;
      }
    }

    return {
      topic: `${subject.charAt(0).toUpperCase() + subject.slice(1)} Simulation`,
      subject,
      complexity: "medium",
    };
  }

  async reportRuntimeError(simulationId: string | null, payload: unknown): Promise<void> {
    try {
      await fetch(
        joinUrl(this.apiBaseUrl, `/api/simulations/agent/error-report${simulationId ? `?simulation_id=${encodeURIComponent(simulationId)}` : ""}`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
    } catch (e) {
      console.error("Failed to report runtime error", e);
    }
  }

  /** Ping backend health check */
  async ping(): Promise<{ success: boolean; message: string }> {
    try {
      const response = await fetch(joinUrl(this.apiBaseUrl, "/"));
      return await response.json();
    } catch (e) {
      return { success: false, message: "Backend unreachable" };
    }
  }
}

export const agentSimulationService = new AgentSimulationService();
