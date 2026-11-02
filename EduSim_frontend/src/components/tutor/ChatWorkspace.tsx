import React, { useEffect, useRef, useState } from "react";
import { ChatBubble } from "./ChatBubble";
import { GeneratingLoader } from "./GeneratingLoader";
import ChatInput from "./ChatInput";
import { TutorHeader } from "./TutorHeader";
import { ChatMessage } from "@/services/TutorService";
import { Atom, Beaker, Leaf, Calculator, Landmark, Code2, Sparkles } from "lucide-react";

export type Message = {
  id: string;
  role: "user" | "ai";
  content: string;
  timestamp: string;
  isError?: boolean;
};

interface Props {
  onSend: (text: string, history?: ChatMessage[]) => void;
  aiResponse?: string | null;
  error?: string | null;
  onClearError?: () => void;
  loading?: boolean;
  initialPrompt?: string | null;
  focusInput?: boolean;
  topicTitle?: string;
  topicContext?: {
    subject?: string;
    className?: string;
    chapter?: string;
  };
  messages?: Message[];
  onNewChat?: () => void;
  toggleHistory?: () => void;
}

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function ChatWorkspace({
  onSend,
  aiResponse,
  error,
  onClearError,
  loading,
  initialPrompt,
  focusInput,
  topicTitle,
  topicContext,
  messages: propsMessages,
  onNewChat,
  toggleHistory,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);

  useEffect(() => {
    if (propsMessages !== undefined) {
      setMessages(propsMessages);
    }
  }, [propsMessages]);

  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastAiResponseRef = useRef<string | null>(null);
  const lastErrorRef = useRef<string | null>(null);
  const executedPromptsRef = useRef<Set<string>>(new Set());

  const send = (text: string) => {
    if (loading) {
      console.warn("[ChatWorkspace] Send ignored because tutor is currently loading.");
      return;
    }
    const newMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: formatTime(new Date()),
    };
    setMessages((current) => [...current, newMsg]);
    setPendingPrompt(text);

    const history: ChatMessage[] = messages
      .filter((m) => !m.isError)
      .map((m) => ({
        role: m.role,
        content: m.content,
      }));
    onSend(text, history);
  };

  useEffect(() => {
    if (!initialPrompt || !initialPrompt.trim()) return;
    const trimmed = initialPrompt.trim();
    if (executedPromptsRef.current.has(trimmed)) {
      return;
    }
    executedPromptsRef.current.add(trimmed);
    send(trimmed);
  }, [initialPrompt]);

  const handleRegenerate = () => {
    if (loading) return;
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) {
      send(lastUser.content);
    }
  };

  const handleRetry = (queryToRetry?: string) => {
    if (loading) return;
    const query = queryToRetry || [...messages].reverse().find((m) => m.role === "user")?.content;
    if (query) {
      // Remove any error messages before retrying
      setMessages((current) => current.filter((m) => !m.isError));
      lastErrorRef.current = null;
      onClearError?.();
      setPendingPrompt(query);
      const history: ChatMessage[] = messages
        .filter((m) => !m.isError)
        .map((m) => ({ role: m.role, content: m.content }));
      onSend(query, history);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setPendingPrompt(null);
    lastAiResponseRef.current = null;
    lastErrorRef.current = null;
    onClearError?.();
    onNewChat?.();
  };

  useEffect(() => {
    if (!loading && aiResponse) {
      const shouldAppend =
        pendingPrompt !== null || messages.length === 0 || lastAiResponseRef.current !== aiResponse;
      if (shouldAppend) {
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "ai",
            content: aiResponse,
            timestamp: formatTime(new Date()),
          },
        ]);
        lastAiResponseRef.current = aiResponse;
        setPendingPrompt(null);
        lastErrorRef.current = null;
      }
    }
  }, [aiResponse, loading, messages.length, pendingPrompt]);

  // Append error as an assistant error bubble when request fails
  useEffect(() => {
    if (!loading && error) {
      if (lastErrorRef.current !== error) {
        lastErrorRef.current = error;
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "ai",
            content: error,
            timestamp: formatTime(new Date()),
            isError: true,
          },
        ]);
        setPendingPrompt(null);
      }
    } else if (!error) {
      lastErrorRef.current = null;
    }
  }, [error, loading]);

  useEffect(() => {
    if (messages.length > 0) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, loading, aiResponse, error]);

  const subjects = [
    { name: "Physics", icon: Atom, bg: "bg-blue-500/10", iconColor: "text-blue-600" },
    { name: "Chemistry", icon: Beaker, bg: "bg-amber-500/10", iconColor: "text-amber-600" },
    { name: "Biology", icon: Leaf, bg: "bg-emerald-500/10", iconColor: "text-emerald-600" },
    { name: "Math", icon: Calculator, bg: "bg-purple-500/10", iconColor: "text-purple-600" },
    { name: "History", icon: Landmark, bg: "bg-rose-500/10", iconColor: "text-rose-600" },
    { name: "Coding", icon: Code2, bg: "bg-sky-500/10", iconColor: "text-sky-600" },
  ];

  return (
    <div className="flex-1 flex flex-col h-full min-h-0 w-full relative bg-transparent">
      <TutorHeader
        onNewChat={handleNewChat}
        topicTitle={topicTitle}
        topicContext={topicContext}
        toggleHistory={toggleHistory}
      />

      {messages.length === 0 && (
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.05),transparent_50%)] dark:bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.02),transparent_50%)] pointer-events-none z-0" />
      )}

      <main className="flex-1 min-h-0 overflow-y-auto custom-scrollbar relative z-10">
        <div
          className={`mx-auto w-full max-w-[1600px] min-h-full flex flex-col px-4 sm:px-6 md:px-8 pb-6 pt-6 ${
            messages.length === 0 ? "justify-center" : "justify-start"
          } space-y-6`}
        >
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center w-full space-y-10 py-12 relative mt-[-2vh] sm:mt-[-5vh]">
              {/* Welcome Badge and Title */}
              <div className="flex flex-col items-center text-center space-y-4 max-w-xl z-10 animate-fade-in">
                <div className="flex items-center gap-1.5 rounded-full bg-primary/10 border border-primary/20 px-3.5 py-1 text-[11px] font-bold uppercase tracking-widest text-primary shadow-sm">
                  <Sparkles className="w-3.5 h-3.5 text-primary fill-primary/20" />
                  <span>AI Tutor</span>
                </div>

                <h2 className="text-3xl sm:text-4.5xl md:text-5xl font-extrabold tracking-tight text-foreground leading-tight">
                  What would you like to learn today?
                </h2>
              </div>

              {/* Subject Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 w-full max-w-4xl px-4 z-10">
                {subjects.map((sub) => {
                  const Icon = sub.icon;
                  return (
                    <button
                      key={sub.name}
                      type="button"
                      disabled={loading}
                      onClick={() => {
                        if (loading) return;
                        send(`Explain ${sub.name}`);
                      }}
                      className="pointer-events-auto flex items-center gap-4 px-5 py-4 bg-card hover:bg-secondary/40 border border-border/80 hover:border-primary/45 rounded-2xl shadow-sm hover:shadow-md transition-all hover:scale-103 active:scale-98 cursor-pointer text-left w-full group disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none"
                    >
                      <div
                        className={`w-11 h-11 rounded-full ${sub.bg} ${sub.iconColor} flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform`}
                      >
                        <Icon className="w-5.5 h-5.5" />
                      </div>
                      <span className="font-bold text-foreground text-sm sm:text-base group-hover:text-primary transition-colors">
                        {sub.name}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {messages.map((m, idx) => {
            const userQuery = m.role === "ai" && idx > 0 ? messages[idx - 1].content : undefined;
            return (
              <ChatBubble
                key={m.id}
                role={m.role}
                content={m.content}
                timestamp={m.timestamp}
                topicTitle={topicTitle}
                userQuery={userQuery}
                isError={m.isError}
                onRetry={m.isError ? () => handleRetry(userQuery) : undefined}
                onCopy={
                  m.role === "ai" && !m.isError
                    ? () => navigator.clipboard?.writeText(m.content)
                    : undefined
                }
                onRegenerate={
                  m.role === "ai" && !loading && !m.isError ? handleRegenerate : undefined
                }
              />
            );
          })}

          {loading && (
            <div className="flex w-full items-start gap-2.5 sm:gap-3">
              <div className="w-9 h-9 sm:w-10 sm:h-10 mt-1 rounded-full flex items-center justify-center shrink-0 bg-primary text-primary-foreground shadow-sm">
                <span className="text-primary-foreground text-xs font-bold tracking-wider">AI</span>
              </div>
              <div className="flex-1 w-full max-w-5xl">
                <GeneratingLoader />
              </div>
            </div>
          )}

          <div ref={bottomRef} className="h-4 w-full shrink-0" />
        </div>
      </main>

      <ChatInput onSend={send} disabled={loading} focus={Boolean(focusInput)} />
    </div>
  );
}

export default ChatWorkspace;
