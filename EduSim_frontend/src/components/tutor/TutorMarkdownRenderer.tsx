import React, { useMemo, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { BlockMath, InlineMath } from "@/components/math/Katex";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";
import { FormulaCard, parseFormulaBody } from "./FormulaCard";
import { motion, AnimatePresence } from "framer-motion";
import { 
  AlertTriangle, 
  CheckCircle2, 
  ListChecks, 
  Sparkles, 
  BookOpen, 
  FunctionSquare, 
  Search, 
  Lightbulb,
  HelpCircle,
  Compass,
  Bookmark,
  Sliders,
  Brain,
  ChevronDown
} from "lucide-react";
import "katex/dist/katex.min.css";

const ListDepthContext = React.createContext(0);

type Density = "compact" | "regular" | "spacious";
type SectionKind = 
  | "default" 
  | "concepts" 
  | "summary" 
  | "applications" 
  | "comparison" 
  | "formula" 
  | "examples" 
  | "questions"
  | "introduction"
  | "definition"
  | "characteristics";

type SectionBlock = {
  id: string;
  level: 1 | 2 | 3;
  title: string;
  kind: SectionKind;
  body: string;
};

type ComparisonGroup = {
  type: "comparison";
  id: string;
  left: SectionBlock;
  right: SectionBlock;
};

type MarkdownGroup = SectionBlock | ComparisonGroup;

interface TutorMarkdownRendererProps {
  content: string;
  className?: string;
  density?: Density;
}

const SECTION_KIND_MATCHERS: Array<{ kind: SectionKind; patterns: RegExp[] }> = [
  { kind: "introduction", patterns: [/introduction/i, /intro/i, /background/i] },
  { kind: "definition", patterns: [/definitions?/i, /what is/i, /meaning/i, /define/i] },
  { kind: "characteristics", patterns: [/characteristics?/i, /properties?/i, /features?/i] },
  { kind: "concepts", patterns: [/key concepts?/i, /concepts?/i, /core ideas?/i, /important ideas?/i] },
  { kind: "summary", patterns: [/summary/i, /key takeaways?/i, /revision/i, /recap/i] },
  { kind: "applications", patterns: [/applications?/i, /real world/i, /uses?/i, /industry usage/i] },
  { kind: "comparison", patterns: [/advantages?/i, /disadvantages?/i, /pros and cons/i, /comparison/i] },
  { kind: "formula", patterns: [/formulas?/i, /equations?/i, /mathematics?/i, /expressions?/i, /derivatives?/i, /derivation/i] },
  { kind: "examples", patterns: [
    /examples?/i, /worked examples?/i, /practice examples?/i, /illustrations?/i, /numerical/i, /solved/i,
    /problem/i, /given/i, /substitution/i, /calculation/i, /final answer/i, /interpretation/i, /step-by-step/i
  ] },
  { kind: "questions", patterns: [/questions?/i, /q&a/i, /questions & answers/i, /suggested questions/i] },
];

function slugify(text: string) {
  return text
    .toLowerCase()
    .replace(/["'`]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "section";
}

function detectSectionKind(title: string): SectionKind {
  for (const matcher of SECTION_KIND_MATCHERS) {
    if (matcher.patterns.some((pattern) => pattern.test(title))) {
      return matcher.kind;
    }
  }
  return "default";
}

function normalizeContent(content: unknown): string {
  if (content == null) return "";
  if (typeof content === "string") return content;
  if (typeof content === "number" || typeof content === "boolean") return String(content);
  if (Array.isArray(content)) {
    return content.map((item) => normalizeContent(item)).filter(Boolean).join("\n");
  }
  if (typeof content === "object") {
    const structured = content as Record<string, unknown>;
    const orderedKeys = [
      "title",
      "introduction",
      "definition",
      "keyConcepts",
      "characteristics",
      "mathematicalFormulas",
      "formulaExplanation",
      "derivation",
      "detailedExample",
      "advantagesDisadvantages",
      "applications",
      "industryUsage",
      "summary",
      "suggestedQuestions",
    ];

    const textParts = orderedKeys
      .map((key) => structured[key])
      .filter((value) => value !== undefined)
      .map((value) => normalizeContent(value))
      .filter(Boolean);

    if (textParts.length > 0) {
      return textParts.join("\n\n");
    }

    return JSON.stringify(content, null, 2);
  }
  return String(content);
}

function mergeFragmentedFormulas(text: string): string {
  const lines = text.split("\n");
  const processed: string[] = [];
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line && (line.length <= 4 || /^[=\-+−*/=<>≤≥∝()/\\_]+$/.test(line)) && !line.startsWith("#") && !line.startsWith("*")) {
      const candidates: string[] = [line];
      let j = i + 1;
      while (j < lines.length) {
        const nextLine = lines[j].trim();
        if (nextLine === "") {
          j++;
          continue;
        }
        if ((nextLine.length <= 4 || /^[=\-+−*/=<>≤≥∝()/\\_]+$/.test(nextLine)) && !nextLine.startsWith("#") && !nextLine.startsWith("*")) {
          candidates.push(nextLine);
          j++;
        } else {
          break;
        }
      }
      
      if (candidates.length >= 3) {
        let formula = candidates.join(" ");
        if (/^1\s+f\s+=\s+1\s+v\s+[−-]\s+1\s+u$/i.test(formula)) {
          formula = "\\frac{1}{f} = \\frac{1}{v} - \\frac{1}{u}";
        } else {
          formula = formula
            .replace(/(\w+)\s*[\/]\s*(\w+)/g, "\\frac{$1}{$2}")
            .replace(/−/g, "-");
        }
        processed.push(`\n\n$$\n${formula}\n$$\n\n`);
        i = j - 1;
        continue;
      }
    }
    processed.push(lines[i]);
  }
  return processed.join("\n");
}

function fixMalformedTables(text: string): string {
  const lines = text.split("\n");
  const processed: string[] = [];
  let tableLines: string[] = [];
  
  const flushTable = () => {
    if (tableLines.length === 0) return;
    const hasDelimiter = tableLines.some(line => /^[|:\s\-]+$/.test(line.trim()) && line.includes("-"));
    
    if (!hasDelimiter && tableLines.length >= 2) {
      const firstRow = tableLines[0].trim();
      const cleanRow = firstRow.replace(/^\||\|$/g, "");
      const colsCount = cleanRow.split("|").length;
      const delimiterRow = "|" + Array(colsCount).fill("---").join("|") + "|";
      tableLines.splice(1, 0, delimiterRow);
    }
    
    processed.push("");
    processed.push(...tableLines);
    processed.push("");
    tableLines = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const currentTrimmed = line.trim();
    const isTable = currentTrimmed.startsWith("|") || (currentTrimmed.split("|").length > 2);
    
    if (isTable) {
      tableLines.push(line);
    } else {
      if (tableLines.length > 0) {
        flushTable();
      }
      processed.push(line);
    }
  }
  if (tableLines.length > 0) {
    flushTable();
  }
  return processed.join("\n");
}

function sanitizeSectionBody(body: string, title: string): string {
  let cleaned = mergeFragmentedFormulas(body);
  cleaned = fixMalformedTables(cleaned);
  cleaned = cleaned.trim();

  // 1. Replace HTML line breaks and spaces/tabs
  cleaned = cleaned.replace(/<br\s*\/?>/gi, "\n");
  cleaned = cleaned.replace(/&nbsp;/gi, " ");
  cleaned = cleaned.replace(/\t/g, " ");

  // 2. Convert literal \n or \\n characters to real newlines
  cleaned = cleaned.replace(/\\n/g, "\n");

  // 3. Remove escaped quotes
  cleaned = cleaned.replace(/\\"/g, '"').replace(/\\'/g, "'");

  // 4. Clean empty lines with whitespace first
  cleaned = cleaned.replace(/^\s+$/gm, "");

  // 5. Remove standalone bullets and clean empty bullet lines
  cleaned = cleaned.replace(/^\s*[•*-]\s*$/gm, "");
  cleaned = cleaned.replace(/\n{2,}\s*[•*-]\s*\n{2,}/g, "\n");

  // 6. Deduplicate adjacent identical text lines (case-insensitive, trimmed comparison)
  const lines = cleaned.split("\n");
  const uniqueLines: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const currentTrimmed = lines[i].trim();
    if (i === 0 || currentTrimmed === "" || currentTrimmed.toLowerCase() !== lines[i - 1].trim().toLowerCase()) {
      uniqueLines.push(lines[i]);
    }
  }
  cleaned = uniqueLines.join("\n");

  // 7. Collapse spaces inside a line (preserving leading spaces for bullet indentation)
  const spaceCleanedLines = cleaned.split("\n").map(line => {
    const leadingSpaces = line.match(/^\s*/)?.[0] || "";
    const rest = line.substring(leadingSpaces.length);
    const cleanRest = rest.replace(/[ \t]{2,}/g, " ");
    return leadingSpaces + cleanRest;
  });
  cleaned = spaceCleanedLines.join("\n");

  // 8. Normalize bullet list markers (•, ●, ▪, ◦, -, +, etc.) to standard '*'
  cleaned = cleaned.replace(/^[•●▪◦]\s*/gm, "* ");
  cleaned = cleaned.replace(/^(\s*)[*•\-\+▪◦⁃‣]\s*[•\-\+▪◦⁃‣\*]?\s+/gm, "$1* ");

  // 9. Ensure bullet list items have blank lines preceding them if not already in a list block
  // Use \n before \* to only match actual line-initial bullets, NOT inline bold closings like **Title:** desc
  cleaned = cleaned.replace(/([^\n])\n(\s*\*\s+)/g, "$1\n\n$2");

  // 10. Ensure markdown headings have blank lines before them
  cleaned = cleaned.replace(/([^\n])\s*(#{1,4}\s+)/g, "$1\n\n$2");

  // 11. Sanitize math blocks (display $$ and inline $) to unescape subscripts \_ and curly braces \{ \}
  // First, display math $$
  cleaned = cleaned.replace(/\$$([\s\S]*?)\$\$/g, (match, math) => {
    const cleanMath = math
      .replace(/\\_/g, "_")
      .replace(/\\\{/g, "{")
      .replace(/\\\}/g, "}")
      .replace(/\\\\/g, "\\\\"); // Keep double backslash for aligned environments
    return `\n\n$$\n${cleanMath.trim()}\n$$\n\n`;
  });
  // Next, inline math $
  cleaned = cleaned.replace(/\$([^$\s][^$]*?[^$\s])\$/g, (match, math) => {
    const cleanMath = math
      .replace(/\\_/g, "_")
      .replace(/\\\{/g, "{")
      .replace(/\\\}/g, "}");
    return `$${cleanMath}$`;
  });

  // 12. Remove duplicate line breaks
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");

  // 13. Strip markdown heading syntax and bold headers from body content completely (excluding solved numerical steps)
  cleaned = cleaned.split("\n").map(line => {
    const trimmed = line.trim();
    const boldMatch = trimmed.match(/^\*\*(.*?)\*\*$/);
    if (boldMatch) {
      const text = boldMatch[1].trim().replace(/[:\-–—]$/, "").trim();
      const isExampleStep = /^(problem|given|formula|substitution|calculation|final answer|interpretation)$/i.test(text);
      if (!isExampleStep) {
        return "";
      }
    }
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const text = headingMatch[2].trim().replace(/\*+/g, "").replace(/[:\-–—]$/, "").trim();
      const isExampleStep = /^(problem|given|formula|substitution|calculation|final answer|interpretation)$/i.test(text);
      if (!isExampleStep) {
        return "";
      }
    }
    return line;
  }).join("\n").trim();

  // 14. Remove duplicate title or subsection lines anywhere in the body
  let cleanTitle = title.replace(/\*+/g, "").trim();
  if (cleanTitle) {
    const escapedTitle = cleanTitle.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
    cleaned = cleaned.replace(new RegExp(`^\\s*(?:#{1,6}|\\*\\*?|[-*•]\\s*)?\\s*${escapedTitle}\\s*(?:\\*\\*?)?\\s*[:\\-–—]?\\s*$`, "gim"), "");
  }

  return cleaned.trim();
}

function splitIntoSections(content: unknown): SectionBlock[] {
  const normalizedContent = normalizeContent(content);
  if (!normalizedContent.trim()) {
    return [];
  }

  const lines = normalizedContent.replace(/\r\n/g, "\n").split("\n");
  const sections: SectionBlock[] = [];
  let currentTitle = "";
  let currentLevel: 1 | 2 | 3 = 2;
  let currentBody: string[] = [];
  let currentKind: SectionKind = "default";

  const flush = () => {
    const body = currentBody.join("\n").trim();
    if (!currentTitle && !body) {
      currentBody = [];
      return;
    }

    const cleanedBody = sanitizeSectionBody(body, currentTitle);

    // Skip empty parent H1 sections or duplicate empty headers to prevent empty cards/accordions
    if (cleanedBody === "" && currentLevel === 1) {
      currentBody = [];
      return;
    }

    if (!currentTitle && cleanedBody === "") {
      currentBody = [];
      return;
    }

    sections.push({
      id: currentTitle ? slugify(currentTitle) : `body-${sections.length + 1}`,
      level: currentLevel,
      title: currentTitle,
      kind: currentKind,
      body: cleanedBody,
    });

    currentBody = [];
  };

  for (const line of lines) {
    // Match standard markdown headings H1 and H2 only (to keep H3 sub-steps like ### Problem inline)
    const headingMatch = line.match(/^(#{1,2})\s+(.+)$/);
    let matchedTitle = "";
    let matchedLevel: 1 | 2 | 3 = 2;

    if (headingMatch) {
      matchedLevel = headingMatch[1].length as 1 | 2 | 3;
      matchedTitle = headingMatch[2].trim().replace(/\*+/g, "").replace(/[:\-–—]$/, "").trim();
    } else {
      // Match bold titles like "**Definition**", "**Definition:**", etc.
      const boldMatch = line.match(/^\s*\*\*(?:\s*#\s*)?([^*]+?)\*\*\s*[:\-–—]?\s*$/);
      if (boldMatch) {
        const potentialTitle = boldMatch[1].trim().replace(/[:\-–—]$/, "").trim();
        const isExampleStep = /^(problem|given|formula|substitution|calculation|final answer|interpretation)$/i.test(potentialTitle);
        const wordCount = potentialTitle.split(/\s+/).length;
        if (wordCount <= 4 && !isExampleStep) {
          matchedTitle = potentialTitle;
          matchedLevel = 2;
        }
      }
    }

    if (matchedTitle) {
      // Ensure we don't split on example steps like "Problem", "Given", etc.
      const isExampleStep = /^(problem|given|formula|substitution|calculation|final answer|interpretation)$/i.test(matchedTitle);
      if (!isExampleStep) {
        flush();
        currentLevel = matchedLevel;
        currentTitle = matchedTitle;
        currentKind = detectSectionKind(currentTitle);
        continue;
      }
    }

    currentBody.push(line);
  }

  flush();

  return sections.length > 0 ? sections : [{ id: "body-1", level: 2, title: "", kind: "default", body: normalizedContent }];
}

function isComparisonPair(left: SectionBlock, right: SectionBlock) {
  const leftTitle = left.title.toLowerCase();
  const rightTitle = right.title.toLowerCase();
  const leftAdvantages = /advantages?/.test(leftTitle);
  const rightAdvantages = /advantages?/.test(rightTitle);
  const leftDisadvantages = /disadvantages?/.test(leftTitle);
  const rightDisadvantages = /disadvantages?/.test(rightTitle);

  return (leftAdvantages && rightDisadvantages) || (leftDisadvantages && rightAdvantages);
}

function groupSections(sections: SectionBlock[]): MarkdownGroup[] {
  const groups: MarkdownGroup[] = [];

  for (let index = 0; index < sections.length; index += 1) {
    const current = sections[index];
    const next = sections[index + 1];

    if (current.title && next?.title && isComparisonPair(current, next)) {
      groups.push({
        type: "comparison",
        id: `${current.id}-${next.id}`,
        left: current,
        right: next,
      });
      index += 1;
      continue;
    }

    groups.push(current);
  }

  return groups;
}

function flattenText(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(flattenText).join(" ");
  if (React.isValidElement(node)) return flattenText((node.props as any).children);
  return "";
}

function hasMath(text: string): boolean {
  return /[$]/.test(text);
}

function countWords(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function listItemTexts(children: React.ReactNode) {
  return React.Children.toArray(children)
    .map((child) => flattenText(child).replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function getSectionIcon(kind: SectionKind) {
  switch (kind) {
    case "introduction":
      return <Compass className="w-5 h-5 text-sky-500" />;
    case "definition":
      return <Bookmark className="w-5 h-5 text-indigo-500" />;
    case "concepts":
      return <Brain className="w-5 h-5 text-purple-500" />;
    case "characteristics":
      return <Sliders className="w-5 h-5 text-pink-500" />;
    case "formula":
      return <FunctionSquare className="w-5 h-5 text-violet-500" />;
    case "applications":
      return <Sparkles className="w-5 h-5 text-emerald-500" />;
    case "summary":
      return <CheckCircle2 className="w-5 h-5 text-amber-500" />;
    case "questions":
      return <HelpCircle className="w-5 h-5 text-teal-500" />;
    case "examples":
      return <BookOpen className="w-5 h-5 text-orange-500" />;
    default:
      return <Sparkles className="w-5 h-5 text-slate-400" />;
  }
}

function getSectionColorClasses(kind: SectionKind): { border: string; bg: string; text: string } {
  switch (kind) {
    case "introduction":
      return { border: "border-l-sky-500", bg: "bg-sky-500/5", text: "text-sky-600 dark:text-sky-300" };
    case "definition":
      return { border: "border-l-indigo-500", bg: "bg-indigo-500/5", text: "text-indigo-600 dark:text-indigo-300" };
    case "concepts":
      return { border: "border-l-purple-500", bg: "bg-purple-500/5", text: "text-purple-600 dark:text-purple-300" };
    case "characteristics":
      return { border: "border-l-pink-500", bg: "bg-pink-500/5", text: "text-pink-600 dark:text-pink-300" };
    case "formula":
      return { border: "border-l-violet-500", bg: "bg-violet-500/5", text: "text-violet-600 dark:text-violet-300" };
    case "applications":
      return { border: "border-l-emerald-500", bg: "bg-emerald-500/5", text: "text-emerald-600 dark:text-emerald-300" };
    case "summary":
      return { border: "border-l-amber-500", bg: "bg-amber-500/5", text: "text-amber-600 dark:text-amber-300" };
    case "questions":
      return { border: "border-l-teal-500", bg: "bg-teal-500/5", text: "text-teal-600 dark:text-teal-300" };
    case "examples":
      return { border: "border-l-orange-500", bg: "bg-orange-500/5", text: "text-orange-600 dark:text-orange-300" };
    default:
      return { border: "border-l-slate-400 dark:border-l-slate-600", bg: "bg-slate-500/5", text: "text-slate-600 dark:text-slate-350" };
  }
}

function renderMarkdownBody(body: string, sectionKind: SectionKind, density: Density, isDark: boolean) {
  const Ul = ({ children }: any) => {
      const depth = React.useContext(ListDepthContext);
      const items = React.Children.toArray(children);
      const texts = listItemTexts(children);
      
      const isChipList = depth === 0 && (sectionKind === "concepts" || (texts.length > 0 && texts.length <= 8 && texts.every((text) => countWords(text) <= 4 && text.length <= 32)));
      const isSummaryList = depth === 0 && (sectionKind === "summary" || texts.some((text) => /^([✓✔-]|\d+\.)/.test(text)));
      const isApplicationList = depth === 0 && sectionKind === "applications";
      const isExampleList = depth === 0 && sectionKind === "examples";
 
      if (isChipList) {
        return (
          <div className="my-3 flex flex-wrap gap-2">
            {texts.map((text) => (
              <span
                key={text}
                className="inline-flex items-center rounded-xl border border-primary/10 bg-secondary/50 px-3 py-1.5 text-xs font-semibold text-foreground/90 shadow-sm hover:scale-[1.02] hover:border-primary/30 transition-all duration-200"
              >
                {text.replace(/^[-•✓✔]\s*/, "")}
              </span>
            ))}
          </div>
        );
      }
 
      if (isApplicationList || isExampleList) {
        const icon = isApplicationList
          ? <Sparkles className="h-4 w-4 text-emerald-500" />
          : <BookOpen className="h-4 w-4 text-orange-500" />;
        const hoverAccent = isApplicationList
          ? "hover:border-emerald-500/30 hover:bg-emerald-500/[0.02]"
          : "hover:border-orange-500/30 hover:bg-orange-500/[0.02]";
 
        return (
          <div className="my-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {texts.map((text, index) => (
              <div
                key={`${text}-${index}`}
                className={cn(
                  "group flex items-start gap-3 rounded-2xl border border-border/50 bg-secondary/20 px-4 py-3.5 transition-all duration-300 shadow-sm",
                  hoverAccent
                )}
              >
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-background border border-border/30 shadow-sm">
                  {icon}
                </div>
                <div className="text-[13px] leading-relaxed text-foreground/80 group-hover:text-foreground transition-colors">
                  {text.replace(/^[-•✓✔]\s*/, "")}
                </div>
              </div>
            ))}
          </div>
        );
      }
 
      if (isSummaryList) {
        const accentClasses = "border-amber-500/10 bg-amber-500/[0.01] hover:border-amber-500/30 hover:bg-amber-500/[0.02] text-foreground";
        const icon = <CheckCircle2 className="h-4 w-4 text-amber-500" />;
 
        return (
          <div className="my-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {texts.map((text, index) => (
              <div key={`${text}-${index}`} className={cn("rounded-2xl border px-4 py-3.5 shadow-sm transition-all duration-300", accentClasses)}>
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-background shadow-sm">
                    {icon}
                  </div>
                  <div className="min-w-0 text-sm leading-relaxed text-foreground/80">{text.replace(/^[-•✓✔]\s*/, "")}</div>
                </div>
              </div>
            ))}
          </div>
        );
      }
 
      return (
        <ListDepthContext.Provider value={depth + 1}>
          <ul className={cn("space-y-2 list-none pl-0", depth > 0 ? "pl-5 mt-2" : "my-3")}>
            {children}
          </ul>
        </ListDepthContext.Provider>
      );
  };
  const Ol = ({ children }: any) => {
      const depth = React.useContext(ListDepthContext);
      return (
        <ListDepthContext.Provider value={depth + 1}>
          <ol className={cn("space-y-2 list-decimal", depth > 0 ? "pl-5 mt-2" : "my-3 pl-5")}>
            {children}
          </ol>
        </ListDepthContext.Provider>
      );
  };
  const Li = ({ children }: any) => {
      const depth = React.useContext(ListDepthContext);
      
      if (depth > 1) {
        return (
          <li className="relative pl-5 text-xs sm:text-sm leading-relaxed text-foreground/80! font-normal my-1">
            <span className="absolute left-0 top-1.5 flex h-1.5 w-1.5 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-background" />
            <span className="min-w-0 flex-1">{children}</span>
          </li>
        );
      }
 
      return (
        <li className="relative flex gap-2.5 rounded-2xl border border-border/40 bg-card px-4 py-3 text-xs sm:text-sm leading-relaxed text-foreground/80! shadow-sm transition-all hover:border-primary/20 hover:bg-secondary/40 my-2">
          <span className="mt-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[8px] font-bold text-primary">
            •
          </span>
          <span className="min-w-0 flex-1 font-medium">{children}</span>
        </li>
      );
  };

  const components: Components & { math?: any; inlineMath?: any } = {
    h1: ({ children }) => (
      <h1
        id={slugify(flattenText(children))}
        className="scroll-mt-28 text-base font-bold text-foreground! mt-4 mb-2"
      >
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2
        id={slugify(flattenText(children))}
        className="scroll-mt-28 text-sm font-semibold text-foreground/80! mt-3 mb-1.5"
      >
        {children}
      </h2>
    ),
    h3: ({ children }) => {
      const text = flattenText(children).trim();
      const isExampleStep = /^(problem|given|formula|substitution|calculation|final answer|interpretation)$/i.test(text);
      if (isExampleStep) {
        return (
          <div className="mt-4 mb-2">
            <span className="inline-flex items-center rounded-lg bg-primary/10 border border-primary/20 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-primary shadow-sm">
              {text}
            </span>
          </div>
        );
      }
      return (
        <h3 className="text-xs font-bold text-foreground/70! mt-4 mb-2 uppercase tracking-wider">
          {children}
        </h3>
      );
    },
    p: ({ children }) => {
      return (
        <p className={cn(
          "text-foreground/80! dark:text-foreground/90! text-sm sm:text-[15px] leading-relaxed w-full font-normal max-w-[85ch]",
          density === "compact" ? "mb-1.5" : "mb-3"
        )}>
          {children}
        </p>
      );
    },
    strong: ({ children }) => <strong className="font-bold text-foreground!">{children}</strong>,
    a: ({ children, href }) => (
      <a href={href} className="font-semibold text-primary underline decoration-primary/30 underline-offset-4 transition-colors hover:decoration-primary">
        {children}
      </a>
    ),
    hr: () => <hr className="my-4 border-border/40" />,
    blockquote: ({ children }) => {
      return (
        <div className="my-3.5 rounded-2xl border border-primary/20 bg-secondary/40 px-5 py-4 shadow-sm">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground/80">
            <Lightbulb className="h-4.5 w-4.5 text-primary" />
            <span>Callout</span>
          </div>
          <div className="space-y-1.5 text-sm leading-relaxed text-foreground/90">{children}</div>
        </div>
      );
    },
    ul: Ul,
    ol: Ol,
    li: Li,
    table: ({ children }) => (
      <div className="my-4 overflow-hidden rounded-2xl border border-border/40 bg-card/30 shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-[13px] sm:text-sm">{children}</table>
        </div>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-secondary/60 border-b border-border/60">{children}</thead>,
    tbody: ({ children }) => <tbody className="divide-y divide-border/30">{children}</tbody>,
    tr: ({ children }) => <tr className="transition-colors hover:bg-secondary/10 even:bg-secondary/5">{children}</tr>,
    th: ({ children }) => (
      <th className="px-5 py-3 font-bold uppercase tracking-wider text-muted-foreground! text-[10px] sm:text-[11px] border-b border-border/40">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="px-5 py-3 align-middle text-foreground/80! leading-relaxed">
        {children}
      </td>
    ),
    code: (props: any) => {
      const { inline, children } = props;
      if (inline) {
        return (
          <code className="rounded-md border border-primary/15 bg-primary/8 px-1.5 py-0.5 font-mono text-[0.92em] font-semibold text-primary">
            {children}
          </code>
        );
      }
 
      return (
        <code className="block overflow-x-auto rounded-2xl border border-border/40 bg-secondary/35 px-4 py-3.5 font-mono text-[13px] leading-relaxed text-foreground shadow-inner">
          {children}
        </code>
      );
    },
    math: (props: any) => <BlockMath math={String(props.value || props.children || "").trim()} />,
    inlineMath: (props: any) => <InlineMath math={String(props.value || props.children || "").trim()} />,
    pre: ({ children }: any) => <div className="my-4 overflow-hidden rounded-2xl border border-border bg-secondary/40 shadow-md">{children}</div>,
  };

  let preprocessedBody = body;
  preprocessedBody = preprocessedBody.replace(/a = v\.e \/ l\.m/g, 'a = \\frac{v \\cdot e}{l \\cdot m}');
  preprocessedBody = preprocessedBody.replace(/v\.e/g, 'v \\cdot e');
  preprocessedBody = preprocessedBody.replace(/l\.m/g, 'l \\cdot m');

  return (
    <div
      className={cn(
        "tutor-markdown prose prose-slate max-w-none w-full",
        isDark && "prose-invert",
        density === "compact" && "prose-p:mb-2.5",
        density === "spacious" && "prose-p:mb-4.5",
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
        {preprocessedBody}
      </ReactMarkdown>
    </div>
  );
}

function ComparisonCard({ group, density, isDark }: { group: ComparisonGroup; density: Density; isDark: boolean }) {
  const leftLabel = group.left.title;
  const rightLabel = group.right.title;

  return (
    <div className="w-full rounded-2xl border border-border/40 bg-card p-4 sm:p-5 shadow-sm transition-all duration-200">
      <div className="grid gap-5 md:grid-cols-2">
        {[{ label: leftLabel, section: group.left }, { label: rightLabel, section: group.right }].map(({ label, section }) => {
          const isDisadvantage = section.title.toLowerCase().includes("disadv") || label.toLowerCase().includes("disadv");
          return (
            <div
              key={section.id}
              className={cn(
                "rounded-2xl border p-4 sm:p-5 shadow-sm transition-all duration-200 hover:scale-[1.01]",
                isDisadvantage
                  ? "border-rose-500/20 bg-rose-500/[0.02] hover:border-rose-500/35"
                  : "border-emerald-500/20 bg-emerald-500/[0.02] hover:border-emerald-500/35",
              )}
            >
              <div className={cn(
                "mb-3 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5",
                isDisadvantage ? "text-rose-500" : "text-emerald-600 dark:text-emerald-400"
              )}>
                {isDisadvantage ? <AlertTriangle className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                <span>{label}</span>
              </div>
              <div className={cn("space-y-1.5", isDark && "prose-invert")}>
                {renderMarkdownBody(section.body, section.kind, density, isDark)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function getGroupKey(item: MarkdownGroup, index: number): string {
  if ("type" in item) {
    return "group5"; // comparison group goes to Applications/Comparison
  }
  
  const kind = item.kind;
  if (kind === "introduction" || kind === "definition" || kind === "concepts") {
    return "group1";
  }
  if (kind === "characteristics") {
    return "group2";
  }
  if (kind === "formula") {
    return "group3";
  }
  if (kind === "examples") {
    return "group4";
  }
  if (kind === "applications") {
    return "group5";
  }
  if (kind === "summary") {
    return "group6";
  }
  if (kind === "questions") {
    return "questions";
  }
  
  return "group1"; // Fallback to group1 (Introduction) instead of "default"
}

function getGroupForKey(key: string) {
  switch (key) {
    case "group1":
      return {
        title: "Introduction",
        icon: <Compass className="w-5 h-5 text-sky-500" />,
        border: "border-l-sky-500",
        text: "text-sky-600 dark:text-sky-300",
        isStandalone: false,
      };
    case "group2":
      return {
        title: "Characteristics",
        icon: <Sliders className="w-5 h-5 text-pink-500" />,
        border: "border-l-pink-500",
        text: "text-pink-600 dark:text-pink-300",
        isStandalone: false,
      };
    case "group3":
      return {
        title: "Formula",
        icon: <FunctionSquare className="w-5 h-5 text-violet-500" />,
        border: "border-l-violet-500",
        text: "text-violet-600 dark:text-violet-300",
        isStandalone: false,
      };
    case "group4":
      return {
        title: "Example",
        icon: <BookOpen className="w-5 h-5 text-orange-500" />,
        border: "border-l-orange-500",
        text: "text-orange-600 dark:text-orange-300",
        isStandalone: false,
      };
    case "group5":
      return {
        title: "Applications",
        icon: <Sparkles className="w-5 h-5 text-emerald-500" />,
        border: "border-l-emerald-500",
        text: "text-emerald-600 dark:text-emerald-300",
        isStandalone: false,
      };
    case "group6":
      return {
        title: "Summary",
        icon: <CheckCircle2 className="w-5 h-5 text-amber-500" />,
        border: "border-l-amber-500",
        text: "text-amber-600 dark:text-amber-300",
        isStandalone: false,
      };
    case "questions":
      return {
        title: "Suggested Questions",
        icon: <HelpCircle className="w-5 h-5 text-teal-500" />,
        border: "border-l-teal-500",
        text: "text-teal-600 dark:text-teal-300",
        isStandalone: true,
      };
    default:
      return {
        title: "Introduction",
        icon: <Compass className="w-5 h-5 text-sky-500" />,
        border: "border-l-sky-500",
        text: "text-sky-600 dark:text-sky-300",
        isStandalone: false,
      };
  }
}

function AccordionGroup({
  groupKey,
  title,
  icon,
  borderClass,
  textClass,
  items,
  isExpanded,
  onToggle,
  density,
  isDark,
  parentContent
}: {
  groupKey: string;
  title: string;
  icon: React.ReactNode;
  borderClass: string;
  textClass: string;
  items: MarkdownGroup[];
  isExpanded: boolean;
  onToggle: () => void;
  density: Density;
  isDark: boolean;
  parentContent: string;
}) {
  let hasRenderedFormulaCard = false;

  return (
    <div className={cn(
      "w-full rounded-[2rem] border border-border/40 bg-card/60 shadow-sm overflow-hidden transition-all duration-300 border-l-4",
      borderClass,
      isExpanded ? "shadow-md" : ""
    )}>
      {/* Accordion Header */}
      <div 
        onClick={onToggle}
        className="flex items-center justify-between p-5 sm:p-6 cursor-pointer select-none hover:bg-secondary/20 transition-colors"
      >
        <div className="flex items-center gap-3.5">
          <div className="p-2 rounded-xl bg-background border border-border/30 shadow-sm flex items-center justify-center">
            {icon}
          </div>
          <h2 className={cn("text-base sm:text-[17px] font-extrabold tracking-tight", textClass)}>
            {title}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-widest bg-secondary/50 px-2.5 py-1 rounded-lg border border-border/30">
            {items.length} {items.length === 1 ? "Section" : "Sections"}
          </span>
          <ChevronDown className={cn(
            "w-5 h-5 text-muted-foreground transition-transform duration-300",
            isExpanded ? "rotate-180" : ""
          )} />
        </div>
      </div>

      {/* Accordion Content */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
          >
            <div className="border-t border-border/30 p-4 sm:p-5 space-y-4 bg-secondary/[0.03]">
              {items.map((item, idx) => {
                if ("type" in item) {
                  return <ComparisonCard key={item.id} group={item} density={density} isDark={isDark} />;
                }

                const colorClasses = getSectionColorClasses(item.kind);
                const sectionIcon = getSectionIcon(item.kind);
                const displayTitle = item.title || "Context";
                const showSubheading = item.title && item.level > 1;

                if (item.kind === "formula") {
                  const formulaData = parseFormulaBody(item.body, item.title);
                  let remainingBody = item.body;
                  
                  if (formulaData.formula) {
                    const escapedFormula = formulaData.formula.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
                    const mathBlockRegex = new RegExp(`\\$\\$\\s*${escapedFormula}\\s*\\$\\$\\n*`, 'g');
                    remainingBody = remainingBody.replace(mathBlockRegex, '');
                    
                    const inlineRegex = new RegExp(`\\$${escapedFormula}\\$\\n*`, 'g');
                    remainingBody = remainingBody.replace(inlineRegex, '');
                  }
                  
                  remainingBody = remainingBody.replace(/^(?:\*\*)?where\s*:?\s*(?:\*\*)?[\s\S]*?(?=\n\n|\n[#*]|$)/im, '').trim();

                  const shouldRenderCard = !hasRenderedFormulaCard && formulaData.formula;
                  if (shouldRenderCard) {
                    hasRenderedFormulaCard = true;
                  }

                  return (
                    <div key={item.id} className="space-y-4">
                      {showSubheading && (
                        <div className="flex items-center gap-2.5">
                          <div className="p-1.5 rounded-lg bg-violet-500/10 text-violet-500">
                            {sectionIcon}
                          </div>
                          <h3 className="text-sm font-bold uppercase tracking-wider text-violet-600 dark:text-violet-400">
                            {displayTitle}
                          </h3>
                        </div>
                      )}
                      {shouldRenderCard && (
                        <FormulaCard body={item.body} sectionTitle={item.title} parentContent={parentContent} />
                      )}
                      {remainingBody.trim() && (
                        <div className={cn(showSubheading ? "pl-0 sm:pl-6" : "pl-0")}>
                          {renderMarkdownBody(remainingBody, item.kind, density, isDark)}
                        </div>
                      )}
                    </div>
                  );
                }

                return (
                  <div key={item.id} className="space-y-2 pb-4 border-b border-border/20 last:border-none last:pb-0">
                    {showSubheading && (
                      <div className="flex items-center gap-2.5">
                        <div className="p-1.5 rounded-lg bg-background border border-border/30 shadow-sm flex items-center justify-center">
                          {sectionIcon}
                        </div>
                        <h3 className={cn("text-[15px] font-bold tracking-tight", colorClasses.text)}>
                          {displayTitle}
                        </h3>
                      </div>
                    )}
                    <div className={cn(showSubheading ? "pl-0 sm:pl-6" : "pl-0")}>
                      {renderMarkdownBody(item.body, item.kind, density, isDark)}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StandaloneCard({
  groupKey,
  title,
  icon,
  borderClass,
  textClass,
  items,
  density,
  isDark,
  parentContent
}: {
  groupKey: string;
  title: string;
  icon: React.ReactNode;
  borderClass: string;
  textClass: string;
  items: MarkdownGroup[];
  density: Density;
  isDark: boolean;
  parentContent: string;
}) {
  return (
    <div className={cn(
      "w-full rounded-[2rem] border border-border/40 bg-card/60 p-5 sm:p-6 shadow-sm border-l-4 transition-all duration-300 hover:shadow-md",
      borderClass
    )}>
      <div className="mb-4 flex items-center gap-3.5">
        <div className="p-2 rounded-xl bg-background border border-border/30 shadow-sm flex items-center justify-center">
          {icon}
        </div>
        <h2 className={cn("text-base sm:text-[17px] font-extrabold tracking-tight", textClass)}>
          {title}
        </h2>
      </div>
      <div className="space-y-4">
        {items.map((item) => {
          if ("type" in item) {
            return <ComparisonCard key={item.id} group={item} density={density} isDark={isDark} />;
          }

          const sectionIcon = getSectionIcon(item.kind);
          const colorClasses = getSectionColorClasses(item.kind);
          const showSubheading = item.title && item.level > 1;

          return (
            <div key={item.id} className="space-y-2 pb-4 border-b border-border/20 last:border-none last:pb-0">
              {showSubheading && (
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg bg-background border border-border/30 shadow-sm flex items-center justify-center">
                    {sectionIcon}
                  </div>
                  <h3 className={cn("text-[15px] font-bold tracking-tight", colorClasses.text)}>
                    {item.title}
                  </h3>
                </div>
              )}
              <div className={cn(showSubheading ? "pl-0 sm:pl-6" : "pl-0")}>
                {renderMarkdownBody(item.body, item.kind, density, isDark)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function TutorMarkdownRenderer({ content, className, density = "regular" }: TutorMarkdownRendererProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  // Check for the warning message
  const hasWarning = useMemo(() => {
    return content.includes("This topic is not available in the provided textbook context");
  }, [content]);

  // Clean content to remove the warning message so it doesn't render inside the card
  const cleanedContent = useMemo(() => {
    let temp = content;
    // Remove the warning lines and double newlines
    temp = temp.replace(/This topic is not available in the provided textbook context\.?\n*/gi, "");
    temp = temp.replace(/The following explanation is AI-generated and may not exactly match your textbook\.?\n*/gi, "");
    return temp.trim();
  }, [content]);

  const normalizedStr = useMemo(() => normalizeContent(cleanedContent), [cleanedContent]);
  const rawGroups = useMemo(() => groupSections(splitIntoSections(normalizedStr)), [normalizedStr]);

  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({ group1: true });

  const toggleGroup = (key: string) => {
    setExpandedGroups(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const groupedData = useMemo(() => {
    const buckets: Record<string, MarkdownGroup[]> = {
      group1: [],
      group2: [],
      group3: [],
      group4: [],
      group5: [],
      group6: [],
      questions: [],
    };

    rawGroups.forEach((item, index) => {
      const key = getGroupKey(item, index);
      if (!buckets[key]) {
        buckets[key] = [];
      }
      buckets[key].push(item);
    });

    return buckets;
  }, [rawGroups]);

  if (!normalizedStr.trim()) {
    if (hasWarning) {
      return (
        <div className={cn("space-y-6 max-w-4xl mx-auto w-full", className)}>
          <div className="flex gap-3.5 p-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 text-amber-600 dark:text-amber-400">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="text-xs sm:text-sm leading-relaxed">
              <p className="font-extrabold tracking-tight">Textbook Context Unavailable</p>
              <p className="text-muted-foreground mt-0.5">
                This topic is not available in the provided textbook. The following explanation is AI-generated and may not exactly match your textbook.
              </p>
            </div>
          </div>
        </div>
      );
    }
    return null;
  }

  const groupKeys = ["group1", "group2", "group3", "group4", "group5", "group6", "questions"];

  return (
    <div className={cn("space-y-6 max-w-4xl mx-auto w-full", className)}>
      {hasWarning && (
        <div className="flex gap-3.5 p-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 text-amber-600 dark:text-amber-400">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-xs sm:text-sm leading-relaxed">
            <p className="font-extrabold tracking-tight">Textbook Context Unavailable</p>
            <p className="text-muted-foreground mt-0.5">
              This topic is not available in the provided textbook. The following explanation is AI-generated and may not exactly match your textbook.
            </p>
          </div>
        </div>
      )}
      {groupKeys.map((key) => {
        const items = groupedData[key] || [];
        const validItems = items.filter(item => {
          if ("type" in item) return true;
          return item.body?.trim()?.length > 0;
        });

        if (validItems.length === 0) return null;

        const groupMeta = getGroupForKey(key);

        if (groupMeta.isStandalone) {
          return (
            <StandaloneCard
              key={key}
              groupKey={key}
              title={groupMeta.title}
              icon={groupMeta.icon}
              borderClass={groupMeta.border}
              textClass={groupMeta.text}
              items={validItems}
              density={density}
              isDark={isDark}
              parentContent={normalizedStr}
            />
          );
        }

        return (
          <AccordionGroup
            key={key}
            groupKey={key}
            title={groupMeta.title}
            icon={groupMeta.icon}
            borderClass={groupMeta.border}
            textClass={groupMeta.text}
            items={validItems}
            isExpanded={!!expandedGroups[key]}
            onToggle={() => toggleGroup(key)}
            density={density}
            isDark={isDark}
            parentContent={normalizedStr}
          />
        );
      })}

      <style>{`
        .tutor-markdown .katex-display {
          margin: 1.25rem 0;
          padding: 1.25rem;
          background: rgba(120, 119, 198, 0.05);
          border: 1px solid rgba(120, 119, 198, 0.12);
          border-radius: 1.25rem;
          overflow-x: auto;
          overflow-y: hidden;
          width: 100%;
          text-align: center;
          box-shadow: inset 0 2px 4px 0 rgba(0,0,0,0.02);
        }
        .tutor-markdown .katex {
          font-size: 1.05em;
          white-space: nowrap;
        }
        .tutor-markdown blockquote {
          margin: 1rem 0;
        }
      `}</style>
    </div>
  );
}