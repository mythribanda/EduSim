import { createFileRoute } from "@tanstack/react-router";
import React, { useState, useEffect, useRef } from "react";
import { PageWrapper } from "@/components/Card";
import { Button } from "@/components/ui/button";
import {
  Sparkles,
  Link2,
  Download,
  Box,
  GitBranch,
  BarChart2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Zap,
} from "lucide-react";
import { useAgentSimulation } from "@/hooks/useAgentSimulation";
import { useSavedSimulations } from "@/hooks/useSavedSimulations";
import SandboxCanvas from "@/sandbox/components/SandboxCanvas";
import type {
  PhysicsDSL,
  DSLEntity,
  DSLInteraction,
  DSLVisualization,
} from "@/types/simulation";

export const Route = createFileRoute("/ai-agent")({
  component: AIAgentPage,
});

const SUGGESTION_CHIPS = [
  "Show me two balls crashing into each other 💥",
  "Make a really fast pendulum 🌀",
  "Drop a heavy rock from a tall building 🪨",
  "Slide a block down a ramp 📐",
];

// =========================================================
// DSL Inspector Sub-components (Technical Breakdown)
// =========================================================

function EntityCard({ entity }: { entity: DSLEntity }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 space-y-1">
      <div className="flex items-center gap-2">
        <Box className="w-3.5 h-3.5 text-[#4F8EF7]" />
        <span className="font-mono text-xs font-semibold text-gray-800">{entity.id}</span>
        <span className="px-1.5 py-0.5 rounded bg-purple-100 text-[10px] text-purple-700 font-medium">
          {entity.type}
        </span>
      </div>
      {entity.mass !== null && (
        <p className="text-xs text-gray-500">mass: {entity.mass} kg</p>
      )}
    </div>
  );
}

function InteractionCard({ interaction }: { interaction: DSLInteraction }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 space-y-1">
      <div className="flex items-center gap-2">
        <GitBranch className="w-3.5 h-3.5 text-purple-600" />
        <span className="font-mono text-xs font-semibold text-gray-800">{interaction.type}</span>
        <span className="text-xs text-gray-500">→ {interaction.target}</span>
      </div>
      {Object.keys(interaction.parameters).length > 0 && (
        <pre className="text-[10px] text-gray-600 font-mono">
          {JSON.stringify(interaction.parameters, null, 2)}
        </pre>
      )}
    </div>
  );
}

function VisualizationBadge({ viz }: { viz: DSLVisualization }) {
  return (
    <span className="px-2.5 py-1 rounded-full bg-blue-50 border border-blue-200 text-[#4F8EF7] text-xs font-mono font-medium">
      {viz.type}
    </span>
  );
}

