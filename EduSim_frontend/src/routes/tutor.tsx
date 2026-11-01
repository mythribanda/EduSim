/**
 * Tutor Page Route
 * AI-powered physics tutor for students
 */

import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import ChatWorkspace, { Message } from "@/components/tutor/ChatWorkspace";
import { ChatHistorySidebar } from "@/components/tutor/ChatHistorySidebar";
import { TutorService, TutorAnalysisResponse, ChatMessage } from "@/services/TutorService";
import { useSimulationStore } from "@/store/useSimulationStore";
import { useCurriculumTopic } from "@/hooks/useCurriculumTopic";
import { toast } from "sonner";

// Define search params for the route
export const Route = createFileRoute("/tutor")({
  component: TutorPage,
  validateSearch: (search: Record<string, unknown>) => ({
    subject: typeof search.subject === "string" ? search.subject : undefined,
    class_name: typeof search.class_name === "string" ? search.class_name : undefined,
    chapter: typeof search.chapter === "string" ? search.chapter : undefined,
    topic: typeof search.topic === "string" ? search.topic : undefined,
    prompt: typeof search.prompt === "string" ? search.prompt : undefined,
  }),
});

function TutorPage() {
  const searchParams = Route.useSearch();
  const [tutorData, setTutorData] = useState<TutorAnalysisResponse["data"] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [messages, setMessages] = useState<Message[] | undefined>(undefined);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  const { setTutorResponse } = useSimulationStore();

  const abortControllerRef = useRef<AbortController | undefined>(undefined);
  const isAnalyzingRef = useRef<boolean>(false);
  const isMountedRef = useRef<boolean>(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      setTimeout(() => {
        if (!isMountedRef.current) {
          abortControllerRef.current?.abort();
        }
      }, 150);
    };
  }, []);

  const { data: topicContent, loading: topicLoading, fetchTopic } = useCurriculumTopic();

  // Load topic content from search params
  useEffect(() => {
    if (searchParams.subject && searchParams.class_name && searchParams.chapter) {
      // Fetch topic content
      fetchTopic(
        searchParams.subject,
        searchParams.class_name,
        searchParams.chapter,
        searchParams.topic,
      );
    }
  }, [searchParams, fetchTopic]);

  const handleAnalyze = async (query: string, history?: ChatMessage[]) => {
    // Prevent duplicate execution while an analysis request is already in-flight
    if (isAnalyzingRef.current) {
      console.warn("[TutorPage] Analysis already in progress. Ignoring duplicate call.");
      return;
    }
    isAnalyzingRef.current = true;

    // Cancel previous request if still pending
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);
    try {
      const contextArgs = {
        class_name: searchParams.class_name,
        subject: searchParams.subject,
        chapter: searchParams.chapter,
        topic: searchParams.topic,
      };
      const response = await TutorService.analyzeQuery(
        query,
        contextArgs,
        history,
        activeSessionId,
        controller.signal,
      );
      if (response.success) {
        setTutorData(response.data);
        setTutorResponse(response.data); // Sync with store for FAB

        if (response.session_id && response.session_id !== activeSessionId) {
          setActiveSessionId(response.session_id);
          setRefreshTrigger((prev) => prev + 1);
        }
      } else {
        setError("Failed to analyze question.");
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // request was aborted; do nothing
      } else {
        console.error("Tutor analyze error:", err);
        setError(
          err instanceof Error
            ? err.message
            : "An error occurred while contacting the tutor service.",
        );
      }
    } finally {
      isAnalyzingRef.current = false;
      setIsLoading(false);
      abortControllerRef.current = undefined;
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    setIsLoading(true);
    try {
      const res = await TutorService.getSessionMessages(sessionId);
      if (res.success && res.session) {
        setActiveSessionId(sessionId);
        const sessionData = res.session as {
          messages?: Array<{ id: string; role: string; content: string; created_at: string }>;
        };
        const formatted = (sessionData.messages || []).map((m) => {
          const date = new Date(m.created_at);
          const timeStr = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
          return {
            id: m.id,
            role: (m.role === "assistant" ? "ai" : "user") as "user" | "ai",
            content: m.content,
            timestamp: timeStr,
          };
        });
        setMessages(formatted);
      }
    } catch (err) {
      toast.error("Failed to load conversation history");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setTutorData(null);
  };

  const compactTopicContext = topicContent
    ? {
        subject: topicContent.subject,
        className: topicContent.class_name,
        chapter: topicContent.chapter,
      }
    : {
        subject: searchParams.subject,
        className: searchParams.class_name,
        chapter: searchParams.chapter,
      };

  const tutorStateMessage = topicLoading
    ? "Searching textbook content..."
    : isLoading
      ? "Generating explanation..."
      : null;

  return (
    <div className="relative w-full h-full overflow-hidden text-foreground bg-background">
      {tutorStateMessage && (
        <div className="absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded-full border border-white/10 bg-black/40 px-4 py-2 text-xs font-semibold tracking-[0.22em] text-muted-foreground backdrop-blur-md">
          {tutorStateMessage}
        </div>
      )}

      <div className="relative mx-auto flex h-full w-full max-w-[100rem] items-stretch">
        <div
          className={`
          ${isHistoryOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
          fixed lg:relative inset-y-0 left-0 z-[80] lg:z-30 transition-transform duration-300 lg:transition-none flex shrink-0
        `}
        >
          <ChatHistorySidebar
            activeSessionId={activeSessionId}
            onSelectSession={(sessionId) => {
              handleSelectSession(sessionId);
              setIsHistoryOpen(false);
            }}
            onNewChat={() => {
              handleNewChat();
              setIsHistoryOpen(false);
            }}
            refreshTrigger={refreshTrigger}
          />
        </div>

        {/* Backdrop for mobile */}
        {isHistoryOpen && (
          <div
            onClick={() => setIsHistoryOpen(false)}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[70] lg:hidden"
          />
        )}

        <div className="flex w-full items-stretch flex-1 min-w-0">
          <ChatWorkspace
            onSend={handleAnalyze}
            aiResponse={
              tutorData
                ? ((tutorData as Record<string, unknown>).explanation as string) ||
                  ((tutorData as Record<string, unknown>).ai_explanation as string) ||
                  null
                : null
            }
            error={error}
            onClearError={() => setError(null)}
            loading={isLoading || topicLoading}
            initialPrompt={
              searchParams.prompt ||
              (searchParams.topic ? `Explain ${searchParams.topic}` : undefined)
            }
            focusInput={Boolean(searchParams.prompt || searchParams.topic)}
            topicTitle={searchParams.topic || searchParams.chapter}
            topicContext={compactTopicContext}
            messages={messages}
            onNewChat={handleNewChat}
            toggleHistory={() => setIsHistoryOpen((prev) => !prev)}
          />
        </div>
      </div>
    </div>
  );
}
