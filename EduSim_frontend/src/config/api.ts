/**
 * Central API Configuration for EduSim
 */

import { joinUrl } from "@/utils/urlUtils";

const rawBaseUrl = import.meta.env.VITE_API_URL || "http://localhost:8001";
// Sanitize BASE_URL to prevent trailing /api or trailing slash from duplicating endpoints (e.g. /api/api/...)
const sanitizedBaseUrl = rawBaseUrl.replace(/\/api\/?$/, "").replace(/\/+$/, "");

export const API_CONFIG = {
  BASE_URL: sanitizedBaseUrl,
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
