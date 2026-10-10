import { getApiUrl } from "@/config/api";
import { joinUrl } from "@/utils/urlUtils";

export interface SimulationResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  detail?: string;
}

class PhysicsSimulationApi {
  private apiBaseUrl: string;

  constructor() {
    this.apiBaseUrl = getApiUrl("");
  }

  async searchRag(
    query: string,
    subject?: string,
    chapter?: string,
  ): Promise<SimulationResponse<{ chunks: { text: string }[] }>> {
    try {
      const response = await fetch(joinUrl(this.apiBaseUrl, "/api/rag/search"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query,
          subject: subject || "physics",
          chapter: chapter || "",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        return { success: false, error: data.detail || "RAG Search API Error" };
      }

      return {
        success: true,
        data: { chunks: data.chunks || [] },
      };
    } catch (error) {
      return { success: false, error: "Network Error" };
    }
  }
}

export const physicsSimulationApi = new PhysicsSimulationApi();

