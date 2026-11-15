import React, { useState, useEffect, useRef, useCallback } from "react";
import { Search, X, Loader } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "@tanstack/react-router";
import { getApiUrl } from "@/config/api";
import { joinUrl } from "@/utils/urlUtils";

interface SearchResult {
  type: "topic" | "chapter" | "subject" | "class";
  class_name?: string;
  subject?: string;
  chapter?: string;
  topic?: string;
  display?: string;
  priority?: number;
}

const TYPE_ORDER: SearchResult["type"][] = ["topic", "chapter", "subject", "class"];

const TYPE_META: Record<SearchResult["type"], { label: string; singular: string; accent: string; border: string; bg: string }> = {
  topic: {
    label: "Topics",
    singular: "Topic",
    accent: "text-emerald-600 font-bold",
    border: "border-emerald-500/30",
    bg: "bg-emerald-500/10",
  },
  chapter: {
    label: "Chapters",
    singular: "Chapter",
    accent: "text-amber-600 font-bold",
    border: "border-amber-500/30",
    bg: "bg-amber-500/10",
  },
  subject: {
    label: "Subjects",
    singular: "Subject",
    accent: "text-primary font-bold",
    border: "border-sky-500/30",
    bg: "bg-sky-500/10",
  },
  class: {
    label: "Classes",
    singular: "Class",
    accent: "text-violet-600 font-bold",
    border: "border-violet-500/30",
    bg: "bg-violet-500/10",
  },
};

