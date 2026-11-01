import { API_CONFIG, getApiUrl } from "@/config/api";
import { joinUrl } from "@/utils/urlUtils";
import { useAuthStore } from "@/store/useAuthStore";

export interface TutorAnalysisResponse {
  success: boolean;
  data: {
    queryType: string;
    concepts: string[];
    formulas: Array<{
      formula: string;
      name: string;
      topic: string;
      meaning: string;
    }>;
    explanation: string;
    ragContent: Array<{
      title: string;
      content: string;
    }>;
  };
}

export interface TutorSession {
  id: string;
  topic: string;
  created_at: string;
  is_active: boolean;
  [key: string]: unknown;
}

export interface TutorSessionDetails {
  id: string;
  topic?: string;
  messages?: Array<{ id: string; role: string; content: string; created_at: string }>;
  [key: string]: unknown;
}

const API_BASE = getApiUrl("");

export interface ChatMessage {
  role: "user" | "assistant" | "ai";
  content: string;
}

/**
 * Classifies HTTP response errors according to status code and body content.
 */
export async function classifyResponseError(response: Response): Promise<string> {
  const status = response.status;
  if (status === 401) {
    return "Session expired, please log in again";
  }
  if (status === 402) {
    return "OpenRouter payment required (HTTP 402). Please add credits to your OpenRouter account.";
  }
  if (status >= 500 && status <= 599) {
    try {
      const data = await response.clone().json();
      const message = data?.message || data?.detail || "Internal server error";
      const requestId = data?.request_id || data?.requestId;
      if (requestId) {
        return `${message} (Request ID: ${requestId})`;
      }
      return message;
    } catch {
      const text = await response
        .clone()
        .text()
        .catch(() => "");
      return text || `Internal server error (${status})`;
    }
  }
  if (status >= 400 && status < 500) {
    try {
      const data = await response.clone().json();
      return data?.detail || data?.message || data?.error || `Request failed with status ${status}`;
    } catch {
      const text = await response
        .clone()
        .text()
        .catch(() => "");
      return text || `Request failed with status ${status}`;
    }
  }
  return `Request failed with status ${status}`;
}

/**
 * Classifies client-side errors (network unreachable, timeouts, user aborts).
 */
export function classifyNetworkOrAbortError(
  err: unknown,
  baseUrl: string = API_CONFIG.BASE_URL,
  isTimeout: boolean = false,
): string {
  if (isTimeout) {
    return "The AI took too long to answer. Local models can be slow on the first question; try again.";
  }
  if (
    (err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.name === "AbortError")
  ) {
    return "Request cancelled";
  }
  if (
    err instanceof TypeError ||
    (err instanceof Error &&
      (err.name === "TypeError" ||
        err.message.toLowerCase().includes("failed to fetch") ||
        err.message.toLowerCase().includes("fetch failed") ||
        err.message.toLowerCase().includes("networkerror") ||
        err.message.toLowerCase().includes("network request failed") ||
        err.message.toLowerCase().includes("load failed")))
  ) {
    console.error("[TutorService] Network error reaching backend:", err);
    return `Can't reach the EduSim server at ${baseUrl}. Is the backend running?`;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return String(err);
}

/**
 * Universal error classifier for responses, exceptions, and timeouts.
 */
export async function classifyError(
  errorOrResponse: unknown,
  options?: { baseUrl?: string; isTimeout?: boolean },
): Promise<string> {
  const baseUrl = options?.baseUrl || API_CONFIG.BASE_URL;
  if (typeof Response !== "undefined" && errorOrResponse instanceof Response) {
    return classifyResponseError(errorOrResponse);
  }
  return classifyNetworkOrAbortError(errorOrResponse, baseUrl, options?.isTimeout);
}

export function isNetworkFailure(err: unknown): boolean {
  if (err instanceof TypeError) {
    return true;
  }
  if (err instanceof Error) {
    if (err.name === "TypeError") return true;
    const msg = err.message.toLowerCase();
    if (
      msg.includes("failed to fetch") ||
      msg.includes("fetch failed") ||
      msg.includes("networkerror") ||
      msg.includes("network request failed") ||
      msg.includes("load failed")
    ) {
      return true;
    }
  }
  return false;
}

export function combineSignals(signals: (AbortSignal | undefined | null)[]): {
  signal: AbortSignal;
  cleanup: () => void;
} {
  const validSignals = signals.filter((s): s is AbortSignal => Boolean(s));

  const abortSignalWithAny =
    typeof AbortSignal !== "undefined"
      ? (AbortSignal as unknown as { any?: (signals: Iterable<AbortSignal>) => AbortSignal })
      : undefined;

  if (abortSignalWithAny && typeof abortSignalWithAny.any === "function") {
    return {
      signal: abortSignalWithAny.any(validSignals),
      cleanup: () => {},
    };
  }

  const controller = new AbortController();
  const onAbort = () => controller.abort();

  for (const sig of validSignals) {
    if (sig.aborted) {
      controller.abort();
      return { signal: controller.signal, cleanup: () => {} };
    }
    sig.addEventListener("abort", onAbort, { once: true });
  }

  const cleanup = () => {
    for (const sig of validSignals) {
      sig.removeEventListener("abort", onAbort);
    }
  };

  return { signal: controller.signal, cleanup };
}

export function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      return reject(signal.reason || new DOMException("Request cancelled", "AbortError"));
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(signal.reason || new DOMException("Request cancelled", "AbortError"));
      },
      { once: true },
    );
  });
}

