import React, { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "@tanstack/react-router";
import { Copy, RefreshCw, Activity, Atom, GraduationCap } from "lucide-react";
import { useMounted } from "@/hooks/useMounted";
import { useTutorStore } from "@/store/tutorStore";
import { TutorMarkdownRenderer } from "./TutorMarkdownRenderer";
import { extractFormulas } from "@/utils/formulaParser";
import { DynamicFormulaExtractor, DynamicParsedFormula } from "@/utils/DynamicFormulaExtractor";

const InteractiveFormulaCard = React.lazy(() => import("./InteractiveFormulaCard"));
const FormulaLabPageLazy = React.lazy(() => import("@/components/formula-lab/FormulaLabPage"));

interface ChatBubbleProps {
  content: string;
  role: "user" | "ai";
  timestamp?: string;
  topicTitle?: string;
  userQuery?: string;
  onCopy?: () => void;
  onRegenerate?: () => void;
}

export function ChatBubble({ content, role, timestamp, topicTitle, userQuery, onCopy, onRegenerate }: ChatBubbleProps) {
  const isAi = role === "ai";
  const mounted = useMounted();
  const {
    activeFormulaId,
    setActiveFormulaId,
    showInlineFormulaLab,
    setShowInlineFormulaLab,
    inlineRagContent,
    setInlineRagContent,
  } = useTutorStore();

  const formulas = useMemo(() => {
    if (!isAi) return [];
    return extractFormulas(content);
  }, [content, isAi]);

  const shouldShowFormulaLab = isAi && showInlineFormulaLab && inlineRagContent === content;

  if (isAi) {
    console.log("[TutorOutputPanel] showFormulaLab", formulas.length);
  }

  let mainContent = content;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      className={`flex w-full mb-2 ${isAi ? "justify-start" : "justify-end"}`}
    >
      <div
        className={`flex flex-col w-full ${isAi ? "max-w-5xl items-start" : "max-w-[80%] sm:max-w-[70%] md:max-w-[600px] items-end"}`}
      >
        <div
          className={`relative group flex items-start gap-2.5 sm:gap-3 ${isAi ? "w-full max-w-5xl" : "w-fit flex-row-reverse"}`}
        >
          {isAi && (
            <div className="w-9 h-9 sm:w-10 sm:h-10 mt-1 rounded-full flex items-center justify-center shrink-0 bg-primary text-primary-foreground shadow-sm">
              <span className="text-primary-foreground text-xs font-bold tracking-wider">AI</span>
            </div>
          )}

          <div
            className={`relative rounded-[20px] transition-all duration-200 shadow-md ${isAi
                ? "px-4 py-3.5 sm:px-6 sm:py-5 border border-border bg-card text-foreground rounded-tl-sm shadow-[0_4px_20px_rgba(112,181,255,0.08)] text-[14.5px] sm:text-[15px] leading-relaxed w-full hover:border-primary/40 hover:shadow-[0_6px_25px_rgba(112,181,255,0.12)]"
                : "px-4 py-2.5 bg-primary text-primary-foreground rounded-tr-sm shadow-[0_4px_12px_rgba(112,181,255,0.25)] text-sm sm:text-[14.5px] font-semibold leading-relaxed hover:-translate-y-[1px] hover:shadow-[0_6px_18px_rgba(112,181,255,0.35)]"
              }`}
          >
            {isAi ? (
              <TutorMarkdownRenderer
                content={mainContent}
                density={"regular" as const}
                className={mounted ? "" : ""}
              />
            ) : (
              <div className="whitespace-pre-wrap">{content}</div>
            )}

            {isAi && formulas.length > 0 && (
              <div className="mt-6 pt-6 border-t border-border flex flex-wrap items-center justify-center gap-3 w-full">
                <button
                  onClick={() => {
                    setInlineRagContent(content);
                    setShowInlineFormulaLab(true);
                  }}
                  className="group relative flex items-center gap-2.5 rounded-[2rem] bg-primary hover:bg-primary/90 px-6 py-3 text-sm font-bold text-primary-foreground transition-all hover:-translate-y-0.5 active:scale-95 shadow-[0_4px_12px_rgba(112,181,255,0.25)] hover:shadow-[0_6px_20px_rgba(112,181,255,0.35)] w-full sm:w-auto justify-center"
                >
                  <Activity className="h-4 w-4 text-primary-foreground/80" />
                  <span>Explore in Formula Lab</span>
                </button>
                <Link
                  to="/sandbox/$simulationId"
                  params={{ simulationId: "default" }}
                  search={{ query: userQuery || topicTitle || "Physics Simulation", mode: "guide" }}
                  className="group relative flex items-center gap-2.5 rounded-[2rem] bg-secondary hover:bg-secondary/80 border border-border px-6 py-3 text-sm font-bold text-foreground transition-all hover:-translate-y-0.5 active:scale-95 shadow-md w-full sm:w-auto justify-center"
                >
                  <Atom className="h-4 w-4 text-primary" />
                  <span>Create Simulation</span>
                </Link>
                <Link
                  to="/formula-lab/$topic"
                  params={{ topic: topicTitle || "General" }}
                  className="group relative flex items-center gap-2.5 rounded-[2rem] bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 px-6 py-3 text-sm font-bold text-white transition-all hover:-translate-y-0.5 active:scale-95 shadow-md w-full sm:w-auto justify-center"
                >
                  <GraduationCap className="h-4 w-4 text-white" />
                  <span>Practice Quiz</span>
                </Link>
              </div>
            )}

            {isAi && (
              <div className="absolute -top-3 right-4 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
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
          {isAi && formulas.some((f) => (f.rawFormula || f.raw) === activeFormulaId) && (
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
                <FormulaLabPageLazy topic={topicTitle || "General"} ragContent={mainContent} isInline={true} />
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
