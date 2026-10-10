"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

interface Assignment {
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

interface ClassDetail {
  id: string;
  name: string;
  grade_level: string;
  join_code: string;
  enrolled_student_count: number;
  subjects?: string[];
}

interface CurriculumTopic {
  id: string;
  name: string;
  chapter_name: string;
  subject_name: string;
  has_simulation?: boolean;
}

function formatDueDate(isoStr?: string | null): { text: string; isPast: boolean } {
  if (!isoStr) return { text: "No deadline", isPast: false };
  try {
    const dt = new Date(isoStr);
    if (isNaN(dt.getTime())) return { text: "No deadline", isPast: false };
    const now = new Date();
    const isPast = now > dt;
    const formatted = dt.toLocaleDateString("en-IN", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    return { text: formatted, isPast };
  } catch {
    return { text: isoStr, isPast: false };
  }
}

export default function ClassAssignmentsPage({
  params: propParams,
}: {
  params?: { classId?: string };
}) {
  const router = useRouter();
  const routeParams = useParams();
  const classId = (routeParams?.classId as string) || propParams?.classId || "";

  const [classInfo, setClassInfo] = useState<ClassDetail | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [curriculumTopics, setCurriculumTopics] = useState<CurriculumTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State (controlled, NO <form> element)
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formModuleId, setFormModuleId] = useState("");
  const [formDueDate, setFormDueDate] = useState("");
  const [formMaxScore, setFormMaxScore] = useState("100");
  const [formError, setFormError] = useState<string | null>(null);

  // Search/Filter
  const [searchQuery, setSearchQuery] = useState("");

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
      if (token) headers["Authorization"] = `Bearer ${token}`;

      // Parallel fetch: class metadata, class assignments, and curriculum topics
      const [classRes, assignRes, topicsRes] = await Promise.all([
        fetch(`${API_URL}/api/classes/${classId}`, { credentials: "omit", headers }),
        fetch(`${API_URL}/api/assignments/class/${classId}`, { credentials: "omit", headers }),
        fetch(`${API_URL}/api/curriculum/all-topics`, { credentials: "omit", headers }).catch(() => null),
      ]);

      if (!classRes.ok) {
        throw new Error(`Failed to load class info (${classRes.status})`);
      }
      if (!assignRes.ok) {
        throw new Error(`Failed to load assignments (${assignRes.status})`);
      }

      const classData: ClassDetail = await classRes.json();
      const assignData: Assignment[] = await assignRes.json();

      setClassInfo(classData);
      setAssignments(assignData);

      if (topicsRes && topicsRes.ok) {
        const topicsData = await topicsRes.json();
        setCurriculumTopics(topicsData);
      }
    } catch (err: any) {
      console.error("[Assignments] Error fetching data:", err);
      setError(err.message || "Failed to load assignments.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [classId]);

  const handleOpenModal = () => {
    setFormTitle("");
    setFormDescription("");
    setFormModuleId("");
    // Set default due date to 7 days from now at 23:59
    const defaultDate = new Date();
    defaultDate.setDate(defaultDate.getDate() + 7);
    defaultDate.setHours(23, 59, 0, 0);
    const localIso = new Date(defaultDate.getTime() - defaultDate.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    setFormDueDate(localIso);
    setFormMaxScore("100");
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    if (creating) return;
    setIsModalOpen(false);
    setFormError(null);
  };

  // Pure onClick handler with controlled state (no HTML form element used)
  const handleCreateAssignment = async () => {
    if (!formTitle.trim()) {
      setFormError("Assignment title is required.");
      return;
    }
    const maxScoreNum = parseFloat(formMaxScore);
    if (isNaN(maxScoreNum) || maxScoreNum <= 0) {
      setFormError("Max score must be a positive number.");
      return;
    }

    setCreating(true);
    setFormError(null);

    try {
      const token =
        typeof window !== "undefined"
          ? window.localStorage.getItem("token")
          : null;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      let dueDateIso: string | null = null;
      if (formDueDate) {
        dueDateIso = new Date(formDueDate).toISOString();
      }

      const res = await fetch(`${API_URL}/api/assignments`, {
        method: "POST",
        credentials: "omit",
        headers,
        body: JSON.stringify({
          class_id: classId,
          title: formTitle.trim(),
          description: formDescription.trim() || null,
          module_id: formModuleId || null,
          due_date: dueDateIso,
          max_score: maxScoreNum,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to create assignment (${res.status})`);
      }

      const newAssignment: Assignment = await res.json();
      setAssignments((prev) => [newAssignment, ...prev]);
      setIsModalOpen(false);
    } catch (err: any) {
      setFormError(err.message || "Could not create assignment.");
    } finally {
      setCreating(false);
    }
  };

  const filteredAssignments = useMemo(() => {
    if (!searchQuery.trim()) return assignments;
    const q = searchQuery.toLowerCase();
    return assignments.filter(
      (a) =>
        a.title.toLowerCase().includes(q) ||
        (a.description && a.description.toLowerCase().includes(q)) ||
        (a.module_id && a.module_id.toLowerCase().includes(q))
    );
  }, [assignments, searchQuery]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link
          href="/dashboard"
          className="font-medium text-slate-600 hover:text-indigo-600 transition-colors"
        >
          My Classes
        </Link>
        <span>/</span>
        <Link
          href={`/dashboard/classes/${classId}`}
          className="font-medium text-slate-600 hover:text-indigo-600 transition-colors"
        >
          {classInfo?.name || "Class Detail"}
        </Link>
        <span>/</span>
        <span className="font-semibold text-slate-900">Assignments</span>
      </div>

      {/* Header Banner */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                Assignments
              </h1>
              {classInfo && (
                <span className="inline-flex items-center rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 border border-indigo-100">
                  {classInfo.name} · Grade {classInfo.grade_level}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Create homework, problem sets, and interactive lab reports. Track student submissions and grade work.
            </p>
          </div>

          <button
            type="button"
            onClick={handleOpenModal}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors shrink-0"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span>Create Assignment</span>
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 flex items-center justify-between">
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchData}
            className="rounded bg-rose-100 px-2.5 py-1 text-xs font-bold text-rose-800 hover:bg-rose-200"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm animate-pulse space-y-3"
            >
              <div className="flex justify-between items-center">
                <div className="h-6 bg-slate-100 rounded w-1/3" />
                <div className="h-6 bg-slate-100 rounded w-24" />
              </div>
              <div className="h-4 bg-slate-100 rounded w-1/2" />
              <div className="flex gap-4 pt-2">
                <div className="h-4 bg-slate-100 rounded w-28" />
                <div className="h-4 bg-slate-100 rounded w-28" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Assignments List */}
      {!loading && !error && (
        <div className="space-y-4">
          {/* Controls Bar */}
          <div className="flex flex-col sm:flex-row justify-between gap-3 sm:items-center">
            <div className="text-sm font-semibold text-slate-700">
              {filteredAssignments.length} {filteredAssignments.length === 1 ? "Assignment" : "Assignments"}
            </div>
            {assignments.length > 0 && (
              <div className="relative w-full sm:w-72">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search assignments..."
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
            )}
          </div>

          {/* Empty State */}
          {assignments.length === 0 ? (
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
                  d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"
                />
              </svg>
              <h3 className="mt-3 text-base font-semibold text-slate-900">
                No Assignments Created Yet
              </h3>
              <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
                Create assignments linked to simulation modules to assign homework and track student comprehension.
              </p>
              <button
                type="button"
                onClick={handleOpenModal}
                className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                <span>Create First Assignment</span>
              </button>
            </div>
          ) : filteredAssignments.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
              No assignments matched "{searchQuery}".
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredAssignments.map((assignment) => {
                const totalStudents = assignment.total_students || classInfo?.enrolled_student_count || 0;
                const submissionCount = assignment.submission_count || 0;
                const gradedCount = assignment.graded_count || 0;
                const dueInfo = formatDueDate(assignment.due_date);

                // Badge styling for X/Y submitted
                const isAllSubmitted = totalStudents > 0 && submissionCount >= totalStudents;
                const isZeroSubmitted = submissionCount === 0;

                return (
                  <div
                    key={assignment.id}
                    onClick={() => router.push(`/dashboard/assignments/${assignment.id}`)}
                    className="group cursor-pointer rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-indigo-300 hover:shadow-md"
                  >
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2.5 flex-wrap">
                          <h2 className="text-base font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                            {assignment.title}
                          </h2>
                          {assignment.module_id && (
                            <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                              🔬 {assignment.module_id}
                            </span>
                          )}
                        </div>

                        {assignment.description && (
                          <p className="mt-1 text-xs text-slate-500 line-clamp-2">
                            {assignment.description}
                          </p>
                        )}

                        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                          {/* Due Date */}
                          <div className="flex items-center gap-1.5">
                            <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>Due: </span>
                            <span className={dueInfo.isPast ? "font-semibold text-rose-600" : "font-semibold text-slate-700"}>
                              {dueInfo.text}
                            </span>
                          </div>

                          {/* Max Score */}
                          <div className="flex items-center gap-1">
                            <span className="text-slate-400">Max Score:</span>
                            <span className="font-semibold text-slate-700">{assignment.max_score} pts</span>
                          </div>
                        </div>
                      </div>

                      {/* Right side stats badges */}
                      <div className="flex sm:flex-col items-center sm:items-end justify-between gap-2 border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-100 shrink-0">
                        {/* X/Y Submitted Badge */}
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
                              isAllSubmitted
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : isZeroSubmitted
                                ? "bg-slate-100 text-slate-600 border border-slate-200"
                                : "bg-indigo-50 text-indigo-700 border border-indigo-200"
                            }`}
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-current" />
                            <span>
                              {submissionCount}/{totalStudents} submitted
                            </span>
                          </span>
                        </div>

                        {/* Average Score Badge */}
                        <div className="text-xs text-slate-600 font-medium">
                          {typeof assignment.average_score === "number" ? (
                            <span className="inline-flex items-center gap-1">
                              <span className="text-slate-400">Avg Score:</span>
                              <span className="font-bold text-emerald-700">
                                {assignment.average_score.toFixed(1)} / {assignment.max_score}
                              </span>
                              <span className="text-[10px] text-slate-400">
                                ({Math.round((assignment.average_score / assignment.max_score) * 100)}%)
                              </span>
                            </span>
                          ) : (
                            <span className="text-[11px] text-slate-400 italic">
                              {gradedCount === 0 ? "No graded work yet" : "Calculating avg..."}
                            </span>
                          )}
                        </div>

                        {/* View Submissions Arrow */}
                        <div className="hidden sm:flex items-center gap-1 text-xs font-semibold text-indigo-600 group-hover:translate-x-0.5 transition-transform">
                          <span>View Submissions</span>
                          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* Create Assignment Modal (Controlled React state only, no form tag)         */}
      {/* ========================================================================= */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Create New Assignment</h3>
                  <p className="text-xs text-slate-500">Section: {classInfo?.name || "Class"}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={creating}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Error Message inside modal */}
            {formError && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 flex items-center gap-2">
                <svg className="h-4 w-4 shrink-0 text-rose-500" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <span>{formError}</span>
              </div>
            )}

            {/* Modal Body: Controlled inputs (No <form> element) */}
            <div className="space-y-4 text-xs">
              {/* Title */}
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Assignment Title <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="e.g. Projectile Motion Simulation & Analysis"
                  className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Description & Instructions
                </label>
                <textarea
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Provide guidance, required parameters, and question prompts for students..."
                  className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Select Topic from Curriculum Dropdown */}
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Curriculum Topic <span className="text-slate-400 font-normal">(optional)</span>
                </label>
                <select
                  value={formModuleId}
                  onChange={(e) => setFormModuleId(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">-- None / General Assignment --</option>
                  {curriculumTopics.map((topic) => (
                    <option key={topic.id} value={topic.name}>
                      {topic.subject_name ? `${topic.subject_name} › ` : ""}
                      {topic.chapter_name ? `${topic.chapter_name} › ` : ""}
                      {topic.name}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-[11px] text-slate-400">
                  Linking a curriculum topic connects this assignment with mastery tracking.
                </p>
              </div>

              {/* Due Date & Max Score 2-column grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Due Date */}
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Due Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    value={formDueDate}
                    onChange={(e) => setFormDueDate(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                {/* Max Score */}
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Maximum Score
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    step="1"
                    value={formMaxScore}
                    onChange={(e) => setFormMaxScore(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              </div>
            </div>

            {/* Modal Actions (onClick handlers only) */}
            <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={handleCloseModal}
                disabled={creating}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreateAssignment}
                disabled={creating}
                className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors disabled:opacity-50"
              >
                {creating ? (
                  <>
                    <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <span>Creating...</span>
                  </>
                ) : (
                  <span>Create Assignment</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
