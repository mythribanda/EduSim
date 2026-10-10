"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

// -----------------------------------------------------------------------------
// Interfaces
// -----------------------------------------------------------------------------

interface TopicBreakdownItem {
  topic: string;
  avg_mastery: number;
  weak_students: number;
}

interface Engagement {
  active_this_week: number;
  total_students: number;
}

interface AtRiskStudent {
  id?: string;
  student_id?: string;
  name: string;
  email?: string;
  mastery: number;
  last_active: string;
}

interface ClassAnalyticsData {
  class_id?: string;
  class_name?: string;
  grade_level?: string;
  class_average_mastery: number;
  topic_breakdown: TopicBreakdownItem[];
  most_asked_topics: string[];
  engagement: Engagement;
  assignments_submitted?: number;
  at_risk_students: AtRiskStudent[];
}

interface ClassDetail {
  id: string;
  name: string;
  grade_level: string;
  join_code?: string;
  enrolled_student_count?: number;
  subjects?: string[];
}

// -----------------------------------------------------------------------------
// Color helpers for Mastery Levels
// -----------------------------------------------------------------------------

function getMasteryColor(score: number): {
  barFill: string;
  bgLight: string;
  text: string;
  badgeBg: string;
  badgeBorder: string;
  label: string;
} {
  if (score >= 70) {
    return {
      barFill: "#10b981", // emerald-500
      bgLight: "bg-emerald-50",
      text: "text-emerald-700",
      badgeBg: "bg-emerald-50",
      badgeBorder: "border-emerald-200",
      label: "Mastered",
    };
  }
  if (score >= 40) {
    return {
      barFill: "#f59e0b", // amber-500
      bgLight: "bg-amber-50",
      text: "text-amber-700",
      badgeBg: "bg-amber-50",
      badgeBorder: "border-amber-200",
      label: "Moderate",
    };
  }
  return {
    barFill: "#ef4444", // rose-500
    bgLight: "bg-rose-50",
    text: "text-rose-700",
    badgeBg: "bg-rose-50",
    badgeBorder: "border-rose-200",
    label: "Needs Support",
  };
}

