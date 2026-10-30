import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { useAuthStore } from "@/store/useAuthStore";
import { Card, PageWrapper } from "@/components/Card";
import { useQuery } from "@tanstack/react-query";
import { CurriculumService } from "@/services/curriculumService";
import { fetchJsonWithRetry } from "@/services/apiClient";
import { getApiUrl } from "@/config/api";
import { 
  Sparkles, 
  BookOpen, 
  Atom, 
  Brain, 
  Compass,
  ArrowRight,
  User,
  GraduationCap,
  FlaskConical,
  Flame,
  Trophy,
  Target,
  CheckCircle2
} from "lucide-react";

export const Route = createFileRoute("/dashboard")({
  component: Dashboard,
});

const EMPTY_LOGIN_SEARCH = {
  verify_token: "",
  reset_token: "",
};

const EMPTY_TUTOR_SEARCH = {
  subject: undefined,
  class_name: undefined,
  chapter: undefined,
  topic: undefined,
  prompt: undefined,
};

interface StudentProfileData {
  student_id: string;
  class: string;
  mastered_topics: string[];
  weak_topics: string[];
  current_streak_days: number;
  total_sessions: number;
  recommended_next: string;
}

function Dashboard() {
  const { user, token } = useAuthStore();
  const navigate = useNavigate();

  const { data: classes = [], isLoading, isError, error, refetch: refetchClasses } = useQuery({
    queryKey: ["classes"],
    queryFn: CurriculumService.getClasses,
  });

  const { data: profile } = useQuery<StudentProfileData | null>({
    queryKey: ["studentProfile", user?.id],
    queryFn: async () => {
      if (!user?.id || !token) return null;
      try {
        return await fetchJsonWithRetry<StudentProfileData>(
          getApiUrl(`/api/students/${user.id}/profile`),
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } catch (err) {
        console.warn("Could not fetch student profile for dashboard:", err);
        return null;
      }
    },
    enabled: Boolean(user?.id && token),
  });

  const activeStreak = profile?.current_streak_days ?? 1;
  const masteredCount = profile?.mastered_topics?.length ?? 0;
  const recommendedTopic = profile?.recommended_next || "Newton's Second Law";

  return (
    <PageWrapper>
      {/* Welcome Banner */}
      <section className="glass-strong rounded-3xl p-8 md:p-12 mb-8 relative overflow-hidden bg-card border border-border shadow-sm">

        <div className="absolute -top-20 -right-20 w-72 h-72 rounded-full bg-primary/10 blur-3xl z-0" />
        <div className="absolute -bottom-20 -left-10 w-72 h-72 rounded-full bg-primary/10 blur-3xl z-0" />

        {/* Animated Quantum Orbit Background Illustration */}
        <div className="absolute right-16 top-1/2 -translate-y-1/2 w-[240px] h-[240px] overflow-hidden pointer-events-none hidden md:block z-0">
          <svg className="w-full h-full opacity-90 dark:opacity-60" viewBox="0 0 300 300" fill="none">
            {/* Center Core */}
            <circle cx="150" cy="150" r="6" fill="currentColor" className="text-primary" />
            <circle cx="150" cy="150" r="14" stroke="currentColor" className="text-primary/35" strokeWidth="1" />
            
            {/* Ring 1 */}
            <circle cx="150" cy="150" r="60" stroke="currentColor" className="text-primary/45" strokeWidth="1" strokeDasharray="4 4" />
            {/* Particle 1 */}
            <g>
              <circle r="4.5" fill="currentColor" className="text-primary">
                <animateMotion 
                  path="M 150,90 A 60,60 0 1,1 150,210 A 60,60 0 1,1 150,90 Z" 
                  dur="8s" 
                  repeatCount="indefinite" 
                />
              </circle>
              <circle r="9" stroke="currentColor" className="text-primary/40" strokeWidth="1">
                <animateMotion 
                  path="M 150,90 A 60,60 0 1,1 150,210 A 60,60 0 1,1 150,90 Z" 
                  dur="8s" 
                  repeatCount="indefinite" 
                />
              </circle>
            </g>

            {/* Ring 2 */}
            <circle cx="150" cy="150" r="100" stroke="currentColor" className="text-primary/30" strokeWidth="1" />
            {/* Particle 2 (Orbiting Counter-Clockwise) */}
            <circle r="5.5" fill="currentColor" className="text-primary/80">
              <animateMotion 
                path="M 250,150 A 100,100 0 1,0 50,150 A 100,100 0 1,0 250,150 Z" 
                dur="15s" 
                repeatCount="indefinite" 
              />
            </circle>

            {/* Ring 3 (First Inclined Ellipse for 3D look) */}
            <g transform="rotate(30 150 150)">
              <ellipse cx="150" cy="150" rx="130" ry="40" stroke="currentColor" className="text-primary/25" strokeWidth="1" strokeDasharray="6 3" />
              {/* Particle 3 (Orbiting Elliptical Path) */}
              <circle r="4" fill="currentColor" className="text-primary/60">
                <animateMotion 
                  path="M 280,150 A 130,40 0 1,1 20,150 A 130,40 0 1,1 280,150 Z" 
                  dur="25s" 
                  repeatCount="indefinite" 
                />
              </circle>
            </g>

            {/* Ring 4 (Second Opposing Inclined Ellipse for balanced 3D look) */}
            <g transform="rotate(-30 150 150)">
              <ellipse cx="150" cy="150" rx="130" ry="40" stroke="currentColor" className="text-primary/25" strokeWidth="1" strokeDasharray="6 3" />
              {/* Particle 4 (Orbiting Elliptical Path, counter-clockwise) */}
              <circle r="4" fill="currentColor" className="text-primary/60">
                <animateMotion 
                  path="M 280,150 A 130,40 0 1,0 20,150 A 130,40 0 1,0 280,150 Z" 
                  dur="20s" 
                  repeatCount="indefinite" 
                />
              </circle>
            </g>
          </svg>
        </div>

        <div className="relative flex flex-col md:flex-row justify-between items-start md:items-center gap-6 z-10">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-secondary border border-border text-xs text-primary font-mono mb-4">
              <GraduationCap className="w-3.5 h-3.5" />
              {user?.role === "teacher" ? "TEACHER" : "STUDENT"}
            </div>
            <motion.h1 
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-4xl font-bold mb-3 tracking-tight text-foreground flex items-center gap-2"
            >
              Welcome, <span className="text-primary font-extrabold">{user?.name || "Explorer"}</span> · {user?.role === "teacher" ? "Teacher" : "Student"}
              <motion.span 
                className="inline-block cursor-grab active:cursor-grabbing"
                animate={{
                  y: [0, -4, 0],
                  rotate: [0, 5, 0],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
                whileHover={{ scale: 1.25, rotate: [0, 15, -10, 0] }}
              >
                🚀
              </motion.span>
            </motion.h1>
            <p className="text-muted-foreground max-w-xl text-base">
              Dive back into your simulations or ask the AI Tutor to explain complex physics concepts in real-time.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Signed in as <span className="font-semibold text-foreground">{user?.email || "unknown"}</span>
            </p>
          </div>
        </div>
      </section>

      {/* Learning Progress & Next Recommended Activity */}
      <section className="rounded-3xl border border-border bg-card p-6 mb-8 shadow-sm relative overflow-hidden">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-primary bg-primary/10 border border-primary/20 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                <Target className="w-3.5 h-3.5" /> Next Pedagogical Activity
              </span>
            </div>
            <h3 className="text-xl font-black text-foreground">
              Continue with <span className="text-primary">{recommendedTopic}</span>
            </h3>
            <p className="text-xs text-muted-foreground max-w-lg">
              Based on your concept mastery and quiz results, our AI tutor recommends exploring {recommendedTopic} through interactive simulation and formula modeling.
            </p>
          </div>

          <div className="flex items-center flex-wrap gap-3">
            <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 px-4 py-2.5 rounded-2xl">
              <Flame className="w-5 h-5 text-amber-500 fill-amber-500" />
              <div>
                <div className="text-[10px] font-extrabold uppercase text-amber-600 dark:text-amber-400">Current Streak</div>
                <div className="text-sm font-black text-foreground">{activeStreak} Days</div>
              </div>
            </div>

            <div className="flex items-center gap-2 bg-violet-500/10 border border-violet-500/20 px-4 py-2.5 rounded-2xl">
              <Trophy className="w-5 h-5 text-violet-500" />
              <div>
                <div className="text-[10px] font-extrabold uppercase text-violet-600 dark:text-violet-400">Mastered Topics</div>
                <div className="text-sm font-black text-foreground">{masteredCount} Completed</div>
              </div>
            </div>

            <Link
              to="/simulation/$topic"
              params={{ topic: recommendedTopic }}
              className="flex items-center gap-2 px-6 py-3 rounded-2xl bg-primary text-primary-foreground font-bold text-xs shadow-md shadow-primary/20 hover:brightness-110 active:scale-95 transition-all"
            >
              <Sparkles className="w-4 h-4 text-primary-foreground" />
              <span>Launch Simulation</span>
              <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Link>
          </div>
        </div>
      </section>

      <section className="glass rounded-3xl p-6 border border-border bg-card mb-8 shadow-sm">
        <h2 className="text-xl font-bold tracking-tight mb-5 text-foreground">Quick Access</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link to="/tutor" search={EMPTY_TUTOR_SEARCH} className="group rounded-2xl border border-border bg-card px-4 py-4 hover:border-primary hover:bg-secondary/40 transition-all shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground group-hover:text-primary transition-colors"><Brain className="w-4 h-4 text-primary" /> AI Tutor</div>
          </Link>
          <Link to="/formula-lab/$topic" params={{ topic: "new" }} className="group rounded-2xl border border-border bg-card px-4 py-4 hover:border-primary hover:bg-secondary/40 transition-all shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground group-hover:text-primary transition-colors"><Atom className="w-4 h-4 text-primary" /> Formula Lab</div>
          </Link>
          <Link to="/sandbox/$simulationId" params={{ simulationId: "new" }} className="group rounded-2xl border border-border bg-card px-4 py-4 hover:border-primary hover:bg-secondary/40 transition-all shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground group-hover:text-primary transition-colors"><FlaskConical className="w-4 h-4 text-primary" /> Simulations</div>
          </Link>
          <Link to="/profile" className="group rounded-2xl border border-border bg-card px-4 py-4 hover:border-amber-500/50 hover:bg-amber-500/5 transition-all shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground group-hover:text-amber-600 transition-colors"><User className="w-4 h-4 text-amber-500" /> Profile</div>
          </Link>
        </div>
      </section>

      {/* Main Grid */}
      <div className="mb-10 space-y-8">
        <h2 className="text-xl font-bold tracking-tight text-foreground">Interactive Modules</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            {/* AI Tutor Card */}
            <Link to="/tutor" search={EMPTY_TUTOR_SEARCH}>
              <div className="group h-full glass rounded-3xl p-6 border border-border bg-card hover:border-primary/45 hover:bg-secondary/20 transition-all duration-300 relative overflow-hidden flex flex-col justify-between shadow-sm">
                <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-bl-full blur-2xl group-hover:bg-primary/10 transition-all duration-500" />
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-secondary border border-border flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <Brain className="w-6 h-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-bold mb-2 flex items-center gap-2 text-foreground group-hover:text-primary transition-colors">
                    AI Tutor
                    <Sparkles className="w-4 h-4 text-primary animate-pulse" />
                  </h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Have questions about physics? Chat with our intelligent assistant to learn via interactive discussions.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-primary font-bold group-hover:translate-x-1.5 transition-transform">
                  Start Chatting <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </Link>

            {/* Formula Lab Card */}
            <Link to="/formula-lab/$topic" params={{ topic: "new" }}>
              <div className="group h-full glass rounded-3xl p-6 border border-border bg-card hover:border-primary/45 hover:bg-secondary/20 transition-all duration-300 relative overflow-hidden flex flex-col justify-between shadow-sm">
                <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-bl-full blur-2xl group-hover:bg-primary/10 transition-all duration-500" />
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-secondary border border-border flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <Atom className="w-6 h-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-bold mb-2 text-foreground group-hover:text-primary transition-colors">Formula Lab</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Experiment with physics variables and see how constants change parameters, plots, and motion equations instantly.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-primary font-bold group-hover:translate-x-1.5 transition-transform">
                  Explore Formulas <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </Link>



            {/* AI Generator Card */}
            <Link to="/sandbox/$simulationId" params={{ simulationId: "new" }}>
              <div className="group h-full glass rounded-3xl p-6 border border-border bg-card hover:border-primary/45 hover:bg-secondary/20 transition-all duration-300 relative overflow-hidden flex flex-col justify-between shadow-sm">
                <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-bl-full blur-2xl group-hover:bg-amber-500/10 transition-all duration-500" />
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <Compass className="w-6 h-6 text-amber-600" />
                  </div>
                  <h3 className="text-lg font-bold mb-2 text-foreground group-hover:text-amber-600 transition-colors">AI Simulation Builder</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Describe a physics concept, and the Educational Intelligence synthesis engine will dynamically build a custom simulation.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-amber-600 font-bold group-hover:translate-x-1.5 transition-transform">
                  Synthesize Simulation <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </Link>

          </div>
      </div>

      {/* Curriculum Class Selector Section */}
      <section className="mt-6">
        <h2 className="text-2xl font-bold mb-6 tracking-tight font-sans text-foreground">Explore Curriculum</h2>
        {isLoading ? (
          <div className="text-muted-foreground p-4">Loading curriculum...</div>
        ) : isError ? (
          <div className="text-destructive p-4 bg-destructive/10 border border-destructive/20 rounded-2xl flex flex-col items-start gap-2">
            <div>Failed to load curriculum classes: {error instanceof Error ? error.message : "Unknown error"}</div>
            <button onClick={() => refetchClasses()} className="text-xs font-bold underline hover:text-foreground">Try again</button>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            {classes.map((c, i) => (
              <Link key={c.id} to="/subjects/$classId" params={{ classId: String(c.id) }}>
                <Card delay={i * 0.04} className="border border-border bg-card shadow-sm hover:border-primary/50">
                  <div className="text-xs text-primary font-mono font-bold mb-2">CLASS</div>
                  <div className="text-3xl font-extrabold text-foreground mb-2">{c.id}</div>
                  <p className="text-xs text-muted-foreground line-clamp-2">{c.description}</p>
                  <div className="mt-3 text-xs text-muted-foreground font-semibold">View Subjects</div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>

    </PageWrapper>
  );
}
