import {
  CLASSES,
  STREAM_CLASSES,
  UNIVERSITY_COURSES,
  Stream,
  Course,
  Subject,
  StreamClassInfo,
} from "@/data/curriculum";
import { fetchJsonWithRetry } from "@/services/apiClient";
import { getApiUrl } from "@/config/api";

// Re-export types so consuming components do not need changes
export type { Stream, Course, Subject, StreamClassInfo };

/**
 * ============================================================================
 * OFFLINE FALLBACK CONFIGURATION
 * ============================================================================
 * When true, if the backend /api/curriculum/v2/* API fails or is unreachable,
 * CurriculumService falls back to the static data in src/data/curriculum.ts
 * and outputs a clear warning in the console.
 */
export const ENABLE_OFFLINE_FALLBACK = true;

export interface DBClass {
  id: number;
  name: string;
  description: string;
}

export interface DBSubject {
  id: string;
  class_id?: number | string;
  code: string;
  name: string;
  description: string;
  icon: string;
}

export interface DBChapter {
  id: string;
  subject_id: string;
  name: string;
  description: string;
}

export interface DBTopic {
  id: string;
  chapter_id: string;
  name: string;
  description: string;
  has_simulation: boolean;
  simulation_route: string | null;
}

// Backend API response schemas for /api/curriculum/v2/*
interface ApiBook {
  id: string;
  code: string;
  title: string;
  board: string;
  class_num: number;
  subject: string;
  language?: string | null;
  part?: number | null;
  total_pages: number;
  ocr_page_count: number;
  text_quality?: string | null;
  extraction_status: string;
  pipeline_version: string;
  is_active: boolean;
}

interface ApiBookListResponse {
  items: ApiBook[];
  total: number;
  limit: number;
  offset: number;
}

interface ApiChapterSummary {
  id: string;
  chapter_number: string;
  official_number?: string | null;
  title: string;
  page_start: number;
  page_end: number;
  source_page_start: number;
  source_page_end: number;
  source_file?: string | null;
  order_index: number;
}

interface ApiTreeNode {
  id: string;
  chapter_number: string;
  level: string;
  parent_id?: string | null;
  order_index: number;
  official_number?: string | null;
  title: string;
  normalized_title: string;
  page_start: number;
  page_end: number;
  source_page_start: number;
  source_page_end: number;
  source_file?: string | null;
  ocr_needed: boolean;
  metadata_json?: any;
  nodes: ApiTreeNode[];
}

// ============================================================================
// Helper formatting & icons
// ============================================================================

function getClassDescription(classNum: number): string {
  const descriptions: Record<number, string> = {
    1: "Foundations of numbers and counting",
    2: "Early mathematical concepts and shapes",
    3: "Elementary science, mathematics and environment",
    4: "Growing understanding of math and nature",
    5: "Transition into primary school STEM logic",
    6: "Foundational middle school science and math",
    7: "Exploring living systems, physical phenomena, and algebra",
    8: "Advanced middle school physical and biological sciences",
    9: "High school foundations in mechanics, chemistry, and geometry",
    10: "Board examination standard in science and mathematics",
    11: "Specialized higher secondary physics, chemistry, and math",
    12: "Advanced higher secondary sciences, calculus, and board prep",
  };
  return descriptions[classNum] || `Comprehensive curriculum for Class ${classNum}`;
}

function formatSubjectName(subjectStr: string): string {
  const map: Record<string, string> = {
    physics: "Physics",
    chemistry: "Chemistry",
    mathematics: "Mathematics",
    math: "Mathematics",
    biology: "Biology",
    science: "Science",
    english: "English",
    "social-science": "Social Science",
    evs: "Environmental Studies",
    telugu: "Telugu",
  };
  const key = subjectStr.trim().toLowerCase();
  return map[key] || subjectStr.charAt(0).toUpperCase() + subjectStr.slice(1);
}

