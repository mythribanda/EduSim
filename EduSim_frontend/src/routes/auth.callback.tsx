import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { useAuthStore } from "@/store/useAuthStore";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/auth/callback")({
  validateSearch: (search: Record<string, unknown>) => {
    return {
      token: (search.token as string) || undefined,
      error: (search.error as string) || undefined,
    };
  },
  component: AuthCallbackComponent,
});

function decodeJwt(token: string) {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      window
        .atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

function AuthCallbackComponent() {
  const { token, error } = Route.useSearch();
  const navigate = useNavigate();
  const hasProcessedRef = useRef(false);

  useEffect(() => {
    // Guard against React double-mount (StrictMode) firing OAuth callback twice
    if (hasProcessedRef.current) {
      return;
    }
    hasProcessedRef.current = true;

    if (error) {
      toast.error(`Authentication failed: ${error}`);
      navigate({ to: "/login", search: { verify_token: "", reset_token: "" } });
      return;
    }

    if (token) {
      const payload = decodeJwt(token);
      if (payload) {
        const userObj = {
          id: payload.sub,
          email: payload.email,
          role: payload.role,
          name: payload.name || payload.email.split("@")[0],
          age_tier: payload.age_tier || "middle",
          class_id: payload.class_id || null,
          institution_id: payload.institution_id || null,
          board: payload.board || null,
          created_at: new Date().toISOString(),
        };

        // 1. Store in localStorage
        localStorage.setItem("edusim_token", token);
        localStorage.setItem("token", token); // for legacy compatibility

        // 2. Set Zustand auth store state so the application is authenticated
        useAuthStore.setState({
          token: token,
          user: userObj as any,
          isAuthenticated: true,
        });

        toast.success("Welcome to EduSim!");
        
        // 3. Redirect to dashboard
        navigate({ to: "/dashboard" });
      } else {
        toast.error("Invalid token format received");
        navigate({ to: "/login", search: { verify_token: "", reset_token: "" } });
      }
    } else {
      toast.error("Authentication callback received no token");
      navigate({ to: "/login", search: { verify_token: "", reset_token: "" } });
    }
  }, [token, error, navigate]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
        <span className="text-sm font-medium text-muted-foreground">
          Completing sign-in…
        </span>
      </div>
    </div>
  );
}