const API_BASE = getApiUrl("");

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Shortcut key listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Fetch autocomplete suggestions
  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    setIsLoading(true);
    setActiveIndex(-1);

    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          joinUrl(API_BASE, `/api/tutor/autocomplete?q=${encodeURIComponent(query)}`)
        );
        const data = await response.json();
        const nextSuggestions = data.suggestions || data.results || [];
        setSuggestions(nextSuggestions);
        setIsOpen(Boolean(query.trim()));
      } catch (error) {
        console.error("Search error:", error);
        setSuggestions([]);
        setIsOpen(Boolean(query.trim()));
      } finally {
        setIsLoading(false);
      }
    }, 300); // Debounce 300ms

    return () => clearTimeout(timer);
  }, [query]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!isOpen || suggestions.length === 0) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setActiveIndex((prev) =>
            prev < suggestions.length - 1 ? prev + 1 : prev
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setActiveIndex((prev) => (prev > 0 ? prev - 1 : -1));
          break;
        case "Enter":
          e.preventDefault();
          if (activeIndex >= 0) {
            handleSelect(suggestions[activeIndex]);
          } else if (suggestions.length > 0) {
            handleSelect(suggestions[0]);
          } else if (query.trim()) {
            // No suggestions: navigate to tutor with a smart prompt and topic param
            setIsOpen(false);
            const topic = query.trim();
            setQuery("");
            (router as any).navigate({ to: "/tutor", search: { topic }, state: { prompt: `Explain ${topic}` } });
          }
          break;
        case "Escape":
          e.preventDefault();
          setIsOpen(false);
          break;
      }
    },
    [isOpen, suggestions, activeIndex]
  );

  const formatResultDisplay = (result: SearchResult): string => {
    if (result.type === "topic") {
      return result.topic || "";
    } else if (result.type === "chapter") {
      return result.chapter || "";
    } else if (result.type === "subject") {
      return result.subject || "";
    } else {
      return result.class_name || "";
    }
  };

  const formatResultSubtext = (result: SearchResult): string => {
    const parts: string[] = [];
    if (result.type === "topic" && result.chapter) {
      parts.push(result.chapter);
    }
    if (result.subject) parts.push(result.subject);
    if (result.class_name) parts.push(result.class_name);
    return parts.join(" • ");
  };

  const renderHighlightedText = (text: string, q: string) => {
    const value = text || "";
    const needle = q.trim();
    if (!needle) {
      return value;
    }

    const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escaped})`, "ig");
    const parts = value.split(regex);

    return parts.map((part, idx) =>
      part.toLowerCase() === needle.toLowerCase() ? (
        <mark
          key={`${part}-${idx}`}
          className="bg-primary/20 text-primary px-0.5 rounded-sm"
        >
          {part}
        </mark>
      ) : (
        <React.Fragment key={`${part}-${idx}`}>{part}</React.Fragment>
      )
    );
  };

  const handleSelect = (item: SearchResult) => {
    setIsOpen(false);
    setQuery("");

    const classMatch = (item.class_name || "").match(/\d+/);
    const classId = classMatch ? classMatch[0] : "9";

    if (item.type === "class") {
      (router as any).navigate({
        to: "/subjects/$classId",
        params: { classId },
      });
      return;
    }

    if (item.type === "subject" && item.subject) {
      (router as any).navigate({
        to: "/chapters/$classId/$subject",
        params: { classId, subject: item.subject.toLowerCase() },
      });
      return;
    }

    if (item.type === "chapter" && item.chapter) {
      const subject = (item.subject || "science").toLowerCase();
      (router as any).navigate({
        to: "/topics/$classId/$subject/$chapter",
        params: { classId, subject, chapter: item.chapter },
      });
      return;
    }

    // Navigate to tutor page with selected topic
    const params: any = {};
    if (item.subject) params.subject = item.subject;
    if (item.class_name) params.class_name = item.class_name;
    if (item.chapter) params.chapter = item.chapter;
    if (item.topic) params.topic = item.topic;

    // Also include a helpful prompt when possible
    const prompt = item.topic ? `Explain ${item.topic}` : undefined;
    (router as any).navigate({ to: "/tutor", search: params, state: prompt ? { prompt } : undefined });
  };

  const groupedSuggestions = TYPE_ORDER.map((type) => ({
    type,
    items: suggestions.filter((item) => item.type === type),
  })).filter((group) => group.items.length > 0);

  const [isMac, setIsMac] = useState(false);
  useEffect(() => {
    setIsMac(typeof window !== "undefined" && navigator.platform.toUpperCase().indexOf("MAC") >= 0);
  }, []);

  const [placeholder, setPlaceholder] = useState("Search...");
  useEffect(() => {
    const handleResize = () => {
      setPlaceholder(window.innerWidth < 640 ? "Search..." : "Search curriculum topics, subjects or formulas...");
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div className="relative w-full min-w-0 flex-1 max-w-4xl group animate-fade-in" ref={containerRef}>
      <motion.div
        animate={{ 
          scale: isOpen ? 1.01 : 1,
          y: isOpen ? -2 : 0
        }}
        className={`glass-strong rounded-full flex items-center px-3 sm:px-6 py-2.5 sm:py-3.5 gap-2 sm:gap-4 transition-all duration-300 border w-full min-w-0 ${
          isOpen
            ? "border-primary shadow-[0_0_40px_rgba(112,181,255,0.25)] bg-background"
            : "border-border hover:border-primary/40 hover:shadow-lg bg-background/60"
        }`}
      >
        <div className={`p-2 rounded-xl transition-colors ${isOpen ? "bg-primary/10" : "bg-secondary/50"} flex-shrink-0`}>
          <Search
            className={`w-5 h-5 transition-colors flex-shrink-0 ${
              isOpen ? "text-primary" : "text-muted-foreground"
            }`}
          />
        </div>
        <input
          ref={inputRef}
          placeholder={placeholder}
          className="bg-transparent outline-none flex-1 min-w-0 text-sm sm:text-base placeholder:text-muted-foreground text-foreground font-medium"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            setIsOpen(true);
            if (query && suggestions.length > 0) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />
        
        {isLoading ? (
          <Loader className="w-5 h-5 text-primary animate-spin flex-shrink-0" />
        ) : (
          <div className="flex items-center gap-3 shrink-0">
            {query && (
              <button
                onClick={() => setQuery("")}
                className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            {!isOpen && (
              <div className="hidden md:flex items-center gap-1 px-2 py-1 rounded-lg border border-border bg-secondary/50 text-[10px] font-bold text-muted-foreground">
                <span>{isMac ? "⌘" : "Ctrl"}</span>
                <span>K</span>
              </div>
            )}
          </div>
        )}
      </motion.div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.99 }}
            className="absolute top-full left-0 right-0 mt-3 glass-strong rounded-3xl border border-border/50 shadow-[0_20px_60px_rgba(0,0,0,0.15)] overflow-hidden z-[100] backdrop-blur-3xl max-h-[520px] flex flex-col"
          >
            <div className="overflow-y-auto custom-scrollbar p-2 flex-1">
              {suggestions.length > 0 ? (
                <div className="space-y-4 p-2">
                  {groupedSuggestions.map((group) => {
                    return (
                      <div key={group.type} className="space-y-1">
                        {group.items.map((item) => {
                          const currentIndex = suggestions.indexOf(item);
                          return (
                            <button
                              key={`${item.type}-${item.class_name}-${item.subject}-${item.chapter}-${item.topic}`}
                              onClick={() => handleSelect(item)}
                              onMouseEnter={() => setActiveIndex(currentIndex)}
                              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-2xl transition-all text-left ${
                                currentIndex === activeIndex
                                  ? "bg-primary/10 border border-primary/20"
                                  : "hover:bg-secondary/40 border border-transparent"
                              }`}
                            >
                              <div className="flex-1 min-w-0">
                                <p className={`text-sm font-bold truncate ${
                                  currentIndex === activeIndex ? "text-primary" : "text-foreground"
                                }`}>
                                  {renderHighlightedText(formatResultDisplay(item), query)}
                                </p>
                                <p className="text-[11px] uppercase tracking-widest text-muted-foreground font-bold mt-0.5 truncate">
                                  {renderHighlightedText(formatResultSubtext(item), query)}
                                </p>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              ) : query && !isLoading ? (
                <div className="py-12 text-center">
                  <div className="w-16 h-16 mx-auto rounded-3xl bg-secondary/50 border border-border flex items-center justify-center mb-4">
                    <Search className="w-6 h-6 text-muted-foreground opacity-50" />
                  </div>
                  <p className="text-base font-bold text-foreground">No matches found</p>
                  <p className="text-sm text-muted-foreground mt-1 max-w-[200px] mx-auto">
                    Try searching for different topics or formulas.
                  </p>
                </div>
              ) : null}
            </div>

            {suggestions.length > 0 && (
              <div className="bg-secondary/30 px-6 py-3 text-[10px] text-muted-foreground flex items-center justify-between border-t border-border/50 uppercase tracking-widest font-bold">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1"><span className="text-primary opacity-70">↑↓</span> Navigate</span>
                  <span className="flex items-center gap-1"><span className="text-primary opacity-70">↵</span> Select</span>
                </div>
                <span>{suggestions.length} Results Found</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