/**
 * Ensures we have a valid auth token before making API calls.
 * If the current token is expired, attempts a refresh via checkAuth.
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  let token = useAuthStore.getState().token;

  if (token) {
    // Quick check if token is expired by decoding the payload
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const expMs = (payload.exp || 0) * 1000;
      const nowMs = Date.now();
      // If token expires within 60 seconds, proactively refresh
      if (expMs - nowMs < 60_000) {
        console.log("[TutorService] Token expiring soon, refreshing...");
        const refreshed = await useAuthStore.getState().checkAuth();
        if (refreshed) {
          token = useAuthStore.getState().token;
        } else {
          console.warn("[TutorService] Token refresh failed, proceeding without auth");
          token = null;
        }
      }
    } catch {
      // If we can't parse the token, just use it as-is
    }
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else {
    console.warn("[TutorService] No auth token available — chat will not be saved");
  }

  return headers;
}

// Module-level in-flight request deduplication to prevent duplicate concurrent network requests
let activeAnalyzePromise: Promise<TutorAnalysisResponse & { session_id?: string }> | null = null;
let activeAnalyzeQuery: string | null = null;

export const TutorService = {
  analyzeQuery: async (
    query: string,
    context?: { class_name?: string; subject?: string; chapter?: string; topic?: string },
    history?: ChatMessage[],
    sessionId?: string | null,
    signal?: AbortSignal,
    requestId?: string,
  ): Promise<TutorAnalysisResponse & { session_id?: string }> => {
    const trimmedQuery = query.trim();

    // Prevent duplicate in-flight analyze calls for the exact same query
    if (activeAnalyzePromise && activeAnalyzeQuery === trimmedQuery) {
      console.warn(
        `[TutorService] Duplicate in-flight analyzeQuery detected for "${trimmedQuery}". Reusing active request.`,
      );
      return activeAnalyzePromise;
    }

    const reqId = requestId || `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    const body = {
      query: trimmedQuery,
      class_name: context?.class_name,
      subject: context?.subject,
      chapter: context?.chapter,
      topic: context?.topic,
      history: history
        ? history.map((h) => ({
            role: h.role === "ai" ? "assistant" : h.role,
            content: h.content,
          }))
        : undefined,
      session_id: sessionId || undefined,
      request_id: reqId,
    };

    activeAnalyzeQuery = trimmedQuery;

    const execute = async () => {
      // 120s timeout controller combined with caller-provided signal
      const timeoutController = new AbortController();
      let isTimedOut = false;
      const timeoutTimer = setTimeout(() => {
        isTimedOut = true;
        timeoutController.abort();
      }, 120_000);

      const { signal: combinedSignal, cleanup: cleanupSignals } = combineSignals([
        signal,
        timeoutController.signal,
      ]);

      const doFetch = async () => {
        const headers = await getAuthHeaders();
        headers["X-Request-ID"] = reqId;

        return fetch(joinUrl(API_BASE, "/api/tutor/analyze"), {
          method: "POST",
          headers,
          body: JSON.stringify(body),
          signal: combinedSignal,
        });
      };

      try {
        let response: Response;
        try {
          response = await doFetch();
        } catch (firstErr: unknown) {
          // If network-level failure only (not user abort/timeout), retry once after 1.5s
          if (isNetworkFailure(firstErr) && !isTimedOut && !signal?.aborted) {
            console.warn(
              "[TutorService] Network failure encountered. Retrying in 1.5s...",
              firstErr,
            );
            await delay(1500, combinedSignal);
            response = await doFetch();
          } else {
            throw firstErr;
          }
        }

        if (!response.ok) {
          const errorMsg = await classifyResponseError(response);
          throw new Error(errorMsg);
        }

        return await response.json();
      } catch (err: unknown) {
        if (isTimedOut) {
          throw new Error(
            "The AI took too long to answer. Local models can be slow on the first question; try again.",
          );
        }
        if (
          (err instanceof DOMException && err.name === "AbortError") ||
          (err instanceof Error && err.name === "AbortError")
        ) {
          // Preserve AbortError so caller can identify user-initiated cancellation
          const abortEx = new DOMException("Request cancelled", "AbortError");
          throw abortEx;
        }
        if (isNetworkFailure(err)) {
          const msg = classifyNetworkOrAbortError(err, API_CONFIG.BASE_URL, false);
          throw new Error(msg);
        }
        throw err instanceof Error ? err : new Error(String(err));
      } finally {
        clearTimeout(timeoutTimer);
        cleanupSignals();
      }
    };

    activeAnalyzePromise = (async () => {
      try {
        return await execute();
      } finally {
        activeAnalyzePromise = null;
        activeAnalyzeQuery = null;
      }
    })();

    return activeAnalyzePromise;
  },

  getSessions: async (): Promise<{ success: boolean; sessions: TutorSession[] }> => {
    const headers = await getAuthHeaders();
    const response = await fetch(joinUrl(API_BASE, "/api/persistence/tutor/sessions"), {
      method: "GET",
      headers,
    });
    if (!response.ok) {
      throw new Error("Failed to fetch tutor sessions");
    }
    return response.json();
  },

  getSessionMessages: async (
    sessionId: string,
  ): Promise<{ success: boolean; session: TutorSessionDetails }> => {
    const headers = await getAuthHeaders();
    const response = await fetch(joinUrl(API_BASE, `/api/persistence/tutor/session/${sessionId}`), {
      method: "GET",
      headers,
    });
    if (!response.ok) {
      throw new Error("Failed to fetch session messages");
    }
    return response.json();
  },

  deleteSession: async (sessionId: string): Promise<{ success: boolean; message: string }> => {
    const headers = await getAuthHeaders();
    const response = await fetch(joinUrl(API_BASE, `/api/persistence/tutor/session/${sessionId}`), {
      method: "DELETE",
      headers,
    });
    if (!response.ok) {
      throw new Error("Failed to delete tutor session");
    }
    return response.json();
  },
};
