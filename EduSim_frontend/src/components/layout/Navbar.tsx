import { User, Menu, Sun, Moon } from "lucide-react";
import { GlobalSearch } from "./GlobalSearch";
import { useSidebarStore } from "@/store/useSidebarStore";
import { useAuthStore } from "@/store/useAuthStore";
import { motion } from "framer-motion";
import { useRouterState, Link } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useTheme } from "@/hooks/useTheme";

export function Navbar() {
  const { setMobileOpen } = useSidebarStore();
  const [isDesktop, setIsDesktop] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  useEffect(() => {
    const updateDesktop = () => setIsDesktop(window.innerWidth >= 1024);
    updateDesktop();
    window.addEventListener("resize", updateDesktop);
    return () => window.removeEventListener("resize", updateDesktop);
  }, []);

  if (pathname.startsWith("/sandbox") || pathname.startsWith("/tutor")) {
    return null;
  }

  const hideSearch = pathname.startsWith("/tutor");

  const getPageTitle = (path: string) => {
    if (path.includes("/dashboard")) return "Home";
    if (path.includes("/profile")) return "Profile";
    if (path.includes("/settings")) return "Settings";
    return "EduSim";
  };

  const { user } = useAuthStore();

  if (isDesktop) {
    return (
      <div className="fixed top-4 left-0 right-0 z-[50] pointer-events-none px-4 md:px-0">
        <motion.header
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
          className="mx-auto max-w-[1500px] w-full h-14 flex items-center justify-between px-4 md:px-10 pointer-events-none"
        >
          <div className="flex items-center gap-3 shrink-0 pointer-events-auto">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden w-11 h-11 rounded-xl flex items-center justify-center bg-card border border-border shadow-sm hover:bg-secondary/50 transition-all hover:scale-105 active:scale-95"
            >
              <Menu className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>

          {/* Centered Search Bar Section */}
          <div className="flex-1 flex justify-center min-w-0 px-4 pointer-events-auto">
            <div className="w-full max-w-3xl">
              {!hideSearch && <GlobalSearch />}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0 pointer-events-auto">
            {user?.role && (
              <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-secondary border border-border text-primary capitalize tracking-wide">
                {user.role}
              </span>
            )}

            <button
              onClick={toggleTheme}
              className="w-11 h-11 rounded-xl flex items-center justify-center bg-card border border-border shadow-sm hover:bg-secondary/50 transition-all hover:scale-105 active:scale-95 cursor-pointer"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? (
                <Sun className="w-5 h-5 text-amber-500" />
              ) : (
                <Moon className="w-5 h-5 text-muted-foreground" />
              )}
            </button>

            <Link 
              to="/profile"
              className="w-12 h-12 rounded-full bg-gradient-to-br from-[var(--neon-purple)] to-[var(--neon-blue)] flex items-center justify-center shadow-lg hover:scale-110 active:scale-90 transition-all border border-border"
            >
              <User className="w-5 h-5 text-white" />
            </Link>
          </div>
        </motion.header>
      </div>
    );
  }

  return (
    <div className="fixed top-4 left-0 right-0 z-[50] pointer-events-none px-4">
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className="mx-auto max-w-5xl w-full h-14 flex items-center justify-between gap-3 sm:gap-6 px-4 border border-border/80 bg-card/65 backdrop-blur-xl rounded-[24px] shadow-sm pointer-events-auto"
      >
        <div className="flex items-center gap-3 shrink-0">
          {/* Mobile Menu Toggle (Hamburger Menu) */}
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center hover:bg-primary/20 transition-all hover:scale-105 active:scale-95 shadow-sm cursor-pointer"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* Page Title */}
          <span className="hidden sm:block text-base sm:text-lg font-bold tracking-tight text-foreground">
            {getPageTitle(pathname)}
          </span>
        </div>

        {/* Centered Search Bar Section */}
        <div className="flex-1 flex justify-center min-w-0 max-w-lg mx-auto">
          <GlobalSearch />
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {user?.role && (
            <span className="hidden xs:inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-secondary border border-border text-primary capitalize">
              {user.role}
            </span>
          )}

          <button
            onClick={toggleTheme}
            className="w-10 h-10 rounded-full bg-card border border-border/85 flex items-center justify-center hover:bg-secondary/50 transition-all hover:scale-105 active:scale-95 cursor-pointer"
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
            className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center shadow-md hover:scale-105 active:scale-95 transition-all cursor-pointer"
          >
            <User className="w-4 h-4" />
          </Link>
        </div>
      </motion.header>
    </div>
  );
}
