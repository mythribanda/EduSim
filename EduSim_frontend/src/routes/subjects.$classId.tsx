import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CurriculumService } from "@/services/curriculumService";
import { Card, PageWrapper } from "@/components/Card";
import { Crumbs } from "@/components/Crumbs";
import * as Icons from "lucide-react";
import { AlertCircle, RefreshCw } from "lucide-react";

export const Route = createFileRoute("/subjects/$classId")({
  component: SubjectsPage,
});

function SubjectsPage() {
  const { classId } = Route.useParams();
  const classIdNum = Number(classId);

  const {
    data: classes = [],
    isLoading: loadingClasses,
    isError: classesError,
    error: classesErr,
    refetch: refetchClasses,
  } = useQuery({
    queryKey: ["classes"],
    queryFn: CurriculumService.getClasses,
  });

  const {
    data: subjects = [],
    isLoading: loadingSubjects,
    isError: subjectsError,
    error: subjectsErr,
    refetch: refetchSubjects,
  } = useQuery({
    queryKey: ["subjects", classIdNum],
    queryFn: () => CurriculumService.getSubjects(classIdNum),
    enabled: !isNaN(classIdNum),
  });

  const isLoading = loadingClasses || loadingSubjects;
  const isError = classesError || subjectsError;
  const error = classesErr || subjectsErr;

  const c = classes.find((cls) => cls.id === classIdNum);

  if (isLoading) {
    return (
      <PageWrapper>
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground gap-4">
          <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium">Loading subjects for Class {classId}...</p>
        </div>
      </PageWrapper>
    );
  }

  if (isError) {
    return (
      <PageWrapper>
        <div className="glass rounded-3xl p-8 border border-destructive/20 bg-destructive/10 text-destructive flex flex-col items-center gap-4 text-center max-w-xl mx-auto my-12">
          <AlertCircle className="w-10 h-10 text-destructive" />
          <h3 className="text-xl font-bold">Failed to load subjects</h3>
          <p className="text-sm">{error instanceof Error ? error.message : "Unknown error"}</p>
          <button
            onClick={() => {
              refetchClasses();
              refetchSubjects();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-bold shadow hover:brightness-110 active:scale-95 transition-all mt-2"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        </div>
      </PageWrapper>
    );
  }

  if (!c) {
    return (
      <PageWrapper>
        <div className="glass rounded-3xl p-8 text-center text-muted-foreground my-12">
          Class {classId} not found.
        </div>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper>
      <Crumbs items={[{ label: "Home", to: "/" }, { label: c.name }]} />
      <h1 className="text-3xl font-bold mb-6">
        {c.name} <span className="text-muted-foreground text-lg font-normal">— Subjects</span>
      </h1>
      {subjects.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground bg-card border border-dashed border-border rounded-2xl">
          No subjects available for {c.name}.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {subjects.map((s, i) => {
            const Icon = (Icons as any)[s.icon || "BookOpen"] ?? Icons.BookOpen;
            return (
              <Link
                key={s.id}
                to="/chapters/$classId/$subject"
                params={{ classId: String(c.id), subject: s.id }}
                className="h-full"
              >
                <Card delay={i * 0.04} className="h-[170px] min-h-[170px] w-full flex flex-col justify-between p-6 border border-border bg-card shadow-sm hover:border-primary/50 rounded-2xl transition-all">
                  <div>
                    <div className="w-12 h-12 rounded-2xl bg-secondary flex items-center justify-center mb-3 transition-all">
                      <Icon className="w-6 h-6 text-primary" />
                    </div>
                    <h3 className="text-lg font-bold mb-1 text-foreground line-clamp-1">{s.name}</h3>
                  </div>
                  <div className="mt-3 text-xs font-mono font-bold text-primary flex items-center justify-between">
                    <span>VIEW CHAPTERS</span>
                    <span>→</span>
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </PageWrapper>
  );
}
