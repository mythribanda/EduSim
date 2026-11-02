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
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const token = typeof window !== "undefined" ? window.localStorage.getItem("token") : null;
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const bodyPayload: Record<string, any> = {
        query,
        chapter: chapter || "",
      };
      if (subject) {
        bodyPayload.subject = subject;
      }

      const response = await fetch(joinUrl(this.apiBaseUrl, "/api/rag/search"), {
        method: "POST",
        headers,
        body: JSON.stringify(bodyPayload),
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

