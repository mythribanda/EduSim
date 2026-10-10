"use client";

import React, { useEffect, useState, useMemo } from "react";
import ClassCard, { getMasteryBand } from "@/components/ClassCard";

interface ClassItem {
  id: string;
  name: string;
  grade_level: string;
  created_by: string;
  join_code: string;
  created_at: string;
  subjects?: string[];
  enrolled_student_count: number;
}

interface ClassAnalytics {
  class_id: string;
  class_name: string;
  grade_level: string;
  student_count: number;
  active_this_week: number;
  average_mastery: number;
  weakest_topic: string | null;
  strongest_topic: string | null;
  topic_breakdown?: Array<{
    topic: string;
    average_score: number;
    student_count: number;
  }>;
}

interface EnrichedClass extends ClassItem {
  analytics?: ClassAnalytics;
}

export default function DashboardPage() {
  const [classes, setClasses] = useState<EnrichedClass[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/$/, "");

  const fetchData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Resolve token from localStorage if available
      const token =
        typeof window !== "undefined"
          ? window.localStorage.getItem("token")
          : null;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      // 1. Fetch teacher classes from GET /api/classes/mine
      const classesRes = await fetch(`${API_URL}/api/classes/mine`, { credentials: "omit", headers });
      if (!classesRes.ok) {
        throw new Error(
          `Failed to fetch teacher classes (${classesRes.status}: ${classesRes.statusText})`
        );
      }
      const rawClasses: ClassItem[] = await classesRes.json();

      // 2. Fetch analytics for each class concurrently from GET /api/classes/{id}/analytics
      const enriched = await Promise.all(
        rawClasses.map(async (cls) => {
          try {
            const analyticsRes = await fetch(
              `${API_URL}/api/classes/${cls.id}/analytics`,
              { credentials: "omit", headers }
            );
            if (analyticsRes.ok) {
              const analytics: ClassAnalytics = await analyticsRes.json();
              return { ...cls, analytics };
            }
          } catch (e) {
            console.warn(`Could not load analytics for class ${cls.id}:`, e);
          }
          return cls;
        })
      );

      setClasses(enriched);
    } catch (err: any) {
      console.error("[Dashboard] Error loading dashboard data:", err);
      setError(
        err.message || "Unable to connect to the backend server. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Compute aggregated overview metrics across all teacher classes
  const overviewMetrics = useMemo(() => {
    let totalStudents = 0;
    let activeThisWeek = 0;
    let totalMasterySum = 0;
    let classesWithMastery = 0;
    const topicScores: Record<string, { total: number; count: number }> = {};

    classes.forEach((c) => {
      const studentCount = c.analytics?.student_count ?? c.enrolled_student_count ?? 0;
      totalStudents += studentCount;

      if (c.analytics) {
        activeThisWeek += c.analytics.active_this_week || 0;

        if (c.analytics.average_mastery > 0) {
          totalMasterySum += c.analytics.average_mastery;
          classesWithMastery += 1;
        }

        // Aggregate topic breakdown if available
        if (c.analytics.topic_breakdown) {
          c.analytics.topic_breakdown.forEach((t) => {
            if (!topicScores[t.topic]) {
              topicScores[t.topic] = { total: 0, count: 0 };
            }
            topicScores[t.topic].total += t.average_score;
            topicScores[t.topic].count += 1;
          });
        } else if (c.analytics.weakest_topic) {
          if (!topicScores[c.analytics.weakest_topic]) {
            topicScores[c.analytics.weakest_topic] = { total: 0, count: 0 };
          }
          topicScores[c.analytics.weakest_topic].total += 35; // default indicative low score
          topicScores[c.analytics.weakest_topic].count += 1;
        }
      }
    });

    const classAverageMastery =
      classesWithMastery > 0
        ? Math.round((totalMasterySum / classesWithMastery) * 10) / 10
        : 0;

    // Find topic with lowest overall average
    let weakestTopic: string | null = null;
    let lowestAvg = Infinity;

    Object.entries(topicScores).forEach(([topic, data]) => {
      const avg = data.total / data.count;
      if (avg < lowestAvg) {
        lowestAvg = avg;
        weakestTopic = topic;
      }
    });

    return {
      totalStudents,
      activeThisWeek,
      classAverageMastery,
      weakestTopic: weakestTopic || "None detected",
    };
  }, [classes]);

  // Filtered classes by search
  const filteredClasses = useMemo(() => {
    if (!searchQuery.trim()) return classes;
    const q = searchQuery.toLowerCase();
    return classes.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.grade_level && c.grade_level.toLowerCase().includes(q)) ||
        (c.subjects && c.subjects.some((s) => s.toLowerCase().includes(q)))
    );
  }, [classes, searchQuery]);

  const masteryBand = getMasteryBand(overviewMetrics.classAverageMastery);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      {/* Page Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Teacher Overview
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Monitor class progress, student mastery, and learning priorities.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            <svg
              className={`h-4 w-4 text-slate-500 ${loading ? "animate-spin" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
              />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <div className="flex items-center gap-3">
            <svg
              className="h-5 w-5 text-rose-500 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
            <div className="flex-1">
              <strong className="font-semibold">Connection Error: </strong>
              {error}
            </div>
            <button
              onClick={fetchData}
              className="rounded-md bg-rose-100 px-2.5 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-200"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* 4 Main Overview Cards */}
      <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: Total Students */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Students
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth="1.75"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"
                />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            {loading ? (
              <div className="h-8 w-16 animate-pulse rounded bg-slate-100" />
            ) : (
              <div className="text-3xl font-extrabold text-slate-900">
                {overviewMetrics.totalStudents}
              </div>
            )}
            <p className="mt-1 text-xs text-slate-500">
              Across {classes.length} class {classes.length === 1 ? "section" : "sections"}
            </p>
          </div>
        </div>

        {/* Card 2: Active This Week */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Active This Week
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth="1.75"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
                />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            {loading ? (
              <div className="h-8 w-16 animate-pulse rounded bg-slate-100" />
            ) : (
              <div className="text-3xl font-extrabold text-slate-900">
                {overviewMetrics.activeThisWeek}
              </div>
            )}
            <p className="mt-1 text-xs text-slate-500">
              {overviewMetrics.totalStudents > 0
                ? `${Math.round(
                    (overviewMetrics.activeThisWeek /
                      overviewMetrics.totalStudents) *
                      100
                  )}% of enrolled students active`
                : "Active learning activity"}
            </p>
          </div>
        </div>

        {/* Card 3: Class Average Mastery */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Class Average Mastery
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50 text-sky-600">
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth="1.75"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.003 0V7.875A3.375 3.375 0 0011.25 4.5h-.5A3.375 3.375 0 007.375 7.875v6.625"
                />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            {loading ? (
              <div className="h-8 w-16 animate-pulse rounded bg-slate-100" />
            ) : (
              <div className="flex items-baseline gap-2">
                <div className="text-3xl font-extrabold text-slate-900">
                  {overviewMetrics.classAverageMastery}%
                </div>
                <span
                  className={`rounded border px-1.5 py-0.5 text-xs font-semibold ${masteryBand.badgeBg}`}
                >
                  {masteryBand.status}
                </span>
              </div>
            )}
            <p className="mt-1 text-xs text-slate-500">
              Target benchmark: &gt;70%
            </p>
          </div>
        </div>

        {/* Card 4: Weakest Topic Across All Classes */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Weakest Topic
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth="1.75"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                />
              </svg>
            </div>
          </div>
          <div className="mt-4">
            {loading ? (
              <div className="h-8 w-28 animate-pulse rounded bg-slate-100" />
            ) : (
              <div
                title={overviewMetrics.weakestTopic}
                className="truncate text-xl font-bold text-slate-900"
              >
                {overviewMetrics.weakestTopic}
              </div>
            )}
            <p className="mt-1 text-xs text-slate-500">
              Lowest mastery across all your sections
            </p>
          </div>
        </div>
      </section>

      {/* Classes Grid Section */}
      <section className="space-y-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-xl font-bold text-slate-900">My Classes</h2>
            <p className="text-xs text-slate-500">
              Class sections, enrollments, and live mastery scores.
            </p>
          </div>

          {/* Search bar */}
          <div className="relative w-full sm:w-64">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search classes or subjects..."
              className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pr-3 pl-9 text-xs placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <svg
              className="pointer-events-none absolute top-2 left-2.5 h-4 w-4 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
              />
            </svg>
          </div>
        </div>

        {/* Loading Skeletons */}
        {loading && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-48 animate-pulse rounded-xl border border-slate-200 bg-white p-5"
              >
                <div className="h-5 w-24 rounded bg-slate-100" />
                <div className="mt-4 h-4 w-32 rounded bg-slate-100" />
                <div className="mt-6 h-3 w-full rounded bg-slate-100" />
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredClasses.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white py-14 text-center">
            <svg
              className="mx-auto h-12 w-12 text-slate-300"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="1.2"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5"
              />
            </svg>
            <h3 className="mt-3 text-sm font-semibold text-slate-900">
              No classes found
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              {searchQuery
                ? `No class sections matched "${searchQuery}".`
                : "No class sections have been assigned or created yet."}
            </p>
          </div>
        )}

        {/* Classes Cards Grid */}
        {!loading && filteredClasses.length > 0 && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {filteredClasses.map((cls) => {
              const studentCount =
                cls.analytics?.student_count ?? cls.enrolled_student_count ?? 0;
              const avgMastery = cls.analytics?.average_mastery ?? 0;
              const weakest = cls.analytics?.weakest_topic ?? null;
              const activeCount = cls.analytics?.active_this_week;

              return (
                <ClassCard
                  key={cls.id}
                  id={cls.id}
                  name={cls.name}
                  gradeLevel={cls.grade_level}
                  studentCount={studentCount}
                  averageMastery={avgMastery}
                  weakestTopic={weakest}
                  activeThisWeek={activeCount}
                  subjects={cls.subjects}
                  joinCode={cls.join_code}
                />
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
