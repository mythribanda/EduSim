import React, { useState, useEffect, useMemo } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { ArrowLeft, Play, Sparkles, AlertCircle } from "lucide-react";
import { getApiUrl } from "@/config/api";
import { getFormulaDescription } from "@/lib/formulaDescriptions";

export const Route = createFileRoute("/simulations/$id")({
  component: SimulationRunnerPage,
});

interface PropertySchema {
  title?: string;
  description?: string;
  default?: any;
  type?: string;
  minimum?: number;
  maximum?: number;
  enum?: string[];
  options?: string[];
}

interface SchemaResponse {
  success: boolean;
  simulation_id: string;
  meta: {
    id: string;
    title: string;
    emoji: string;
    description: string;
    category: string;
    difficulty: "beginner" | "intermediate" | "advanced";
    key_concepts?: string[];
  };
  schema: {
    title: string;
    type: string;
    properties: Record<string, PropertySchema>;
    required?: string[];
  };
}

interface RunResult {
  graph_data?: any[];
  formulas_used?: string[];
  [key: string]: any;
}

const LINE_COLORS = ["#4F8EF7", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899"];

const SUGGESTED_QUESTIONS = [
  "Why did this happen?",
  "What if I changed the speed?",
  "Explain the formula",
];

export function SimulationRunnerPage() {
  const { id } = Route.useParams();

  const [meta, setMeta] = useState<SchemaResponse["meta"] | null>(null);
  const [properties, setProperties] = useState<Record<string, PropertySchema>>({});
  const [params, setParams] = useState<Record<string, any>>({});
  const [result, setResult] = useState<RunResult | null>(null);

  const [isLoadingSchema, setIsLoadingSchema] = useState<boolean>(true);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // AI Tutor State
  const [studentQuestion, setStudentQuestion] = useState<string>("");
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);
  const [isAskingAi, setIsAskingAi] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Load schema and initialize defaults
  useEffect(() => {
    let isMounted = true;
    const fetchSchema = async () => {
      setIsLoadingSchema(true);
      setErrorMsg(null);
      try {
        const res = await fetch(getApiUrl(`/api/simulations/static/${id}/schema`));
        if (!res.ok) throw new Error(`Simulation '${id}' schema not found.`);
        const data: SchemaResponse = await res.json();
        if (isMounted) {
          setMeta(data.meta);
          const props = data.schema?.properties || {};
          setProperties(props);

          // Build default params
          const initialParams: Record<string, any> = {};
          Object.entries(props).forEach(([key, schema]) => {
            initialParams[key] = schema.default !== undefined ? schema.default : 0;
          });
          setParams(initialParams);

          // Initial calculation
          runSimulation(initialParams);
        }
      } catch (err: any) {
        if (isMounted) setErrorMsg(err.message || "Failed to load simulation schema.");
      } finally {
        if (isMounted) setIsLoadingSchema(false);
      }
    };

    fetchSchema();
    return () => {
      isMounted = false;
    };
  }, [id]);

  const runSimulation = async (currentParams = params) => {
    setIsRunning(true);
    setErrorMsg(null);
    try {
      const res = await fetch(getApiUrl(`/api/simulations/static/${id}/run`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentParams),
      });

      if (!res.ok) throw new Error("Simulation calculation failed.");
      const data = await res.json();
      setResult(data.result || data);
    } catch (err: any) {
      setErrorMsg(err.message || "Error running simulation.");
    } finally {
      setIsRunning(false);
    }
  };

  const handleParamChange = (key: string, value: any) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  const handleAskAi = async (overrideQuestion?: string) => {
    const questionToAsk = (overrideQuestion || studentQuestion).trim();
    if (!questionToAsk || isAskingAi) return;

    setIsAskingAi(true);
    setAiError(null);
    setStudentQuestion("");

    try {
      const res = await fetch(getApiUrl("/api/simulations/explain"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          simulation_id: id,
          params,
          result: result || {},
          student_question: questionToAsk,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to get explanation");
      }

      const data = await res.json();
      setAiExplanation(data.explanation || "Great question! Try tweaking the controls to explore further.");
    } catch (err: any) {
      setAiError("Oops! Try asking again 😅");
    } finally {
      setIsAskingAi(false);
    }
  };

  // Helper to extract unit from property description (e.g., "(m/s)")
  const getUnit = (description?: string): string => {
    if (!description) return "";
    const match = description.match(/\(([^)]+)\)/);
    if (match && match[1]) {
      const val = match[1];
      if (val.includes("m/s") || val.includes("kg") || val.includes("m") || val.includes("N") || val.includes("s") || val.includes("°")) {
        return val;
      }
    }
    return "";
  };

  // Format friendly labels
  const formatFriendlyLabel = (key: string, schema: PropertySchema): string => {
    if (schema.title) return schema.title;
    return key
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  };

  // Prepare chart series and data
  const chartConfig = useMemo(() => {
    if (!result?.graph_data || !Array.isArray(result.graph_data) || result.graph_data.length === 0) {
      return { tabs: [], data: [] };
    }

    const firstRow = result.graph_data[0];

    // Projectile Motion [t, x, y, vx, vy]
    if (id === "projectile-motion" && firstRow.length >= 5) {
      const data = result.graph_data.map((row: number[]) => ({
        t: row[0],
        x: row[1],
        y: row[2],
        vx: row[3],
        vy: row[4],
      }));
      return {
        tabs: [
          { label: "Trajectory (Height vs Distance)", xKey: "x", xLabel: "Distance (m)", lines: [{ key: "y", name: "Height (m)", color: LINE_COLORS[0] }] },
          { label: "Velocities over Time", xKey: "t", xLabel: "Time (s)", lines: [{ key: "vx", name: "Vx (m/s)", color: LINE_COLORS[1] }, { key: "vy", name: "Vy (m/s)", color: LINE_COLORS[2] }] },
        ],
        data,
      };
    }

    // Pendulum [t, angle, angular_velocity, height, speed]
    if (id === "pendulum" && firstRow.length >= 5) {
      const data = result.graph_data.map((row: number[]) => ({
        t: row[0],
        angle: row[1],
        angular_velocity: row[2],
        height: row[3],
        speed: row[4],
      }));
      return {
        tabs: [
          { label: "Angle & Speed", xKey: "t", xLabel: "Time (s)", lines: [{ key: "angle", name: "Angle (°)", color: LINE_COLORS[0] }, { key: "speed", name: "Speed (m/s)", color: LINE_COLORS[1] }] },
          { label: "Height & Angular Velocity", xKey: "t", xLabel: "Time (s)", lines: [{ key: "height", name: "Height (m)", color: LINE_COLORS[2] }, { key: "angular_velocity", name: "ω (rad/s)", color: LINE_COLORS[3] }] },
        ],
        data,
      };
    }

    // Free Fall [t, height, velocity, acceleration]
    if (id === "free-fall" && firstRow.length >= 4) {
      const data = result.graph_data.map((row: number[]) => ({
        t: row[0],
        height: row[1],
        velocity: row[2],
        acceleration: row[3],
      }));
      return {
        tabs: [
          { label: "Height vs Time", xKey: "t", xLabel: "Time (s)", lines: [{ key: "height", name: "Height (m)", color: LINE_COLORS[0] }] },
          { label: "Velocity & Acceleration", xKey: "t", xLabel: "Time (s)", lines: [{ key: "velocity", name: "Velocity (m/s)", color: LINE_COLORS[1] }, { key: "acceleration", name: "Acc (m/s²)", color: LINE_COLORS[2] }] },
        ],
        data,
      };
    }

    // Collision [t, pos1, pos2, vel1, vel2]
    if (id === "collision" && firstRow.length >= 5) {
      const data = result.graph_data.map((row: number[]) => ({
        t: row[0],
        pos1: row[1],
        pos2: row[2],
        vel1: row[3],
        vel2: row[4],
      }));
      return {
        tabs: [
          { label: "Positions over Time", xKey: "t", xLabel: "Time (s)", lines: [{ key: "pos1", name: "Object 1 Pos (m)", color: LINE_COLORS[0] }, { key: "pos2", name: "Object 2 Pos (m)", color: LINE_COLORS[1] }] },
          { label: "Velocities", xKey: "t", xLabel: "Time (s)", lines: [{ key: "vel1", name: "Object 1 Vel (m/s)", color: LINE_COLORS[2] }, { key: "vel2", name: "Object 2 Vel (m/s)", color: LINE_COLORS[3] }] },
        ],
        data,
      };
    }

    // Spring Mass [t, displacement, velocity, acceleration, spring_force, kinetic_energy, potential_energy]
    if (id === "spring-mass" && firstRow.length >= 7) {
      const data = result.graph_data.map((row: number[]) => ({
        t: row[0],
        displacement: row[1],
        velocity: row[2],
        acceleration: row[3],
        force: row[4],
        ke: row[5],
        pe: row[6],
      }));
      return {
        tabs: [
          { label: "Motion (Displacement & Velocity)", xKey: "t", xLabel: "Time (s)", lines: [{ key: "displacement", name: "Displacement (m)", color: LINE_COLORS[0] }, { key: "velocity", name: "Velocity (m/s)", color: LINE_COLORS[1] }] },
          { label: "Energy (Kinetic & Potential)", xKey: "t", xLabel: "Time (s)", lines: [{ key: "ke", name: "Kinetic Energy (J)", color: LINE_COLORS[1] }, { key: "pe", name: "Potential Energy (J)", color: LINE_COLORS[2] }] },
        ],
        data,
      };
    }

    // Inclined Plane [t, position, velocity, acceleration]
    if (id === "inclined-plane" && firstRow.length >= 4) {
      const data = result.graph_data.map((row: number[]) => ({
        t: row[0],
        position: row[1],
        velocity: row[2],
        acceleration: row[3],
      }));
      return {
        tabs: [
          { label: "Position along Slope", xKey: "t", xLabel: "Time (s)", lines: [{ key: "position", name: "Position (m)", color: LINE_COLORS[0] }] },
          { label: "Velocity & Acceleration", xKey: "t", xLabel: "Time (s)", lines: [{ key: "velocity", name: "Velocity (m/s)", color: LINE_COLORS[1] }, { key: "acceleration", name: "Acceleration (m/s²)", color: LINE_COLORS[2] }] },
        ],
        data,
      };
    }

    // Generic fallback for any [t, y1, y2, ...]
    const data = result.graph_data.map((row: number[]) => {
      const item: Record<string, number> = { t: row[0] };
      row.slice(1).forEach((val, idx) => {
        item[`val_${idx + 1}`] = val;
      });
      return item;
    });

    return {
      tabs: [
        {
          label: "Simulation Overview",
          xKey: "t",
          xLabel: "Time (s)",
          lines: Object.keys(data[0] || {})
            .filter((k) => k !== "t")
            .map((k, i) => ({ key: k, name: `Observable ${i + 1}`, color: LINE_COLORS[i % LINE_COLORS.length] })),
        },
      ],
      data,
    };
  }, [id, result]);

  // Plain English Summary Generator
  const summaryText = useMemo(() => {
    if (!result) return null;

    if (id === "projectile-motion") {
      return `Your projectile flew for ${result.time_of_flight || 0} seconds, reaching an apex height of ${result.max_height || 0} meters and landing ${result.range || 0} meters away at ${result.final_velocity || 0} m/s!`;
    }
    if (id === "pendulum") {
      return `The pendulum swings with a cycle period of ${result.period || 0} seconds. It reaches a top speed of ${result.max_speed || 0} m/s as it passes the bottom and swings up to ${result.max_height || 0} meters high!`;
    }
    if (id === "free-fall") {
      return `The object fell from its release height and hit the ground in ${result.time_to_ground || 0} seconds, reaching an impact speed of ${result.final_velocity || 0} m/s!`;
    }
    if (id === "collision") {
      return `After the collision, Object 1 moves at ${result.final_velocity1 || 0} m/s and Object 2 moves at ${result.final_velocity2 || 0} m/s. Initial kinetic energy was ${result.kinetic_energy_before || 0} J and final energy is ${result.kinetic_energy_after || 0} J (energy dissipated: ${result.energy_lost || 0} J).`;
    }
    if (id === "spring-mass") {
      return `The spring oscillator moves with a natural frequency of ${result.natural_frequency || 0} rad/s and period of ${result.period || 0} seconds, swinging back and forth with an amplitude of ${result.amplitude || 0} meters!`;
    }
    if (id === "inclined-plane") {
      if (result.will_move === false) {
        return `Static friction (${result.friction_force || 0} N) is strong enough to resist the slope gravity, so the block stays put and does not slide down!`;
      }
      return `The block slides down the slope with an acceleration of ${result.acceleration || 0} m/s², reaching the bottom in ${result.time_to_bottom || 0} seconds at ${result.final_velocity || 0} m/s! (Friction: ${result.friction_force || 0} N)`;
    }

    return "Experiment computed successfully! Review the values and graph curves above.";
  }, [id, result]);

  if (isLoadingSchema) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-12 h-12 border-4 border-[#4F8EF7] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-gray-600 font-medium">Setting up your laboratory...</p>
        </div>
      </div>
    );
  }

  const currentTabConfig = chartConfig.tabs[activeTab] || chartConfig.tabs[0];

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      {/* Custom Slider Thumb Styles */}
      <style>{`
        input[type=range]::-webkit-slider-thumb {
          -webkit-appearance: none;
          height: 24px;
          width: 24px;
          border-radius: 50%;
          background: #4F8EF7;
          cursor: pointer;
          border: 2px solid white;
          box-shadow: 0 2px 6px rgba(79, 142, 247, 0.4);
        }
        input[type=range]::-moz-range-thumb {
          height: 24px;
          width: 24px;
          border-radius: 50%;
          background: #4F8EF7;
          cursor: pointer;
          border: 2px solid white;
          box-shadow: 0 2px 6px rgba(79, 142, 247, 0.4);
        }
      `}</style>

      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Navigation & Title Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-4">
            <Link
              to="/simulations"
              className="p-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div className="flex items-center gap-3">
              <span className="text-4xl">{meta?.emoji || "🔬"}</span>
              <div>
                <h1 className="text-2xl font-bold text-[#1F2937] flex items-center gap-2">
                  {meta?.title || "Physics Simulation"}
                </h1>
                <p className="text-sm text-[#6B7280]">
                  {meta?.description || "Adjust the controls on the left and run the experiment."}
                </p>
              </div>
            </div>
          </div>
          {meta?.difficulty && (
            <span className="self-start sm:self-center text-xs font-semibold px-3 py-1 rounded-full uppercase tracking-wider bg-blue-100 text-blue-700 border border-blue-200">
              {meta.difficulty}
            </span>
          )}
        </div>

        {errorMsg && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3 text-red-700">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm font-medium">{errorMsg}</p>
          </div>
        )}

        {/* Layout: controls on the left (30% width), graph + results on the right (70%) on desktop. Stacked on mobile. */}
        <div className="flex flex-col lg:flex-row gap-8 items-start">
          {/* Controls Panel (30% width on desktop) */}
          <div className="w-full lg:w-[30%] lg:flex-shrink-0 bg-white rounded-[16px] p-6 shadow-md border border-gray-100 space-y-6">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="text-[18px] font-bold text-[#1F2937] flex items-center gap-2">
                <span>🎛️</span> Experiment Controls
              </h2>
            </div>

            <div className="space-y-6">
              {Object.entries(properties).map(([key, schema]) => {
                const label = formatFriendlyLabel(key, schema);
                const unit = getUnit(schema.description);
                const currentValue = params[key] !== undefined ? params[key] : schema.default;

                // 1. Boolean Toggle Switch
                if (schema.type === "boolean") {
                  const isChecked = Boolean(currentValue);
                  return (
                    <div key={key} className="flex items-center justify-between pt-2">
                      <div>
                        <label className="text-[16px] font-medium text-[#1F2937] block">
                          {label}
                        </label>
                        {schema.description && (
                          <span className="text-xs text-gray-500">{schema.description}</span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleParamChange(key, !isChecked)}
                        className={`relative inline-flex h-8 w-16 items-center rounded-full transition-colors cursor-pointer ${
                          isChecked ? "bg-[#4F8EF7]" : "bg-gray-300"
                        }`}
                      >
                        <span
                          className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
                            isChecked ? "translate-x-9" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>
                  );
                }

                // 2. Select / Dropdown for Enum / Literals
                if (schema.enum || schema.options) {
                  const options = schema.enum || schema.options || [];
                  return (
                    <div key={key} className="space-y-1.5">
                      <label className="text-[16px] font-medium text-[#1F2937] block">
                        {label}
                      </label>
                      <select
                        value={currentValue}
                        onChange={(e) => handleParamChange(key, e.target.value)}
                        className="w-full text-[16px] p-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#4F8EF7] text-[#1F2937]"
                      >
                        {options.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    </div>
                  );
                }

                // 3. Numeric Slider
                const min = schema.minimum !== undefined ? schema.minimum : 0;
                const max = schema.maximum !== undefined ? schema.maximum : 100;
                const step = max - min <= 1 ? 0.05 : max - min <= 10 ? 0.1 : 1;

                return (
                  <div key={key} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-[16px] font-medium text-[#1F2937]">
                        {label}
                      </label>
                      <span className="text-[16px] font-bold text-[#4F8EF7] bg-blue-50 px-2.5 py-0.5 rounded-lg border border-blue-100">
                        {currentValue} {unit}
                      </span>
                    </div>

                    <input
                      type="range"
                      min={min}
                      max={max}
                      step={step}
                      value={currentValue}
                      onChange={(e) => handleParamChange(key, parseFloat(e.target.value))}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer focus:outline-none"
                    />

                    <div className="flex justify-between text-xs text-[#6B7280]">
                      <span>{min} {unit}</span>
                      <span>{max} {unit}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Run Button */}
            <div className="pt-4 border-t">
              <button
                type="button"
                onClick={() => runSimulation()}
                disabled={isRunning}
                className="w-full h-[54px] bg-[#4F8EF7] hover:bg-[#3b7be8] active:bg-[#2b6bd8] text-white text-[18px] font-bold rounded-[14px] flex items-center justify-center gap-3 shadow-md hover:shadow-lg transition-all duration-200 cursor-pointer disabled:opacity-60"
              >
                {isRunning ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Calculating Physics...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5 fill-white" />
                    <span>▶️ Run Experiment!</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Graph & Results Panel (70% width on desktop) */}
          <div className="w-full lg:w-[70%] lg:flex-1 space-y-6">
            {/* Graph Card */}
            <div className="bg-white rounded-[16px] p-6 shadow-md border border-gray-100 space-y-4">
              {/* Tab Selector if multiple tabs */}
              {chartConfig.tabs.length > 1 && (
                <div className="flex flex-wrap gap-2 border-b pb-3">
                  {chartConfig.tabs.map((tab, idx) => (
                    <button
                      key={tab.label}
                      type="button"
                      onClick={() => setActiveTab(idx)}
                      className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                        activeTab === idx
                          ? "bg-[#4F8EF7] text-white shadow-sm"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              )}

              {/* Legend with colored dots */}
              <div className="flex flex-wrap items-center gap-4 pt-1">
                {currentTabConfig?.lines.map((line) => (
                  <div key={line.key} className="flex items-center gap-2 text-sm font-medium text-gray-700">
                    <span
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: line.color }}
                    />
                    <span>{line.name}</span>
                  </div>
                ))}
              </div>

              {/* Recharts LineChart */}
              <div className="h-[360px] w-full pt-4">
                {chartConfig.data.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartConfig.data} margin={{ top: 10, right: 30, left: 10, bottom: 25 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                      <XAxis
                        dataKey={currentTabConfig?.xKey || "t"}
                        stroke="#9CA3AF"
                        tick={{ fontSize: 14, fill: "#6B7280" }}
                        label={{
                          value: currentTabConfig?.xLabel || "Time (s)",
                          position: "insideBottom",
                          offset: -12,
                          fill: "#4B5563",
                          fontSize: 14,
                        }}
                      />
                      <YAxis
                        stroke="#9CA3AF"
                        tick={{ fontSize: 14, fill: "#6B7280" }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#FFFFFF",
                          borderRadius: "12px",
                          border: "1px solid #E5E7EB",
                          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                          fontSize: "14px",
                        }}
                      />
                      {currentTabConfig?.lines.map((line) => (
                        <Line
                          key={line.key}
                          type="monotone"
                          dataKey={line.key}
                          name={line.name}
                          stroke={line.color}
                          strokeWidth={3}
                          dot={false}
                          activeDot={{ r: 6, strokeWidth: 0 }}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                    No graph data generated yet. Click "Run Experiment!" to start.
                  </div>
                )}
              </div>
            </div>

            {/* "The Math Behind It 🧮" - Formulas Used Section */}
            {result?.formulas_used && result.formulas_used.length > 0 && (
              <div className="bg-white rounded-[16px] p-6 shadow-md border border-gray-100 space-y-4">
                <div className="flex items-center justify-between border-b pb-3">
                  <h3 className="text-[20px] font-bold text-[#1F2937]">
                    The Math Behind It 🧮
                  </h3>
                  <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
                    What does this formula mean?
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                  {result.formulas_used.map((formula, idx) => (
                    <div
                      key={idx}
                      className="bg-gray-50/80 hover:bg-blue-50/30 border border-gray-200 rounded-[14px] p-4 flex flex-col items-center justify-center text-center space-y-2 shadow-xs transition-colors"
                    >
                      <div className="font-mono text-[18px] text-center font-bold text-[#1F2937]">
                        {formula}
                      </div>
                      <p className="text-[14px] text-gray-600 text-center leading-relaxed">
                        {getFormulaDescription(formula)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* "What happened?" Explanation */}
            {result && (
              <div className="bg-white rounded-[16px] p-6 shadow-md border border-gray-100 space-y-4">
                <div className="flex items-center gap-2 text-[20px] font-bold text-[#1F2937]">
                  <Sparkles className="w-5 h-5 text-[#4F8EF7]" />
                  <h3>What happened?</h3>
                </div>

                <div className="bg-blue-50/60 border border-blue-100 rounded-xl p-4 text-[16px] text-[#1F2937] leading-relaxed">
                  {summaryText}
                </div>
              </div>
            )}

            {/* "Ask the AI Tutor 🤖" Section */}
            <div className="bg-white rounded-[16px] p-6 shadow-md border border-gray-100 space-y-4">
              <div className="border-b pb-3">
                <h3 className="text-[20px] font-bold text-[#1F2937]">
                  Got questions? Ask me! 🤖
                </h3>
              </div>

              {/* Suggested Questions Pill Buttons */}
              <div className="flex flex-wrap gap-2 pt-1">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setStudentQuestion(q)}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 active:bg-gray-300 text-gray-700 rounded-full text-sm font-medium transition-colors cursor-pointer"
                  >
                    {q}
                  </button>
                ))}
              </div>

              {/* Question Input Form */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAskAi();
                }}
                className="flex flex-col sm:flex-row gap-3 pt-2"
              >
                <input
                  type="text"
                  value={studentQuestion}
                  onChange={(e) => setStudentQuestion(e.target.value)}
                  placeholder="Ask anything about this experiment..."
                  className="flex-1 text-[16px] px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#4F8EF7] text-[#1F2937]"
                />
                <button
                  type="submit"
                  disabled={isAskingAi || !studentQuestion.trim()}
                  className="h-[48px] px-6 bg-[#4F8EF7] hover:bg-[#3b7be8] active:bg-[#2b6bd8] text-white text-[16px] font-bold rounded-xl flex items-center justify-center shadow-sm transition-all duration-150 disabled:opacity-50 cursor-pointer flex-shrink-0"
                >
                  Ask! →
                </button>
              </form>

              {/* Loading State with Pulsing Animation */}
              {isAskingAi && (
                <div className="bg-white rounded-xl p-4 border border-blue-100 shadow-sm flex items-center gap-3">
                  <div className="w-3.5 h-3.5 rounded-full bg-[#4F8EF7] animate-ping" />
                  <span className="text-[16px] font-medium text-[#4F8EF7] animate-pulse">
                    Thinking... 🤔
                  </span>
                </div>
              )}

              {/* Error State */}
              {aiError && !isAskingAi && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-[15px] text-red-600 font-medium">
                  {aiError}
                </div>
              )}

              {/* Response Area: White Card, Rounded, Plain Text Response */}
              {aiExplanation && !isAskingAi && (
                <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-2 shadow-sm">
                  <div className="flex items-center gap-2 text-xs font-bold text-gray-500 uppercase tracking-wider">
                    <span>🤖 AI Tutor</span>
                  </div>
                  <p className="text-[16px] text-[#1F2937] leading-relaxed whitespace-pre-wrap">
                    {aiExplanation}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SimulationRunnerPage;
