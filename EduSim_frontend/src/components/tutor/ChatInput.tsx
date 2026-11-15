import React, { useState, useRef, useEffect } from "react";
import { Send, Mic, Sparkles } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  focus?: boolean;
  language?: "en" | "te" | "hi";
}

export function ChatInput({ onSend, disabled, focus = false, language = "en" }: ChatInputProps) {
  const [text, setText] = useState("");
  const [isDesktop, setIsDesktop] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const isSubmittingRef = useRef(false);
  const recognitionRef = useRef<unknown>(null);

  // Release the submission lock whenever the disabled prop switches back to false
  useEffect(() => {
    if (!disabled) {
      isSubmittingRef.current = false;
    }
  }, [disabled]);

  const toggleVoiceInput = () => {
    if (disabled) return;
    const win = typeof window !== "undefined" ? (window as unknown as Record<string, unknown>) : null;
    if (!win) return;
    const SpeechRecognition =
      (win.SpeechRecognition as new () => any) ||
      (win.webkitSpeechRecognition as new () => any);

    if (!SpeechRecognition) {
      console.warn("[Voice STT] SpeechRecognition API not supported in this browser.");
      return;
    }

    if (isListening && recognitionRef.current) {
      try {
        (recognitionRef.current as any).stop();
      } catch {}
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;

      const langMap: Record<string, string> = {
        te: "te-IN",
        hi: "hi-IN",
        en: "en-IN",
      };
      recognition.lang = langMap[language] || "en-IN";

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((result: any) => result[0].transcript)
          .join("");
        setText(transcript);
      };

      recognition.onerror = (event: any) => {
        console.warn("[Voice STT] Recognition error:", event?.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error("[Voice STT] Failed to start speech recognition:", err);
      setIsListening(false);
    }
  };

  useEffect(() => {
    const updateDesktop = () => setIsDesktop(window.innerWidth >= 1024);
    updateDesktop();
    window.addEventListener("resize", updateDesktop);
    return () => window.removeEventListener("resize", updateDesktop);
  }, []);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [text]);

  useEffect(() => {
    if (focus && taRef.current) {
      setTimeout(() => taRef.current?.focus(), 80);
    }
  }, [focus]);

  const handleSubmit = () => {
    if (!text.trim() || disabled || isSubmittingRef.current) {
      return;
    }
    isSubmittingRef.current = true;
    const content = text.trim();
    setText("");
    onSend(content);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="w-full z-10 flex flex-col items-center justify-end pb-2 sm:pb-3 bg-transparent pt-1">
      <div className="mx-auto w-full max-w-[1600px] px-4 sm:px-6 md:px-8">
        <div className="relative flex flex-col rounded-[22px] border border-border/80 bg-transparent shadow-[0_10px_30px_rgba(0,0,0,0.06)] backdrop-blur-3xl overflow-hidden p-1.5 transition-all hover:border-primary/40">
          
          <div className="flex items-center gap-2 px-2">
            {/* Sparkles Icon Indicator - Only shown on mobile/tablet */}
            {!isDesktop && (
              <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
                <Sparkles className="w-5 h-5 fill-primary/10 animate-pulse" />
              </div>
            )}

            <textarea
              ref={taRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder={disabled ? "Tutor is thinking..." : "Ask the tutor..."}
              className="flex-1 min-w-0 bg-transparent border-0 outline-none text-foreground placeholder:text-muted-foreground/60 text-sm sm:text-base focus:ring-0 resize-none min-h-[24px] max-h-[120px] py-1.5 custom-scrollbar font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              rows={1}
            />

            <div className="flex items-center gap-1.5 shrink-0">
              {/* Mic Button with Speech Recognition */}
              <button
                type="button"
                aria-label="Voice input"
                onClick={toggleVoiceInput}
                disabled={disabled}
                title={isListening ? "Listening... (click to stop)" : "Voice input (Speak in English, Telugu, or Hindi)"}
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-all duration-200 cursor-pointer ${
                  isListening
                    ? "bg-red-500 text-white animate-pulse shadow-[0_0_15px_rgba(239,68,68,0.5)]"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground hover:scale-105 active:scale-95"
                }`}
              >
                <Mic className={`h-5 w-5 ${isListening ? "animate-bounce" : ""}`} />
              </button>
              
              {/* Send Button */}
              <button
                type="button"
                aria-label="Send message"
                onClick={handleSubmit}
                disabled={disabled || !text.trim() || isSubmittingRef.current}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[0_4px_12px_rgba(112,181,255,0.3)] transition-all duration-200 hover:scale-105 active:scale-95 disabled:scale-100 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none hover:bg-primary/95 cursor-pointer disabled:pointer-events-none"
              >
                <Send className="h-4.5 w-4.5 ml-0.5" />
              </button>
            </div>
          </div>

          <div className="text-center py-0.5">
            <span className="text-[10px] sm:text-[11px] text-muted-foreground/45 font-medium">Press Enter to send</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatInput;