function getSubjectIcon(subjectStr: string): string {
  const s = subjectStr.trim().toLowerCase();
  if (s.includes("physic")) return "Atom";
  if (s.includes("chem")) return "FlaskConical";
  if (s.includes("math")) return "Calculator";
  if (s.includes("bio")) return "Dna";
  if (s.includes("evs") || s.includes("env")) return "TreePine";
  if (s.includes("soc") || s.includes("geo") || s.includes("hist")) return "Globe";
  if (s.includes("eng") || s.includes("lit") || s.includes("telugu")) return "BookOpen";
  return "BookOpen";
}

function matchSubjectId(bookSubject: string, requestedSubjectId: string): boolean {
  const b = (bookSubject || "").trim().toLowerCase();
  const r = (requestedSubjectId || "").trim().toLowerCase();
  if (b === r) return true;
  if ((r === "math" || r === "mathematics") && (b === "math" || b === "mathematics")) return true;
  if ((r === "physic" || r === "physics") && (b === "physic" || b === "physics")) return true;
  if ((r === "chem" || r === "chemistry") && (b === "chem" || b === "chemistry")) return true;
  if ((r === "bio" || r === "biology") && (b === "bio" || b === "biology")) return true;
  return false;
}

// ============================================================================
// Offline Fallback Implementations (from src/data/curriculum.ts)
// ============================================================================

function fallbackGetClasses(): DBClass[] {
  console.warn(
    "[CurriculumService] Falling back to offline static data from src/data/curriculum.ts for getClasses()"
  );
  return CLASSES.map((c) => ({
    id: c.id,
    name: c.name,
    description: c.description,
  }));
}

function fallbackGetSubjects(classId: number): DBSubject[] {
  console.warn(
    `[CurriculumService] Falling back to offline static data from src/data/curriculum.ts for getSubjects(classId=${classId})`
  );
  const cls = CLASSES.find((c) => c.id === classId);
  if (!cls) return [];
  return cls.subjects.map((s) => ({
    id: s.id,
    class_id: cls.id,
    code: s.id,
    name: s.name,
    description: s.description,
    icon: s.icon,
  }));
}

function fallbackGetChapters(subjectId: string, classId?: number): DBChapter[] {
  console.warn(
    `[CurriculumService] Falling back to offline static data from src/data/curriculum.ts for getChapters(subjectId=${subjectId}, classId=${classId})`
  );
  let subject: any = null;
  const normSubjectId = (subjectId || "").toLowerCase();
  for (const c of CLASSES) {
    if (classId !== undefined && c.id !== classId) continue;
    const s = c.subjects.find((sub) => (sub.id || "").toLowerCase() === normSubjectId);
    if (s) {
      subject = s;
      break;
    }
  }
  if (!subject || typeof subject.chapters === "number" || !Array.isArray(subject.chapters)) {
    return [];
  }

  return subject.chapters.map((ch: any) => ({
    id: ch.name,
    subject_id: subjectId,
    name: ch.name,
    description: "",
  }));
}

function fallbackGetTopics(chapterId: string, classId?: number): DBTopic[] {
  console.warn(
    `[CurriculumService] Falling back to offline static data from src/data/curriculum.ts for getTopics(chapterId=${chapterId}, classId=${classId})`
  );
  let chapter: any = null;
  let decodedChapterId = chapterId || "";
  try {
    decodedChapterId = decodeURIComponent(chapterId);
  } catch (e) {
    // ignore decode error
  }
  const normChapterId = decodedChapterId.toLowerCase();

  for (const c of CLASSES) {
    if (classId !== undefined && c.id !== classId) continue;
    for (const s of c.subjects) {
      if (s && typeof s.chapters !== "number" && Array.isArray(s.chapters)) {
        const ch = s.chapters.find((chap: any) => (chap.name || "").toLowerCase() === normChapterId);
        if (ch) {
          chapter = ch;
          break;
        }
      }
    }
    if (chapter) break;
  }
  if (!chapter || !Array.isArray(chapter.topics)) return [];

  return chapter.topics.map((t: any) => ({
    id: t.name,
    chapter_id: chapterId,
    name: t.name,
    description: "",
    has_simulation: t.hasSimulation || false,
    simulation_route: t.simulationRoute || null,
  }));
}

