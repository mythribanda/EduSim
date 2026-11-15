import React, { useMemo, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "@tanstack/react-router";
import { Copy, RefreshCw, Activity, Atom, GraduationCap, AlertCircle, Volume2, VolumeX } from "lucide-react";
import { useMounted } from "@/hooks/useMounted";
import { useTutorStore } from "@/store/tutorStore";
import { TutorMarkdownRenderer } from "./TutorMarkdownRenderer";
import { extractFormulas } from "@/utils/formulaParser";

const InteractiveFormulaCard = React.lazy(() => import("./InteractiveFormulaCard"));
const FormulaLabPageLazy = React.lazy(() => import("@/components/formula-lab/FormulaLabPage"));
const QASectionLazy = React.lazy(() => import("./QASection"));

interface ChatBubbleProps {
  content: string;
  role: "user" | "ai";
  timestamp?: string;
  topicTitle?: string;
  userQuery?: string;
  isError?: boolean;
  onCopy?: () => void;
  onRegenerate?: () => void;
  onRetry?: () => void;
}

export function ChatBubble({
  content,
  role,
  timestamp,
  topicTitle,
  userQuery,
  isError = false,
  onCopy,
  onRegenerate,
  onRetry,
}: ChatBubbleProps) {
  const isAi = role === "ai";
  const mounted = useMounted();
  const {
    activeFormulaId,
    showInlineFormulaLab,
    setShowInlineFormulaLab,
    inlineRagContent,
    setInlineRagContent,
  } = useTutorStore();

  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showQuiz, setShowQuiz] = useState(false);

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const toggleSpeak = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    const cleanText = content
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\$([^$]+)\$/g, "$1")
      .replace(/#+\s+/g, "")
      .replace(/[*_~]/g, "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .trim();

    if (!cleanText) return;

    try {
      const utterance = new SpeechSynthesisUtterance(cleanText);
      const isTelugu = /[\u0C00-\u0C7F]/.test(cleanText);
      const isHindi = /[\u0900-\u097F]/.test(cleanText);
      utterance.lang = isTelugu ? "te-IN" : isHindi ? "hi-IN" : "en-US";
      utterance.rate = 1.0;

      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);

      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
      setIsSpeaking(true);
    } catch {
      setIsSpeaking(false);
    }
  };

  const formulas = useMemo(() => {
    if (!isAi || isError) return [];
    return extractFormulas(content);
  }, [content, isAi, isError]);

  const shouldShowFormulaLab =
    isAi && !isError && showInlineFormulaLab && inlineRagContent === content;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      className={`flex w-full mb-2 ${isAi ? "justify-start" : "justify-end"}`}
    >
      <div
        className={`flex flex-col w-full ${
          isAi ? "max-w-5xl items-start" : "max-w-[80%] sm:max-w-[70%] md:max-w-[600px] items-end"
        }`}
      >
        <div
          className={`relative group flex items-start gap-2.5 sm:gap-3 ${
            isAi ? "w-full max-w-5xl" : "w-fit flex-row-reverse"
          }`}
        >
          {isAi && (
            <div
              className={`w-9 h-9 sm:w-10 sm:h-10 mt-1 rounded-full flex items-center justify-center shrink-0 shadow-sm ${
                isError
                  ? "bg-destructive text-destructive-foreground"
                  : "bg-primary text-primary-foreground"
              }`}
            >
              {isError ? (
                <AlertCircle className="w-5 h-5 text-destructive-foreground" />
              ) : (
                <span className="text-xs font-bold tracking-wider">AI</span>
              )}
            </div>
          )}

          <div
            className={`relative rounded-[20px] transition-all duration-200 shadow-md ${
              isAi
                ? isError
                  ? "px-4 py-3.5 sm:px-6 sm:py-5 border border-destructive/40 bg-destructive/10 text-destructive-foreground rounded-tl-sm shadow-sm text-[14.5px] sm:text-[15px] leading-relaxed w-full"
                  : "px-4 py-3.5 sm:px-6 sm:py-5 border border-border bg-card text-foreground rounded-tl-sm shadow-[0_4px_20px_rgba(112,181,255,0.08)] text-[14.5px] sm:text-[15px] leading-relaxed w-full hover:border-primary/40 hover:shadow-[0_6px_25px_rgba(112,181,255,0.12)]"
                : "px-4 py-2.5 bg-primary text-primary-foreground rounded-tr-sm shadow-[0_4px_12px_rgba(112,181,255,0.25)] text-sm sm:text-[14.5px] font-semibold leading-relaxed hover:-translate-y-[1px] hover:shadow-[0_6px_18px_rgba(112,181,255,0.35)]"
            }`}
          >
            {isError ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-start gap-2.5 text-foreground">
                  <span className="text-sm sm:text-base font-medium whitespace-pre-wrap leading-relaxed">
                    {content}
                  </span>
                </div>
                {onRetry && (
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={onRetry}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90 px-3.5 py-1.5 text-xs sm:text-sm font-semibold transition-all hover:scale-102 active:scale-98 shadow-sm cursor-pointer"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Retry</span>
                    </button>
                  </div>
                )}
              </div>
            ) : isAi ? (
              <TutorMarkdownRenderer
                content={content}
                density={"regular" as const}
                className={mounted ? "" : ""}
              />
            ) : (
              <div className="whitespace-pre-wrap">{content}</div>
            )}

            {isAi && !isError && (
              <div className="mt-6 pt-6 border-t border-border flex flex-wrap items-center justify-center gap-3 w-full">
                {formulas.length > 0 && (
                  <button
                    onClick={() => {
                      setInlineRagContent(content);
                      setShowInlineFormulaLab(true);
                    }}
                    className="group relative flex items-center gap-2.5 rounded-[2rem] bg-primary hover:bg-primary/90 px-6 py-3 text-sm font-bold text-primary-foreground transition-all hover:-translate-y-0.5 active:scale-95 shadow-[0_4px_12px_rgba(112,181,255,0.25)] hover:shadow-[0_6px_20px_rgba(112,181,255,0.35)] w-full sm:w-auto justify-center cursor-pointer"
                  >
                    <Activity className="h-4 w-4 text-primary-foreground/80" />
                    <span>Explore in Formula Lab</span>
                  </button>
                )}
                <Link
                  to="/sandbox/$simulationId"
                  params={{ simulationId: "default" }}
                  search={{ query: userQuery || topicTitle || "Physics Simulation", mode: "guide" }}
                  className="group relative flex items-center gap-2.5 rounded-[2rem] bg-secondary hover:bg-secondary/80 border border-border px-6 py-3 text-sm font-bold text-foreground transition-all hover:-translate-y-0.5 active:scale-95 shadow-md w-full sm:w-auto justify-center"
                >
                  <Atom className="h-4 w-4 text-primary" />
                  <span>Create Simulation</span>
                </Link>
                <button
                  type="button"
                  onClick={() => setShowQuiz(!showQuiz)}
                  className={`group relative flex items-center gap-2.5 rounded-[2rem] px-6 py-3 text-sm font-bold transition-all hover:-translate-y-0.5 active:scale-95 shadow-md w-full sm:w-auto justify-center cursor-pointer ${
                    showQuiz
                      ? "bg-violet-700 text-white shadow-violet-500/25 ring-2 ring-violet-400"
                      : "bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 text-white"
                  }`}
                >
                  <GraduationCap className="h-4 w-4 text-white" />
                  <span>{showQuiz ? "Hide Quiz" : "Practice AI Quiz"}</span>
                </button>
              </div>
            )}

            {isAi && !isError && (
              <div className="absolute -top-3 right-4 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  title={isSpeaking ? "Stop reading" : "Read aloud (Text-to-Speech)"}
                  onClick={toggleSpeak}
                  className={`rounded-full border border-border p-1.5 shadow-md transition-colors ${
                    isSpeaking
                      ? "bg-primary text-primary-foreground"
                      : "bg-background border-border hover:bg-secondary text-muted-foreground"
                  }`}
                >
                  {isSpeaking ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                </button>
                <button
                  type="button"
                  title="Copy"
                  onClick={onCopy}
                  className="rounded-full bg-background border border-border p-1.5 shadow-md hover:bg-secondary"
                >
                  <Copy className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  title="Regenerate"
                  onClick={onRegenerate}
                  className="rounded-full bg-background border border-border p-1.5 shadow-md hover:bg-secondary"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
              </div>
            )}
          </div>
        </div>

        {timestamp && (
          <span
            className={`text-[11px] text-muted-foreground/60 mt-1.5 px-2 ${isAi ? "ml-12" : "mr-2"}`}
          >
            {timestamp}
          </span>
        )}

        <AnimatePresence>
          {showQuiz && (
            <motion.div
              initial={{ opacity: 0, height: 0, marginTop: 0 }}
              animate={{ opacity: 1, height: "auto", marginTop: 16 }}
              exit={{ opacity: 0, height: 0, marginTop: 0 }}
              className="w-full ml-[46px] sm:ml-[52px] max-w-[calc(100%-46px)] sm:max-w-[calc(100%-52px)] overflow-hidden"
            >
              <div className="rounded-3xl border border-primary/30 bg-card p-4 sm:p-6 shadow-xl">
                <div className="flex items-center justify-between pb-3 mb-4 border-b border-border">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-primary/10 flex items-center justify-center text-primary font-bold">
                      <GraduationCap className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="font-bold text-sm text-foreground">AI-Generated Quiz</h4>
                      <p className="text-xs text-muted-foreground">Test your understanding with instant feedback</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowQuiz(false)}
                    className="text-xs font-semibold px-3 py-1.5 rounded-xl border border-border hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  >
                    Hide Quiz
                  </button>
                </div>
                <React.Suspense
                  fallback={
                    <div className="h-40 w-full animate-pulse rounded-2xl bg-secondary/30 flex items-center justify-center text-muted-foreground text-xs font-medium">
                      Generating AI Quiz questions...
                    </div>
                  }
                >
                  <QASectionLazy
                    topic={topicTitle || userQuery || "Science Concepts"}
                    ragContent={content}
                  />
                </React.Suspense>
              </div>
            </motion.div>
          )}

          {isAi &&
            !isError &&
            formulas.some((f) => (f.rawFormula || f.raw) === activeFormulaId) && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginTop: 0 }}
                animate={{ opacity: 1, height: "auto", marginTop: 16 }}
                exit={{ opacity: 0, height: 0, marginTop: 0 }}
                className="w-full ml-[46px] sm:ml-[52px] max-w-[calc(100%-46px)] sm:max-w-[calc(100%-52px)] overflow-hidden"
              >
                <React.Suspense
                  fallback={<div className="h-32 w-full animate-pulse rounded-2xl bg-white/5" />}
                >
                  <InteractiveFormulaCard formulaRaw={activeFormulaId!} />
                </React.Suspense>
              </motion.div>
            )}

          {shouldShowFormulaLab && (
            <motion.div
              initial={{ opacity: 0, height: 0, marginTop: 0 }}
              animate={{ opacity: 1, height: "auto", marginTop: 16 }}
              exit={{ opacity: 0, height: 0, marginTop: 0 }}
              className="w-full ml-[46px] sm:ml-[52px] max-w-[calc(100%-46px)] sm:max-w-[calc(100%-52px)] overflow-hidden"
            >
              <React.Suspense
                fallback={<div className="h-48 w-full animate-pulse rounded-2xl bg-white/5" />}
              >
                <FormulaLabPageLazy
                  topic={topicTitle || "General"}
                  ragContent={content}
                  isInline={true}
                />
              </React.Suspense>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export function TypingAnimation() {
  return (
    <div className="flex gap-1.5 px-5 py-4 rounded-[24px] rounded-tl-sm bg-card border border-border w-fit items-center h-[68px] shadow-sm">
      <motion.div
        animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
        transition={{ repeat: Infinity, duration: 1 }}
        className="w-2 h-2 rounded-full bg-primary"
      />
      <motion.div
        animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
        transition={{ repeat: Infinity, duration: 1, delay: 0.2 }}
        className="w-2 h-2 rounded-full bg-primary"
      />
      <motion.div
        animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
        transition={{ repeat: Infinity, duration: 1, delay: 0.4 }}
        className="w-2 h-2 rounded-full bg-primary"
      />
    </div>
  );
}
