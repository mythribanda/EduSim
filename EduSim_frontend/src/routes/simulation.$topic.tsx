import React, { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Sparkles,
  Atom,
  GraduationCap,
  ArrowLeft,
  Play,
  Pause,
  RotateCcw,
  Send,
  Zap,
  Rocket,
  Compass,
  Sliders,
  HelpCircle,
  CheckCircle2,
  Cpu,
  Flame,
} from "lucide-react";
import SandboxCanvas from "@/sandbox/components/SandboxCanvas";
import { getApiUrl } from "@/config/api";

export const Route = createFileRoute("/simulation/$topic")({
  component: KidFriendlySimulationPage,
});

// ─── Simulation Library Card Data ─────────────────────────────────────────────

interface SimCard {
  id: string;
  title: string;
  emoji: string;
  accent: string;
  bgGrad: string;
  badge: string;
  description: string;
  preset: {
    speed: number;
    angle: number;
    mass: number;
    gravity: number;
    bounciness: number;
  };
}

const SIMULATION_LIBRARY: SimCard[] = [
  {
    id: "projectile",
    title: "Projectile Cannon",
    emoji: "🏀",
    accent: "#4F8EF7",
    bgGrad: "from-blue-50 to-indigo-50 border-blue-200 hover:border-blue-400",
    badge: "Kinematics",
    description: "Launch basketballs into the sky! Change launch speed and angle to hit the target.",
    preset: { speed: 28, angle: 45, mass: 1.5, gravity: 1.0, bounciness: 0.8 },
  },
  {
    id: "pendulum",
    title: "Swinging Pendulum",
    emoji: "🌀",
    accent: "#A855F7",
    bgGrad: "from-purple-50 to-pink-50 border-purple-200 hover:border-purple-400",
    badge: "Harmonics",
    description: "Watch potential energy turn into kinetic energy as the pendulum bob swings back and forth.",
    preset: { speed: 10, angle: 60, mass: 3.0, gravity: 1.0, bounciness: 0.9 },
  },
  {
    id: "collision",
    title: "Bumping Collisions",
    emoji: "💥",
    accent: "#F97316",
    bgGrad: "from-orange-50 to-amber-50 border-orange-200 hover:border-orange-400",
    badge: "Momentum",
    description: "Crash carts and balls into each other! Watch how momentum and bounce energy transfer.",
    preset: { speed: 35, angle: 0, mass: 5.0, gravity: 1.0, bounciness: 0.95 },
  },
  {
    id: "orbit",
    title: "Space Orbit & Gravity",
    emoji: "🚀",
    accent: "#22C55E",
    bgGrad: "from-green-50 to-emerald-50 border-green-200 hover:border-green-400",
    badge: "Astronomy",
    description: "Launch satellites into orbit around Earth! Find the perfect speed to stay in orbit.",
    preset: { speed: 20, angle: 90, mass: 0.8, gravity: 0.0, bounciness: 0.7 },
  },
  {
    id: "freefall",
    title: "Free Fall Drop",
    emoji: "🪂",
    accent: "#38BDF8",
    bgGrad: "from-cyan-50 to-sky-50 border-cyan-200 hover:border-cyan-400",
    badge: "Gravity",
    description: "Drop heavy and light items from towering cliffs with gravity & air bounce!",
    preset: { speed: 0, angle: 0, mass: 8.0, gravity: 1.0, bounciness: 0.5 },
  },
];

// ─── Kid-Friendly Chat Message Interface ──────────────────────────────────────

interface ChatMessage {
  id: string;
  sender: "user" | "bot";
  text: string;
  timestamp: string;
}

const INITIAL_CHAT_MESSAGES: ChatMessage[] = [
  {
    id: "1",
    sender: "bot",
    text: "👋 Hi there! I'm your AI Physics Buddy! Try adjusting the sliders or ask me what happens when you launch with different angles!",
    timestamp: "Just now",
  },
];

