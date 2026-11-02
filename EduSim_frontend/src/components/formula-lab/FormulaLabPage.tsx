import React, { useEffect, useState, useMemo } from "react";
import { useFormulaLab } from "@/hooks/useFormulaLab";
import { DynamicFormulaExtractor, DynamicParsedFormula } from "@/utils/DynamicFormulaExtractor";
import { physicsSimulationApi } from "@/services/physicsSimulationApi";
import FormulaAnatomy from "./FormulaAnatomy";
import FormulaPlayground from "./FormulaPlayground";
import FormulaGraph from "./FormulaGraph";
import { motion, AnimatePresence } from "framer-motion";
import QASection from "../tutor/QASection";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import {
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  Sparkles,
  Search,
  BookOpen,
  Calculator,
  LineChart,
  HelpCircle,
  Star,
  History,
  Compass,
  Bookmark,
  ArrowRight,
  GraduationCap
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { BlockMath, InlineMath } from "@/components/math/Katex";
import "katex/dist/katex.min.css";

interface Props {
  topic: string;
  classId?: string;
  subject?: string;
  chapter?: string;
  ragContent?: string;
  formulas?: DynamicParsedFormula[] | null;
  isInline?: boolean;
  formulaExpression?: string;
  formulaMeaning?: string;
}

function getFormulaCategory(f: DynamicParsedFormula): string {
  const text = ((f.title || "") + " " + (f.description || "")).toLowerCase();
  if (/force|acceleration|motion|velocity|gravity|momentum|speed|inertia|mass|projectile/i.test(text)) {
    return "Dynamics";
  }
  if (/refraction|reflection|lens|light|wave|sound|frequency|pitch|optics/i.test(text)) {
    return "Waves & Optics";
  }
  if (/electric|magnetic|charge|current|ohm|resistance|voltage|circuit/i.test(text)) {
    return "Electromagnetism";
  }
  return "General Physics";
}

const getSubjectTheme = (subName?: string) => {
  const name = (subName || "physics").toLowerCase();
  if (name.includes("math")) {
    return {
      gradient: "from-slate-950 via-purple-950/80 to-slate-900 border-purple-500/20",
      symbolColor: "text-purple-400/40",
      formulaHighlight: "text-purple-300 drop-shadow-[0_0_6px_rgba(168,85,247,0.25)]",
      accentColor: "cyan",
      platformBorder: "border-cyan-400/30",
      platformBg: "bg-cyan-500/5",
      platformShadow: "shadow-[0_0_30px_rgba(34,211,238,0.25)]",
      cubeBorder: "border-cyan-400/60",
      cubeBg: "bg-cyan-500/5",
      cubeShadow: "shadow-[0_0_20px_rgba(34,211,238,0.15)]",
      nodeBg: "bg-cyan-300",
    };
  }
  if (name.includes("physic") || name.includes("science")) {
    return {
      gradient: "from-[#090d16] via-[#101b2d]/90 to-[#070b12] border-blue-500/20",
      symbolColor: "text-cyan-400/55",
      formulaHighlight: "text-cyan-300/90 drop-shadow-[0_0_8px_rgba(34,211,238,0.25)]",
      accentColor: "cyan",
      platformBorder: "border-cyan-400/35",
      platformBg: "bg-cyan-500/5",
      platformShadow: "shadow-[0_0_35px_rgba(34,211,238,0.3)]",
      cubeBorder: "border-cyan-400/65",
      cubeBg: "bg-cyan-500/5",
      cubeShadow: "shadow-[0_0_25px_rgba(34,211,238,0.2)]",
      nodeBg: "bg-cyan-300",
    };
  }
  if (name.includes("biolog") || name.includes("evs")) {
    return {
      gradient: "from-slate-950 via-teal-950/80 to-slate-900 border-emerald-500/20",
      symbolColor: "text-emerald-400/40",
      formulaHighlight: "text-emerald-300 drop-shadow-[0_0_6px_rgba(16,185,129,0.25)]",
      accentColor: "emerald",
      platformBorder: "border-emerald-400/30",
      platformBg: "bg-emerald-500/5",
      platformShadow: "shadow-[0_0_30px_rgba(16,185,129,0.25)]",
      cubeBorder: "border-emerald-400/60",
      cubeBg: "bg-emerald-500/5",
      cubeShadow: "shadow-[0_0_20px_rgba(16,185,129,0.15)]",
      nodeBg: "bg-emerald-300",
    };
  }
  // Default dark violet/fuchsia lab theme
  return {
    gradient: "from-slate-950 via-slate-900 to-zinc-950 border-fuchsia-500/20",
    symbolColor: "text-fuchsia-400/40",
    formulaHighlight: "text-fuchsia-300 drop-shadow-[0_0_6px_rgba(217,70,239,0.25)]",
    accentColor: "fuchsia",
    platformBorder: "border-fuchsia-400/30",
    platformBg: "bg-fuchsia-500/5",
    platformShadow: "shadow-[0_0_30px_rgba(217,70,239,0.25)]",
    cubeBorder: "border-fuchsia-400/60",
    cubeBg: "bg-fuchsia-500/5",
    cubeShadow: "shadow-[0_0_20px_rgba(217,70,239,0.15)]",
    nodeBg: "bg-fuchsia-300",
  };
};

const getFloatingSymbols = (subName?: string) => {
  const name = (subName || "physics").toLowerCase();
  if (name.includes("math")) {
    return ["+", "−", "×", "÷", "√", "π", "%", "=", "∞", "x²", "a+b", "½"];
  }
  if (name.includes("physic") || name.includes("science")) {
    return ["c", "G", "g", "h", "λ", "Σ", "Ω", "Δ", "F=ma", "E=mc²", "v=d/t"];
  }
  return ["★", "✦", "●", "▲", "◆", "■", "✿", "☘", "☀", "⚡"];
};

const FormulaLabPage: React.FC<Props> = ({
  topic,
  classId,
  subject,
  chapter,
  ragContent,
  formulas: directFormulas,
  isInline = false,
  formulaExpression,
  formulaMeaning,
}) => {
  const { formulas, selectedFormula, selectFormula, loadForTopic } = useFormulaLab();
  const theme = getSubjectTheme(subject);

  const [localFormulas, setLocalFormulas] = useState<DynamicParsedFormula[] | null>(null);
  const [localSelectedIndex, setLocalSelectedIndex] = useState(0);
  const [isSearchingAi, setIsSearchingAi] = useState(false);
  const [aiSearchError, setAiSearchError] = useState<string | null>(null);

  const activeFormulas = localFormulas || directFormulas || formulas;
  const activeCount = activeFormulas ? activeFormulas.length : 0;

  const activeSelectedFormula = localFormulas
    ? (localFormulas[localSelectedIndex] || null)
    : (directFormulas && directFormulas.length > 0 ? directFormulas[localSelectedIndex] : selectedFormula);

  const handleSelectFormula = (raw: string) => {
    if (localFormulas) {
      const idx = localFormulas.findIndex(f => f.id === raw || f.raw === raw);
      if (idx >= 0) setLocalSelectedIndex(idx);
    } else if (directFormulas) {
      const idx = directFormulas.findIndex(f => f.id === raw || f.raw === raw);
      if (idx >= 0) setLocalSelectedIndex(idx);
    } else {
      selectFormula(raw);
    }
  };

  const handleSearchAi = async (queryToSearch?: string) => {
    const q = queryToSearch || searchQuery;
    if (!q.trim()) return;

    setIsSearchingAi(true);
    setAiSearchError(null);
    try {
      const response = await physicsSimulationApi.searchRag(q, subject, chapter || "");
      let rag = "";
      if (response.success && response.data?.chunks) {
        rag = response.data.chunks.map((c: any) => c.text).join("\n\n");
      }

      let parsed = await DynamicFormulaExtractor.parseTutorResponse(
        rag,
        q,
        subject || "physics",
        classId
      );

      if ((!parsed || parsed.length === 0) && q.includes("=")) {
        parsed = await DynamicFormulaExtractor.parseTutorResponse(
          q,
          q,
          subject || "physics",
          classId
        );
      }

      if (parsed && parsed.length > 0) {
        setLocalFormulas(parsed);
        setLocalSelectedIndex(0);
        setSearchQuery(""); // Clear input to show results
      } else {
        setAiSearchError(`Could not find equations for "${q}". Try asking for "Newton's Second Law", "Ohm's Law", or "Kinetic Energy".`);
      }
    } catch (err) {
      console.error("AI Search in Formula Lab failed:", err);
      setAiSearchError("Failed to connect to the AI Tutor.");
    } finally {
      setIsSearchingAi(false);
    }
  };

  const [values, setValues] = useState<Record<string, number>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [activeListTab, setActiveListTab] = useState<"all" | "recent" | "saved">("all");
  const [activeTabId, setActiveTabId] = useState("anatomy");

  // LocalStorage state for Recent and Saved Formulas
  const [recentIds, setRecentIds] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("formula-lab-recent") || "[]");
    } catch {
      return [];
    }
  });

  const [savedIds, setSavedIds] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("formula-lab-saved") || "[]");
    } catch {
      return [];
    }
  });

  useEffect(() => {
    if (!directFormulas) {
      loadForTopic({ topic, classId, subject, chapter, ragContent, formulaExpression, formulaMeaning });
    }
  }, [topic, classId, subject, chapter, ragContent, loadForTopic, directFormulas, formulaExpression, formulaMeaning]);

  // Set initial values when formula changes
  useEffect(() => {
    if (activeSelectedFormula && Array.isArray(activeSelectedFormula.controls)) {
      const initial = activeSelectedFormula.controls.reduce<Record<string, number>>((acc, control) => {
        acc[control.symbol] = control.defaultValue;
        return acc;
      }, {});
      setValues(initial);
    } else {
      setValues({});
    }
  }, [activeSelectedFormula?.id, activeSelectedFormula?.raw]);

  // Update recent list when formula changes
  useEffect(() => {
    if (activeSelectedFormula) {
      const id = activeSelectedFormula.id || activeSelectedFormula.raw;
      setRecentIds(prev => {
        const filtered = prev.filter(x => x !== id);
        const updated = [id, ...filtered].slice(0, 8);
        localStorage.setItem("formula-lab-recent", JSON.stringify(updated));
        return updated;
      });
    }
  }, [activeSelectedFormula?.id, activeSelectedFormula?.raw]);

  const toggleSaveFormula = (id: string) => {
    setSavedIds(prev => {
      const updated = prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id];
      localStorage.setItem("formula-lab-saved", JSON.stringify(updated));
      return updated;
    });
  };

  // Dynamic Categories extracted from loaded formulas
  const categories = useMemo(() => {
    const list = activeFormulas || [];
    const cats = new Set<string>();
    cats.add("All");
    list.forEach(f => cats.add(getFormulaCategory(f)));
    return Array.from(cats);
  }, [activeFormulas]);

  // Filtered Formulas for Directory List
  const filteredFormulas = useMemo(() => {
    let list = activeFormulas || [];
    if (activeListTab === "recent") {
      list = list.filter(f => recentIds.includes(f.id || f.raw));
    } else if (activeListTab === "saved") {
      list = list.filter(f => savedIds.includes(f.id || f.raw));
    }

    return list.filter(f => {
      const cat = getFormulaCategory(f);
      const matchesCategory = selectedCategory === "All" || cat === selectedCategory;
      const text = (
        (f.title || "") + " " +
        (f.description || "") + " " +
        (f.displayFormula || f.formula || f.raw)
      ).toLowerCase();
      const matchesSearch = text.includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [activeFormulas, activeListTab, recentIds, savedIds, selectedCategory, searchQuery]);

  const fallbackCard = (
    <div className="w-full rounded-2xl border border-red-500/20 bg-red-950/10 p-6 text-sm text-red-100 shadow-2xl">
      <h2 className="text-xl font-semibold">Formula Lab unavailable</h2>
      <p className="mt-2 text-red-100/70 leading-relaxed">
        Formula Lab hit an error while loading this topic. You can continue using Tutor or reload
        the page.
      </p>
    </div>
  );

  if (!activeFormulas) {
    if (isInline) {
      return (
        <div className="w-full rounded-[2rem] border border-border/60 bg-card/85 p-12 shadow-sm flex flex-col items-center justify-center min-h-[280px]">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-4 border-violet-500/30 border-t-violet-600 rounded-full animate-spin" />
            <span className="text-sm text-muted-foreground font-bold tracking-wider animate-pulse">Analyzing textbook formulas...</span>
          </div>
        </div>
      );
    }

    return (
      <div className="w-full mx-auto space-y-6 animate-pulse p-4 md:p-6">
        {/* Header Skeleton */}
        <header className="flex flex-col gap-4 rounded-3xl border border-border/60 bg-card/85 p-6 shadow-sm md:flex-row md:items-center md:justify-between">
          <div className="space-y-2">
            <div className="h-4 w-32 bg-muted rounded-full" />
            <div className="h-8 w-48 bg-muted/80 rounded-xl" />
            <div className="h-3 w-64 bg-muted rounded-full" />
          </div>
          <div className="h-8 w-36 bg-muted rounded-full" />
        </header>

        {/* Directory & Workspace Grid Skeleton */}
        <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] 2xl:grid-cols-[380px_1fr] gap-6 items-start">
          <aside className="rounded-3xl border border-border/60 bg-card/85 p-5 shadow-sm space-y-5 hidden xl:block">
            <div className="h-10 bg-muted rounded-xl w-full" />
            <div className="flex gap-4 border-b border-border/60 pb-2">
              <div className="h-4 w-24 bg-muted rounded-full" />
              <div className="h-4 w-16 bg-muted rounded-full" />
              <div className="h-4 w-16 bg-muted rounded-full" />
            </div>
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="border border-border/60 bg-card rounded-2xl p-4 space-y-3">
                  <div className="h-3 w-16 bg-muted rounded-full" />
                  <div className="h-5 w-40 bg-muted/90 rounded-xl" />
                  <div className="h-12 bg-secondary/50 rounded-xl w-full" />
                </div>
              ))}
            </div>
          </aside>

          <main className="rounded-3xl border border-border/60 bg-card/85 p-6 min-h-[500px] flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-10 h-10 border-4 border-violet-500/30 border-t-violet-600 rounded-full animate-spin" />
              <span className="text-sm text-muted-foreground font-bold tracking-wider animate-pulse">Analyzing textbook formulas...</span>
            </div>
          </main>
        </div>
      </div>
    );
  }



  const tabs = [
    { id: "anatomy", label: "Anatomy", icon: BookOpen },
    { id: "solve", label: "Solve", icon: Calculator },
    { id: "visualize", label: "Visualize", icon: LineChart },
    { id: "practice", label: "Practice", icon: GraduationCap }
  ];

  const activeTabIndex = tabs.findIndex(t => t.id === activeTabId);

  const handlePrev = () => {
    if (activeTabIndex > 0) setActiveTabId(tabs[activeTabIndex - 1].id);
  };

  const handleNext = () => {
    if (activeTabIndex < tabs.length - 1) setActiveTabId(tabs[activeTabIndex + 1].id);
  };

  const renderTabContent = () => {
    if (!activeSelectedFormula) return null;
    switch (activeTabId) {
      case "anatomy":
        return <FormulaAnatomy formula={activeSelectedFormula} mode="variables" />;
      case "solve":
        return <FormulaPlayground formula={activeSelectedFormula} values={values} setValues={setValues} />;
      case "visualize":
        return <FormulaGraph formula={activeSelectedFormula} values={values} />;
      case "practice":
        return (
          <QASection
            topic={topic}
            chapter={chapter}
            subject={subject}
            formulas={activeFormulas}
            ragContent={ragContent}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className={`w-full max-w-[1600px] mx-auto space-y-6 ${isInline ? "px-0 py-2" : "p-4 md:p-6"}`}>
      {/* Premium SaaS Header Banner with Holographic 3D Blueprint Animation */}
      <header className={`relative overflow-hidden rounded-[24px] bg-gradient-to-r ${theme.gradient} py-14 px-8 mb-6 shadow-xl border border-white/10 min-h-[260px] flex items-center transition-all duration-300 z-10`}>
        {/* Glow Spheres */}
        <div className="absolute -right-20 -top-20 w-80 h-80 rounded-full bg-white/5 blur-[100px] pointer-events-none z-0" />
        <div className="absolute -left-20 -bottom-20 w-64 h-64 rounded-full bg-white/5 blur-[100px] pointer-events-none z-0" />

        {/* Beautiful Dotted Connecting Lines & Mathematical Graphs */}
        <svg className="absolute inset-0 w-full h-full opacity-25 pointer-events-none z-0" xmlns="http://www.w3.org/2000/svg">
          {/* Background Grid Pattern */}
          <defs>
            <pattern id="math-grid-header" width="25" height="25" patternUnits="userSpaceOnUse">
              <path d="M 25 0 L 0 0 0 25" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
            </pattern>
            <linearGradient id="headerGraphGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.1" />
              <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.1" />
            </linearGradient>
            <linearGradient id="headerGraphGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#a855f7" stopOpacity="0.05" />
              <stop offset="50%" stopColor="#ec4899" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.05" />
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#math-grid-header)" />

          {/* Dotted axis lines */}
          <line x1="280" y1="10" x2="280" y2="250" stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="150" y1="130" x2="650" y2="130" stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="3 3" />

          {/* Sine curve graph with morphing animation */}
          <motion.path
            d="M 180 130 Q 280 40, 380 130 T 580 130"
            fill="none"
            stroke="url(#headerGraphGrad1)"
            strokeWidth="2.5"
            animate={{
              d: [
                "M 180 130 Q 280 40, 380 130 T 580 130",
                "M 180 130 Q 280 220, 380 130 T 580 130",
                "M 180 130 Q 280 40, 380 130 T 580 130",
              ],
              strokeDashoffset: [0, -100]
            }}
            transition={{
              d: { duration: 12, repeat: Infinity, ease: "easeInOut" },
              strokeDashoffset: { duration: 20, repeat: Infinity, ease: "linear" }
            }}
            style={{ strokeDasharray: "4 4" }}
          />

          {/* Secondary cosine wave graph with morphing animation */}
          <motion.path
            d="M 180 90 Q 300 190, 420 70 T 600 130"
            fill="none"
            stroke="url(#headerGraphGrad2)"
            strokeWidth="1.5"
            animate={{
              d: [
                "M 180 90 Q 300 190, 420 70 T 600 130",
                "M 180 170 Q 300 50, 420 190 T 600 130",
                "M 180 90 Q 300 190, 420 70 T 600 130",
              ],
              strokeDashoffset: [0, 100]
            }}
            transition={{
              d: { duration: 15, repeat: Infinity, ease: "easeInOut" },
              strokeDashoffset: { duration: 24, repeat: Infinity, ease: "linear" }
            }}
            style={{ strokeDasharray: "3 3" }}
          />

          {/* Pulsing Graph Nodes with Dual Radar Wave Rings */}
          <circle cx="380" cy="130" r="4.5" className="fill-cyan-400 opacity-90" />
          <motion.circle
            cx="380"
            cy="130"
            r="4.5"
            className="fill-none stroke-cyan-400 stroke-[1.5]"
            animate={{ scale: [1, 3], opacity: [0.8, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeOut" }}
          />
          <motion.circle
            cx="380"
            cy="130"
            r="4.5"
            className="fill-none stroke-cyan-400 stroke-[1]"
            animate={{ scale: [1, 2], opacity: [0.6, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeOut", delay: 1.5 }}
          />
        </svg>

        {/* Holographic 3D Blueprint Illustration */}
        <div className="absolute right-[240px] top-1/2 -translate-y-1/2 w-56 h-56 pointer-events-none hidden lg:block z-0" style={{ perspective: "800px" }}>
          {/* Glowing Platform Ring */}
          <div className={`absolute left-2 bottom-4 w-52 h-10 border ${theme.platformBorder} rounded-full ${theme.platformBg} ${theme.platformShadow}`} style={{ transform: "rotateX(75deg)" }} />
          <motion.div
            className="absolute left-8 bottom-5 w-40 h-8 border border-dashed border-white/20 rounded-full"
            style={{ transform: "rotateX(75deg)" }}
            animate={{ rotate: 360 }}
            transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
          />

          {/* Central Holographic 3D Spinning Cube */}
          <div className="absolute left-10 top-6 w-36 h-36 flex items-center justify-center">
            <motion.div
              className="w-24 h-24 relative"
              style={{ transformStyle: "preserve-3d" }}
              animate={{
                rotateX: [0, 360],
                rotateY: [0, 360],
                rotateZ: [0, 360],
              }}
              transition={{
                duration: 20,
                repeat: Infinity,
                ease: "linear",
              }}
            >
              {/* Front Face */}
              <div className={`absolute inset-0 border ${theme.cubeBorder} ${theme.cubeBg} rounded ${theme.cubeShadow}`} style={{ transform: "translateZ(48px)" }}>
                <div className={`absolute top-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute top-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
              </div>
              {/* Back Face */}
              <div className={`absolute inset-0 border ${theme.cubeBorder} ${theme.cubeBg} rounded ${theme.cubeShadow}`} style={{ transform: "rotateY(180deg) translateZ(48px)" }}>
                <div className={`absolute top-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute top-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
              </div>
              {/* Left Face */}
              <div className={`absolute inset-0 border ${theme.cubeBorder} ${theme.cubeBg} rounded ${theme.cubeShadow}`} style={{ transform: "rotateY(-90deg) translateZ(48px)" }}>
                <div className={`absolute top-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute top-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
              </div>
              {/* Right Face */}
              <div className={`absolute inset-0 border ${theme.cubeBorder} ${theme.cubeBg} rounded ${theme.cubeShadow}`} style={{ transform: "rotateY(90deg) translateZ(48px)" }}>
                <div className={`absolute top-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute top-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
              </div>
              {/* Top Face */}
              <div className={`absolute inset-0 border ${theme.cubeBorder} ${theme.cubeBg} rounded ${theme.cubeShadow}`} style={{ transform: "rotateX(90deg) translateZ(48px)" }}>
                <div className={`absolute top-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute top-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
              </div>
              {/* Bottom Face */}
              <div className={`absolute inset-0 border ${theme.cubeBorder} ${theme.cubeBg} rounded ${theme.cubeShadow}`} style={{ transform: "rotateX(-90deg) translateZ(48px)" }}>
                <div className={`absolute top-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute top-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 left-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
                <div className={`absolute bottom-0 right-0 w-2 h-2 ${theme.nodeBg} rounded-full`} />
              </div>
            </motion.div>
          </div>
        </div>

        {/* Floating animated background math/physics symbols (positioned to strictly prevent overlap) */}
        {(() => {
          const baseSymbols = getFloatingSymbols(subject);
          const renderedSymbols = [
            baseSymbols[0] || "+",
            baseSymbols[1] || "−",
            "π ≈ 3.14159",
            baseSymbols[2] || "×",
            baseSymbols[3] || "÷",
          ];
          return renderedSymbols.map((sym, idx) => {
            const positions = [
              { top: "15%", left: "6%", rotate: "12deg", scale: 1.0, opacity: 0.45, duration: 6, delay: 0 },
              { bottom: "15%", left: "6%", rotate: "-15deg", scale: 1.1, opacity: 0.35, duration: 8, delay: 1 },
              { top: "18%", left: "45%", rotate: "0deg", scale: 1.25, opacity: 0.55, duration: 7, delay: 0.5 },
              { top: "15%", right: "6%", rotate: "25deg", scale: 1.1, opacity: 0.4, duration: 5, delay: 1.2 },
              { bottom: "15%", right: "6%", rotate: "-8deg", scale: 1.0, opacity: 0.45, duration: 9, delay: 0.8 },
            ];
            const pos = positions[idx];
            const styleObj: React.CSSProperties = {
              opacity: pos.opacity,
            };
            if (pos.top) styleObj.top = pos.top;
            if (pos.bottom) styleObj.bottom = pos.bottom;
            if (pos.left) styleObj.left = pos.left;
            if (pos.right) styleObj.right = pos.right;

            const textSizeClass = sym.includes("≈") 
              ? "text-lg sm:text-2xl md:text-3xl font-sans" 
              : "text-3xl sm:text-4xl md:text-5xl font-mono";

            const renderContent = () => {
              if (sym.includes("π")) {
                return (
                  <span>
                    <span className="font-serif italic font-medium">π</span>
                    <span> ≈ 3.14159</span>
                  </span>
                );
              }
              return sym;
            };

            return (
              <motion.span
                key={idx}
                className={`absolute font-black select-none pointer-events-none ${textSizeClass} ${theme.symbolColor}`}
                style={styleObj}
                animate={{
                  y: [0, -8, 0],
                  rotate: [parseFloat(pos.rotate), parseFloat(pos.rotate) + (sym.includes("≈") ? 2 : 5), parseFloat(pos.rotate)],
                }}
                transition={{
                  duration: pos.duration,
                  repeat: Infinity,
                  ease: "easeInOut",
                  delay: pos.delay,
                }}
              >
                {renderContent()}
              </motion.span>
            );
          });
        })()}

        {/* Center-placed Floating Equation (merged as a floating highlighted symbol at the bottom) */}
        <div className="absolute inset-x-0 bottom-6 flex justify-center pointer-events-none z-10">
          <motion.div 
            className={`font-mono text-2xl sm:text-3xl md:text-4xl font-extrabold select-none pointer-events-none opacity-80 ${theme.formulaHighlight}`}
            animate={{
              y: [0, -6, 0],
              rotate: [0, 1.5, 0],
            }}
            transition={{
              duration: 6,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 0.5,
            }}
          >
            <InlineMath math={
              activeSelectedFormula 
                ? (activeSelectedFormula.latex || activeSelectedFormula.formula || activeSelectedFormula.raw)
                : (subject?.toLowerCase().includes("math") ? "e^{i\\pi} + 1 = 0" : "E = m c^2")
            } />
          </motion.div>
        </div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10 w-full">
          <div className="space-y-1.5 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-white animate-pulse" />
              <span className="text-[11px] font-extrabold uppercase tracking-[0.2em] text-white/80">EduSim Laboratory</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-black tracking-tight text-white leading-none">Formula Lab</h1>
            <div className="text-sm text-white/85 font-semibold mt-1.5">
              {localFormulas ? `AI Search: "${localFormulas[0]?.topic || topic}"` : (topic === "new" ? "New Workspace" : topic)} • <span className="capitalize">{subject || "physics"}</span> {classId ? `• Class ${classId}` : ""}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-full border border-white/20 bg-white/10 px-5 py-2.5 text-sm font-semibold text-white shadow-inner backdrop-blur-md">
              Detected Formulas: <span className="text-white font-extrabold">{activeCount}</span>
            </div>
          </div>
        </div>
      </header>

      <ErrorBoundary fallback={fallbackCard}>
        <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] 2xl:grid-cols-[380px_1fr] gap-6 items-start">

          {/* LEFT COLUMN: Directory Sidebar */}
          <aside className="rounded-3xl border border-border/60 bg-card/85 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] backdrop-blur-md space-y-5">
            {/* Search Input */}
            <div className="relative">
              <div className="relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search formulas or ask AI..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === "Enter") {
                      handleSearchAi();
                    }
                  }}
                  className="w-full pl-10 pr-10 py-2.5 bg-secondary/40 border border-border/60 rounded-xl text-sm focus:outline-none focus:bg-card focus:border-violet-500 focus:ring-4 focus:ring-violet-500/10 transition-all text-foreground placeholder:text-muted-foreground"
                />
                {searchQuery.trim() && (
                  <button
                    onClick={() => handleSearchAi()}
                    title="Query AI for matching formulas"
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-violet-600 hover:text-violet-700 hover:bg-violet-500/10 transition-all cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5 animate-pulse" />
                  </button>
                )}
              </div>
            </div>

            {aiSearchError && (
              <div className="p-3.5 rounded-2xl border border-red-500/20 bg-red-500/10 text-red-200 text-xs leading-relaxed font-medium">
                {aiSearchError}
              </div>
            )}

            {/* List Selection Tabs */}
            <div className="flex border-b border-border/40 pb-2 gap-4">
              <button
                onClick={() => { setActiveListTab("all"); setSelectedCategory("All"); }}
                className={`text-xs font-bold pb-1.5 border-b-2 transition-all flex items-center gap-1.5 ${activeListTab === "all"
                  ? "border-violet-600 text-violet-600"
                  : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
              >
                <Compass className="w-3.5 h-3.5" />
                All Formulas
              </button>
              <button
                onClick={() => setActiveListTab("recent")}
                className={`text-xs font-bold pb-1.5 border-b-2 transition-all flex items-center gap-1.5 ${activeListTab === "recent"
                  ? "border-violet-600 text-violet-600"
                  : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
              >
                <History className="w-3.5 h-3.5" />
                Recent
              </button>
              <button
                onClick={() => setActiveListTab("saved")}
                className={`text-xs font-bold pb-1.5 border-b-2 transition-all flex items-center gap-1.5 ${activeListTab === "saved"
                  ? "border-violet-600 text-violet-600"
                  : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
              >
                <Bookmark className="w-3.5 h-3.5" />
                Saved
              </button>
            </div>

            {/* Category Pills (rendered only for "all" formulas) */}
            {activeListTab === "all" && categories.length > 1 && (
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto custom-scrollbar">
                {categories.map(cat => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-3 py-1 rounded-full text-[11px] font-bold tracking-wide transition-all border ${selectedCategory === cat
                      ? "bg-violet-500/10 border-violet-500/20 text-violet-600 dark:text-violet-400 font-extrabold"
                      : "bg-secondary/40 border-border/60 text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                      }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            )}

            {/* Formulas List Grid */}
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1 custom-scrollbar">
              {isSearchingAi ? (
                <div className="py-16 flex flex-col items-center justify-center gap-3">
                  <div className="w-8 h-8 border-4 border-violet-500/20 border-t-violet-600 rounded-full animate-spin" />
                  <span className="text-xs text-muted-foreground font-bold tracking-wider animate-pulse">Querying AI Tutor for formulas...</span>
                </div>
              ) : filteredFormulas.length > 0 ? (
                filteredFormulas.map((f, idx) => {
                  const isSelected = activeSelectedFormula?.id === f.id || activeSelectedFormula?.raw === f.raw;
                  const title = f.title || f.displayFormula || f.formula || f.raw || "Formula";
                  const category = getFormulaCategory(f);

                  return (
                    <div
                      key={f.id || f.raw}
                      onClick={() => {
                        handleSelectFormula(f.id || f.raw);
                      }}
                      className={`w-full rounded-2xl border p-4 text-left cursor-pointer transition-all duration-300 flex flex-col gap-3 relative overflow-hidden group ${isSelected
                        ? "border-violet-500 dark:border-violet-400 bg-violet-500/5 dark:bg-violet-950/30 shadow-[0_4px_20px_rgba(139,92,246,0.05)] scale-[1.01]"
                        : "border-border/60 bg-card hover:bg-secondary/20 hover:border-border hover:shadow-md"
                        }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <span className="text-[9px] font-extrabold uppercase tracking-widest text-muted-foreground">
                            {category}
                          </span>
                          <h3 className="text-sm font-bold text-foreground group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors line-clamp-1">{title}</h3>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSaveFormula(f.id || f.raw);
                          }}
                          className={`p-1.5 rounded-lg hover:bg-secondary/65 transition-colors ${savedIds.includes(f.id || f.raw) ? "text-yellow-500" : "text-muted-foreground hover:text-yellow-500"
                            }`}
                        >
                          <Star className={`w-3.5 h-3.5 ${savedIds.includes(f.id || f.raw) ? "fill-yellow-500" : ""}`} />
                        </button>
                      </div>

                      {/* Formula latex centered card */}
                      <div className="py-2.5 px-3 bg-gradient-to-br from-violet-500/[0.06] to-indigo-500/[0.06] dark:from-violet-950/45 dark:to-indigo-950/45 rounded-xl border border-violet-500/20 dark:border-violet-500/40 shadow-inner overflow-x-auto text-center font-mono text-xs text-violet-700 dark:text-violet-300">
                        {f.latex || f.formula ? (
                          <BlockMath math={f.latex || f.formula || ""} />
                        ) : (
                          <span className="text-[10px] text-muted-foreground">No formula preview</span>
                        )}
                      </div>

                      <div className="flex items-center justify-between gap-2 mt-1">
                        <p className="text-[11px] text-muted-foreground leading-normal line-clamp-2 pr-4 font-normal">
                          {f.description || "Interactive dynamic equation analysis."}
                        </p>
                        <button
                          className={`flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider transition-colors shrink-0 ${isSelected ? "text-violet-600 dark:text-violet-400" : "text-muted-foreground group-hover:text-foreground"
                            }`}
                        >
                          <span>Open</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="py-12 text-center text-muted-foreground text-xs space-y-4">
                  <p>{topic === "new" && !localFormulas && !searchQuery ? "Enter a topic in the search bar above to generate formulas." : "No formulas found matching filters."}</p>
                  {searchQuery.trim() && (
                    <button
                      onClick={() => handleSearchAi()}
                      className="px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs shadow-md transition-all active:scale-95 flex items-center gap-2 mx-auto cursor-pointer"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-white/80" />
                      <span>Search AI for "{searchQuery}"</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </aside>

          {/* RIGHT COLUMN: Operations Workspace */}
          <main className="space-y-6">
            {activeSelectedFormula ? (
              <div className="space-y-6">

                {/* Active Selected Formula Details Header */}
                <div className="rounded-3xl border border-border/60 bg-card/85 p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.02)] backdrop-blur-md">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-violet-500/[0.03] blur-3xl -z-10" />
                  <div className="space-y-1.5 max-w-xl">
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-extrabold uppercase tracking-widest text-violet-600 dark:text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded">
                        {getFormulaCategory(activeSelectedFormula)}
                      </span>
                      {subject && (
                        <span className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">
                          {subject}
                        </span>
                      )}
                    </div>
                    <h2 className="text-xl md:text-2xl font-black text-foreground">
                      {activeSelectedFormula.title || "Formula Analyzer"}
                    </h2>
                    <p className="text-xs sm:text-sm text-muted-foreground font-normal leading-relaxed">
                      {activeSelectedFormula.description || "Detailed dynamic calculations and visualizations."}
                    </p>
                  </div>
                  <button
                    onClick={() => toggleSaveFormula(activeSelectedFormula.id || activeSelectedFormula.raw)}
                    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl border transition-all text-xs font-bold ${savedIds.includes(activeSelectedFormula.id || activeSelectedFormula.raw)
                      ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-600 dark:text-yellow-400 shadow-sm"
                      : "bg-secondary/40 border-border/60 text-muted-foreground hover:border-border hover:bg-secondary/80 hover:text-foreground"
                      }`}
                  >
                    <Star className={`w-3.5 h-3.5 ${savedIds.includes(activeSelectedFormula.id || activeSelectedFormula.raw) ? "fill-yellow-500 text-yellow-500" : ""}`} />
                    <span>
                      {savedIds.includes(activeSelectedFormula.id || activeSelectedFormula.raw) ? "Saved" : "Save Formula"}
                    </span>
                  </button>
                </div>

                {/* Operations Tabs Navigation */}
                <div className="flex items-center justify-between w-full rounded-2xl border border-border/60 bg-secondary/40 p-1.5 shadow-inner overflow-x-auto">
                  <div className="flex items-center gap-1">
                    {tabs.map((tab) => {
                      const isActive = activeTabId === tab.id;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTabId(tab.id)}
                          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold whitespace-nowrap cursor-pointer transition-all ${isActive
                            ? "bg-violet-600 text-white shadow-md shadow-violet-600/15 scale-[1.01]"
                            : "text-muted-foreground hover:bg-secondary/40 hover:text-foreground"
                            }`}
                        >
                          <tab.icon className="w-3.5 h-3.5" />
                          <span>{tab.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  <div className="hidden sm:block text-[10px] font-extrabold uppercase tracking-widest text-muted-foreground px-3">
                    Step {activeTabIndex + 1} of 4
                  </div>
                </div>

                {/* Main Operations Interactive Screen */}
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTabId + "-" + activeSelectedFormula.id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -15 }}
                    transition={{ duration: 0.2 }}
                    className="min-h-[350px]"
                  >
                    {renderTabContent()}
                  </motion.div>
                </AnimatePresence>

                {/* Footer Controls */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pt-4 border-t border-border/60 gap-3">
                  <div className="flex items-center justify-between w-full sm:w-auto gap-3 order-1 sm:order-1">
                    <button
                      onClick={handlePrev}
                      disabled={activeTabIndex === 0}
                      className="flex-1 sm:flex-initial flex h-10 items-center justify-center gap-1.5 px-5 rounded-full border border-border/60 bg-secondary/30 text-xs font-bold text-muted-foreground hover:text-foreground hover:bg-secondary/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all active:scale-95 whitespace-nowrap"
                    >
                      <ChevronLeft className="w-4 h-4" /> Previous
                    </button>

                    <button
                      onClick={handleNext}
                      disabled={activeTabIndex === tabs.length - 1}
                      className="flex-1 sm:flex-initial flex h-10 items-center justify-center gap-1.5 px-5 rounded-full bg-violet-600 hover:bg-violet-500 text-xs font-bold text-white shadow-md shadow-violet-600/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all active:scale-95 whitespace-nowrap"
                    >
                      Next <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>

                  <Link
                    to="/sandbox/$simulationId"
                    params={{ simulationId: "default" }}
                    search={{
                      query: activeSelectedFormula?.title ? `Explain ${activeSelectedFormula.title}` : "Physics Simulation",
                    }}
                    className="w-full sm:w-auto flex h-10 items-center justify-center gap-1.5 px-6 rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 active:scale-95 text-xs font-bold text-white shadow-md shadow-violet-600/10 transition-all cursor-pointer whitespace-nowrap order-2 sm:order-2"
                  >
                    <Sparkles className="w-3.5 h-3.5" /> Create Simulation
                  </Link>
                </div>

              </div>
            ) : (
              <div className="rounded-3xl border border-border/60 bg-card/85 p-12 text-center text-muted-foreground shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
                <Compass className="w-12 h-12 text-muted-foreground mx-auto mb-4 animate-pulse" />
                <h3 className="text-lg font-bold text-foreground/80">Select a Formula or Query AI</h3>
                <p className="text-xs text-muted-foreground mt-1.5 max-w-md mx-auto leading-relaxed">
                  Choose a formula from the directory on the left to start analyzing it, or use the search bar above to query the AI Tutor for matching equations.
                </p>
              </div>
            )}
          </main>

        </div>
      </ErrorBoundary>
    </div>
  );
};

export default FormulaLabPage;
