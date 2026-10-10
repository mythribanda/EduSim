"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

interface AssignmentDetail {
  id: string;
  class_id: string;
  class_name?: string | null;
  teacher_id: string;
  teacher_name?: string | null;
  title: string;
  description?: string | null;
  module_id?: string | null;
  due_date?: string | null;
  due_date_ist?: string | null;
  max_score: number;
  created_at: string;
  submission_count: number;
  graded_count: number;
  total_students: number;
  average_score?: number | null;
}

interface Submission {
  id: string;
  assignment_id: string;
  assignment_title?: string | null;
  student_id: string;
  student_name?: string | null;
  submitted_at?: string | null;
  submitted_at_ist?: string | null;
  score?: number | null;
  feedback?: string | null;
  status: "pending" | "submitted" | "graded" | string;
  max_score?: number | null;
  due_date?: string | null;
  is_overdue?: boolean;
  created_at: string;
  updated_at: string;
}

function formatDateTime(isoStr?: string | null): string {
  if (!isoStr) return "Not submitted yet";
  try {
    const dt = new Date(isoStr);
    if (isNaN(dt.getTime())) return isoStr;
    return dt.toLocaleDateString("en-IN", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

export default function AssignmentGradingPage({
  params: propParams,
}: {
  params?: { assignmentId?: string };
}) {
  const router = useRouter();
  const routeParams = useParams();
  const assignmentId =
    (routeParams?.assignmentId as string) || propParams?.assignmentId || "";

  const [assignment, setAssignment] = useState<AssignmentDetail | null>(null);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Controlled form state for each submission: scores[subId], feedbacks[subId]
  const [scores, setScores] = useState<Record<string, string>>({});
  const [feedbacks, setFeedbacks] = useState<Record<string, string>>({});
  const [gradingIds, setGradingIds] = useState<Set<string>>(new Set());
  const [successIds, setSuccessIds] = useState<Set<string>>(new Set());
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});

  // Filtering & search
  const [statusFilter, setStatusFilter] = useState<"all" | "submitted" | "graded" | "pending">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/$/, "");

  const fetchData = async () => {
    if (!assignmentId) return;
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
      if (token) headers["Authorization"] = `Bearer ${token}`;

      // Parallel fetch: assignment metadata + all submissions for this assignment
      const [assignRes, subsRes] = await Promise.all([
        fetch(`${API_URL}/api/assignments/${assignmentId}`, { credentials: "omit", headers }),
        fetch(`${API_URL}/api/assignments/${assignmentId}/submissions`, { credentials: "omit", headers }),
      ]);

      if (!assignRes.ok) {
        throw new Error(`Failed to load assignment details (${assignRes.status})`);
      }
      if (!subsRes.ok) {
        throw new Error(`Failed to load submissions (${subsRes.status})`);
      }

      const assignData: AssignmentDetail = await assignRes.json();
      const subsData: Submission[] = await subsRes.json();

      setAssignment(assignData);
      setSubmissions(subsData);

      // Initialize controlled inputs from existing values
      const initialScores: Record<string, string> = {};
      const initialFeedbacks: Record<string, string> = {};
      subsData.forEach((s) => {
        if (s.score !== null && s.score !== undefined) {
          initialScores[s.id] = s.score.toString();
        }
        if (s.feedback) {
          initialFeedbacks[s.id] = s.feedback;
        }
      });
      setScores(initialScores);
      setFeedbacks(initialFeedbacks);
    } catch (err: any) {
      console.error("[Grading] Error fetching data:", err);
      setError(err.message || "Failed to load assignment grading data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [assignmentId]);

  // Pure onClick handler with controlled React state (no HTML form element)
  const handleGradeSubmission = async (submissionId: string) => {
    const rawScore = scores[submissionId];
    if (rawScore === undefined || rawScore === "" || rawScore.trim() === "") {
      setRowErrors((prev) => ({ ...prev, [submissionId]: "Please enter a score." }));
      return;
    }

    const numericScore = parseFloat(rawScore);
    const maxScore = assignment?.max_score ?? 100;

    if (isNaN(numericScore) || numericScore < 0) {
      setRowErrors((prev) => ({ ...prev, [submissionId]: "Score must be a positive number." }));
      return;
    }

    if (numericScore > maxScore) {
      setRowErrors((prev) => ({
        ...prev,
        [submissionId]: `Score cannot exceed max score of ${maxScore}.`,
      }));
      return;
    }

    setRowErrors((prev) => {
      const copy = { ...prev };
      delete copy[submissionId];
      return copy;
    });

    setGradingIds((prev) => new Set(prev).add(submissionId));

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
        `${API_URL}/api/assignments/${assignmentId}/submissions/${submissionId}/grade`,
        {
          method: "PATCH",
          credentials: "omit",
          headers,
          body: JSON.stringify({
            score: numericScore,
            feedback: feedbacks[submissionId]?.trim() || null,
          }),
        }
      );

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Grading failed (${res.status})`);
      }

      const updatedSub: Submission = await res.json();

      // Update submission state
      setSubmissions((prev) =>
        prev.map((s) => (s.id === submissionId ? updatedSub : s))
      );

      // Flash success badge
      setSuccessIds((prev) => new Set(prev).add(submissionId));
      setTimeout(() => {
        setSuccessIds((prev) => {
          const next = new Set(prev);
          next.delete(submissionId);
          return next;
        });
      }, 2500);

      // Re-fetch assignment stats to update average score and graded count
      const freshAssignRes = await fetch(`${API_URL}/api/assignments/${assignmentId}`, {
        credentials: "omit",
        headers,
      });
      if (freshAssignRes.ok) {
        const freshAssign: AssignmentDetail = await freshAssignRes.json();
        setAssignment(freshAssign);
      }
    } catch (err: any) {
      setRowErrors((prev) => ({
        ...prev,
        [submissionId]: err.message || "Failed to save grade.",
      }));
    } finally {
      setGradingIds((prev) => {
        const next = new Set(prev);
        next.delete(submissionId);
        return next;
      });
    }
  };

  const filteredSubmissions = useMemo(() => {
    return submissions.filter((sub) => {
      // Filter by status
      if (statusFilter !== "all" && sub.status !== statusFilter) {
        return false;
      }
      // Filter by search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const nameMatch = (sub.student_name || "").toLowerCase().includes(q);
        const feedbackMatch = (sub.feedback || "").toLowerCase().includes(q);
        return nameMatch || feedbackMatch;
      }
      return true;
    });
  }, [submissions, statusFilter, searchQuery]);

  const stats = useMemo(() => {
    const total = submissions.length;
    const submitted = submissions.filter((s) => s.status === "submitted" || s.status === "graded").length;
    const graded = submissions.filter((s) => s.status === "graded").length;
    const pending = submissions.filter((s) => s.status === "pending").length;
    return { total, submitted, graded, pending };
  }, [submissions]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center gap-2 text-sm text-slate-500 flex-wrap">
        <Link
          href="/dashboard"
          className="font-medium text-slate-600 hover:text-indigo-600 transition-colors"
        >
          My Classes
        </Link>
        <span>/</span>
        {assignment?.class_id && (
          <>
            <Link
              href={`/dashboard/classes/${assignment.class_id}`}
              className="font-medium text-slate-600 hover:text-indigo-600 transition-colors"
            >
              {assignment.class_name || "Class"}
            </Link>
            <span>/</span>
            <Link
              href={`/dashboard/classes/${assignment.class_id}/assignments`}
              className="font-medium text-slate-600 hover:text-indigo-600 transition-colors"
            >
              Assignments
            </Link>
            <span>/</span>
          </>
        )}
        <span className="font-semibold text-slate-900 truncate max-w-xs sm:max-w-md">
          {loading ? "Loading..." : assignment?.title || "Grading"}
        </span>
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm animate-pulse space-y-4">
            <div className="h-8 bg-slate-100 rounded w-1/3" />
            <div className="h-4 bg-slate-100 rounded w-2/3" />
            <div className="grid grid-cols-4 gap-4 pt-2">
              <div className="h-16 bg-slate-100 rounded" />
              <div className="h-16 bg-slate-100 rounded" />
              <div className="h-16 bg-slate-100 rounded" />
              <div className="h-16 bg-slate-100 rounded" />
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm animate-pulse h-64" />
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 flex items-center justify-between">
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchData}
            className="rounded bg-rose-100 px-3 py-1 text-xs font-bold text-rose-800 hover:bg-rose-200"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && assignment && (
        <>
          {/* Assignment Header Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
            <div className="flex flex-col md:flex-row justify-between gap-4 md:items-center">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                    {assignment.title}
                  </h1>
                  {assignment.module_id && (
                    <span className="inline-flex items-center rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 border border-indigo-100">
                      🔬 {assignment.module_id}
                    </span>
                  )}
                  {assignment.class_name && (
                    <span className="inline-flex items-center rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                      {assignment.class_name}
                    </span>
                  )}
                </div>
                {assignment.description && (
                  <p className="mt-2 text-sm text-slate-600 max-w-3xl leading-relaxed">
                    {assignment.description}
                  </p>
                )}
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <Link
                  href={`/dashboard/classes/${assignment.class_id}/assignments`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                  </svg>
                  <span>All Assignments</span>
                </Link>
              </div>
            </div>

            {/* Overview Stats Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-slate-100">
              {/* Total Enrolled */}
              <div className="rounded-lg bg-slate-50 p-3">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Total Students
                </span>
                <p className="mt-1 text-xl font-bold text-slate-900">{stats.total}</p>
              </div>

              {/* Submitted Count */}
              <div className="rounded-lg bg-indigo-50/70 p-3">
                <span className="text-[11px] font-semibold text-indigo-600 uppercase tracking-wider">
                  Submitted
                </span>
                <p className="mt-1 text-xl font-bold text-indigo-950">
                  {stats.submitted} / {stats.total}
                </p>
              </div>

              {/* Graded Count */}
              <div className="rounded-lg bg-emerald-50/70 p-3">
                <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider">
                  Graded
                </span>
                <p className="mt-1 text-xl font-bold text-emerald-950">
                  {stats.graded} / {stats.total}
                </p>
              </div>

              {/* Average Score */}
              <div className="rounded-lg bg-amber-50/70 p-3">
                <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider">
                  Average Score
                </span>
                <p className="mt-1 text-xl font-bold text-amber-950">
                  {typeof assignment.average_score === "number"
                    ? `${assignment.average_score.toFixed(1)} / ${assignment.max_score}`
                    : "—"}
                </p>
              </div>
            </div>
          </div>

          {/* Submissions Section */}
          <div className="space-y-4">
            {/* Filter and Search Bar */}
            <div className="flex flex-col sm:flex-row justify-between gap-3 sm:items-center">
              {/* Filter Tabs */}
              <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white p-1 shadow-2xs">
                <button
                  type="button"
                  onClick={() => setStatusFilter("all")}
                  className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                    statusFilter === "all"
                      ? "bg-indigo-600 text-white shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  All ({submissions.length})
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter("submitted")}
                  className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                    statusFilter === "submitted"
                      ? "bg-indigo-600 text-white shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Needs Grading ({submissions.filter((s) => s.status === "submitted").length})
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter("graded")}
                  className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                    statusFilter === "graded"
                      ? "bg-indigo-600 text-white shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Graded ({stats.graded})
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter("pending")}
                  className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                    statusFilter === "pending"
                      ? "bg-indigo-600 text-white shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Pending ({stats.pending})
                </button>
              </div>

              {/* Search Box */}
              <div className="relative w-full sm:w-64">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search student or feedback..."
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

            {/* Submission Table */}
            {submissions.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500 text-sm">
                No students enrolled in this class section yet.
              </div>
            ) : filteredSubmissions.length === 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
                No submissions matched your filter criteria.
              </div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-600">
                    <thead className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                      <tr>
                        <th scope="col" className="px-5 py-3.5">
                          Student
                        </th>
                        <th scope="col" className="px-5 py-3.5">
                          Submitted At
                        </th>
                        <th scope="col" className="px-5 py-3.5">
                          Status
                        </th>
                        <th scope="col" className="px-5 py-3.5 w-32">
                          Score (/{assignment.max_score})
                        </th>
                        <th scope="col" className="px-5 py-3.5">
                          Feedback
                        </th>
                        <th scope="col" className="px-5 py-3.5 text-right w-28">
                          Action
                        </th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-100">
                      {filteredSubmissions.map((sub) => {
                        const isGrading = gradingIds.has(sub.id);
                        const isSuccess = successIds.has(sub.id);
                        const rowError = rowErrors[sub.id];
                        const isPending = sub.status === "pending";
                        const isGraded = sub.status === "graded";
                        const isSubmitted = sub.status === "submitted";

                        return (
                          <tr
                            key={sub.id}
                            className={`transition-colors ${
                              isSuccess
                                ? "bg-emerald-50/50"
                                : isSubmitted
                                ? "bg-amber-50/30 hover:bg-amber-50/50"
                                : "hover:bg-slate-50"
                            }`}
                          >
                            {/* Student Name */}
                            <td className="px-5 py-4">
                              <div className="flex items-center gap-2.5">
                                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 font-bold text-indigo-700 text-xs uppercase">
                                  {(sub.student_name || "S").slice(0, 2)}
                                </div>
                                <div className="min-w-0">
                                  <p className="font-semibold text-slate-900 truncate">
                                    {sub.student_name || "Student"}
                                  </p>
                                  <Link
                                    href={`/dashboard/students/${sub.student_id}`}
                                    className="text-[11px] text-indigo-600 hover:underline"
                                  >
                                    View Profile →
                                  </Link>
                                </div>
                              </div>
                            </td>

                            {/* Submitted At */}
                            <td className="px-5 py-4 whitespace-nowrap">
                              {sub.submitted_at ? (
                                <div>
                                  <p className="font-medium text-slate-800">
                                    {formatDateTime(sub.submitted_at)}
                                  </p>
                                  {sub.submitted_at_ist && (
                                    <p className="text-[10px] text-slate-400">IST</p>
                                  )}
                                </div>
                              ) : (
                                <span className="text-slate-400 italic">Not submitted</span>
                              )}
                            </td>

                            {/* Status Badge */}
                            <td className="px-5 py-4 whitespace-nowrap">
                              {isGraded ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700">
                                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                                  Graded
                                </span>
                              ) : isSubmitted ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[11px] font-bold text-amber-800 animate-pulse">
                                  <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                                  Needs Grading
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
                                  Pending
                                </span>
                              )}
                            </td>

                            {/* Score Input (Controlled React state) */}
                            <td className="px-5 py-4">
                              <div className="space-y-1">
                                <div className="flex items-center gap-1.5">
                                  <input
                                    type="number"
                                    min="0"
                                    max={assignment.max_score}
                                    step="0.5"
                                    value={scores[sub.id] ?? ""}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      setScores((prev) => ({ ...prev, [sub.id]: val }));
                                      if (rowErrors[sub.id]) {
                                        setRowErrors((prev) => {
                                          const copy = { ...prev };
                                          delete copy[sub.id];
                                          return copy;
                                        });
                                      }
                                    }}
                                    disabled={isPending || isGrading}
                                    placeholder="Score"
                                    className={`w-20 rounded-lg border bg-white p-1.5 text-xs text-slate-900 text-right font-semibold focus:outline-none focus:ring-1 ${
                                      rowError
                                        ? "border-rose-300 focus:border-rose-500 focus:ring-rose-500"
                                        : "border-slate-300 focus:border-indigo-500 focus:ring-indigo-500"
                                    } disabled:bg-slate-50 disabled:text-slate-400`}
                                  />
                                  <span className="text-slate-400 font-medium">
                                    / {assignment.max_score}
                                  </span>
                                </div>
                                {rowError && (
                                  <p className="text-[10px] text-rose-600 leading-tight">
                                    {rowError}
                                  </p>
                                )}
                              </div>
                            </td>

                            {/* Feedback Field (Controlled React state) */}
                            <td className="px-5 py-4">
                              <input
                                type="text"
                                value={feedbacks[sub.id] ?? ""}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  setFeedbacks((prev) => ({ ...prev, [sub.id]: val }));
                                }}
                                disabled={isPending || isGrading}
                                placeholder={
                                  isPending
                                    ? "Student has not submitted yet"
                                    : "Enter constructive feedback for student..."
                                }
                                className="w-full min-w-[200px] rounded-lg border border-slate-300 bg-white p-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
                              />
                            </td>

                            {/* Grade Button (Pure onClick handler, NO <form>) */}
                            <td className="px-5 py-4 text-right whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => handleGradeSubmission(sub.id)}
                                disabled={isPending || isGrading}
                                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold shadow-xs transition-colors ${
                                  isGraded
                                    ? "bg-slate-100 text-slate-700 hover:bg-slate-200"
                                    : "bg-indigo-600 text-white hover:bg-indigo-700"
                                } disabled:opacity-40 disabled:cursor-not-allowed`}
                              >
                                {isGrading ? (
                                  <>
                                    <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                    </svg>
                                    <span>Saving...</span>
                                  </>
                                ) : isSuccess ? (
                                  <>
                                    <svg className="h-3.5 w-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" strokeWidth="2.5" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                    </svg>
                                    <span className="text-emerald-700">Saved!</span>
                                  </>
                                ) : (
                                  <span>{isGraded ? "Update" : "Grade"}</span>
                                )}
                              </button>
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
  );
}