function DSLInspector({ dsl }: { dsl: PhysicsDSL }) {
  const [showRaw, setShowRaw] = useState(false);

  return (
    <div className="space-y-4 pt-2">
      {/* Header row */}
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-[#4F8EF7]" />
            <span className="text-sm font-semibold text-gray-800 font-mono">
              {dsl.simulation_type}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{dsl.topic}</p>
        </div>
        <div className="text-right text-xs text-gray-500 space-y-0.5">
          <p>g = {dsl.environment.gravity} m/s²</p>
          <p>μ = {dsl.environment.friction}</p>
        </div>
      </div>

      {/* Entities */}
      <div>
        <p className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1.5">
          <Box className="w-3.5 h-3.5 text-[#4F8EF7]" /> Entities ({dsl.entities.length})
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {dsl.entities.map((e: DSLEntity) => (
            <EntityCard key={e.id} entity={e} />
          ))}
        </div>
      </div>

      {/* Interactions */}
      <div>
        <p className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1.5">
          <GitBranch className="w-3.5 h-3.5 text-purple-600" /> Interactions ({dsl.interactions.length})
        </p>
        <div className="space-y-2">
          {dsl.interactions.map((inter: DSLInteraction, i: number) => (
            <InteractionCard key={i} interaction={inter} />
          ))}
        </div>
      </div>

      {/* Visualizations */}
      <div>
        <p className="text-xs font-semibold text-gray-600 mb-2 flex items-center gap-1.5">
          <BarChart2 className="w-3.5 h-3.5 text-blue-600" /> Visualizations
        </p>
        <div className="flex flex-wrap gap-2">
          {dsl.visualizations.map((v: DSLVisualization, i: number) => (
            <VisualizationBadge key={i} viz={v} />
          ))}
        </div>
      </div>

      {/* Equations */}
      {dsl.equations.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-2">Key Equations</p>
          <div className="space-y-1">
            {dsl.equations.map((eq: string, i: number) => (
              <p
                key={i}
                className="font-mono text-xs text-purple-700 bg-purple-50 px-3 py-1.5 rounded-lg border border-purple-200"
              >
                {eq}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Raw JSON toggle */}
      <button
        type="button"
        onClick={() => setShowRaw(!showRaw)}
        className="w-full text-left text-xs p-2.5 rounded-xl border border-gray-200 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-gray-600 font-medium transition-colors cursor-pointer"
      >
        <span>Raw DSL JSON</span>
        {showRaw ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {showRaw && (
        <pre className="text-[11px] font-mono text-gray-700 bg-gray-900 text-gray-100 rounded-xl p-3 overflow-auto max-h-64">
          {JSON.stringify(dsl, null, 2)}
        </pre>
      )}

      {/* Notice */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-3">
        <p className="text-xs text-blue-700 flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 flex-shrink-0" />
          Physics DSL compiled successfully. Executing inside interactive sandbox canvas.
        </p>
      </div>
    </div>
  );
}

// =========================================================
// Main Page: Kid-Friendly AI Simulation Builder
// =========================================================

function AIAgentPage() {
  const {
    simulation,
    loading,
    streaming,
    error,
    progress,
    progressPercentage,
    generateStream,
    clearError,
  } = useAgentSimulation();

  const { saveSimulation } = useSavedSimulations();

  const [prompt, setPrompt] = useState("");
  const canvasRef = useRef<HTMLDivElement>(null);

  // Auto-save generated simulation
  useEffect(() => {
    if (simulation) {
      saveSimulation({
        id: simulation.id,
        title: simulation.title,
        subject: simulation.topic?.subject || "Physics",
        type: "dsl",
        simulation: simulation.dsl,
      });

      // Smooth scroll down to the canvas
      setTimeout(() => {
        canvasRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 250);
    }
  }, [simulation, saveSimulation]);

  const handleGenerate = async () => {
    if (!prompt.trim() || loading || streaming) return;
    await generateStream(prompt, "medium");
  };

  const handleShare = async () => {
    if (!simulation?.id) return;
    const shareUrl = `${window.location.origin}/ai-agent?sim=${simulation.id}`;
    try {
      await navigator.clipboard.writeText(shareUrl);
      alert("Share link copied to clipboard!");
    } catch {
      alert("Failed to copy share link");
    }
  };

  const handleExportDSL = () => {
    if (!simulation?.dsl) return;
    const blob = new Blob([JSON.stringify(simulation.dsl, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${simulation.id ?? "simulation"}.dsl.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Derive 3 kid-friendly progress states
  const getKidProgressState = () => {
    const stage = progress?.stage?.toLowerCase() || "";
    if (
      stage.includes("analyz") ||
      stage.includes("detect") ||
      stage.includes("retriev") ||
      progressPercentage < 35
    ) {
      return "Understanding your idea... 🧠";
    }
    if (
      stage.includes("extract") ||
      stage.includes("synthesiz") ||
      stage.includes("sanitiz") ||
      progressPercentage < 80
    ) {
      return "Building the simulation... ⚙️";
    }
    return "Almost ready... ✨";
  };

  return (
    <PageWrapper>
      <div className="max-w-5xl mx-auto space-y-8 py-6 px-4">
        {/* 1 & 2: Header and Subtitle */}
        <div className="text-center space-y-2">
          <h1 className="text-[32px] font-bold text-[#1F2937] tracking-tight flex items-center justify-center gap-2">
            Build Your Own Experiment ✨
          </h1>
          <p className="text-[18px] text-[#6B7280]">
            Describe what you want to see, and I'll build it for you!
          </p>
        </div>

        {/* Input Card Container */}
        <div className="bg-white rounded-[24px] p-6 sm:p-8 shadow-md border border-gray-100 space-y-6">
          {/* 3: Suggestion chips above the input */}
          <div className="space-y-2.5">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
              💡 Tap an idea to try it out
            </label>
            <div className="flex flex-wrap gap-2.5">
              {SUGGESTION_CHIPS.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  onClick={() => {
                    setPrompt(chip);
                    clearError();
                  }}
                  className="px-4 py-2 bg-gray-50 hover:bg-blue-50/80 active:bg-blue-100 text-gray-700 hover:text-[#4F8EF7] border border-gray-200 hover:border-blue-300 rounded-full text-sm font-medium transition-all duration-150 cursor-pointer shadow-2xs"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>

          {/* 4: Large Textarea (3 rows, placeholder) */}
          <div className="space-y-2">
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="What do you want to experiment with? Describe it in your own words..."
              disabled={loading || streaming}
              className="w-full text-[16px] p-4 bg-gray-50/80 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-[#4F8EF7] focus:bg-white text-[#1F2937] resize-none transition-all shadow-2xs disabled:opacity-60"
            />
          </div>

          {/* 5: "✨ Build It!" button */}
          <div>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={loading || streaming || !prompt.trim()}
              className="w-full h-[56px] bg-[#4F8EF7] hover:bg-[#3b7be8] active:bg-[#2b6bd8] text-white text-[18px] font-bold rounded-2xl flex items-center justify-center gap-2 shadow-md hover:shadow-lg transition-all duration-200 disabled:opacity-50 cursor-pointer"
            >
              <Sparkles className="w-5 h-5 fill-white" />
              <span>✨ Build It!</span>
            </button>
          </div>

          {/* 6: Progress states shown below the button */}
          {(loading || streaming) && (
            <div className="bg-blue-50/80 border border-blue-200 rounded-2xl p-5 space-y-3 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-[17px] font-bold text-[#1F2937] flex items-center gap-2 animate-pulse">
                  {getKidProgressState()}
                </span>
                <span className="text-sm font-semibold text-[#4F8EF7]">
                  {progressPercentage || 25}%
                </span>
              </div>
              <div className="w-full h-3 bg-blue-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#4F8EF7] rounded-full transition-all duration-300"
                  style={{ width: `${Math.max(15, progressPercentage)}%` }}
                />
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 flex items-center justify-between">
              <p className="text-sm text-red-700 font-medium flex items-center gap-2">
                <span>⚠️</span>
                <span>{error}</span>
              </p>
              <button
                type="button"
                onClick={clearError}
                className="text-xs text-red-600 hover:underline font-semibold cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>

        {/* 7: On success, smoothly scroll down to show the sandbox canvas */}
        {simulation && (
          <div ref={canvasRef} className="pt-4 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-[24px] border border-gray-100 shadow-md">
              <div>
                <h2 className="text-2xl font-bold text-[#1F2937] flex items-center gap-2">
                  <span>🎉</span> {simulation.title || "Your Custom Experiment"}
                </h2>
                <p className="text-sm text-[#6B7280] mt-1">
                  {simulation.description || "Interact with the physical objects on the canvas below!"}
                </p>
              </div>
              <div className="flex items-center gap-2.5">
                <Button size="sm" variant="outline" onClick={handleShare} className="rounded-xl cursor-pointer">
                  <Link2 className="w-4 h-4 mr-1.5" /> Share
                </Button>
                <Button size="sm" variant="outline" onClick={handleExportDSL} className="rounded-xl cursor-pointer">
                  <Download className="w-4 h-4 mr-1.5" /> Export DSL
                </Button>
              </div>
            </div>

            {/* Sandbox Canvas Container */}
            <div className="w-full h-[640px] rounded-[24px] overflow-hidden border border-gray-200 shadow-xl relative bg-slate-950">
              <SandboxCanvas />
            </div>

            {/* Collapsible Technical Details for curious students */}
            {simulation.dsl && (
              <details className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm group">
                <summary className="font-semibold text-sm text-gray-700 cursor-pointer flex items-center justify-between">
                  <span>🔬 View Physical Entities & Equations Breakdown</span>
                  <ChevronDown className="w-4 h-4 transition-transform group-open:rotate-180 text-gray-500" />
                </summary>
                <div className="pt-4 border-t mt-3">
                  <DSLInspector dsl={simulation.dsl as unknown as PhysicsDSL} />
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}

export default AIAgentPage;
