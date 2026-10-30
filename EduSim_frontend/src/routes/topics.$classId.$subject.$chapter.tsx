import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { CurriculumService } from "@/services/curriculumService";
import { PageWrapper } from "@/components/Card";
import { Crumbs } from "@/components/Crumbs";
import { Play, GraduationCap, Sparkles, BookOpen, ChevronRight, ClipboardList, AlertCircle, RefreshCw } from "lucide-react";
import * as Icons from "lucide-react";

export const Route = createFileRoute("/topics/$classId/$subject/$chapter")({
  component: TopicsPage,
});

const getSubjectTheme = (subName: string) => {
  const name = subName.toLowerCase();
  if (name.includes("math")) {
    return {
      gradient: "from-purple-600 via-indigo-600 to-indigo-500",
      border: "hover:border-purple-500/30",
      iconBg: "bg-purple-500/20 text-purple-400 border-purple-500/30",
      glow: "hover:shadow-[0_0_30px_rgba(168,85,247,0.15)]",
      badge: "bg-purple-500/10 text-purple-500 dark:text-purple-400 border-purple-500/20",
      btnGradient: "from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 shadow-purple-500/20",
    };
  }
  if (name.includes("physic") || name.includes("science")) {
    return {
      gradient: "from-blue-600 via-indigo-600 to-blue-500",
      border: "hover:border-blue-500/30",
      iconBg: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      glow: "hover:shadow-[0_0_30px_rgba(59,130,246,0.15)]",
      badge: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
      btnGradient: "from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-blue-500/20",
    };
  }
  if (name.includes("biolog") || name.includes("evs")) {
    return {
      gradient: "from-emerald-600 via-teal-600 to-emerald-500",
      border: "hover:border-emerald-500/30",
      iconBg: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
      glow: "hover:shadow-[0_0_30px_rgba(16,185,129,0.15)]",
      badge: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
      btnGradient: "from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-emerald-500/20",
    };
  }
  return {
    gradient: "from-pink-600 via-rose-600 to-pink-500",
    border: "hover:border-pink-500/30",
    iconBg: "bg-pink-500/20 text-pink-400 border-pink-500/30",
    glow: "hover:shadow-[0_0_30px_rgba(244,63,94,0.15)]",
    badge: "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/20",
    btnGradient: "from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 shadow-pink-500/20",
  };
};

const getFloatingSymbols = (subName: string) => {
  const name = subName.toLowerCase();
  if (name.includes("math")) {
    return ["+", "−", "×", "÷", "√", "π", "%", "=", "∞", "x²", "a+b", "½"];
  }
  if (name.includes("physic") || name.includes("science")) {
    return ["c", "G", "g", "h", "λ", "Σ", "Ω", "Δ", "F=ma", "E=mc²", "v=d/t"];
  }
  return ["★", "✦", "●", "▲", "◆", "■", "✿", "☘", "☀", "⚡"];
};

const getChapterDescription = (chapName: string, subName: string) => {
  const name = chapName.toLowerCase();
  if (name.includes("motion")) {
    return "Explore the fundamental principles that govern the motion of objects in our physical world.";
  }
  if (name.includes("rational")) {
    return "Master the properties, operations, and representations of rational numbers on the number line.";
  }
  if (name.includes("force")) {
    return "Discover how forces shape actions, interactions, and the mechanics of the universe.";
  }
  if (name.includes("gravit")) {
    return "Delve into gravitational attraction, Kepler's laws, and cosmic orbital dynamics.";
  }
  return `Explore the fundamental concepts and practical applications of ${chapName} in ${subName}.`;
};

