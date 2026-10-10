import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BookOpen, CheckCircle2, XCircle, ArrowRight, Sparkles, Loader2, Flame, Trophy, Target } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { DynamicParsedFormula } from "@/utils/DynamicFormulaExtractor";
import { getApiUrl } from "@/config/api";
import { useAuthStore } from "@/store/useAuthStore";

interface QASectionProps {
  topic: string;
  chapter?: string;
  subject?: string;
  formulas?: DynamicParsedFormula[] | null;
  ragContent?: string;
}

type QuestionType = "multiple-choice" | "fill-blanks" | "concept";

interface QuizQuestion {
  id: string;
  backendId?: number;
  type: QuestionType;
  question: string;
  options?: string[];
  correctAnswer: string;
  explanation: string;
}

interface SubmitResult {
  is_correct: boolean;
  mastery_score?: number;
  streak?: number;
  recommended_next?: string;
}

export default function QASection({ topic, chapter, subject, formulas }: QASectionProps) {
  const { user, token } = useAuthStore();
  const isNewton = topic.toLowerCase().includes("newton") || 
                   (formulas && formulas.some(f => f.title?.toLowerCase().includes("newton")));

  // Demo Questions as fallback
  const demoQuestions: QuizQuestion[] = [
    {
      id: "q1", type: "multiple-choice",
      question: "What is the SI unit of force?",
      options: ["Joule", "Newton", "Watt", "Pascal"],
      correctAnswer: "Newton",
      explanation: "The SI unit of force is the Newton (N), which is equivalent to 1 kg·m/s²."
    },
    {
      id: "q2", type: "multiple-choice",
      question: "If the mass of an object is kept constant, what happens to the force if the acceleration is doubled?",
      options: ["It is halved", "It remains the same", "It is doubled", "It is quadrupled"],
      correctAnswer: "It is doubled",
      explanation: "Since F = m × a, force is directly proportional to acceleration when mass is constant. Doubling acceleration doubles the force."
    },
    {
      id: "q3", type: "multiple-choice",
      question: "Which of the following describes mass in Newton's Second Law?",
      options: ["A measure of velocity", "A vector quantity", "A scalar quantity measuring inertia", "A unit of force"],
      correctAnswer: "A scalar quantity measuring inertia",
      explanation: "Mass is a scalar quantity that represents an object's resistance to acceleration (inertia)."
    },
    {
      id: "q4", type: "fill-blanks",
      question: "Newton's Second Law states:\nF = ___ × a",
      correctAnswer: "m",
      explanation: "Force (F) equals Mass (m) multiplied by Acceleration (a)."
    },
    {
      id: "q5", type: "fill-blanks",
      question: "If a force of 20N is applied to a 5kg mass, the acceleration is ___ m/s².",
      correctAnswer: "4",
      explanation: "Since F = ma, a = F/m. 20 / 5 = 4 m/s²."
    },
    {
      id: "q6", type: "concept",
      question: "Concept: Does an object require a net force to stay in motion at a constant velocity?",
      options: ["Yes, a constant force is required", "No, net force must be zero", "Yes, but only in a vacuum"],
      correctAnswer: "No, net force must be zero",
      explanation: "According to Newton's First Law, an object at constant velocity has zero acceleration. By Newton's Second Law (F=ma), if a=0, net Force must be 0."
    }
  ];

  const genericQuestions = [
    {
      id: "q1", type: "multiple-choice",
      question: `What does ${formulas?.[0]?.resultSymbol || 'the result'} represent in this formula?`,
      options: ["Rate of change", "Constant", formulas?.[0]?.title || "The main variable", "Energy"],
      correctAnswer: formulas?.[0]?.title || "The main variable",
      explanation: "This is derived from the formula's primary purpose."
    }
  ] as QuizQuestion[];

  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({});
  const [submitFeedback, setSubmitFeedback] = useState<Record<string, SubmitResult>>({});
  const [latestMastery, setLatestMastery] = useState<{ score: number; streak: number; recommended?: string } | null>(null);
  const [score, setScore] = useState(0);

  const parseQuestionsResponse = (data: any): QuizQuestion[] => {
    const rawList = Array.isArray(data) ? data : (Array.isArray(data?.questions) ? data.questions : []);
    if (!rawList || rawList.length === 0) return [];
    return rawList.map((q: any) => {
      const hasOptions = Array.isArray(q.options) && q.options.length > 0;
      return {
        id: q.id ? `q-${q.id}` : `q-${Math.random().toString(36).substring(2, 9)}`,
        backendId: typeof q.id === "number" ? q.id : undefined,
        type: hasOptions ? "multiple-choice" : "fill-blanks",
        question: q.question,
        options: hasOptions ? q.options : undefined,
        correctAnswer: q.correct || q.answer || "",
        explanation: q.explanation || ""
      };
    });
  };

  // Load initial questions
  const loadInitialQuestions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(getApiUrl("/api/questions/generate"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          subject: subject || "physics",
          chapter: chapter || "",
          topic: topic || "",
          formula: formulas && formulas.length > 0 ? formulas[0].formula : "",
          difficulty: "Medium",
          question_type: "mixed",
          exclude_questions: []
        })
      });

      if (!response.ok) throw new Error("Failed to generate questions");
      const data = await response.json();
      const mapped = parseQuestionsResponse(data);
      
      if (mapped.length > 0) {
        setQuestions(mapped);
      } else {
        setQuestions(isNewton ? demoQuestions : genericQuestions);
      }
    } catch (err) {
      console.warn("Failed to load questions via API, using fallbacks:", err);
      setQuestions(isNewton ? demoQuestions : genericQuestions);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialQuestions();
    // Reset quiz state when topic changes
    setCurrentIndex(0);
    setAnswers({});
    setSubmitted({});
    setSubmitFeedback({});
    setLatestMastery(null);
    setScore(0);
  }, [topic]);

  // Generate more questions
  const generateMoreQuestions = async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const shownQuestions = questions.map(q => q.question);
      const response = await fetch(getApiUrl("/api/questions/generate"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          subject: subject || "physics",
          chapter: chapter || "",
          topic: topic || "",
          formula: formulas && formulas.length > 0 ? formulas[0].formula : "",
          difficulty: "Medium",
          question_type: "mixed",
          exclude_questions: shownQuestions
        })
      });

      if (!response.ok) throw new Error("Failed to generate more questions");
      const data = await response.json();
      const mapped = parseQuestionsResponse(data);

      if (mapped.length > 0) {
        const prevLength = questions.length;
        setQuestions(prev => [...prev, ...mapped]);
        
        // If they finished the quiz, immediately point them to the first new question
        if (currentIndex >= prevLength - 1 && submitted[questions[currentIndex]?.id]) {
          setCurrentIndex(prevLength);
        }
      } else {
        alert("The AI couldn't generate more unique questions for this topic right now. Please try again.");
      }
    } catch (err) {
      console.error("Failed to fetch more questions:", err);
      alert("Error generating more questions. Check your connection to the AI Tutor.");
    } finally {
      setLoadingMore(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-3xl border border-slate-100 bg-white/85 p-16 text-center text-slate-400 font-medium shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-violet-600 animate-spin" />
        <span className="text-sm text-slate-500 font-bold tracking-wider animate-pulse">Generating dynamic quiz questions...</span>
      </div>
    );
  }

  if (questions.length === 0) return null;

  const currentQ = questions[currentIndex];
  const isSubmitted = currentQ ? submitted[currentQ.id] : false;
  const submitInfo = currentQ ? submitFeedback[currentQ.id] : undefined;
  const isCorrect = isSubmitted && currentQ && (
    submitInfo ? submitInfo.is_correct : answers[currentQ.id]?.toLowerCase().trim() === currentQ.correctAnswer.toLowerCase().trim()
  );

  const handleSelectOption = (option: string) => {
    if (isSubmitted) return;
    setAnswers(prev => ({ ...prev, [currentQ.id]: option }));
  };

  const handleTextChange = (value: string) => {
    if (isSubmitted) return;
    setAnswers(prev => ({ ...prev, [currentQ.id]: value }));
  };

  const handleSubmit = async () => {
    if (!answers[currentQ.id] || isSubmitted) return;
    const selected = answers[currentQ.id];
    setSubmitted(prev => ({ ...prev, [currentQ.id]: true }));

    const localCorrect = selected.toLowerCase().trim() === currentQ.correctAnswer.toLowerCase().trim();
    if (localCorrect) {
      setScore(s => s + 1);
    }

    try {
      const response = await fetch(getApiUrl("/api/questions/submit"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          topic: topic || "Physics",
          selected_option: selected,
          question_id: currentQ.backendId,
          correct_option: currentQ.correctAnswer,
          student_id: user?.id
        })
      });

        if (response.ok) {
          const result: any = await response.json();
          setSubmitFeedback(prev => ({ ...prev, [currentQ.id]: result }));
          const resolvedStreak = result.correct_streak ?? result.streak ?? 1;
          if (result.mastery_score !== undefined) {
            setLatestMastery({
              score: result.mastery_score,
              streak: resolvedStreak,
              recommended: result.recommended_next
            });
          }
        }
    } catch (err) {
      console.warn("Could not post answer to /api/questions/submit:", err);
    }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(i => i + 1);
    }
  };

  const progressPercent = ((currentIndex + 1) / questions.length) * 100;

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-violet-50 flex items-center justify-center border border-violet-150 shadow-sm">
            <BookOpen className="w-5 h-5 text-violet-600" />
          </div>
          <div>
            <h2 className="text-2xl font-black tracking-tight text-slate-800">Practice Q&A</h2>
            <p className="text-xs font-semibold text-slate-400">Question {currentIndex + 1} of {questions.length}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {latestMastery && (
            <div className="hidden sm:flex items-center gap-3 bg-secondary/60 border border-border px-3.5 py-1.5 rounded-2xl">
              <div className="flex items-center gap-1 text-xs font-bold text-amber-500">
                <Flame className="w-4 h-4" />
                <span>{latestMastery.streak} Streak</span>
              </div>
              <div className="h-3 w-[1px] bg-border" />
              <div className="flex items-center gap-1 text-xs font-bold text-violet-500">
                <Trophy className="w-4 h-4" />
                <span>{latestMastery.score.toFixed(0)}% Mastery</span>
              </div>
            </div>
          )}
          <button
            onClick={generateMoreQuestions}
            disabled={loadingMore}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-violet-50 hover:bg-violet-100 text-violet-750 text-xs font-bold border border-violet-150 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
          >
            {loadingMore ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 text-violet-600 animate-pulse" />
            )}
            <span>{loadingMore ? "Generating..." : "Get More Questions"}</span>
          </button>
          <div className="text-right">
            <p className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Score</p>
            <p className="text-xl font-black text-violet-600">{score}/{questions.length}</p>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden shadow-inner">
        <div 
          className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-500" 
          style={{ width: `${progressPercent}%` }} 
        />
      </div>
      
      <AnimatePresence mode="wait">
        <motion.div 
          key={currentQ.id}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          className={`rounded-3xl border p-8 transition-all duration-300 ${
            isSubmitted 
              ? (isCorrect 
                  ? 'border-green-200 bg-green-50/20 shadow-[0_8px_30px_rgba(34,197,94,0.04)]' 
                  : 'border-red-200 bg-red-50/20 shadow-[0_8px_30px_rgba(239,68,68,0.04)]') 
              : 'border-slate-100 bg-white shadow-[0_8px_30px_rgb(0,0,0,0.02)]'
          }`}
        >
          <h3 className="text-lg font-bold leading-relaxed text-slate-800 whitespace-pre-wrap">
            {currentQ.question}
          </h3>

          <div className="mt-8">
            {(currentQ.type === "multiple-choice" || currentQ.type === "concept") && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {currentQ.options?.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => handleSelectOption(opt)}
                    disabled={isSubmitted}
                    className={`p-4 rounded-xl border text-left font-semibold text-sm transition-all duration-200 ${
                      answers[currentQ.id] === opt
                        ? 'border-violet-500 bg-violet-50 text-violet-700 shadow-sm'
                        : 'border-slate-100 bg-slate-50/40 text-slate-600 hover:bg-slate-100/50 hover:text-slate-800'
                    } ${isSubmitted ? 'cursor-not-allowed opacity-80' : ''} ${
                      isSubmitted && opt === currentQ.correctAnswer ? 'border-green-500 bg-green-50 text-green-700 shadow-[0_0_15px_rgba(34,197,94,0.1)]' : ''
                    } ${
                      isSubmitted && answers[currentQ.id] === opt && opt !== currentQ.correctAnswer ? 'border-red-500 bg-red-50 text-red-700 shadow-[0_0_15px_rgba(239,68,68,0.1)]' : ''
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {currentQ.type === "fill-blanks" && (
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={answers[currentQ.id] || ""}
                  onChange={(e) => handleTextChange(e.target.value)}
                  disabled={isSubmitted}
                  placeholder="Type your answer..."
                  className="w-full sm:max-w-md bg-slate-50 border border-slate-200 rounded-xl px-5 py-4 focus:outline-none focus:bg-white focus:border-violet-500 focus:ring-4 focus:ring-violet-500/10 disabled:opacity-50 text-slate-850 text-lg"
                />
              </div>
            )}

            {!isSubmitted ? (
              <button
                onClick={handleSubmit}
                disabled={!answers[currentQ.id]}
                className="mt-8 rounded-xl bg-violet-600 hover:bg-violet-500 px-8 py-3 font-bold text-white shadow-md shadow-violet-600/15 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
              >
                Submit Answer
              </button>
            ) : (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-8 space-y-6"
              >
                <div className={`p-5 rounded-2xl border ${
                  isCorrect ? 'bg-green-50 border-green-150 text-green-800' : 'bg-red-50 border-red-150 text-red-800'
                }`}>
                  <div className="flex items-start gap-4">
                    {isCorrect ? (
                      <CheckCircle2 className="w-6 h-6 text-green-500 mt-0.5 shrink-0" />
                    ) : (
                      <XCircle className="w-6 h-6 text-red-500 mt-0.5 shrink-0" />
                    )}
                    <div>
                      <p className={`text-lg font-bold ${isCorrect ? 'text-green-700' : 'text-red-700'}`}>
                        {isCorrect ? 'Correct!' : 'Incorrect'}
                      </p>
                      <p className="mt-2 text-slate-700 font-normal leading-relaxed text-sm">
                        {currentQ.explanation}
                      </p>
                    </div>
                  </div>
                </div>

                {currentIndex < questions.length - 1 ? (
                  <button
                    onClick={handleNext}
                    className="flex items-center gap-2 rounded-xl bg-slate-900 text-white hover:bg-slate-800 px-8 py-3 font-bold shadow-md transition-all active:scale-95"
                  >
                    Next Question <ArrowRight className="w-4 h-4" />
                  </button>
                ) : (
                  <div className="flex flex-col items-center justify-center p-8 bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-100 rounded-2xl text-center shadow-lg shadow-violet-100/10 gap-4">
                    <h4 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-violet-600 to-indigo-650">🎉 Practice Complete!</h4>
                    <p className="text-base text-slate-600 font-semibold">You scored <span className="font-extrabold text-violet-600">{score}</span> out of <span className="font-extrabold text-slate-800">{questions.length}</span></p>

                    {latestMastery && (
                      <div className="flex items-center gap-4 bg-white/80 border border-violet-200/60 rounded-2xl px-6 py-3 shadow-sm">
                        <div className="flex items-center gap-2 text-sm font-bold text-amber-600">
                          <Flame className="w-5 h-5 fill-amber-500 text-amber-500" />
                          <span>{latestMastery.streak} Day Streak</span>
                        </div>
                        <div className="h-4 w-[1px] bg-slate-200" />
                        <div className="flex items-center gap-2 text-sm font-bold text-violet-600">
                          <Trophy className="w-5 h-5 text-violet-600" />
                          <span>{latestMastery.score.toFixed(0)}% Mastery Score</span>
                        </div>
                      </div>
                    )}

                    {latestMastery?.recommended && (
                      <div className="mt-2 p-4 rounded-2xl bg-white/90 border border-violet-200 max-w-md w-full text-center space-y-2">
                        <div className="flex items-center justify-center gap-1.5 text-xs font-bold text-violet-600 uppercase tracking-wider">
                          <Target className="w-4 h-4" /> Recommended Next Topic
                        </div>
                        <p className="text-sm font-bold text-slate-800">{latestMastery.recommended}</p>
                        <Link
                          to="/simulation/$topic"
                          params={{ topic: latestMastery.recommended }}
                          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs shadow-md transition-all active:scale-95"
                        >
                          Launch Next Simulation <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    )}
                    
                    <div className="flex flex-col sm:flex-row gap-3 w-full max-w-sm justify-center mt-2">
                      <button
                        onClick={() => {
                          setCurrentIndex(0);
                          setAnswers({});
                          setSubmitted({});
                          setSubmitFeedback({});
                          setScore(0);
                        }}
                        className="flex-1 px-6 py-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-755 font-bold transition-all active:scale-95 shadow-sm"
                      >
                        Retry Practice
                      </button>
                      <button
                        onClick={generateMoreQuestions}
                        disabled={loadingMore}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-violet-600 text-white font-bold hover:bg-violet-500 shadow-md shadow-violet-600/15 transition-all active:scale-95 disabled:opacity-50"
                      >
                        {loadingMore ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Sparkles className="w-4 h-4 text-white/80" />
                        )}
                        <span>{loadingMore ? "Generating..." : "More Questions"}</span>
                      </button>
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

