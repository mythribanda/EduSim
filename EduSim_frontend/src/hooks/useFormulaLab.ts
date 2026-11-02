import { useCallback, useState, useEffect } from "react";
import { physicsSimulationApi } from "@/services/physicsSimulationApi";
import { DynamicFormulaExtractor, DynamicParsedFormula } from "@/utils/DynamicFormulaExtractor";

interface LoadParams {
  topic: string;
  classId?: string;
  subject?: string;
  chapter?: string;
  ragContent?: string;
  formulaExpression?: string;
  formulaMeaning?: string;
}

import { getApiUrl } from "@/config/api";
import { FormulaControl } from "@/utils/DynamicFormulaExtractor";

export function useFormulaLab() {
  const [formulas, setFormulas] = useState<DynamicParsedFormula[] | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const loadForTopic = useCallback(
    async (params: LoadParams) => {
      if (params.topic === "new" || !params.topic) {
        setFormulas([]);
        return;
      }

      let contentHash = "";
      if (params.ragContent) {
        let hash = 0;
        for (let i = 0; i < params.ragContent.length; i++) {
          const char = params.ragContent.charCodeAt(i);
          hash = (hash << 5) - hash + char;
          hash = hash & hash;
        }
        contentHash = Math.abs(hash).toString(36);
      }
      const cacheKey = `formula-lab-v6:${params.topic}-${params.classId || ""}-${params.subject || ""}-${params.chapter || ""}-${contentHash}`;

      let parsed: DynamicParsedFormula[] = [];
      const cached = typeof window !== "undefined" ? window.localStorage.getItem(cacheKey) : null;
      if (cached) {
        try {
          parsed = JSON.parse(cached);
        } catch {
          // ignore cache parse failures
        }
      }

      if (!parsed || parsed.length === 0) {
        setFormulas(null);

        let rag = params.ragContent || null;
        if (!rag) {
          const response = await physicsSimulationApi.searchRag(
            params.topic,
            params.subject,
            params.chapter || ""
          );
          if (response.success && response.data?.chunks) {
            rag = response.data.chunks.map((c: any) => c.text).join("\n\n");
          } else {
            rag = "";
          }
        }

        parsed = await DynamicFormulaExtractor.parseTutorResponse(
          rag || "",
          params.topic,
          params.subject,
          params.classId,
        );

        if ((!parsed || parsed.length === 0) && params.topic.includes("=")) {
          parsed = await DynamicFormulaExtractor.parseTutorResponse(
            params.topic,
            params.topic,
            params.subject,
            params.classId,
          );
        }
      }

      // Check if we have a custom formula passed via route/search parameters
      if (params.formulaExpression) {
        const cleanCustom = params.formulaExpression.replace(/\s+/g, "");
        const formulaExists = parsed.some(
          (f) =>
            (f.raw && f.raw.replace(/\s+/g, "") === cleanCustom) ||
            (f.formula && f.formula.replace(/\s+/g, "") === cleanCustom) ||
            (f.expression && f.expression.replace(/\s+/g, "") === cleanCustom)
        );

        if (!formulaExists) {
          try {
            let labData: any = null;
            const labRes = await fetch(getApiUrl("/api/formula/lab"), {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ formula: params.formulaExpression })
            });
            if (labRes.ok) {
              labData = await labRes.json();
            }

            let uniqueControls: FormulaControl[] = [];
            const seenVars = new Set<string>();
            for (const v of (labData?.variables || [])) {
              if (!seenVars.has(v.symbol)) {
                seenVars.add(v.symbol);
                uniqueControls.push({
                  symbol: v.symbol,
                  label: v.label || v.symbol,
                  unit: v.unit || "",
                  min: v.min ?? 1,
                  max: v.max ?? 100,
                  step: v.step ?? 1,
                  defaultValue: v.defaultValue ?? 10
                });
              }
            }

            const customFormula: DynamicParsedFormula = {
              id: `custom-${cleanCustom}`,
              raw: params.formulaExpression,
              expression: params.formulaExpression,
              latex: params.formulaExpression,
              formula: params.formulaExpression,
              displayFormula: params.formulaExpression,
              title: params.formulaMeaning || "Key Equation",
              description: labData?.description || params.formulaMeaning || "Formula from lesson",
              category: "Custom",
              controls: uniqueControls,
              variables: uniqueControls,
              anatomy: labData?.anatomy || [],
              examples: labData?.examples || [],
              practiceQuestions: labData?.practiceQuestions || [],
              revisionCards: labData?.revisionCards || []
            };

            parsed = [customFormula, ...parsed];
          } catch (err) {
            console.error("Failed to load details for passed formula:", err);
          }
        }
      }

      // Find the index of the formula to select
      let activeIndex = 0;
      if (params.formulaExpression) {
        const cleanCustom = params.formulaExpression.replace(/\s+/g, "");
        const matchIdx = parsed.findIndex(
          (f) =>
            (f.raw && f.raw.replace(/\s+/g, "") === cleanCustom) ||
            (f.formula && f.formula.replace(/\s+/g, "") === cleanCustom) ||
            (f.expression && f.expression.replace(/\s+/g, "") === cleanCustom)
        );
        if (matchIdx >= 0) {
          activeIndex = matchIdx;
        }
      }

      console.log("[FormulaLab] formulas ready:", parsed);
      setFormulas(parsed);
      setSelectedIndex(activeIndex);

      try {
        if (typeof window !== "undefined" && parsed.length > 0) {
          window.localStorage.setItem(cacheKey, JSON.stringify(parsed));
        }
      } catch {
        // ignore storage failures
      }
    },
    [],
  );

  const selectFormula = useCallback(
    (raw: string) => {
      if (!formulas) return;
      const idx = formulas.findIndex((formula) => formula.id === raw || formula.raw === raw);
      if (idx >= 0) setSelectedIndex(idx);
    },
    [formulas],
  );

  const selectedFormula = formulas && formulas.length > 0 ? formulas[selectedIndex] : null;

  // Reset selection when formulas change to avoid stale selectedIndex
  useEffect(() => {
    if (!formulas || formulas.length === 0) {
      setSelectedIndex(0);
      return;
    }
    if (selectedIndex < 0 || selectedIndex >= formulas.length) {
      setSelectedIndex(0);
    }
  }, [formulas, selectedIndex]);

  return {
    formulas,
    selectedFormula,
    selectFormula,
    detectedCount: formulas ? formulas.length : 0,
    loadForTopic,
  };
}

export default useFormulaLab;
