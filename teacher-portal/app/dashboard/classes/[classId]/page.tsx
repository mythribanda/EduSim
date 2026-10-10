"use client";

import React, { useEffect, useState, useMemo, useCallback, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

interface EnrolledStudent {
  enrollment_id: string;
  student_id: string;
  name: string;
  email: string;
  enrolled_at: string;
  status: string;
  mastery_percentage: number;
  last_active?: string | null;
  weakest_topic?: string | null;
  weakest_topic_score?: number | null;
  has_critical_weakness?: boolean;
}

interface ClassDetail {
  id: string;
  name: string;
  grade_level: string;
  join_code: string;
  created_at: string;
  subjects?: string[];
  enrolled_student_count: number;
}

interface ActivityItem {
  event_id: string;
  student_id: string;
  student_name: string;
  event_type: string;
  event_label: string;
  topic?: string | null;
  occurred_at_ist: string; // ISO-8601 string, e.g. "2026-09-07T18:15:00+05:30"
  occurred_at_utc: string;
}

type SortField = "name" | "mastery" | "last_active" | "weakest_topic";
type SortDirection = "asc" | "desc";

// -------------------------------------------------------
// Activity panel helpers
// -------------------------------------------------------

function getEventIcon(event_type: string): string {
  if (event_type.includes("correct")) return "✅";
  if (event_type.includes("incorrect")) return "❌";
  if (event_type.includes("quiz") || event_type.includes("answer")) return "📝";
  if (event_type.includes("simulation")) return "🔬";
  if (event_type.includes("tutor")) return "🤖";
  if (event_type.includes("video")) return "▶️";
  if (event_type.includes("session_started")) return "🟢";
  if (event_type.includes("session_ended")) return "🔴";
  if (event_type.includes("exercise")) return "📐";
  return "📌";
}

function getEventDotColor(event_type: string): string {
  if (event_type.includes("correct")) return "bg-emerald-500";
  if (event_type.includes("incorrect")) return "bg-rose-500";
  if (event_type.includes("simulation")) return "bg-purple-500";
  if (event_type.includes("tutor")) return "bg-blue-500";
  if (event_type.includes("session")) return "bg-slate-400";
  return "bg-amber-500";
}

/** Format an IST ISO string as a short relative or absolute time label. */
function formatActivityTime(istStr: string): string {
  try {
    const date = new Date(istStr);
    if (isNaN(date.getTime())) return "";
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    // Show IST time for older events
    return date.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Kolkata",
    });
  } catch {
    return "";
  }
}

function formatLastActive(dateStr?: string | null): string {
  if (!dateStr) return "No activity yet";
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "No activity yet";

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffHours < 1) return "Just now";
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getMasteryPill(score: number) {
  const clamped = Math.min(100, Math.max(0, Math.round(score * 10) / 10));
  if (clamped > 70) {
    return {
      textColor: "text-emerald-700",
      bgColor: "bg-emerald-50 border-emerald-200",
      barColor: "bg-emerald-500",
      label: "Mastered",
    };
  }
  if (clamped >= 40) {
    return {
      textColor: "text-amber-700",
      bgColor: "bg-amber-50 border-amber-200",
      barColor: "bg-amber-500",
      label: "Developing",
    };
  }
  return {
    textColor: "text-rose-700",
    bgColor: "bg-rose-50 border-rose-200",
    barColor: "bg-rose-500",
    label: "Critical",
  };
}