const getIndexColors = (i: number) => {
  const colors = [
    { bg: "bg-indigo-50 dark:bg-indigo-950/40", text: "text-indigo-600 dark:text-indigo-400", border: "border-indigo-100 dark:border-indigo-900/30" },
    { bg: "bg-blue-50 dark:bg-blue-950/40", text: "text-blue-600 dark:text-blue-400", border: "border-blue-100 dark:border-blue-900/30" },
    { bg: "bg-emerald-50 dark:bg-emerald-950/40", text: "text-emerald-600 dark:text-emerald-400", border: "border-emerald-100 dark:border-emerald-900/30" },
    { bg: "bg-amber-50 dark:bg-amber-950/40", text: "text-amber-600 dark:text-amber-400", border: "border-amber-100 dark:border-amber-900/30" },
    { bg: "bg-rose-50 dark:bg-rose-950/40", text: "text-rose-600 dark:text-rose-400", border: "border-rose-100 dark:border-rose-900/30" },
    { bg: "bg-purple-50 dark:bg-purple-950/40", text: "text-purple-600 dark:text-purple-400", border: "border-purple-100 dark:border-purple-900/30" },
  ];
  return colors[i % colors.length];
};

function TopicsPage() {
  const { classId, subject: subjectParam, chapter: chapterParam } = Route.useParams();
  const classIdNum = Number(classId);
  const navigate = useNavigate();

  let decodedChapterParam = chapterParam || "";
  try {
    decodedChapterParam = decodeURIComponent(chapterParam || "");
  } catch {
    // ignore
  }

  const {
    data: classes = [],
    isLoading: loadingClasses,
    isError: classesError,
    error: classesErr,
    refetch: refetchClasses,
  } = useQuery({
    queryKey: ["classes"],
    queryFn: CurriculumService.getClasses,
  });

  const {
    data: subjects = [],
    isLoading: loadingSubjects,
    isError: subjectsError,
    error: subjectsErr,
    refetch: refetchSubjects,
  } = useQuery({
    queryKey: ["subjects", classIdNum],
    queryFn: () => CurriculumService.getSubjects(classIdNum),
    enabled: !isNaN(classIdNum),
  });

  const c = classes.find((cls) => cls.id === classIdNum);
  const s = subjects.find(
    (sub) =>
      (sub.code || "").toLowerCase() === (subjectParam || "").toLowerCase() ||
      (sub.id || "").toLowerCase() === (subjectParam || "").toLowerCase()
  );

  const {
    data: chapters = [],
    isLoading: loadingChapters,
    isError: chaptersError,
    error: chaptersErr,
    refetch: refetchChapters,
  } = useQuery({
    queryKey: ["chapters", classIdNum, s?.id || subjectParam],
    queryFn: () => CurriculumService.getChapters(s?.id || subjectParam, classIdNum),
    enabled: !isNaN(classIdNum) && Boolean(subjectParam),
  });

  const chapter = chapters.find(
    (ch) => (ch.name || "").toLowerCase() === decodedChapterParam.toLowerCase()
  );

  const {
    data: topics = [],
    isLoading: loadingTopics,
    isError: topicsError,
    error: topicsErr,
    refetch: refetchTopics,
  } = useQuery({
    queryKey: ["topics", chapter?.id || decodedChapterParam, classIdNum],
    queryFn: () =>
      CurriculumService.getTopics(
        chapter?.id || decodedChapterParam,
        classIdNum
      ),
    enabled: !isNaN(classIdNum) && Boolean(decodedChapterParam),
  });

  const isLoading = loadingClasses || loadingSubjects || loadingChapters || loadingTopics;
  const isError = classesError || subjectsError || chaptersError || topicsError;
  const error = classesErr || subjectsErr || chaptersErr || topicsErr;

  if (isLoading) {
    return (
      <PageWrapper>
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground gap-4">
          <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium">Loading topics for {decodedChapterParam}...</p>
        </div>
      </PageWrapper>
    );
  }

  if (isError) {
    return (
      <PageWrapper>
        <div className="glass rounded-3xl p-8 border border-destructive/20 bg-destructive/10 text-destructive flex flex-col items-center gap-4 text-center max-w-xl mx-auto my-12">
          <AlertCircle className="w-10 h-10 text-destructive" />
          <h3 className="text-xl font-bold">Failed to load topics</h3>
          <p className="text-sm">{error instanceof Error ? error.message : "Unknown error"}</p>
          <button
            onClick={() => {
              refetchClasses();
              refetchSubjects();
              refetchChapters();
              refetchTopics();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-bold shadow hover:brightness-110 active:scale-95 transition-all mt-2"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        </div>
      </PageWrapper>
    );
  }

  if (!c || !s || !chapter) {
    return (
      <PageWrapper>
        <div className="glass rounded-3xl p-8 text-center text-muted-foreground my-12">
          Chapter, Subject or Class not found.
        </div>
      </PageWrapper>
    );
  }

  const theme = getSubjectTheme(s.name);
  const SubjectIcon = (Icons as any)[s.icon] || Icons.BookOpen;

  const symbolColorClass = s.name.toLowerCase().includes("math")
    ? "text-purple-300"
    : s.name.toLowerCase().includes("physic") || s.name.toLowerCase().includes("science")
    ? "text-cyan-300"
    : s.name.toLowerCase().includes("biolog") || s.name.toLowerCase().includes("evs")
    ? "text-emerald-300"
    : "text-pink-300";

  const handleAskTutor = (topic: any) => {
    navigate({
      to: "/tutor",
      search: {
        subject: s.name,
        class_name: c.name,
        chapter: chapter.name,
        topic: topic.name,
        prompt: `Explain "${topic.name}" from the chapter "${chapter.name}" in ${s.name} for ${c.name}.`,
      } as any,
    });
  };

  return (
    <PageWrapper>
      <Crumbs
        items={[
          { label: "Home", to: "/" },
          { label: c.name, to: "/subjects/$classId", params: { classId: String(c.id) } },
          {
            label: s.name,
            to: "/chapters/$classId/$subject",
            params: { classId: String(c.id), subject: s.id },
          },
          { label: chapter.name },
        ]}
      />

      {/* Hero Banner Section */}
      <div className={`relative overflow-hidden rounded-[32px] bg-gradient-to-r ${theme.gradient} py-16 px-8 md:py-20 md:px-12 mb-8 shadow-xl border border-white/10 min-h-[320px] md:min-h-[380px] flex items-center`}>
        {/* Glow Spheres */}
        <div className="absolute -right-20 -top-20 w-96 h-96 rounded-full bg-white/5 blur-[100px] pointer-events-none z-0" />
        <div className="absolute -left-20 -bottom-20 w-80 h-80 rounded-full bg-white/5 blur-[100px] pointer-events-none z-0" />

        {/* Beautiful Dotted Connecting Lines & Mathematical Graphs */}
        <svg className="absolute inset-0 w-full h-full opacity-25 pointer-events-none z-0" xmlns="http://www.w3.org/2000/svg">
          {/* Background Grid Pattern */}
          <defs>
            <pattern id="math-grid" width="30" height="30" patternUnits="userSpaceOnUse">
              <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
            </pattern>
            <linearGradient id="graphGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.1" />
              <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.7" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.1" />
            </linearGradient>
            <linearGradient id="graphGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#a855f7" stopOpacity="0.05" />
              <stop offset="50%" stopColor="#ec4899" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.05" />
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#math-grid)" />

          {/* Dotted axis line */}
          <line x1="380" y1="20" x2="380" y2="340" stroke="rgba(255,255,255,0.08)" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="300" y1="180" x2="800" y2="180" stroke="rgba(255,255,255,0.08)" strokeWidth="1" strokeDasharray="3 3" />

          {/* Sine curve graph with morphing animation */}
          <motion.path
            d="M 320 180 Q 420 50, 520 180 T 720 180"
            fill="none"
            stroke="url(#graphGrad1)"
            strokeWidth="3"
            animate={{
              d: [
                "M 320 180 Q 420 50, 520 180 T 720 180",
                "M 320 180 Q 420 280, 520 180 T 720 180",
                "M 320 180 Q 420 50, 520 180 T 720 180",
              ],
              strokeDashoffset: [0, -120]
            }}
            transition={{
              d: { duration: 10, repeat: Infinity, ease: "easeInOut" },
              strokeDashoffset: { duration: 24, repeat: Infinity, ease: "linear" }
            }}
            style={{ strokeDasharray: "5 5" }}
          />

          {/* Secondary cosine wave graph with morphing animation */}
          <motion.path
            d="M 320 120 Q 450 260, 580 100 T 760 180"
            fill="none"
            stroke="url(#graphGrad2)"
            strokeWidth="2"
            animate={{
              d: [
                "M 320 120 Q 450 260, 580 100 T 760 180",
                "M 320 200 Q 450 60, 580 220 T 760 180",
                "M 320 120 Q 450 260, 580 100 T 760 180",
              ],
              strokeDashoffset: [0, 120]
            }}
            transition={{
              d: { duration: 12, repeat: Infinity, ease: "easeInOut" },
              strokeDashoffset: { duration: 18, repeat: Infinity, ease: "linear" }
            }}
            style={{ strokeDasharray: "4 4" }}
          />

          {/* Dotted connectors */}
          <line x1="160" y1="120" x2="260" y2="80" stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="3 3" />
          <line x1="620" y1="240" x2="720" y2="280" stroke="rgba(255,255,255,0.06)" strokeWidth="1" strokeDasharray="3 3" />
        </svg>

        {/* Floating Mathematical / Science Symbols */}
        {(() => {
          const symbols = getFloatingSymbols(s.name);
          return symbols.map((sym, idx) => {
            const positions = [
              { top: "10%", left: "8%", rotate: "-12deg", scale: 1.1, opacity: 0.5, duration: 6, delay: 0 },
              { top: "25%", left: "28%", rotate: "15deg", scale: 0.9, opacity: 0.45, duration: 8, delay: 1.5 },
              { top: "68%", left: "14%", rotate: "8deg", scale: 1.2, opacity: 0.4, duration: 7, delay: 0.8 },
              { top: "18%", right: "18%", rotate: "-20deg", scale: 1.15, opacity: 0.4, duration: 9, delay: 0.3 },
              { top: "62%", right: "24%", rotate: "10deg", scale: 0.85, opacity: 0.5, duration: 6, delay: 2 },
              { top: "35%", right: "8%", rotate: "-5deg", scale: 1.0, opacity: 0.35, duration: 8, delay: 1.2 },
              { bottom: "15%", left: "42%", rotate: "18deg", scale: 0.95, opacity: 0.4, duration: 7, delay: 0.6 },
              { top: "8%", left: "55%", rotate: "-10deg", scale: 1.05, opacity: 0.4, duration: 6.5, delay: 1.8 },
              { bottom: "12%", left: "6%", rotate: "-15deg", scale: 1.1, opacity: 0.35, duration: 8, delay: 1 },
              { top: "15%", left: "48%", rotate: "0deg", scale: 1.25, opacity: 0.55, duration: 7, delay: 0.5 },
              { top: "12%", right: "6%", rotate: "25deg", scale: 1.1, opacity: 0.4, duration: 5, delay: 1.2 },
              { bottom: "12%", right: "6%", rotate: "-8deg", scale: 1.0, opacity: 0.45, duration: 9, delay: 0.8 },
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
                className={`absolute font-black select-none pointer-events-none ${textSizeClass} ${symbolColorClass}`}
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

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10 w-full">
          <div className="flex items-start md:items-center gap-6">
            {/* Subject icon badge */}
            <div className="p-5 rounded-[24px] bg-white/10 border border-white/20 flex items-center justify-center shrink-0 backdrop-blur-md">
              <SubjectIcon className="w-12 h-12 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5 mb-2">
                <span className="text-[12px] tracking-[0.25em] uppercase font-bold text-white/70">{c.name}</span>
                <span className="text-white/40">•</span>
                <span className="text-[12px] tracking-[0.25em] uppercase font-bold text-white bg-white/20 px-3.5 py-1 rounded-full border border-white/10">{s.name}</span>
              </div>
              <h1 className="text-5xl sm:text-6xl md:text-7.5xl font-black tracking-tight text-white leading-none mb-3">
                {chapter.name}
              </h1>
              <p className="text-white/85 text-base md:text-xl mt-3 max-w-2xl leading-relaxed font-medium">
                {getChapterDescription(chapter.name, s.name)}
              </p>
            </div>
          </div>

          {/* Chapter Mastery Card */}
          <div className="flex flex-col bg-white/95 dark:bg-slate-900/95 border border-slate-200/50 dark:border-slate-800/80 rounded-[24px] px-8 py-6.5 shrink-0 shadow-xl min-w-[200px] relative z-10">
            <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 font-extrabold tracking-wider text-[10.5px] uppercase">
              <span>👑</span> CHAPTER MASTERY
            </div>
            <div className="flex items-baseline gap-2 mt-3">
              <span className="text-5xl font-black text-slate-800 dark:text-white font-mono leading-none">
                {topics.length}
              </span>
              <span className="text-[12px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">
                Quests
              </span>
            </div>
            {/* Progress bar visual */}
            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2.5 rounded-full mt-4.5 overflow-hidden">
              <div className="bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-600 h-full rounded-full w-[35%] shadow-[0_0_8px_rgba(99,102,241,0.4)]" />
            </div>
          </div>
        </div>
      </div>

      {topics.length === 0 ? (
        <div className="text-center py-12 text-slate-500 bg-card border border-dashed border-border rounded-[24px]">
          No topics available yet. Let's head back home!
        </div>
      ) : (
        <div className="space-y-4">
          {topics.map((topic, i) => {
            const isPremium = topic.has_simulation && topic.simulation_route;
            const indexColors = getIndexColors(i);
            return (
              <motion.div
                key={topic.name}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 100, damping: 15, delay: i * 0.05 }}
                whileHover={{ scale: 1.01, y: -1 }}
                className={`group relative overflow-hidden bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800/80 rounded-[24px] p-5 md:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-5 transition-all shadow-sm hover:shadow-md ${theme.glow}`}
              >
                {/* Decorative background glow on hover */}
                <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

                <div className="flex items-center gap-4 relative z-10">
                  {/* Glowing Index Badge matching design mockup colors */}
                  <div className={`w-12 h-12 rounded-full ${indexColors.bg} flex items-center justify-center font-mono text-base ${indexColors.text} font-black border ${indexColors.border} transition-all shrink-0`}>
                    {String(i + 1).padStart(2, "0")}
                  </div>

                  <div>
                    <h3 className="font-extrabold text-base md:text-lg text-slate-800 dark:text-slate-100 group-hover:text-primary transition-colors">
                      {topic.name}
                    </h3>

                    <div className="flex flex-wrap items-center gap-2 mt-1.5">
                      {isPremium ? (
                        <span className="flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30">
                          <Sparkles className="w-3 h-3 text-emerald-500 dark:text-emerald-400 fill-emerald-500/20" />
                          Interactive Lab Ready
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700/60">
                          <BookOpen className="w-3 h-3" />
                          Theory Quest
                        </span>
                      )}
                      <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/30">
                        Class {classId}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 relative z-10 shrink-0 self-end sm:self-auto">
                  {/* Clipboard icon for Formula Lab */}
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={() =>
                      navigate({
                        to: `/formula-lab/${encodeURIComponent(topic.name)}`,
                        search: {
                          classId: classId,
                          subject: s.name,
                        } as any,
                      })
                    }
                    className="w-10 h-10 rounded-full border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center justify-center text-slate-400 dark:text-slate-500 hover:text-indigo-500 transition-all shrink-0"
                  >
                    <ClipboardList className="w-5 h-5 text-indigo-500" />
                  </motion.button>

                  {isPremium ? (
                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() =>
                        navigate({
                          to: topic.simulation_route || undefined,
                        })
                      }
                      className="flex items-center gap-2 px-5 py-3 rounded-2xl bg-gradient-to-r from-emerald-400 to-teal-500 hover:from-emerald-500 hover:to-teal-600 text-white text-xs md:text-sm font-extrabold shadow-lg shadow-emerald-500/20 border border-emerald-400/30 hover:scale-105 active:scale-95 transition-all"
                    >
                      <Play className="w-4 h-4 fill-white" /> Go to Lab
                    </motion.button>
                  ) : null}

                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => handleAskTutor(topic)}
                    className={`flex items-center gap-2 px-5 py-3 rounded-full bg-gradient-to-r ${theme.btnGradient} text-white text-xs md:text-sm font-extrabold shadow-lg hover:scale-105 active:scale-95 transition-all`}
                  >
                    <GraduationCap className="w-4 h-4" /> Explain Topic <ChevronRight className="w-4 h-4 ml-0.5" />
                  </motion.button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </PageWrapper>
  );
}
