/**
 * Central API Configuration for EduSim
 */

import { joinUrl } from "@/utils/urlUtils";

export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_URL || "http://localhost:8001",
  ENDPOINTS: {
    SIMULATIONS: "/api/simulations",
    GENERATE: "/api/simulations/generate",
    TUTOR: "/api/tutor",
    RAG: "/api/rag",
  },
};

export const getApiUrl = (endpoint: string) => {
  return joinUrl(API_CONFIG.BASE_URL, endpoint);
};
