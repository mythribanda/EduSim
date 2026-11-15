import React, { useState, useEffect, useMemo } from "react";
import { 
  Plus, 
  Search, 
  Trash2, 
  Loader2, 
  MessageSquare, 
  PanelLeftClose, 
  PanelLeftOpen,
  User as UserIcon,
  Sparkles
} from "lucide-react";
import { useAuthStore } from "@/store/useAuthStore";
import { TutorService } from "@/services/TutorService";
import { toast } from "sonner";

interface ChatHistorySidebarProps {
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  refreshTrigger: number;
  onClose?: () => void;
}

interface Session {
  id: string;
  topic: string;
  created_at: string;
  is_active: boolean;
}

export function ChatHistorySidebar({
  activeSessionId,
  onSelectSession,
  onNewChat,
  refreshTrigger,
  onClose,
}: ChatHistorySidebarProps) {
  const { user, isAuthenticated } = useAuthStore();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);

  const fetchSessions = async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const res = await TutorService.getSessions();
      if (res.success) {
        setSessions(res.sessions || []);
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [refreshTrigger, isAuthenticated]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      const res = await TutorService.deleteSession(sessionId);
      if (res.success) {
        toast.success("Chat history deleted");
        if (activeSessionId === sessionId) {
          onNewChat();
        }
        fetchSessions();
      } else {
        toast.error("Failed to delete chat history");
      }
    } catch (err) {
      toast.error("An error occurred while deleting chat history");
      console.error(err);
    }
  };

  // Grouping logic
  const groupedSessions = useMemo(() => {
    const filtered = sessions.filter(s => 
      (s.topic || "AI Tutor Session").toLowerCase().includes(searchQuery.toLowerCase())
    );

    const today: Session[] = [];
    const yesterday: Session[] = [];
    const previous7Days: Session[] = [];
    const older: Session[] = [];

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 24 * 60 * 60 * 1000;
    const sevenDaysAgoStart = todayStart - 7 * 24 * 60 * 60 * 1000;

    filtered.forEach(session => {
      const date = new Date(session.created_at).getTime();
      if (date >= todayStart) {
        today.push(session);
      } else if (date >= yesterdayStart) {
        yesterday.push(session);
      } else if (date >= sevenDaysAgoStart) {
        previous7Days.push(session);
      } else {
        older.push(session);
      }
    });

    return [
      { title: "Today", items: today },
      { title: "Yesterday", items: yesterday },
      { title: "Previous 7 Days", items: previous7Days },
      { title: "Older", items: older }
    ].filter(group => group.items.length > 0);
  }, [sessions, searchQuery]);

  if (isCollapsed) {
    return (
      <div className="w-[60px] h-full bg-card border-r border-border flex flex-col items-center py-4 space-y-4 shrink-0 transition-all duration-300">
        <button
          onClick={() => setIsCollapsed(false)}
          className="p-2 hover:bg-secondary rounded-xl text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          title="Expand Sidebar"
        >
          <PanelLeftOpen className="w-5 h-5" />
        </button>
        <button
          onClick={onNewChat}
          className="p-2.5 bg-primary rounded-xl text-primary-foreground hover:opacity-90 active:scale-95 transition-all shadow-sm cursor-pointer"
          title="New Chat"
        >
          <Plus className="w-5 h-5" />
        </button>
      </div>
    );
  }

  return (
    <div className="w-[280px] h-full bg-card border-r border-border flex flex-col shrink-0 transition-all duration-300 relative text-foreground">
      {/* Header */}
      <div className="p-4 flex items-center justify-between border-b border-border shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center shadow-sm">
            <Sparkles className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-bold tracking-tight text-sm text-foreground">Chats</span>
        </div>
        <button
          onClick={() => {
            if (onClose) onClose();
            setIsCollapsed(true);
          }}
          className="p-1.5 hover:bg-secondary rounded-lg text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          title="Close Sidebar"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* Action Buttons */}
      <div className="p-3 space-y-2 shrink-0">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-primary text-primary-foreground hover:opacity-90 rounded-xl text-sm font-semibold transition-all hover:scale-[1.01] active:scale-[0.99] shadow-sm cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </button>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-secondary/50 border border-border rounded-xl text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:bg-card transition-colors"
          />
        </div>
      </div>

      {/* Recents List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-3 pb-4 space-y-4">
        {loading && sessions.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-primary animate-spin" />
          </div>
        ) : groupedSessions.length === 0 ? (
          <div className="text-center text-xs text-muted-foreground py-8">
            {searchQuery ? "No matching chats found" : "No recent chats"}
          </div>
        ) : (
          groupedSessions.map(group => (
            <div key={group.title} className="space-y-1.5">
              <h3 className="px-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                {group.title}
              </h3>
              <div className="space-y-1">
                {group.items.map(session => {
                  const isActive = activeSessionId === session.id;
                  return (
                    <div
                      key={session.id}
                      onClick={() => onSelectSession(session.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-all duration-150 ${
                        isActive
                          ? "bg-primary/10 text-primary font-semibold border border-primary/20 shadow-sm"
                          : "text-muted-foreground hover:text-foreground hover:bg-secondary/60 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 pr-4">
                        <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-primary" : "text-muted-foreground"}`} />
                        <span className="truncate">{session.topic || "AI Tutor Session"}</span>
                      </div>
                      <button
                        onClick={(e) => handleDelete(e, session.id)}
                        className="opacity-0 group-hover:opacity-100 hover:text-destructive p-1 rounded transition-all cursor-pointer"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* User profile footer */}
      {user && (
        <div className="p-3 border-t border-border bg-card shrink-0">
          <div className="flex items-center justify-between p-2 rounded-xl bg-secondary/40 border border-border">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-full bg-primary/15 text-primary border border-primary/30 flex items-center justify-center shadow-sm shrink-0 font-bold text-xs">
                {user.avatar ? (
                  <img src={user.avatar} alt="Avatar" className="w-full h-full rounded-full object-cover" />
                ) : (
                  user.name ? user.name.charAt(0).toUpperCase() : <UserIcon className="w-4 h-4" />
                )}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-foreground truncate leading-tight">{user.name}</p>
                <p className="text-[10px] text-muted-foreground truncate capitalize mt-0.5">{user.role || "student"}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
