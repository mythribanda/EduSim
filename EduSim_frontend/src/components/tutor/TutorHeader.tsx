import React from "react";
import { Menu, User, History, Sun, Moon, Flame, Plus, Sparkles, Compass } from "lucide-react";
import { useSidebarStore } from "@/store/useSidebarStore";
import { useAuthStore } from "@/store/useAuthStore";
import { Link } from "@tanstack/react-router";
import { useTheme } from "@/hooks/useTheme";
import { useQuery } from "@tanstack/react-query";
import { fetchJsonWithRetry } from "@/services/apiClient";
import { getApiUrl } from "@/config/api";

interface TutorHeaderProps {
  onNewChat: () => void;
  topicTitle?: string;
  topicContext?: {
    subject?: string;
    className?: string;
    chapter?: string;
  };
  toggleHistory?: () => void;
  isHistoryOpen?: boolean;
}

export function TutorHeader({ onNewChat, topicTitle, topicContext, toggleHistory, isHistoryOpen }: TutorHeaderProps) {
  const { setMobileOpen } = useSidebarStore();
  const { theme, toggleTheme } = useTheme();
  const { user, token } = useAuthStore();

  const { data: profile } = useQuery<{ current_streak_days?: number } | null>({
    queryKey: ["studentProfile", user?.id],
    queryFn: async () => {
      if (!user?.id || !token) return null;
      try {
        return await fetchJsonWithRetry<{ current_streak_days?: number }>(
          getApiUrl(`/api/students/${user.id}/profile`),
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } catch {
        return null;
      }
    },
    enabled: Boolean(user?.id && token),
    staleTime: 60_000,
  });

  const activeStreak = profile?.current_streak_days ?? 1;

  return (
    <header className="z-30 flex items-center justify-between shrink-0 pointer-events-auto w-full h-16 px-4 sm:px-6 border-b border-border bg-card/85 backdrop-blur-xl transition-colors">
      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Toggle Global App Sidebar */}
        <button
          onClick={() => setMobileOpen(true)}
          className="lg:hidden w-9 h-9 rounded-xl bg-secondary hover:bg-secondary/80 text-foreground flex items-center justify-center transition-all cursor-pointer hover:scale-105 active:scale-95 shadow-sm shrink-0 border border-border"
          title="Open Menu"
        >
          <Menu className="w-4.5 h-4.5" />
        </button>

        {/* Brand Home Link */}
        <Link to="/dashboard" className="hidden sm:flex items-center gap-2 group mr-2">
          <div className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center shadow-sm group-hover:scale-105 transition-transform">
            <Compass className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold tracking-tight text-sm text-foreground">
            Edu<span className="text-primary">Sim</span>
          </span>
        </Link>

        {/* Toggle Chat History Button (Visible on BOTH desktop and mobile) */}
        <button
          onClick={toggleHistory}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all cursor-pointer shadow-sm ${
            isHistoryOpen
              ? "bg-primary text-white border-primary"
              : "bg-secondary hover:bg-secondary/80 text-foreground border-border hover:border-primary/40"
          }`}
          title="Toggle Chat History"
        >
          <History className={`w-4 h-4 ${isHistoryOpen ? "text-white" : "text-primary"}`} />
          <span className="hidden sm:inline">History</span>
        </button>

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-secondary hover:bg-secondary/80 border border-border text-xs font-semibold text-foreground transition-all hover:border-primary/40 active:scale-95 cursor-pointer shadow-sm"
          title="Start New Chat"
        >
          <Plus className="w-3.5 h-3.5 text-primary" />
          <span className="hidden sm:inline">New Chat</span>
        </button>

        {topicTitle && (
          <div className="hidden md:flex flex-col border-l border-border pl-3 ml-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground leading-none">
              Active Topic
            </span>
            <span className="text-xs font-bold text-primary truncate max-w-[220px] mt-0.5">{topicTitle}</span>
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Streak symbol beside theme toggle */}
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-600 dark:text-amber-400 font-extrabold text-xs shadow-sm"
          title={`Active Learning Streak: ${activeStreak} days`}
        >
          <Flame className="w-4 h-4 fill-amber-500 text-amber-500 animate-pulse" />
          <span>{activeStreak}</span>
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="w-9 h-9 rounded-xl bg-card border border-border flex items-center justify-center hover:bg-secondary transition-all hover:scale-105 active:scale-95 cursor-pointer shadow-sm"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? (
            <Sun className="w-4.5 h-4.5 text-amber-500" />
          ) : (
            <Moon className="w-4.5 h-4.5 text-muted-foreground" />
          )}
        </button>

        {/* User Profile Button */}
        <Link
          to="/profile"
          className="w-9 h-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-sm cursor-pointer border border-border transition-all hover:scale-105 active:scale-95"
          title="Profile"
        >
          <User className="w-4 h-4" />
        </Link>
      </div>
    </header>
  );
}