export default function ClassDetailPage({
  params: propParams,
}: {
  params?: { classId?: string };
}) {
  const router = useRouter();
  const routeParams = useParams();
  const classId = (routeParams?.classId as string) || propParams?.classId || "";

  const [classInfo, setClassInfo] = useState<ClassDetail | null>(null);
  const [students, setStudents] = useState<EnrolledStudent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedJoinCode, setCopiedJoinCode] = useState(false);

  // Sorting state — SORT BY MASTERY ASCENDING BY DEFAULT (weakest students first)
  const [sortField, setSortField] = useState<SortField>("mastery");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [filterQuery, setFilterQuery] = useState("");

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/$/, "");

  const fetchData = async () => {
    if (!classId) return;
    setLoading(true);
    setError(null);

    try {
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

      // Fetch class metadata & students list in parallel
      const [classRes, studentsRes] = await Promise.all([
        fetch(`${API_URL}/api/classes/${classId}`, { credentials: "omit", headers }),
        fetch(`${API_URL}/api/classes/${classId}/students`, { credentials: "omit", headers }),
      ]);

      if (!classRes.ok) {
        throw new Error(
          `Failed to fetch class info (${classRes.status}: ${classRes.statusText})`
        );
      }
      if (!studentsRes.ok) {
        throw new Error(
          `Failed to fetch class students (${studentsRes.status}: ${studentsRes.statusText})`
        );
      }

      const classData: ClassDetail = await classRes.json();
      const studentsData: EnrolledStudent[] = await studentsRes.json();

      setClassInfo(classData);
      setStudents(studentsData);
    } catch (err: any) {
      console.error("[ClassDetail] Error loading data:", err);
      setError(err.message || "Failed to load class details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [classId]);

  // ── Live Activity Panel ──────────────────────────────────────────────────
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  // Track "new event" flash IDs so we can highlight them briefly on each poll
  const [newEventIds, setNewEventIds] = useState<Set<string>>(new Set());
  const prevEventIdsRef = useRef<Set<string>>(new Set());

  const fetchActivity = useCallback(async () => {
    if (!classId) return;
    try {
      const token =
        typeof window !== "undefined"
          ? window.localStorage.getItem("token")
          : null;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(
        `${API_URL}/api/classes/${classId}/recent-activity?limit=20`,
        { credentials: "omit", headers }
      );
      if (!res.ok) {
        setActivityError(`Activity fetch failed (${res.status})`);
        return;
      }
      const data: ActivityItem[] = await res.json();
      setActivityError(null);

      // Identify truly new events since last poll for the flash highlight
      const incoming = new Set(data.map((e) => e.event_id));
      const prev = prevEventIdsRef.current;
      const fresh = new Set([...incoming].filter((id) => !prev.has(id)));
      prevEventIdsRef.current = incoming;
      if (fresh.size > 0) {
        setNewEventIds(fresh);
        setTimeout(() => setNewEventIds(new Set()), 2500);
      }

      setActivity(data);
    } catch (err: any) {
      setActivityError("Could not reach activity feed.");
    } finally {
      setActivityLoading(false);
    }
  }, [classId, API_URL]);

  // Initial load + 15-second polling
  useEffect(() => {
    if (!classId) return;
    setActivityLoading(true);
    fetchActivity();
    const interval = setInterval(fetchActivity, 15_000);
    return () => clearInterval(interval);
  }, [classId, fetchActivity]);

  const copyJoinCode = () => {
    if (classInfo?.join_code && typeof navigator !== "undefined") {
      navigator.clipboard.writeText(classInfo.join_code);
      setCopiedJoinCode(true);
      setTimeout(() => setCopiedJoinCode(false), 2000);
    }
  };

  // Check if >30% of class has mastery < 40% in any topic
  const weakStudentsStats = useMemo(() => {
    if (!students || students.length === 0) {
      return { count: 0, percentage: 0, showBanner: false, commonTopic: null };
    }

    const weakStudents = students.filter(
      (s) => s.has_critical_weakness || s.mastery_percentage < 40.0
    );
    const percentage = Math.round((weakStudents.length / students.length) * 100);

    // Identify most frequent weak topic
    const topicFrequency: Record<string, number> = {};
    weakStudents.forEach((s) => {
      if (s.weakest_topic) {
        topicFrequency[s.weakest_topic] =
          (topicFrequency[s.weakest_topic] || 0) + 1;
      }
    });

    let commonTopic: string | null = null;
    let maxFreq = 0;
    Object.entries(topicFrequency).forEach(([topic, count]) => {
      if (count > maxFreq) {
        maxFreq = count;
        commonTopic = topic;
      }
    });

    return {
      count: weakStudents.length,
      percentage,
      showBanner: percentage > 30,
      commonTopic,
    };
  }, [students]);

  // Handle sorting toggle
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      // Default to ascending for mastery (weakest first), descending for name
      setSortDirection(field === "mastery" ? "asc" : "asc");
    }
  };

  // Filter and sort students list
  const sortedAndFilteredStudents = useMemo(() => {
    let result = [...students];

    // Filter
    if (filterQuery.trim()) {
      const q = filterQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.email.toLowerCase().includes(q) ||
          (s.weakest_topic && s.weakest_topic.toLowerCase().includes(q))
      );
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;

      if (sortField === "mastery") {
        comparison = a.mastery_percentage - b.mastery_percentage;
      } else if (sortField === "name") {
        comparison = a.name.localeCompare(b.name);
      } else if (sortField === "last_active") {
        const timeA = a.last_active ? new Date(a.last_active).getTime() : 0;
        const timeB = b.last_active ? new Date(b.last_active).getTime() : 0;
        comparison = timeA - timeB;
      } else if (sortField === "weakest_topic") {
        const topicA = a.weakest_topic || "";
        const topicB = b.weakest_topic || "";
        comparison = topicA.localeCompare(topicB);
      }

      return sortDirection === "asc" ? comparison : -comparison;
    });

    return result;
  }, [students, sortField, sortDirection, filterQuery]);

  return (
    <div className="mx-auto max-w-screen-2xl">
      <div className="flex gap-6 items-start">
        {/* ── Main Content Column ───────────────────────────────── */}
        <div className="min-w-0 flex-1 space-y-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link
          href="/dashboard"
          className="flex items-center gap-1 font-medium text-slate-600 hover:text-indigo-600 transition-colors"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth="2"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"
            />
          </svg>
          My Classes
        </Link>
        <span>/</span>
        <span className="font-semibold text-slate-900">
          {loading ? "Loading class..." : classInfo?.name || "Class Detail"}
        </span>
      </div>

      {/* Loading Skeleton Header */}
      {loading && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm animate-pulse">
            <div className="h-8 w-48 rounded bg-slate-100" />
            <div className="mt-3 flex gap-3">
              <div className="h-5 w-24 rounded bg-slate-100" />
              <div className="h-5 w-24 rounded bg-slate-100" />
              <div className="h-5 w-32 rounded bg-slate-100" />
            </div>
          </div>

          <div className="h-16 w-full rounded-xl bg-slate-100 animate-pulse" />

          {/* Skeleton Table */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm animate-pulse">
            <div className="h-5 w-36 rounded bg-slate-100 mb-6" />
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-full bg-slate-100" />
                    <div>
                      <div className="h-4 w-32 rounded bg-slate-100" />
                      <div className="mt-1 h-3 w-44 rounded bg-slate-100" />
                    </div>
                  </div>
                  <div className="h-4 w-16 rounded bg-slate-100" />
                  <div className="h-4 w-28 rounded bg-slate-100" />
                  <div className="h-4 w-20 rounded bg-slate-100" />
                  <div className="h-7 w-24 rounded bg-slate-100" />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && !loading && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
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
              <span>{error}</span>
            </div>
            <button
              onClick={fetchData}
              className="rounded-md bg-rose-100 px-3 py-1 font-semibold text-rose-800 hover:bg-rose-200"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {!loading && classInfo && (
        <>
          {/* Header Card: Class Name, Grade, Subject */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                    {classInfo.name}
                  </h1>
                  <span className="inline-flex items-center rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 border border-indigo-100">
                    Grade {classInfo.grade_level}
                  </span>
                  {classInfo.subjects && classInfo.subjects.length > 0 && (
                    <span className="inline-flex items-center rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                      {classInfo.subjects.join(" • ")}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm text-slate-500">
                  {students.length} {students.length === 1 ? "student" : "students"} actively enrolled in this class section.
                </p>
              </div>

              <div className="flex items-center gap-3 sm:self-start flex-wrap">
                {/* Assignments Link */}
                <Link
                  href={`/dashboard/classes/${classId}/assignments`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100 transition-colors shadow-2xs"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" />
                  </svg>
                  <span>Assignments</span>
                </Link>

                {/* Join Code Box */}
                <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                  <div>
                    <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Class Join Code
                    </span>
                    <span className="font-mono text-base font-bold text-slate-800 tracking-wider">
                      {classInfo.join_code}
                    </span>
                  </div>
                  <button
                    onClick={copyJoinCode}
                    title="Copy Join Code"
                    className="ml-2 rounded p-1.5 text-slate-500 hover:bg-white hover:text-slate-900 transition-colors"
                  >
                    {copiedJoinCode ? (
                      <span className="text-xs font-semibold text-emerald-600">
                        Copied!
                      </span>
                    ) : (
                      <svg
                        className="h-4 w-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth="2"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75"
                        />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* "Weak Students" Banner (Triggered if > 30% of class has mastery < 40%) */}
          {weakStudentsStats.showBanner && (
            <div className="relative overflow-hidden rounded-xl border border-amber-300 bg-gradient-to-r from-amber-50 to-orange-50 p-5 text-amber-900 shadow-sm">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white shadow-sm">
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth="2"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                    />
                  </svg>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-amber-950">
                      Targeted Support Needed
                    </h3>
                    <span className="rounded-full bg-amber-200/80 px-2 py-0.5 text-xs font-bold text-amber-900">
                      {weakStudentsStats.percentage}% Struggling
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-amber-800 leading-relaxed">
                    <strong>{weakStudentsStats.count} of {students.length} students</strong> in this section currently show topic mastery below 40%.
                    {weakStudentsStats.commonTopic ? (
                      <span> The most frequent struggle point across these students is <strong className="underline decoration-amber-400 font-semibold">{weakStudentsStats.commonTopic}</strong>.</span>
                    ) : (
                      <span> Review individual student profiles below to assign practice simulations.</span>
                    )}
                  </p>
                  <p className="mt-2 text-xs font-semibold text-amber-700">
                    💡 Tip: Students are sorted by mastery % ascending so you can focus on the most vulnerable learners first.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Student Table Section */}
          <div className="space-y-4">
            {/* Search & Sort Controls */}
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Enrolled Students</h2>
                <p className="text-xs text-slate-500">
                  Sorted by <span className="font-semibold text-indigo-600">lowest mastery first</span> for fast intervention.
                </p>
              </div>

              <div className="flex items-center gap-3">
                {/* Search Box */}
                <div className="relative w-full sm:w-64">
                  <input
                    type="text"
                    value={filterQuery}
                    onChange={(e) => setFilterQuery(e.target.value)}
                    placeholder="Search by student name or topic..."
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
            </div>

            {/* Empty State */}
            {students.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
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
                    d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"
                  />
                </svg>
                <h3 className="mt-3 text-sm font-semibold text-slate-900">
                  No Students Enrolled Yet
                </h3>
                <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
                  Share the join code <strong className="font-mono text-slate-800">{classInfo.join_code}</strong> with your students to let them self-enroll in this section.
                </p>
                <button
                  onClick={copyJoinCode}
                  className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors"
                >
                  <svg
                    className="h-3.5 w-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth="2"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75"
                    />
                  </svg>
                  {copiedJoinCode ? "Copied Code!" : "Copy Join Code"}
                </button>
              </div>
            ) : sortedAndFilteredStudents.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
                No students matched your search criteria.
              </div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm text-slate-600">
                    <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                      <tr>
                        {/* Student Name */}
                        <th
                          scope="col"
                          onClick={() => handleSort("name")}
                          className="cursor-pointer px-6 py-3.5 hover:text-slate-900 transition-colors"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>Student</span>
                            {sortField === "name" && (
                              <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                            )}
                          </div>
                        </th>

                        {/* Mastery % */}
                        <th
                          scope="col"
                          onClick={() => handleSort("mastery")}
                          className="cursor-pointer px-6 py-3.5 hover:text-slate-900 transition-colors"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>Mastery %</span>
                            {sortField === "mastery" && (
                              <span className="font-bold text-indigo-600">
                                {sortDirection === "asc" ? "↑ (Weakest First)" : "↓ (Highest First)"}
                              </span>
                            )}
                          </div>
                        </th>

                        {/* Weakest Topic */}
                        <th
                          scope="col"
                          onClick={() => handleSort("weakest_topic")}
                          className="cursor-pointer px-6 py-3.5 hover:text-slate-900 transition-colors"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>Weakest Topic</span>
                            {sortField === "weakest_topic" && (
                              <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                            )}
                          </div>
                        </th>

                        {/* Last Active */}
                        <th
                          scope="col"
                          onClick={() => handleSort("last_active")}
                          className="cursor-pointer px-6 py-3.5 hover:text-slate-900 transition-colors"
                        >
                          <div className="flex items-center gap-1.5">
                            <span>Last Active</span>
                            {sortField === "last_active" && (
                              <span>{sortDirection === "asc" ? "↑" : "↓"}</span>
                            )}
                          </div>
                        </th>

                        {/* Action link */}
                        <th scope="col" className="px-6 py-3.5 text-right">
                          Action
                        </th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-100">
                      {sortedAndFilteredStudents.map((student) => {
                        const pill = getMasteryPill(student.mastery_percentage);
                        const isCritical =
                          student.has_critical_weakness ||
                          student.mastery_percentage < 40.0;

                        return (
                          <tr
                            key={student.enrollment_id}
                            className={`transition-colors hover:bg-slate-50 ${
                              isCritical ? "bg-rose-50/30" : ""
                            }`}
                          >
                            {/* Student name & email */}
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-3">
                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 font-bold text-slate-700 text-xs uppercase">
                                  {student.name.slice(0, 2)}
                                </div>
                                <div className="min-w-0">
                                  <p className="font-semibold text-slate-900 truncate">
                                    {student.name}
                                  </p>
                                  <p className="text-xs text-slate-500 truncate">
                                    {student.email || "No email on record"}
                                  </p>
                                </div>
                              </div>
                            </td>

                            {/* Mastery % with colored bar */}
                            <td className="px-6 py-4">
                              <div className="w-36">
                                <div className="flex items-center justify-between text-xs mb-1.5">
                                  <span className={`font-bold ${pill.textColor}`}>
                                    {student.mastery_percentage.toFixed(1)}%
                                  </span>
                                  <span
                                    className={`rounded border px-1.5 py-0.2 text-[10px] font-semibold ${pill.bgColor}`}
                                  >
                                    {pill.label}
                                  </span>
                                </div>
                                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                                  <div
                                    className={`h-full rounded-full transition-all duration-300 ${pill.barColor}`}
                                    style={{
                                      width: `${Math.min(
                                        100,
                                        Math.max(0, student.mastery_percentage)
                                      )}%`,
                                    }}
                                  />
                                </div>
                              </div>
                            </td>

                            {/* Weakest Topic */}
                            <td className="px-6 py-4">
                              {student.weakest_topic ? (
                                <div className="flex items-center gap-1.5">
                                  {isCritical && (
                                    <span className="h-2 w-2 shrink-0 rounded-full bg-rose-500" />
                                  )}
                                  <span
                                    className={`text-xs font-medium truncate max-w-[180px] ${
                                      isCritical ? "text-rose-900 font-semibold" : "text-slate-700"
                                    }`}
                                    title={student.weakest_topic}
                                  >
                                    {student.weakest_topic}
                                  </span>
                                  {typeof student.weakest_topic_score === "number" && (
                                    <span className="text-[11px] text-slate-400">
                                      ({student.weakest_topic_score.toFixed(0)}%)
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className="text-xs text-slate-400 italic">
                                  None recorded
                                </span>
                              )}
                            </td>

                            {/* Last Active */}
                            <td className="px-6 py-4 text-xs text-slate-500 whitespace-nowrap">
                              {formatLastActive(student.last_active)}
                            </td>

                            {/* View Profile Link */}
                            <td className="px-6 py-4 text-right whitespace-nowrap">
                              <Link
                                href={`/dashboard/students/${student.student_id}`}
                                className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 hover:text-indigo-600 hover:border-indigo-300"
                              >
                                <span>View Profile</span>
                                <svg
                                  className="h-3.5 w-3.5"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  strokeWidth="2"
                                  stroke="currentColor"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M8.25 4.5l7.5 7.5-7.5 7.5"
                                  />
                                </svg>
                              </Link>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </>
      )}
        </div>
        {/* ── Live Activity Sidebar ──────────────────────────────── */}
        <aside className="w-80 shrink-0 sticky top-6">
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            {/* Sidebar Header */}
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                </span>
                <h2 className="text-sm font-semibold text-slate-800">Live Activity</h2>
              </div>
              <div className="flex items-center gap-1.5">
                {activityLoading && (
                  <svg className="h-3.5 w-3.5 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                )}
                <button
                  onClick={fetchActivity}
                  title="Refresh activity"
                  className="rounded p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Poll cadence hint */}
            <div className="px-4 py-1.5 bg-slate-50 border-b border-slate-100">
              <p className="text-[10px] text-slate-400 font-medium tracking-wide">
                Refreshes every 15 s · Last 20 events · IST
              </p>
            </div>

            {/* Activity Feed */}
            <div className="divide-y divide-slate-50 overflow-y-auto max-h-[calc(100vh-14rem)]">
              {/* Error state */}
              {activityError && (
                <div className="px-4 py-3 text-xs text-rose-600 bg-rose-50 flex items-center gap-2">
                  <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                  </svg>
                  {activityError}
                </div>
              )}

              {/* Loading skeleton for first load */}
              {activityLoading && activity.length === 0 && (
                <div className="animate-pulse space-y-0 divide-y divide-slate-50">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="flex items-start gap-3 px-4 py-3">
                      <div className="mt-1 h-2 w-2 rounded-full bg-slate-200 shrink-0" />
                      <div className="flex-1 space-y-1.5">
                        <div className="h-3 bg-slate-100 rounded w-3/4" />
                        <div className="h-2.5 bg-slate-100 rounded w-full" />
                        <div className="h-2 bg-slate-100 rounded w-1/3" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Empty state */}
              {!activityLoading && activity.length === 0 && !activityError && (
                <div className="px-4 py-10 text-center">
                  <svg className="mx-auto h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="mt-2 text-xs text-slate-400">No activity yet.</p>
                  <p className="text-[10px] text-slate-300">Events will appear here when students are active.</p>
                </div>
              )}

              {/* Activity items */}
              {activity.map((ev) => {
                const isNew = newEventIds.has(ev.event_id);
                const dotColor = getEventDotColor(ev.event_type);
                const icon = getEventIcon(ev.event_type);
                const timeLabel = formatActivityTime(ev.occurred_at_ist);

                return (
                  <div
                    key={ev.event_id}
                    className={`flex items-start gap-3 px-4 py-3 transition-colors duration-700 ${
                      isNew ? "bg-emerald-50" : "hover:bg-slate-50"
                    }`}
                  >
                    {/* Event type dot */}
                    <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${dotColor}`} />

                    <div className="min-w-0 flex-1">
                      {/* Student name + action */}
                      <p className="text-xs text-slate-800 leading-snug">
                        <span className="font-semibold">{ev.student_name}</span>
                        {" "}
                        <span className="text-slate-500">{ev.event_label}</span>
                        {" "}
                        <span className="mr-1">{icon}</span>
                      </p>

                      {/* Topic badge */}
                      {ev.topic && (
                        <p className="mt-0.5 inline-flex items-center rounded bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700 truncate max-w-[180px]">
                          {ev.topic}
                        </p>
                      )}

                      {/* Timestamp */}
                      <p className="mt-1 text-[10px] text-slate-400">{timeLabel}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer */}
            {activity.length > 0 && (
              <div className="border-t border-slate-100 px-4 py-2 text-center">
                <p className="text-[10px] text-slate-400">
                  Showing {activity.length} most recent events
                </p>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
