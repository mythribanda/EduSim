import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CurriculumService } from "@/services/curriculumService";
import { Card, PageWrapper } from "@/components/Card";
import { Crumbs } from "@/components/Crumbs";
import { AlertCircle, RefreshCw } from "lucide-react";

export const Route = createFileRoute("/chapters/$classId/$subject")({
  component: ChaptersPage,
});

function ChaptersPage() {
  const { classId, subject: subjectParam } = Route.useParams();
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

  const c = classes.find((cls) => cls.id === classIdNum);
  const s = subjects.find(
    (sub) =>
      (sub.code || "").toLowerCase() === (subjectParam || "").toLowerCase() ||
      (sub.id || "").toLowerCase() === (subjectParam || "").toLowerCase()
  );

  const {
    data: chapters = [],
    isLoading: loadingChapters,
    isError: chaptersError,
    error: chaptersErr,
    refetch: refetchChapters,
  } = useQuery({
    queryKey: ["chapters", classIdNum, s?.id || subjectParam],
    queryFn: () => CurriculumService.getChapters(s?.id || subjectParam, classIdNum),
    enabled: !isNaN(classIdNum) && Boolean(subjectParam),
  });

  const isLoading = loadingClasses || loadingSubjects || loadingChapters;
  const isError = classesError || subjectsError || chaptersError;
  const error = classesErr || subjectsErr || chaptersErr;

  if (isLoading) {
    return (
      <PageWrapper>
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground gap-4">
          <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium">Loading chapters...</p>
        </div>
      </PageWrapper>
    );
  }

  if (isError) {
    return (
      <PageWrapper>
        <div className="glass rounded-3xl p-8 border border-destructive/20 bg-destructive/10 text-destructive flex flex-col items-center gap-4 text-center max-w-xl mx-auto my-12">
          <AlertCircle className="w-10 h-10 text-destructive" />
          <h3 className="text-xl font-bold">Failed to load chapters</h3>
          <p className="text-sm">{error instanceof Error ? error.message : "Unknown error"}</p>
          <button
            onClick={() => {
              refetchClasses();
              refetchSubjects();
              refetchChapters();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-bold shadow hover:brightness-110 active:scale-95 transition-all mt-2"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        </div>
      </PageWrapper>
    );
  }

  if (!c || !s) {
    return (
      <PageWrapper>
        <div className="glass rounded-3xl p-8 text-center text-muted-foreground my-12">
          Subject or Class not found.
        </div>
      </PageWrapper>
    );
  }

  const safeChapters = Array.isArray(chapters) ? chapters : [];
  const chapterCount = safeChapters.length;

  return (
    <PageWrapper>
      <Crumbs
        items={[
          { label: "Home", to: "/" },
          { label: c.name, to: "/subjects/$classId", params: { classId: String(c.id) } },
          { label: s.name },
        ]}
      />

      <h1 className="text-3xl font-bold mb-2">
        {s.name} <span className="text-muted-foreground text-lg">— Chapters</span>
      </h1>

      <p className="text-muted-foreground mb-8">{chapterCount} chapters available</p>

      {chapterCount === 0 ? (
        <div className="text-center py-12 text-muted-foreground bg-card border border-dashed border-border rounded-2xl">
          No chapters available.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {safeChapters.map((chapter, i) => (
            <Link
              key={chapter.name}
              to="/topics/$classId/$subject/$chapter"
              params={{
                classId: String(c.id),
                subject: s.id,
                chapter: chapter.name,
              }}
            >
              <Card delay={i * 0.02}>
                <div className="text-xs font-bold text-primary mb-2">CHAPTER</div>

                <div className="text-lg font-bold mb-2">{chapter.name}</div>

                <p className="text-xs text-muted-foreground">
                  Chapter {i + 1} of {safeChapters.length}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </PageWrapper>
  );
}
