import React, { useState, useEffect, useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { getApiUrl } from "@/config/api";
import { SimulationCard } from "@/components/simulations/SimulationCard";

export const Route = createFileRoute("/simulations")({
  component: SimulationsLibraryPage,
});

export interface StaticSimulationItem {
  id: string;
  title: string;
  emoji: string;
  description: string;
  category: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  has_graphs?: boolean;
  has_guided_mode?: boolean;
  key_concepts?: string[];
  grade_levels?: string[];
}

const CATEGORIES = ["All", "Mechanics", "Waves", "Electricity"] as const;
type CategoryType = (typeof CATEGORIES)[number];

export function SimulationsLibraryPage() {
  const navigate = useNavigate();
  const [simulations, setSimulations] = useState<StaticSimulationItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<CategoryType>("All");

  useEffect(() => {
    let isMounted = true;
    const fetchSimulations = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(getApiUrl("/api/simulations/static"));
        if (!response.ok) {
          throw new Error("Failed to load simulations");
        }
        const data = await response.json();
        if (isMounted) {
          setSimulations(data.simulations || []);
        }
      } catch (err) {
        console.error("Error fetching static simulations:", err);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchSimulations();
    return () => {
      isMounted = false;
    };
  }, []);

  const filteredSimulations = useMemo(() => {
    return simulations.filter((sim) => {
      // Category filter
      let matchesCategory = true;
      if (selectedCategory !== "All") {
        const cat = sim.category?.toLowerCase() || "";
        const target = selectedCategory.toLowerCase();
        if (target === "waves") {
          matchesCategory = cat.includes("wave") || cat.includes("oscillation");
        } else {
          matchesCategory = cat.includes(target);
        }
      }

      // Search filter
      const query = searchQuery.trim().toLowerCase();
      let matchesSearch = true;
      if (query) {
        const titleMatch = sim.title.toLowerCase().includes(query);
        const descMatch = sim.description.toLowerCase().includes(query);
        const conceptsMatch = sim.key_concepts?.some((c) =>
          c.toLowerCase().includes(query)
        );
        matchesSearch = Boolean(titleMatch || descMatch || conceptsMatch);
      }

      return matchesCategory && matchesSearch;
    });
  }, [simulations, selectedCategory, searchQuery]);

  const handleCardClick = (id: string) => {
    navigate({
      to: `/simulations/${id}`,
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-[32px] font-bold text-[#1F2937] tracking-tight">
            Physics Lab 🔬
          </h1>
          <p className="text-[18px] text-[#6B7280]">
            Pick an experiment and start exploring!
          </p>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
          {/* Category Filter Pills */}
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            {CATEGORIES.map((category) => {
              const isSelected = selectedCategory === category;
              return (
                <button
                  key={category}
                  type="button"
                  onClick={() => setSelectedCategory(category)}
                  className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-200 cursor-pointer ${
                    isSelected
                      ? "bg-[#4F8EF7] text-white shadow-sm"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {category}
                </button>
              );
            })}
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-72">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <Search className="h-5 w-5" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search experiments..."
              className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-[#4F8EF7] focus:bg-white transition-all text-[#1F2937]"
            />
          </div>
        </div>

        {/* Main Content: Loading Skeletons, Empty State, or Card Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, idx) => (
              <div
                key={idx}
                className="bg-white rounded-[16px] p-6 shadow-md border border-gray-100 flex flex-col justify-between h-[340px] animate-pulse"
              >
                <div>
                  <div className="flex justify-end mb-4">
                    <div className="h-6 w-20 bg-gray-200 rounded-full" />
                  </div>
                  <div className="flex justify-center my-4">
                    <div className="h-16 w-16 bg-gray-200 rounded-full" />
                  </div>
                  <div className="space-y-2 mt-4">
                    <div className="h-6 w-3/4 mx-auto bg-gray-200 rounded-md" />
                    <div className="h-4 w-5/6 mx-auto bg-gray-200 rounded-md" />
                    <div className="h-4 w-2/3 mx-auto bg-gray-200 rounded-md" />
                  </div>
                </div>
                <div className="mt-6 pt-2">
                  <div className="h-[48px] w-full bg-gray-200 rounded-[12px]" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredSimulations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center space-y-3 bg-white rounded-2xl border border-gray-100 shadow-sm">
            <span className="text-5xl">🤔</span>
            <h3 className="text-xl font-semibold text-[#1F2937]">
              No experiments found 🤔
            </h3>
            <p className="text-gray-500 text-sm max-w-sm">
              Try a different search or pick another category to find what you're looking for!
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredSimulations.map((sim) => (
              <SimulationCard
                key={sim.id}
                id={sim.id}
                title={sim.title}
                emoji={sim.emoji}
                description={sim.description}
                difficulty={sim.difficulty}
                onClick={() => handleCardClick(sim.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default SimulationsLibraryPage;