export default function ClassAnalyticsPage({
  params: propParams,
}: {
  params?: { classId?: string };
}) {
  const router = useRouter();
  const routeParams = useParams();
  const classId = (routeParams?.classId as string) || propParams?.classId || "";

  const [classInfo, setClassInfo] = useState<ClassDetail | null>(null);
  const [analytics, setAnalytics] = useState<ClassAnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Export State
  const [exporting, setExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);

  // Notification State (student_id -> "sending" | "sent" | "error")
  const [reminderState, setReminderState] = useState<Record<string, "idle" | "sending" | "sent" | "error">>({});
  const [customModalStudent, setCustomModalStudent] = useState<AtRiskStudent | null>(null);
  const [customReminderMsg, setCustomReminderMsg] = useState("");
  const [customReminderTopic, setCustomReminderTopic] = useState("");

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/$/, "");

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------
  const fetchData = useCallback(async () => {
    if (!classId) return;
    setLoading(true);
    setError(null);

    const token =
      typeof window !== "undefined"
        ? window.localStorage.getItem("token")
        : null;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      // 1. Fetch Class Analytics from Python endpoint
      const analyticsRes = await fetch(`${API_URL}/api/analytics/class/${classId}`, {
        credentials: "omit",
        headers,
      });
      if (!analyticsRes.ok) {
        throw new Error(
          analyticsRes.status === 404
            ? "Class not found or no analytics available yet."
            : `Failed to load analytics (HTTP ${analyticsRes.status})`
        );
      }
      const data = await analyticsRes.json();
      setAnalytics(data);

      // 2. Fetch Class Details for header title / navigation
      try {
        const classRes = await fetch(`${API_URL}/api/classes/${classId}`, {
          credentials: "omit",
          headers,
        });
        if (classRes.ok) {
          const cData = await classRes.json();
          setClassInfo(cData);
        }
      } catch {
        // Class info optional if analytics contains name
      }
    } catch (err: any) {
      console.error("Failed to load class analytics:", err);
      setError(err.message || "Failed to load class analytics.");
    } finally {
      setLoading(false);
    }
  }, [API_URL, classId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ---------------------------------------------------------------------------
  // Export CSV Report Handler
  // ---------------------------------------------------------------------------
  const handleExportCSV = async () => {
    if (!classId || exporting) return;
    setExporting(true);
    setExportSuccess(false);

    const token =
      typeof window !== "undefined"
        ? window.localStorage.getItem("token")
        : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      const res = await fetch(`${API_URL}/api/analytics/class/${classId}/export`, {
        credentials: "omit",
        headers,
      });

      if (!res.ok) {
        throw new Error(`Export failed with HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      const cName = classInfo?.name || analytics?.class_name || classId.slice(0, 8);
      link.download = `Class_${cName}_Analytics_Report.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      setExportSuccess(true);
      setTimeout(() => setExportSuccess(false), 3000);
    } catch (err: any) {
      console.error("Export error:", err);
      alert(`Export failed: ${err.message || "Please try again."}`);
    } finally {
      setExporting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Send Reminder Handler
  // ---------------------------------------------------------------------------
  const handleSendReminder = async (
    student: AtRiskStudent,
    customMsg?: string,
    topicName?: string
  ) => {
    const studentId = student.id || student.student_id;
    if (!studentId) return;

    setReminderState((prev) => ({ ...prev, [studentId]: "sending" }));

    const token =
      typeof window !== "undefined"
        ? window.localStorage.getItem("token")
        : null;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      const payload: { message?: string; topic?: string } = {};
      if (customMsg && customMsg.trim()) payload.message = customMsg.trim();
      if (topicName && topicName.trim()) payload.topic = topicName.trim();

      const res = await fetch(`${API_URL}/api/students/${studentId}/notify`, {
        method: "POST",
        credentials: "omit",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`Notification failed with HTTP ${res.status}`);
      }
      }

      setReminderState((prev) => ({ ...prev, [studentId]: "sent" }));
      if (customModalStudent) {
        setCustomModalStudent(null);
        setCustomReminderMsg("");
        setCustomReminderTopic("");
      }

      // Reset 'sent' status after 4 seconds
      setTimeout(() => {
        setReminderState((prev) => ({ ...prev, [studentId]: "idle" }));
      }, 4000);
    } catch (err: any) {
      console.error("Send reminder error:", err);
      setReminderState((prev) => ({ ...prev, [studentId]: "error" }));
      setTimeout(() => {
        setReminderState((prev) => ({ ...prev, [studentId]: "idle" }));
      }, 3000);
    }
  };

  // ---------------------------------------------------------------------------
  // Computed Stat Metrics
  // ---------------------------------------------------------------------------
  const stats = useMemo(() => {
    if (!analytics) {
      return {
        avgMastery: 0,
        activeThisWeek: 0,
        totalStudents: 0,
        activePercent: 0,
        assignmentsSubmitted: 0,
        atRiskCount: 0,
      };
    }

    const total = analytics.engagement?.total_students || 0;
    const active = analytics.engagement?.active_this_week || 0;
    const percent = total > 0 ? Math.round((active / total) * 100) : 0;

    return {
      avgMastery: analytics.class_average_mastery || 0,
      activeThisWeek: active,
      totalStudents: total,
      activePercent: percent,
      assignmentsSubmitted: analytics.assignments_submitted || 0,
      atRiskCount: analytics.at_risk_students?.length || 0,
    };
  }, [analytics]);

  const displayClassName =
    classInfo?.name || analytics?.class_name || "Class Analytics";
  const displayGrade = classInfo?.grade_level || analytics?.grade_level || "";

  // ---------------------------------------------------------------------------
  // Render Loading Skeleton
  // ---------------------------------------------------------------------------
  if (loading) {
    return (
      <div className="space-y-6 pb-12 animate-pulse">
        {/* Header Skeleton */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-200">
          <div className="space-y-2">
            <div className="h-4 w-40 bg-slate-200 rounded"></div>
            <div className="h-8 w-64 bg-slate-200 rounded"></div>
          </div>
          <div className="h-10 w-36 bg-slate-200 rounded-lg"></div>
        </div>

        {/* 4 Stat Cards Skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white p-5 rounded-xl border border-slate-200 space-y-3">
              <div className="h-4 w-24 bg-slate-200 rounded"></div>
              <div className="h-8 w-20 bg-slate-200 rounded"></div>
              <div className="h-3 w-32 bg-slate-100 rounded"></div>
            </div>
          ))}
        </div>

        {/* Chart Skeleton */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 space-y-4">
          <div className="h-6 w-48 bg-slate-200 rounded"></div>
          <div className="space-y-3 pt-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 bg-slate-100 rounded-lg w-full"></div>
            ))}
          </div>
        </div>

        {/* Table Skeleton */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 space-y-4">
          <div className="h-6 w-48 bg-slate-200 rounded"></div>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-slate-50 rounded w-full"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render Error State
  // ---------------------------------------------------------------------------
  if (error && !analytics) {
    return (
      <div className="max-w-xl mx-auto py-12 text-center space-y-4">
        <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-full flex items-center justify-center mx-auto text-xl">
          ⚠️
        </div>
        <h2 className="text-xl font-bold text-slate-900">Failed to Load Analytics</h2>
        <p className="text-sm text-slate-600">{error}</p>
        <div className="flex justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => fetchData()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition shadow-sm"
          >
            Retry
          </button>
          <Link
            href={`/dashboard/classes/${classId}`}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium transition"
          >
            Back to Class
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      {/* --------------------------------------------------------------------- */}
      {/* Navigation Breadcrumb & Header Action Bar */}
      {/* --------------------------------------------------------------------- */}
      <div>
        {/* Breadcrumbs */}
        <nav className="flex items-center gap-2 text-xs text-slate-500 mb-2">
          <Link href="/dashboard" className="hover:text-indigo-600 transition">
            My Classes
          </Link>
          <span>/</span>
          <Link
            href={`/dashboard/classes/${classId}`}
            className="hover:text-indigo-600 transition"
          >
            {displayClassName}
          </Link>
          <span>/</span>
          <span className="text-slate-900 font-medium">Analytics</span>
        </nav>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                {displayClassName} Analytics
              </h1>
              {displayGrade && (
                <span className="px-2.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-full text-xs font-semibold">
                  Grade {displayGrade}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Class mastery diagnostics, topic breakdown, and at-risk student intervention.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleExportCSV}
              disabled={exporting}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition shadow-sm border ${
                exportSuccess
                  ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                  : "bg-white border-slate-300 text-slate-700 hover:bg-slate-50 hover:border-slate-400"
              } disabled:opacity-60`}
            >
              {exporting ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-slate-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                  </svg>
                  <span>Exporting...</span>
                </>
              ) : exportSuccess ? (
                <>
                  <span className="text-emerald-600">✓</span>
                  <span>Report Downloaded</span>
                </>
              ) : (
                <>
                  <svg className="h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24" strokeWidth="1.75" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  <span>Export Report (CSV)</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => fetchData()}
              className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition"
              title="Refresh Analytics"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth="1.75" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
            </button>
          </div>
        </div>

        {/* Tab Navigation Sub-bar */}
        <div className="flex gap-2 pt-3 border-b border-slate-100">
          <Link
            href={`/dashboard/classes/${classId}`}
            className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 hover:bg-slate-50 rounded-md transition"
          >
            Overview & Students
          </Link>
          <Link
            href={`/dashboard/classes/${classId}/assignments`}
            className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 hover:bg-slate-50 rounded-md transition"
          >
            Assignments
          </Link>
          <span className="px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-md">
            Analytics & Diagnostics
          </span>
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* 1. TOP ROW: 4 STAT CARDS */}
      {/* --------------------------------------------------------------------- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Card 1: Class Avg Mastery */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow transition">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 mb-1">
            <span>Class Average Mastery</span>
            <span
              className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                getMasteryColor(stats.avgMastery).badgeBg
              } ${getMasteryColor(stats.avgMastery).text} ${
                getMasteryColor(stats.avgMastery).badgeBorder
              }`}
            >
              {getMasteryColor(stats.avgMastery).label}
            </span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-extrabold text-slate-900 tracking-tight">
              {stats.avgMastery}%
            </span>
          </div>
          <div className="mt-3 w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(100, Math.max(0, stats.avgMastery))}%`,
                backgroundColor: getMasteryColor(stats.avgMastery).barFill,
              }}
            ></div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Calculated across all student topic attempts
          </p>
        </div>

        {/* Card 2: Active This Week */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow transition">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 mb-1">
            <span>Active This Week</span>
            <span className="text-emerald-600 font-semibold text-[11px] bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
              {stats.activePercent}% engagement
            </span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-extrabold text-slate-900 tracking-tight">
              {stats.activeThisWeek}
            </span>
            <span className="text-sm font-medium text-slate-500">
              / {stats.totalStudents} students
            </span>
          </div>
          <div className="mt-3 w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-600 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, stats.activePercent))}%` }}
            ></div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Engaged in simulations or quizzes in last 7 days
          </p>
        </div>

        {/* Card 3: Assignments Submitted */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow transition">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 mb-1">
            <span>Assignments Submitted</span>
            <span className="text-indigo-600 font-semibold text-[11px] bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
              Submissions
            </span>
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-extrabold text-slate-900 tracking-tight">
              {stats.assignmentsSubmitted}
            </span>
            <span className="text-sm font-medium text-slate-500">completed</span>
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-600">
            <svg className="w-4 h-4 text-indigo-500 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-slate-500 text-[11px]">Across all modules</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            <Link
              href={`/dashboard/classes/${classId}/assignments`}
              className="text-indigo-600 hover:underline"
            >
              View class assignments &rarr;
            </Link>
          </p>
        </div>

        {/* Card 4: At-Risk Count */}
        <div
          className={`p-5 rounded-xl border shadow-sm transition ${
            stats.atRiskCount > 0
              ? "bg-rose-50/40 border-rose-200"
              : "bg-white border-slate-200"
          }`}
        >
          <div className="flex items-center justify-between text-xs font-medium text-slate-500 mb-1">
            <span>At-Risk Students</span>
            {stats.atRiskCount > 0 ? (
              <span className="px-2 py-0.5 bg-rose-100 text-rose-700 font-bold rounded-full text-[11px] border border-rose-200">
                Action Needed
              </span>
            ) : (
              <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 font-semibold rounded-full text-[11px] border border-emerald-100">
                All Clear
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-2 mt-2">
            <span
              className={`text-3xl font-extrabold tracking-tight ${
                stats.atRiskCount > 0 ? "text-rose-600" : "text-slate-900"
              }`}
            >
              {stats.atRiskCount}
            </span>
            <span className="text-sm font-medium text-slate-500">
              {stats.atRiskCount === 1 ? "student (<40%)" : "students (<40%)"}
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mt-3">
            {stats.atRiskCount > 0
              ? "Students with critical topic weaknesses"
              : "No students currently flagged below 40%"}
          </p>
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* 2. TOPIC BREAKDOWN: PURE SVG HORIZONTAL BAR CHART */}
      {/* --------------------------------------------------------------------- */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Curriculum Topic Breakdown
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Average student mastery score per topic. Pure SVG rendered with zero external chart dependencies.
            </p>
          </div>

          {/* Color Legend */}
          <div className="flex items-center gap-4 text-xs font-medium text-slate-600">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block"></span>
              <span>&gt;70% Mastered</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-amber-500 inline-block"></span>
              <span>40-70% Moderate</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-rose-500 inline-block"></span>
              <span>&lt;40% Needs Support</span>
            </div>
          </div>
        </div>

        {/* SVG Horizontal Bar Chart */}
        {analytics?.topic_breakdown && analytics.topic_breakdown.length > 0 ? (
          <div className="space-y-4">
            {/* Grid Scale Header */}
            <div className="grid grid-cols-12 gap-3 text-[11px] font-semibold text-slate-400 px-2 pb-1 border-b border-slate-100">
              <div className="col-span-4 sm:col-span-3 text-left">TOPIC</div>
              <div className="col-span-8 sm:col-span-9 flex justify-between">
                <span>0%</span>
                <span className="hidden sm:inline">25%</span>
                <span>50%</span>
                <span className="hidden sm:inline">75%</span>
                <span>100%</span>
              </div>
            </div>

            {/* Topic Rows with Inline SVG Bars */}
            <div className="space-y-3">
              {analytics.topic_breakdown.map((item, idx) => {
                const score = Math.min(100, Math.max(0, item.avg_mastery));
                const colorConfig = getMasteryColor(score);

                return (
                  <div
                    key={idx}
                    className="grid grid-cols-12 gap-3 items-center py-2 px-2 rounded-lg hover:bg-slate-50/80 transition group"
                  >
                    {/* Topic Name & Weak Students Badge */}
                    <div className="col-span-4 sm:col-span-3 pr-2">
                      <div
                        className="text-xs font-semibold text-slate-800 truncate"
                        title={item.topic}
                      >
                        {item.topic}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {item.weak_students > 0 ? (
                          <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-rose-600 bg-rose-50 border border-rose-200 px-1.5 py-0.2 rounded">
                            <span>⚠️</span> {item.weak_students} weak
                          </span>
                        ) : (
                          <span className="text-[10px] text-emerald-600 font-medium">
                            ✓ No weak students
                          </span>
                        )}
                      </div>
                    </div>

                    {/* SVG Bar Track */}
                    <div className="col-span-8 sm:col-span-9 relative flex items-center">
                      <svg
                        className="w-full h-7 rounded-md"
                        viewBox="0 0 500 28"
                        preserveAspectRatio="none"
                      >
                        {/* Background track */}
                        <rect
                          x="0"
                          y="0"
                          width="500"
                          height="28"
                          rx="6"
                          ry="6"
                          fill="#f1f5f9"
                        />

                        {/* Grid ticks */}
                        <line x1="125" y1="0" x2="125" y2="28" stroke="#e2e8f0" strokeDasharray="2 2" />
                        <line x1="250" y1="0" x2="250" y2="28" stroke="#e2e8f0" strokeDasharray="2 2" />
                        <line x1="375" y1="0" x2="375" y2="28" stroke="#e2e8f0" strokeDasharray="2 2" />

                        {/* Active mastery fill bar */}
                        {score > 0 && (
                          <rect
                            x="0"
                            y="0"
                            width={`${(score / 100) * 500}`}
                            height="28"
                            rx="6"
                            ry="6"
                            fill={colorConfig.barFill}
                            className="transition-all duration-700 ease-out"
                          />
                        )}
                      </svg>

                      {/* Overlaid Score Text Label */}
                      <div className="absolute right-3 flex items-center gap-1.5 pointer-events-none">
                        <span
                          className={`text-xs font-bold ${
                            score > 85 ? "text-white" : "text-slate-700"
                          } drop-shadow-sm`}
                        >
                          {score.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="py-12 text-center text-slate-400 text-sm">
            No topic mastery data recorded for this class yet.
          </div>
        )}

        {/* Most Asked Topics Nudge */}
        {analytics?.most_asked_topics && analytics.most_asked_topics.length > 0 && (
          <div className="mt-6 pt-5 border-t border-slate-100 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Most Asked Topics in AI Tutor:
            </span>
            {analytics.most_asked_topics.map((t, idx) => (
              <span
                key={idx}
                className="px-2.5 py-1 bg-slate-100 text-slate-700 rounded-md text-xs font-medium border border-slate-200 capitalize flex items-center gap-1"
              >
                <span>💬</span> {t}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* 3. AT-RISK STUDENTS TABLE */}
      {/* --------------------------------------------------------------------- */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">
                At-Risk Students Roster
              </h2>
              {stats.atRiskCount > 0 && (
                <span className="px-2 py-0.5 bg-rose-100 text-rose-700 text-xs font-bold rounded-full">
                  {stats.atRiskCount} Flagged
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Students whose average or individual topic mastery is below 40%. Send a personalized nudge or practice recommendation.
            </p>
          </div>

          {stats.atRiskCount > 0 && (
            <div className="text-xs text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg">
              Sorted by Lowest Mastery First
            </div>
          )}
        </div>

        {/* Table */}
        {analytics?.at_risk_students && analytics.at_risk_students.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/80 text-slate-600 text-xs font-semibold uppercase tracking-wider">
                  <th className="py-3.5 px-6">Student Name</th>
                  <th className="py-3.5 px-6">Mastery Score</th>
                  <th className="py-3.5 px-6">Last Active</th>
                  <th className="py-3.5 px-6 text-right">Intervention</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {analytics.at_risk_students.map((student, idx) => {
                  const sId = student.id || student.student_id || `student-${idx}`;
                  const state = reminderState[sId] || "idle";
                  const score = student.mastery;
                  const colorConfig = getMasteryColor(score);

                  return (
                    <tr
                      key={sId}
                      className="hover:bg-slate-50/60 transition"
                    >
                      {/* Student Info */}
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs shrink-0">
                            {student.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-semibold text-slate-900">
                              {student.name}
                            </div>
                            {student.email && (
                              <div className="text-xs text-slate-400">
                                {student.email}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Mastery Score */}
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <span
                            className={`px-2.5 py-1 rounded-md text-xs font-bold border ${colorConfig.badgeBg} ${colorConfig.text} ${colorConfig.badgeBorder}`}
                          >
                            {score.toFixed(1)}%
                          </span>
                          <div className="w-24 bg-slate-100 h-1.5 rounded-full overflow-hidden hidden sm:block">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.min(100, Math.max(0, score))}%`,
                                backgroundColor: colorConfig.barFill,
                              }}
                            ></div>
                          </div>
                        </div>
                      </td>

                      {/* Last Active */}
                      <td className="py-4 px-6 text-slate-600 text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                          <span>{student.last_active || "Unknown"}</span>
                        </div>
                      </td>

                      {/* Action Button: Send Reminder */}
                      <td className="py-4 px-6 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => handleSendReminder(student)}
                            disabled={state === "sending" || state === "sent"}
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition shadow-sm border ${
                              state === "sent"
                                ? "bg-emerald-50 border-emerald-300 text-emerald-700 font-semibold"
                                : state === "sending"
                                ? "bg-indigo-50 border-indigo-200 text-indigo-600 opacity-80"
                                : state === "error"
                                ? "bg-rose-50 border-rose-300 text-rose-700"
                                : "bg-indigo-600 hover:bg-indigo-700 text-white border-transparent"
                            }`}
                          >
                            {state === "sending" ? (
                              <>
                                <svg className="animate-spin h-3.5 w-3.5 text-indigo-600" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                                </svg>
                                <span>Sending...</span>
                              </>
                            ) : state === "sent" ? (
                              <>
                                <span>✓ Reminder Sent</span>
                              </>
                            ) : state === "error" ? (
                              <>
                                <span>Failed - Retry</span>
                              </>
                            ) : (
                              <>
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                                </svg>
                                <span>Send Reminder</span>
                              </>
                            )}
                          </button>

                          {/* Customize Note Button */}
                          <button
                            type="button"
                            onClick={() => {
                              setCustomModalStudent(student);
                              setCustomReminderMsg(
                                `Hi ${student.name}, let's work on boosting your physics mastery! Try running the simulations or asking the AI Tutor.`
                              );
                              setCustomReminderTopic("");
                            }}
                            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition"
                            title="Customize reminder note"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth="1.75" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-12 px-6 text-center space-y-2">
            <div className="w-10 h-10 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto text-lg">
              ✓
            </div>
            <h3 className="text-sm font-bold text-slate-800">
              No Students Currently at Risk
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Every student in {displayClassName} is performing at or above the 40% mastery threshold.
            </p>
          </div>
        )}
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* 4. CUSTOM REMINDER MODAL (CONTROLLED STATE, NO <form> TAG) */}
      {/* --------------------------------------------------------------------- */}
      {customModalStudent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-100 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h3 className="font-bold text-slate-900">
                  Send Reminder to {customModalStudent.name}
                </h3>
                <p className="text-xs text-slate-500">
                  Current Mastery: {customModalStudent.mastery.toFixed(1)}%
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCustomModalStudent(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Target Topic (Optional)
                </label>
                <input
                  type="text"
                  value={customReminderTopic}
                  onChange={(e) => setCustomReminderTopic(e.target.value)}
                  placeholder="e.g. Newton's First Law or Projectile Motion"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Message Note
                </label>
                <textarea
                  rows={4}
                  value={customReminderMsg}
                  onChange={(e) => setCustomReminderMsg(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Type a helpful guidance message..."
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCustomModalStudent(null)}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg font-medium transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  handleSendReminder(
                    customModalStudent,
                    customReminderMsg,
                    customReminderTopic
                  )
                }
                className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition shadow-sm"
              >
                Send Direct Nudge
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