// In-memory request caches to avoid duplicate network waterfalls
let cachedBooksPromise: Promise<ApiBook[]> | null = null;
async function getAllBooks(): Promise<ApiBook[]> {
  if (!cachedBooksPromise) {
    cachedBooksPromise = (async () => {
      const url = getApiUrl("/api/curriculum/v2/books?limit=100");
      const resp = await fetchJsonWithRetry<ApiBookListResponse>(url, {
        scope: "CurriculumService",
        timeoutMs: 15000,
        retries: 1,
      });
      return resp.items || [];
    })().catch((err) => {
      cachedBooksPromise = null;
      throw err;
    });
  }
  return cachedBooksPromise;
}

// ============================================================================
// CurriculumService Implementation
// ============================================================================

export const CurriculumService = {
  /**
   * Returns all active classes by querying books and extracting unique class numbers.
   */
  getClasses: async (): Promise<DBClass[]> => {
    try {
      const books = await getAllBooks();
      if (!books || books.length === 0) {
        throw new Error("No books returned from backend API");
      }

      const classNumbers = Array.from(new Set(books.map((b) => b.class_num))).sort((a, b) => a - b);
      return classNumbers.map((num) => ({
        id: num,
        name: `Class ${num}`,
        description: getClassDescription(num),
      }));
    } catch (err) {
      if (ENABLE_OFFLINE_FALLBACK) {
        return fallbackGetClasses();
      }
      throw err;
    }
  },

  /**
   * Returns subjects available for a class by grouping active books for that class.
   */
  getSubjects: async (classId: number): Promise<DBSubject[]> => {
    try {
      const books = await getAllBooks();
      const classBooks = books.filter((b) => b.class_num === classId);
      if (!classBooks || classBooks.length === 0) {
        // Fallback or empty if class has no books loaded
        if (ENABLE_OFFLINE_FALLBACK) {
          return fallbackGetSubjects(classId);
        }
        return [];
      }

      const subjectMap = new Map<string, DBSubject>();
      for (const b of classBooks) {
        const subKey = b.subject.trim().toLowerCase();
        if (!subjectMap.has(subKey)) {
          subjectMap.set(subKey, {
            id: subKey,
            class_id: classId,
            code: subKey,
            name: formatSubjectName(subKey),
            description: `NCERT & State Board ${formatSubjectName(subKey)} for Class ${classId}`,
            icon: getSubjectIcon(subKey),
          });
        }
      }

      return Array.from(subjectMap.values()).sort((a, b) => a.name.localeCompare(b.name));
    } catch (err) {
      if (ENABLE_OFFLINE_FALLBACK) {
        return fallbackGetSubjects(classId);
      }
      throw err;
    }
  },

  /**
   * Returns flat list of chapters for a subject and class.
   */
  getChapters: async (subjectId: string, classId?: number): Promise<DBChapter[]> => {
    try {
      const books = await getAllBooks();
      const matchingBooks = books.filter((b) => {
        if (classId !== undefined && b.class_num !== classId) return false;
        return matchSubjectId(b.subject, subjectId) || b.code.toLowerCase() === subjectId.toLowerCase();
      });

      if (!matchingBooks || matchingBooks.length === 0) {
        if (ENABLE_OFFLINE_FALLBACK) {
          return fallbackGetChapters(subjectId, classId);
        }
        return [];
      }

      // Fetch chapters for all matching books (e.g. Physics Part 1 and Part 2)
      const chaptersList: DBChapter[] = [];
      for (const book of matchingBooks) {
        const url = getApiUrl(`/api/curriculum/v2/books/${encodeURIComponent(book.code)}/chapters`);
        const chapters = await fetchJsonWithRetry<ApiChapterSummary[]>(url, {
          scope: "CurriculumService",
          timeoutMs: 15000,
          retries: 1,
        });

        for (const ch of chapters) {
          chaptersList.push({
            id: ch.title, // Kept as title for route path matching compatibility
            subject_id: subjectId,
            name: ch.title,
            description: ch.official_number ? `Chapter ${ch.official_number}` : "",
          });
        }
      }

      if (chaptersList.length === 0 && ENABLE_OFFLINE_FALLBACK) {
        return fallbackGetChapters(subjectId, classId);
      }

      return chaptersList;
    } catch (err) {
      if (ENABLE_OFFLINE_FALLBACK) {
        return fallbackGetChapters(subjectId, classId);
      }
      throw err;
    }
  },

  /**
   * Returns child topics for a given chapter by inspecting the book tree.
   */
  getTopics: async (chapterId: string, classId?: number): Promise<DBTopic[]> => {
    try {
      let decodedChapterId = chapterId || "";
      try {
        decodedChapterId = decodeURIComponent(chapterId).trim();
      } catch (e) {
        // ignore decode error
      }
      const normChapterId = decodedChapterId.toLowerCase();

      const books = await getAllBooks();
      const candidateBooks = classId !== undefined ? books.filter((b) => b.class_num === classId) : books;

      for (const book of candidateBooks) {
        const url = getApiUrl(
          `/api/curriculum/v2/books/${encodeURIComponent(book.code)}/tree?max_level=subtopic`
        );
        let treeRoots: ApiTreeNode[] = [];
        try {
          treeRoots = await fetchJsonWithRetry<ApiTreeNode[]>(url, {
            scope: "CurriculumService",
            timeoutMs: 15000,
            retries: 1,
          });
        } catch {
          continue;
        }

        const foundChapter = treeRoots.find((root) => {
          if (root.id === chapterId) return true;
          const rootTitle = (root.title || "").trim().toLowerCase();
          const rootNorm = (root.normalized_title || "").trim().toLowerCase();
          return rootTitle === normChapterId || rootNorm === normChapterId;
        });

        if (foundChapter && Array.isArray(foundChapter.nodes) && foundChapter.nodes.length > 0) {
          return foundChapter.nodes.map((n) => ({
            id: n.id || n.title,
            chapter_id: chapterId,
            name: n.title,
            description: n.official_number ? `Section ${n.official_number}` : "",
            has_simulation: Boolean(n.metadata_json?.has_simulation || false),
            simulation_route: n.metadata_json?.simulation_route || null,
          }));
        }
      }

      if (ENABLE_OFFLINE_FALLBACK) {
        return fallbackGetTopics(chapterId, classId);
      }
      return [];
    } catch (err) {
      if (ENABLE_OFFLINE_FALLBACK) {
        return fallbackGetTopics(chapterId, classId);
      }
      throw err;
    }
  },

  // Stream & University methods preserved for full compatibility
  getStreamClasses: async (): Promise<StreamClassInfo[]> => {
    return STREAM_CLASSES;
  },

  getStreams: async (classId: number): Promise<Stream[]> => {
    const cls = STREAM_CLASSES.find((sc) => sc.id === classId);
    return cls ? cls.streams : [];
  },

  getStreamSubjects: async (classId: number, streamId: string): Promise<DBSubject[]> => {
    const cls = STREAM_CLASSES.find((sc) => sc.id === classId);
    const stream = cls?.streams.find((s) => s.id === streamId);
    if (!stream) return [];
    return stream.subjects.map((s) => ({
      id: s.id,
      class_id: classId,
      code: s.id,
      name: s.name,
      description: s.description,
      icon: s.icon,
    }));
  },

  getUniversityCourses: async (): Promise<Course[]> => {
    return UNIVERSITY_COURSES;
  },

  getCourseSubjects: async (courseId: string): Promise<DBSubject[]> => {
    const course = UNIVERSITY_COURSES.find((c) => c.id === courseId);
    if (!course) return [];
    return course.subjects.map((s) => ({
      id: s.id,
      class_id: course.id,
      code: s.id,
      name: s.name,
      description: s.description,
      icon: s.icon,
    }));
  },
};