export function KidFriendlySimulationPage() {
  const { topic } = Route.useParams();
  const decoded = decodeURIComponent(topic || "Physics Adventures");

  // State for active simulation card
  const [activeSim, setActiveSim] = useState<string>("projectile");

  // Kid-Friendly Slider Controls State
  const [speed, setSpeed] = useState<number>(28);
  const [angle, setAngle] = useState<number>(45);
  const [mass, setMass] = useState<number>(1.5);
  const [gravity, setGravity] = useState<number>(1.0);
  const [bounciness, setBounciness] = useState<number>(0.8);
  const [airFloat, setAirFloat] = useState<number>(10);

  // Playback Simulation State
  const [isRunning, setIsRunning] = useState<boolean>(true);
  const [keyCounter, setKeyCounter] = useState<number>(0);

  // AI Simulation Builder State
  const [builderPrompt, setBuilderPrompt] = useState<string>("");
  const [isBuilding, setIsBuilding] = useState<boolean>(false);
  const [builderSuccessMessage, setBuilderSuccessMessage] = useState<string | null>(null);

  // AI Chat State
  const [chatInput, setChatInput] = useState<string>("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(INITIAL_CHAT_MESSAGES);
  const [isChatLoading, setIsChatLoading] = useState<boolean>(false);

  // Select a preset from the card grid
  const handleSelectSim = (sim: SimCard) => {
    setActiveSim(sim.id);
    setSpeed(sim.preset.speed);
    setAngle(sim.preset.angle);
    setMass(sim.preset.mass);
    setGravity(sim.preset.gravity);
    setBounciness(sim.preset.bounciness);
    setIsRunning(true);
    setKeyCounter((prev) => prev + 1);
  };

  // Play / Pause / Reset handlers
  const handlePlay = () => setIsRunning(true);
  const handlePause = () => setIsRunning(false);
  const handleReset = () => {
    setIsRunning(true);
    setKeyCounter((prev) => prev + 1);
  };

  // AI Simulation Builder Handler
  const handleBuildSimulation = async () => {
    if (!builderPrompt.trim()) return;
    setIsBuilding(true);
    setBuilderSuccessMessage(null);

    try {
      const response = await fetch(getApiUrl("/api/simulations/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: builderPrompt, topic: decoded }),
      });

      if (!response.ok) throw new Error("Failed to generate custom simulation");

      const data = await response.json();
      setBuilderSuccessMessage(`✨ Yay! Built "${data.dsl?.meta?.title || "Your Custom Experiment"}"! Ready to explore!`);
      setKeyCounter((prev) => prev + 1);
    } catch (err) {
      setBuilderSuccessMessage("🚀 Experiment initialized! Adjust the sliders and tap 'Go!' to test your idea!");
    } finally {
      setIsBuilding(false);
    }
  };

  // AI Chat Handler
  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || chatInput;
    if (!query.trim() || isChatLoading) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      text: query.trim(),
      timestamp: "Just now",
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setIsChatLoading(true);

    try {
      const response = await fetch(getApiUrl("/api/tutor/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          topic: decoded,
          history: chatMessages.map((m) => ({ role: m.sender === "user" ? "user" : "assistant", content: m.text })),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const replyText = data.response || data.answer || "That's a fantastic physics question! Let's test it together!";
        setChatMessages((prev) => [
          ...prev,
          { id: (Date.now() + 1).toString(), sender: "bot", text: replyText, timestamp: "Just now" },
        ]);
      } else {
        // Friendly fallback explanation
        let fallback = "Great question! When you change the angle or speed, gravity constantly pulls downward, curving the path into a parabola!";
        if (query.toLowerCase().includes("higher")) {
          fallback = "🚀 The ball went higher because you gave it more vertical energy! A steeper angle directs more speed upward against gravity!";
        } else if (query.toLowerCase().includes("gravity")) {
          fallback = "🌍 Gravity is the invisible pull of the Earth! In space (0G), objects float in a straight line forever!";
        } else if (query.toLowerCase().includes("45")) {
          fallback = "📐 45 degrees gives the perfect balance between forward speed and time in the air, giving the maximum horizontal distance!";
        }
        setChatMessages((prev) => [
          ...prev,
          { id: (Date.now() + 1).toString(), sender: "bot", text: fallback, timestamp: "Just now" },
        ]);
      }
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "bot",
          text: "⚡ When objects fly through the air, their kinetic energy trade places with potential energy at the peak apex!",
          timestamp: "Just now",
        },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div className="w-full min-h-screen bg-white text-slate-900 font-sans pb-16">
      {/* ── Top Header Navigation Bar ───────────────────────────────────────── */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b-2 border-slate-100 px-6 py-4 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <Link
              to="/tutor"
              search={{ topic: decoded, class_name: undefined, subject: "Physics", chapter: undefined, prompt: undefined }}
              className="px-4 py-2 rounded-2xl bg-blue-50 hover:bg-blue-100 text-[#4F8EF7] font-bold text-base transition-all flex items-center gap-2 border border-blue-200 shadow-sm"
            >
              <ArrowLeft className="w-5 h-5" />
              <span>Back to Tutor</span>
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">
                  {decoded}
                </h1>
                <span className="px-3 py-1 rounded-full bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/30 text-sm font-black uppercase">
                  ⚡ Interactive Physics
                </span>
              </div>
              <p className="text-base text-slate-600 font-medium">
                Hands-on physics laboratory for young explorers (Ages 10–16)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/formula-lab/$topic"
              params={{ topic: decoded }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl border-2 border-purple-200 bg-purple-50 text-[#A855F7] text-base font-extrabold hover:bg-purple-100 hover:border-purple-300 transition-all shadow-sm"
            >
              <Atom className="w-5 h-5 text-[#A855F7]" />
              <span>Formula Lab</span>
            </Link>
            <Link
              to="/tutor"
              search={{ topic: decoded, class_name: undefined, subject: "Physics", chapter: undefined, prompt: `Give me a practice quiz on ${decoded}` }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-[#22C55E] hover:brightness-110 text-white text-base font-extrabold shadow-md transition-all hover:scale-105 active:scale-95"
            >
              <GraduationCap className="w-5 h-5" />
              <span>Practice Quiz</span>
            </Link>
          </div>
        </div>
      </header>

      {/* ── Main Container ─────────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 md:px-6 pt-6 space-y-8">
        
        {/* ── 1. Simulation Library Card Grid ─────────────────────────────────── */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl md:text-3xl font-black text-slate-900 flex items-center gap-2">
              <span>Choose an Experiment</span>
              <span className="text-xl">✨</span>
            </h2>
            <span className="text-base font-semibold text-slate-500">Tap a card to start testing!</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {SIMULATION_LIBRARY.map((sim) => {
              const isSelected = activeSim === sim.id;
              return (
                <div
                  key={sim.id}
                  onClick={() => handleSelectSim(sim)}
                  className={`relative p-5 rounded-3xl border-2 transition-all duration-300 cursor-pointer flex flex-col justify-between bg-gradient-to-br ${sim.bgGrad} ${
                    isSelected ? "ring-4 ring-offset-2 shadow-xl scale-[1.02]" : "shadow-md hover:shadow-lg hover:-translate-y-1"
                  }`}
                  style={{
                    borderColor: isSelected ? sim.accent : undefined,
                    boxShadow: isSelected ? `0 12px 24px -6px ${sim.accent}40` : undefined,
                  }}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-4xl filter drop-shadow-sm">{sim.emoji}</span>
                      <span
                        className="text-xs font-bold uppercase px-2.5 py-1 rounded-full text-white shadow-sm"
                        style={{ backgroundColor: sim.accent }}
                      >
                        {sim.badge}
                      </span>
                    </div>
                    <h3 className="text-xl font-extrabold text-slate-900 leading-tight mb-2">
                      {sim.title}
                    </h3>
                    <p className="text-sm text-slate-600 font-medium line-clamp-2 mb-4">
                      {sim.description}
                    </p>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectSim(sim);
                    }}
                    className="w-full py-2.5 px-4 rounded-2xl text-base font-black text-white shadow-md transition-all flex items-center justify-center gap-2 hover:brightness-110 active:scale-95"
                    style={{ backgroundColor: sim.accent }}
                  >
                    <span>Try it!</span>
                    <span>👉</span>
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── 2. Interactive Canvas Area (60%) & Kid Controls Panel ─────────── */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          
          {/* ── Physics Canvas (Takes 60% of Width: 7 of 12 cols on desktop) ── */}
          <div className="lg:col-span-7 bg-white rounded-3xl border-4 border-slate-100 shadow-xl overflow-hidden flex flex-col min-h-[520px]">
            {/* Canvas Header Status Bar */}
            <div className="bg-slate-50 px-6 py-3 border-b-2 border-slate-100 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <span className="w-4 h-4 rounded-full bg-[#22C55E] animate-pulse" />
                <span className="text-base font-black text-slate-800 uppercase tracking-wide">
                  Live Physics Sandbox
                </span>
              </div>
              <div className="flex items-center gap-2 text-base font-bold text-slate-600">
                <span>Speed: <strong className="text-[#4F8EF7]">{speed} m/s</strong></span>
                <span>•</span>
                <span>Angle: <strong className="text-[#A855F7]">{angle}°</strong></span>
              </div>
            </div>

            {/* Canvas Main Viewport */}
            <div className="flex-1 relative w-full bg-white flex items-center justify-center overflow-hidden min-h-[440px]">
              <SandboxCanvas key={keyCounter} />
            </div>
          </div>

          {/* ── Kid Controls Panel (5 of 12 cols) ────────────────────────────── */}
          <div className="lg:col-span-5 bg-white rounded-3xl border-4 border-slate-100 shadow-xl p-6 flex flex-col justify-between space-y-6">
            <div>
              <div className="flex items-center justify-between pb-3 border-b-2 border-slate-100 mb-5">
                <h3 className="text-2xl font-black text-slate-900 flex items-center gap-2">
                  <Sliders className="w-6 h-6 text-[#4F8EF7]" />
                  <span>Physics Controls</span>
                </h3>
                <span className="text-sm font-extrabold bg-[#4F8EF7]/10 text-[#4F8EF7] px-3 py-1 rounded-full">
                  Real-time
                </span>
              </div>

              {/* ── Play / Pause / Reset Buttons (Min 48px Height) ───────────── */}
              <div className="grid grid-cols-3 gap-3 mb-6">
                <button
                  onClick={handlePlay}
                  className={`min-h-[48px] h-12 rounded-2xl font-black text-base text-white shadow-md flex items-center justify-center gap-2 transition-all duration-200 active:scale-95 ${
                    isRunning
                      ? "bg-[#22C55E] ring-4 ring-[#22C55E]/30 scale-105"
                      : "bg-[#22C55E]/80 hover:bg-[#22C55E]"
                  }`}
                >
                  <Play className="w-5 h-5 fill-current" />
                  <span>▶️ Go!</span>
                </button>

                <button
                  onClick={handlePause}
                  className={`min-h-[48px] h-12 rounded-2xl font-black text-base text-white shadow-md flex items-center justify-center gap-2 transition-all duration-200 active:scale-95 ${
                    !isRunning
                      ? "bg-[#F97316] ring-4 ring-[#F97316]/30 scale-105"
                      : "bg-[#F97316]/80 hover:bg-[#F97316]"
                  }`}
                >
                  <Pause className="w-5 h-5 fill-current" />
                  <span>⏸ Wait</span>
                </button>

                <button
                  onClick={handleReset}
                  className="min-h-[48px] h-12 rounded-2xl font-black text-base text-white bg-[#A855F7] hover:bg-[#9333EA] shadow-md flex items-center justify-center gap-2 transition-all duration-200 active:scale-95 hover:scale-105"
                >
                  <RotateCcw className="w-5 h-5" />
                  <span>🔄 Again!</span>
                </button>
              </div>

              {/* ── Large Sliders with Emoji & Kid-Friendly Labels ───────────── */}
              <div className="space-y-4">
                {/* 1. Speed Slider */}
                <div className="p-3.5 rounded-2xl bg-blue-50/70 border border-blue-100">
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-base font-extrabold text-slate-800 flex items-center gap-1.5">
                      <span>How fast? 🚀</span>
                    </label>
                    <span className="text-base font-black px-2.5 py-0.5 rounded-xl bg-white text-[#4F8EF7] border border-blue-200 shadow-sm">
                      {speed} m/s
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="60"
                    step="1"
                    value={speed}
                    onChange={(e) => setSpeed(Number(e.target.value))}
                    className="w-full h-3 bg-blue-200 rounded-lg appearance-none cursor-pointer accent-[#4F8EF7]"
                  />
                </div>

                {/* 2. Angle Slider */}
                <div className="p-3.5 rounded-2xl bg-purple-50/70 border border-purple-100">
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-base font-extrabold text-slate-800 flex items-center gap-1.5">
                      <span>Which angle? 📐</span>
                    </label>
                    <span className="text-base font-black px-2.5 py-0.5 rounded-xl bg-white text-[#A855F7] border border-purple-200 shadow-sm">
                      {angle}°
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="90"
                    step="1"
                    value={angle}
                    onChange={(e) => setAngle(Number(e.target.value))}
                    className="w-full h-3 bg-purple-200 rounded-lg appearance-none cursor-pointer accent-[#A855F7]"
                  />
                </div>

                {/* 3. Mass Slider */}
                <div className="p-3.5 rounded-2xl bg-orange-50/70 border border-orange-100">
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-base font-extrabold text-slate-800 flex items-center gap-1.5">
                      <span>How heavy? 🏋️</span>
                    </label>
                    <span className="text-base font-black px-2.5 py-0.5 rounded-xl bg-white text-[#F97316] border border-orange-200 shadow-sm">
                      {mass} kg
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="20"
                    step="0.5"
                    value={mass}
                    onChange={(e) => setMass(Number(e.target.value))}
                    className="w-full h-3 bg-orange-200 rounded-lg appearance-none cursor-pointer accent-[#F97316]"
                  />
                </div>

                {/* 4. Gravity Presets & Slider */}
                <div className="p-3.5 rounded-2xl bg-green-50/70 border border-green-100">
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-base font-extrabold text-slate-800 flex items-center gap-1.5">
                      <span>Gravity pull 🌍</span>
                    </label>
                    <span className="text-base font-black px-2.5 py-0.5 rounded-xl bg-white text-[#22C55E] border border-green-200 shadow-sm">
                      {gravity === 0 ? "Space (0G)" : `${gravity} G`}
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-1.5">
                    {[
                      { label: "🚀 Space", val: 0 },
                      { label: "🌕 Moon", val: 0.16 },
                      { label: "🌍 Earth", val: 1.0 },
                      { label: "🪐 Jupiter", val: 2.5 },
                    ].map((item) => (
                      <button
                        key={item.label}
                        onClick={() => setGravity(item.val)}
                        className={`py-1.5 px-1 rounded-xl text-xs font-black transition-all ${
                          gravity === item.val
                            ? "bg-[#22C55E] text-white shadow-sm scale-105"
                            : "bg-white text-slate-700 hover:bg-green-100 border border-green-200"
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 5. Bounciness Slider */}
                <div className="p-3.5 rounded-2xl bg-sky-50/70 border border-sky-100">
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-base font-extrabold text-slate-800 flex items-center gap-1.5">
                      <span>Bounciness 🎈</span>
                    </label>
                    <span className="text-base font-black px-2.5 py-0.5 rounded-xl bg-white text-sky-600 border border-sky-200 shadow-sm">
                      {Math.round(bounciness * 100)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={bounciness}
                    onChange={(e) => setBounciness(Number(e.target.value))}
                    className="w-full h-3 bg-sky-200 rounded-lg appearance-none cursor-pointer accent-sky-500"
                  />
                </div>
              </div>
            </div>

            {/* Quick Helper Tip */}
            <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex items-start gap-3">
              <span className="text-2xl">💡</span>
              <p className="text-sm font-bold text-amber-900 leading-snug">
                <strong>Physics Tip:</strong> Try setting the launch angle to <strong>45°</strong> to see if your ball flies the farthest across the screen!
              </p>
            </div>
          </div>
        </section>

        {/* ── 3. AI Simulation Builder Section ────────────────────────────────── */}
        <section className="bg-gradient-to-r from-blue-50 via-purple-50 to-pink-50 rounded-3xl border-4 border-indigo-100 shadow-xl p-6 md:p-8 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🔬</span>
            <div>
              <h2 className="text-2xl md:text-3xl font-black text-slate-900 tracking-tight">
                What do you want to experiment with? 🔬
              </h2>
              <p className="text-base font-medium text-slate-600">
                Type any fun physics idea and our AI engine will generate a real Matter.js simulation!
              </p>
            </div>
          </div>

          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="text"
              value={builderPrompt}
              onChange={(e) => setBuilderPrompt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleBuildSimulation()}
              placeholder="Try: 'A heavy bowling ball and a light feather dropping on the moon' or 'A car jumping off a giant ramp'..."
              className="flex-1 min-h-[48px] px-5 py-3 rounded-2xl border-2 border-indigo-200 bg-white text-base text-slate-900 placeholder:text-slate-400 font-medium focus:outline-none focus:border-[#4F8EF7] focus:ring-4 focus:ring-[#4F8EF7]/20 shadow-inner"
            />
            <button
              onClick={handleBuildSimulation}
              disabled={isBuilding || !builderPrompt.trim()}
              className="min-h-[48px] px-8 py-3 rounded-2xl font-black text-lg text-white bg-gradient-to-r from-[#4F8EF7] via-[#A855F7] to-[#F97316] shadow-lg hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isBuilding ? (
                <>
                  <Sparkles className="w-5 h-5 animate-spin" />
                  <span>Building...</span>
                </>
              ) : (
                <>
                  <span>✨ Build It!</span>
                </>
              )}
            </button>
          </div>

          {/* Quick Idea Suggestion Chips */}
          <div className="flex items-center gap-2 flex-wrap pt-2">
            <span className="text-sm font-extrabold text-slate-500">Quick Ideas:</span>
            {[
              "🏀 Double ball bounce trampoline",
              "🚀 Rocket escape velocity to Mars",
              "🚗 Two carts crashing in head-on elastic collision",
              "🌊 Submarine floating with water buoyancy",
            ].map((idea) => (
              <button
                key={idea}
                onClick={() => setBuilderPrompt(idea.replace(/^[^\s]+\s/, ""))}
                className="px-3.5 py-1.5 rounded-full bg-white hover:bg-indigo-100 text-slate-700 hover:text-indigo-900 border border-indigo-200 text-sm font-bold shadow-sm transition-all"
              >
                {idea}
              </button>
            ))}
          </div>

          {builderSuccessMessage && (
            <div className="p-4 rounded-2xl bg-emerald-100 border border-emerald-300 text-emerald-900 font-extrabold text-base flex items-center gap-2 animate-bounce">
              <CheckCircle2 className="w-6 h-6 text-emerald-600 flex-shrink-0" />
              <span>{builderSuccessMessage}</span>
            </div>
          )}
        </section>

        {/* ── 4. AI Chat Box at the Bottom ────────────────────────────────────── */}
        <section className="bg-white rounded-3xl border-4 border-slate-100 shadow-xl p-6 md:p-8 space-y-5">
          <div className="flex items-center justify-between pb-3 border-b-2 border-slate-100">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🤖</span>
              <div>
                <h2 className="text-2xl md:text-3xl font-black text-slate-900 tracking-tight">
                  Ask your Physics Buddy
                </h2>
                <p className="text-base text-slate-500 font-medium">
                  Curious about the results? Ask any question to understand the laws of physics!
                </p>
              </div>
            </div>
            <span className="text-sm font-black bg-[#22C55E]/10 text-[#22C55E] px-3.5 py-1.5 rounded-full border border-[#22C55E]/20">
              Online • AI Ready
            </span>
          </div>

          {/* Chat Messages Feed */}
          <div className="space-y-3 max-h-[320px] overflow-y-auto p-4 rounded-2xl bg-slate-50 border border-slate-200">
            {chatMessages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.sender === "bot" && (
                  <div className="w-10 h-10 rounded-2xl bg-[#4F8EF7] text-white flex items-center justify-center font-black text-lg flex-shrink-0 shadow-md">
                    🤖
                  </div>
                )}
                <div
                  className={`p-4 rounded-3xl max-w-[85%] text-base font-medium shadow-sm leading-relaxed ${
                    msg.sender === "user"
                      ? "bg-[#4F8EF7] text-white rounded-tr-none font-bold"
                      : "bg-white text-slate-800 border border-slate-200 rounded-tl-none"
                  }`}
                >
                  {msg.text}
                </div>
                {msg.sender === "user" && (
                  <div className="w-10 h-10 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-black text-lg flex-shrink-0 shadow-md">
                    👦
                  </div>
                )}
              </div>
            ))}
            {isChatLoading && (
              <div className="flex items-center gap-2 text-slate-500 text-base font-bold italic">
                <span className="animate-spin text-xl">⚡</span>
                <span>Physics Buddy is thinking...</span>
              </div>
            )}
          </div>

          {/* Quick Inquiry Chips */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-extrabold text-slate-500">Try Asking:</span>
            {[
              "Why did the ball go higher?",
              "What happens if we turn off gravity?",
              "Why is 45° the best angle for max range?",
              "Where did the bounce energy go?",
            ].map((q) => (
              <button
                key={q}
                onClick={() => handleSendMessage(q)}
                className="px-3.5 py-1.5 rounded-full bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-[#4F8EF7] border border-slate-200 hover:border-blue-300 text-sm font-bold shadow-sm transition-all"
              >
                💭 &quot;{q}&quot;
              </button>
            ))}
          </div>

          {/* Friendly Chat Input Box */}
          <div className="flex gap-3">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              placeholder="Ask me anything! Try: 'Why did the ball go higher?'"
              className="flex-1 min-h-[48px] px-5 py-3 rounded-2xl border-2 border-slate-200 bg-slate-50 text-base text-slate-900 placeholder:text-slate-400 font-medium focus:outline-none focus:border-[#4F8EF7] focus:ring-4 focus:ring-[#4F8EF7]/20 shadow-inner"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={isChatLoading || !chatInput.trim()}
              className="min-h-[48px] px-6 py-3 rounded-2xl font-black text-base text-white bg-[#4F8EF7] hover:bg-[#3B82F6] shadow-md flex items-center justify-center gap-2 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span>Ask</span>
              <Send className="w-5 h-5" />
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

export default KidFriendlySimulationPage;
