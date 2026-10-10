"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface ClassItem {
  id: string;
  name: string;
  grade_level: string;
  join_code: string;
  subjects: string[];
  enrolled_student_count: number;
}

export default function AssignmentsLandingPage() {
  const router = useRouter();
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API_URL = (
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"
  ).replace(/\/$/, "");

  const fetchClasses = async () => {
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

      const res = await fetch(`${API_URL}/api/classes/mine`, {
        credentials: "omit",
        headers,
      });
      if (!res.ok) {
        throw new Error(`Failed to load classes (${res.status})`);
      }
      const data = await res.json();
      setClasses(data);
    } catch (err: any) {
      console.error("[AssignmentsLanding] Error:", err);
      setError(err.message || "Failed to load classes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClasses();
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Header Banner */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              Assignments Management
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Select a class section to view, create, and grade assignments.
            </p>
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 flex items-center justify-between">
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchClasses}
            className="rounded bg-rose-100 px-3 py-1 text-xs font-bold text-rose-800 hover:bg-rose-200"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm animate-pulse space-y-4"
            >
              <div className="h-6 bg-slate-100 rounded w-1/2" />
              <div className="h-4 bg-slate-100 rounded w-3/4" />
              <div className="h-9 bg-slate-100 rounded mt-4" />
            </div>
          ))}
        </div>
      )}

      {/* Classes Grid */}
      {!loading && !error && (
        <>
          {classes.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
              <p className="text-sm text-slate-500">
                You haven't created or joined any classes yet.
              </p>
              <Link
                href="/dashboard"
                className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700"
              >
                Go to My Classes
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {classes.map((cls) => (
                <div
                  key={cls.id}
                  className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <h2 className="text-lg font-bold text-slate-900">{cls.name}</h2>
                      <span className="rounded-md bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 border border-indigo-100">
                        Grade {cls.grade_level}
                      </span>
                    </div>

                    <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                      <span>👥 {cls.enrolled_student_count} Enrolled Students</span>
                    </div>

                    {cls.subjects && cls.subjects.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {cls.subjects.map((sub, i) => (
                          <span
                            key={i}
                            className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600"
                          >
                            {sub}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between">
                    <Link
                      href={`/dashboard/classes/${cls.id}/assignments`}
                      className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors"
                    >
                      <span>View & Manage Assignments</span>
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
