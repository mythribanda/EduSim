import React, { useState, useEffect } from "react";
import { FormulaDefinition } from "@/data/formulaRegistry";

interface Props {
  formulaDef?: FormulaDefinition;
}

export default function FormulaCalculator({ formulaDef }: Props) {
  const variables = formulaDef?.variables || {};
  const unitMap = formulaDef?.unitMap || {};
  const symbols = Object.keys(variables);

  // Default target is the first variable (typically LHS of equation)
  const [targetSymbol, setTargetSymbol] = useState<string>(symbols[0] || "");
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Initialize values
  useEffect(() => {
    if (!formulaDef) return;
    const initialValues: Record<string, string> = {};
    symbols.forEach((sym) => {
      if (sym !== targetSymbol) {
        // Set some sensible default values based on the formula
        if (formulaDef.id === "newton-second-law") {
          initialValues[sym] = sym === "m" ? "10" : "9.8";
        } else if (formulaDef.id === "ohms-law") {
          initialValues[sym] = sym === "I" ? "2" : "10";
        } else if (formulaDef.id === "kinetic-energy") {
          initialValues[sym] = sym === "m" ? "5" : "4";
        } else {
          initialValues[sym] = "1";
        }
      }
    });
    setValues(initialValues);
    setErrorMsg(null);
  }, [targetSymbol, formulaDef?.id]);

  // Recalculate
  useEffect(() => {
    if (!formulaDef) return;
    setErrorMsg(null);
    const inputs: Record<string, number> = {};
    let hasEmpty = false;

    for (const sym of symbols) {
      if (sym !== targetSymbol) {
        const valStr = values[sym];
        if (!valStr || valStr.trim() === "") {
          hasEmpty = true;
          break;
        }
        const valNum = parseFloat(valStr);
        if (isNaN(valNum)) {
          setErrorMsg("Please enter valid numeric values.");
          return;
        }
        inputs[sym] = valNum;
      }
    }

    if (hasEmpty) {
      setResult(null);
      return;
    }

    try {
      let calculated = 0;
      if (formulaDef.id === "newton-second-law") {
        // F = m * a
        if (targetSymbol === "F") {
          calculated = inputs.m * inputs.a;
        } else if (targetSymbol === "m") {
          if (inputs.a === 0) throw new Error("Acceleration cannot be zero.");
          calculated = inputs.F / inputs.a;
        } else if (targetSymbol === "a") {
          if (inputs.m === 0) throw new Error("Mass cannot be zero.");
          calculated = inputs.F / inputs.m;
        }
      } else if (formulaDef.id === "ohms-law") {
        // V = I * R
        if (targetSymbol === "V") {
          calculated = inputs.I * inputs.R;
        } else if (targetSymbol === "I") {
          if (inputs.R === 0) throw new Error("Resistance cannot be zero.");
          calculated = inputs.V / inputs.R;
        } else if (targetSymbol === "R") {
          if (inputs.I === 0) throw new Error("Current cannot be zero.");
          calculated = inputs.V / inputs.I;
        }
      } else if (formulaDef.id === "kinetic-energy") {
        // KE = 0.5 * m * v^2
        if (targetSymbol === "KE") {
          calculated = 0.5 * inputs.m * Math.pow(inputs.v, 2);
        } else if (targetSymbol === "m") {
          if (inputs.v === 0) throw new Error("Velocity cannot be zero.");
          calculated = (2 * inputs.KE) / Math.pow(inputs.v, 2);
        } else if (targetSymbol === "v") {
          if (inputs.m === 0) throw new Error("Mass cannot be zero.");
          const val = (2 * inputs.KE) / inputs.m;
          if (val < 0) throw new Error("Cannot take square root of negative value.");
          calculated = Math.sqrt(val);
        }
      } else {
        calculated = 1;
      }

      setResult(calculated);
    } catch (e: any) {
      setErrorMsg(e.message || "Calculation error");
      setResult(null);
    }
  }, [values, targetSymbol, formulaDef?.id]);

  if (!formulaDef) {
    return (
      <div className="flex flex-col items-center justify-center p-6 text-center text-muted-foreground">
        <p>No calculator available for this formula definition.</p>
      </div>
    );
  }

  const handleInputChange = (sym: string, val: string) => {
    setValues((prev) => ({ ...prev, [sym]: val }));
  };

  return (
    <div className="flex flex-col gap-6 w-full max-w-md mx-auto">
      {/* Target Selector */}
      <div className="space-y-2">
        <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          Solve For
        </label>
        <div className="flex gap-2">
          {symbols.map((sym) => (
            <button
              key={sym}
              type="button"
              onClick={() => setTargetSymbol(sym)}
              className={`flex-1 py-2 px-3 rounded-xl border text-xs font-semibold transition-all ${
                targetSymbol === sym
                  ? "bg-primary border-primary text-white"
                  : "bg-background border-border text-foreground hover:bg-secondary"
              }`}
            >
              {variables[sym]} ({sym})
            </button>
          ))}
        </div>
      </div>

      {/* Inputs List */}
      <div className="space-y-4">
        {symbols
          .filter((sym) => sym !== targetSymbol)
          .map((sym) => (
            <div key={sym} className="space-y-1 text-left">
              <label htmlFor={`input-${sym}`} className="text-xs font-semibold text-foreground">
                {variables[sym]} ({sym})
              </label>
              <div className="relative flex items-center">
                <input
                  id={`input-${sym}`}
                  type="number"
                  step="any"
                  value={values[sym] || ""}
                  onChange={(e) => handleInputChange(sym, e.target.value)}
                  placeholder={`Enter ${variables[sym].toLowerCase()}`}
                  className="w-full pl-4 pr-12 py-2.5 rounded-xl bg-background border border-border text-sm text-foreground focus:border-primary outline-none"
                />
                {unitMap[sym] && (
                  <span className="absolute right-4 text-xs font-semibold text-muted-foreground">
                    {unitMap[sym]}
                  </span>
                )}
              </div>
            </div>
          ))}
      </div>

      {/* Result Display */}
      <div className="mt-2 p-4 rounded-2xl bg-secondary border border-border/40 text-center">
        <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1">
          Result ({targetSymbol})
        </div>
        {errorMsg ? (
          <div className="text-sm font-bold text-red-500">{errorMsg}</div>
        ) : result !== null ? (
          <div className="text-2xl font-black text-primary">
            {result.toLocaleString(undefined, { maximumFractionDigits: 4 })}
            <span className="text-sm font-bold text-muted-foreground ml-1">
              {unitMap[targetSymbol] || ""}
            </span>
          </div>
        ) : (
          <div className="text-sm font-semibold text-muted-foreground">
            Waiting for values...
          </div>
        )}
      </div>
    </div>
  );
}
