import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/useAuthStore";
import { 
  Mail, 
  Lock, 
  KeyRound, 
  Brain,
  Atom,
  Play,
  TrendingUp,
  Compass, 
  Eye, 
  EyeOff,
  Loader2,
  Sparkles,
  ArrowLeft,
  ArrowRight
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>) => {
    return {
      verify_token: (search.verify_token as string) || undefined,
      reset_token: (search.reset_token as string) || undefined,
    };
  },
  component: Login,
});

function Login() {
  const { verify_token, reset_token } = Route.useSearch();
  const navigate = useNavigate();
  const CLEAR_LOGIN_SEARCH = { verify_token: undefined, reset_token: undefined };
  
  const { 
    login, 
    loginWithGoogle,
    register,
    forgotPassword, 
    resetPassword, 
    verifyEmail,
    isLoading 
  } = (useAuthStore as any)();

  // Role selection state (defaults to "student")
  const [selectedRole, setSelectedRole] = useState<"student" | "teacher">("student");

  // Email form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  
  // Sub-screens
  const [showForgotForm, setShowForgotForm] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Validation States
  const [touched, setTouched] = useState({
    loginEmail: false,
    loginPassword: false,
    forgotEmail: false,
    resetPassword: false,
    resetConfirm: false
  });
  const [submittedLogin, setSubmittedLogin] = useState(false);
  const [submittedForgot, setSubmittedForgot] = useState(false);
  const [submittedReset, setSubmittedReset] = useState(false);

  // Floating particles state and generator
  const [particles, setParticles] = useState<{ id: number; left: number; top: number; delay: number; duration: number }[]>([]);
  useEffect(() => {
    const newParticles = Array.from({ length: 20 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      top: Math.random() * 100,
      delay: Math.random() * 2,
      duration: 8 + Math.random() * 4,
    }));
    setParticles(newParticles);
  }, []);

  // Handle Verify Token (on mount)
  useEffect(() => {
    if (verify_token) {
      const runVerify = async () => {
        const success = await verifyEmail(verify_token);
        if (success) {
          toast.success("Account activated successfully! You can now log in.");
          navigate({ to: "/login", replace: true, search: CLEAR_LOGIN_SEARCH });
        }
      };
      runVerify();
    }
  }, [verify_token, verifyEmail, navigate]);

  const handleGoogleSignInSuccess = async (credential: string) => {
    const success = await loginWithGoogle(credential, selectedRole);
    if (success) {
      toast.success("Welcome back!");
      navigate({ to: "/dashboard" });
    }
  };

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
    if (!clientId || clientId.includes("placeholder") || clientId.includes("your-google-client-id-here")) {
      return;
    }

    const initGoogle = () => {
      if ((window as any).google?.accounts?.id) {
        (window as any).google.accounts.id.initialize({
          client_id: clientId,
          callback: (response: any) => {
            handleGoogleSignInSuccess(response.credential);
          }
        });
        const btn = document.getElementById("google-signin-button");
        if (btn) {
          (window as any).google.accounts.id.renderButton(btn, {
            theme: "outline",
            size: "large",
            width: 360,
            shape: "pill",
            text: "continue_with"
          });
        }
      }
    };

    if ((window as any).google?.accounts?.id) {
      initGoogle();
    } else {
      const interval = setInterval(() => {
        if ((window as any).google?.accounts?.id) {
          initGoogle();
          clearInterval(interval);
        }
      }, 100);
      return () => clearInterval(interval);
    }
  }, []);

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittedLogin(true);
    const normalizedEmail = email.trim().toLowerCase();
    
    if (normalizedEmail.length === 0 && password.length === 0) {
      toast.error("Email and Password are required");
      return;
    }
    
    if (normalizedEmail.length === 0 || password.length === 0 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      return;
    }
    
    const success = await login({ email: normalizedEmail, password, role: selectedRole });
    if (success) {
      toast.success("Login successful");
      navigate({ to: "/dashboard" });
    }
  };

  const handleForgotSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittedForgot(true);
    const normalizedEmail = email.trim().toLowerCase();
    
    if (normalizedEmail.length === 0 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      return;
    }
    
    const success = await forgotPassword(normalizedEmail);
    if (success) {
      toast.success("Password reset link sent to your email");
      setShowForgotForm(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittedReset(true);
    
    const isStrong = newPassword.length >= 8 && /[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword) && /[0-9]/.test(newPassword) && /[^A-Za-z0-9]/.test(newPassword);
    
    if (!isStrong || newPassword !== confirmPassword) {
      return;
    }
    
    const success = await resetPassword(reset_token!, newPassword);
    if (success) {
      toast.success("Password reset successful");
      navigate({ to: "/login", replace: true, search: CLEAR_LOGIN_SEARCH });
    }
  };

  return (
    <div className="relative min-h-[100svh] overflow-hidden bg-background text-foreground font-sans">
      {/* Soft Ambient Background Gradient */}
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-br from-[#FAFCFF] via-[#F4F9FF] to-[#E6F2FF] dark:from-[#030712] dark:via-[#080E1A] dark:to-[#050811]" />

      <div className="relative z-10 grid min-h-[100svh] w-full max-w-[1100px] grid-cols-1 lg:grid-cols-2 items-center gap-12 px-6 py-8 mx-auto">
        
        {/* Left Hero Panel */}
        <div className="hidden lg:flex flex-col justify-center gap-8 h-full">
          <Link to="/" className="flex items-center gap-2.5 group relative z-10 w-fit">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-sm hover:rotate-12 transition-transform duration-300">
              <Compass className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold tracking-wider font-mono text-foreground">
              Edu<span className="text-primary">Sim</span>
            </span>
          </Link>

          <div className="space-y-4">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-secondary border border-border/40 text-[10px] text-primary font-semibold uppercase tracking-wider">
              <Sparkles className="w-3 h-3 text-primary" /> Next Generation Learning
            </div>

            <h1 className="text-4xl xl:text-5xl font-extrabold tracking-tight text-foreground leading-tight">
              Explore Science Through <br />
              <span className="text-primary">Immersive Simulations</span>
            </h1>

            <p className="text-muted-foreground text-[13px] leading-relaxed max-w-lg">
              Step into a new era of interactive learning with AI tutors, smart simulations, and powerful formula labs.
            </p>
          </div>

          <div className="space-y-4">
            {[
              { label: "AI-Powered Tutor", desc: "Get instant answers and explanations", icon: Brain, color: "#70B5FF" },
              { label: "Interactive Simulations", desc: "High-fidelity physics engine", icon: Play, color: "#70B5FF" },
              { label: "Formula Lab Explorer", desc: "Track variables and master formulas", icon: Atom, color: "#70B5FF" },
              { label: "Progress Tracking", desc: "Detailed mastery dashboards", icon: TrendingUp, color: "#70B5FF" },
            ].map((f, idx) => {
              const Icon = f.icon;
              return (
                <div
                  key={idx}
                  className="group bg-card border border-border rounded-2xl p-4 hover:border-primary/60 hover:bg-secondary/40 transition-all duration-300 cursor-pointer shadow-sm"
                  style={{
                    animation: `slideInLeft 0.6s ease-out ${idx * 0.1}s both`,
                  }}
                >
                  <div className="flex items-start gap-4">
                    <div 
                      className="p-2.5 rounded-xl flex items-center justify-center shrink-0"
                      style={{ backgroundColor: `${f.color}12`, border: `1px solid ${f.color}25`, color: f.color }}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors text-sm">
                        {f.label}
                      </h3>
                      <p className="text-xs text-muted-foreground">{f.desc}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Auth Card */}
        <div className="w-full max-w-[420px] mx-auto rounded-[24px] p-8 md:p-10 border border-border shadow-[0_8px_30px_rgba(112,181,255,0.06)] relative bg-card overflow-hidden group">
            {reset_token ? (
              <div>
                <div className="text-center mb-6">
                  <div className="w-12 h-12 rounded-2xl bg-secondary border border-border flex items-center justify-center mx-auto mb-4">
                    <KeyRound className="w-6 h-6 text-primary" />
                  </div>
                  <h3 className="text-2xl font-black text-foreground">New Password</h3>
                </div>
                <form onSubmit={handleResetPassword} className="space-y-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground font-mono">NEW PASSWORD</label>
                    <div className="relative">
                      <Lock className="absolute left-3.5 top-3.5 w-4 h-4 text-muted-foreground" />
                      <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} onBlur={() => setTouched(t => ({...t, resetPassword: true}))} className={`w-full pl-10 pr-4 py-3 rounded-2xl bg-background border text-sm text-foreground focus:border-primary outline-none placeholder:text-muted-foreground/60 ${((touched.resetPassword || submittedReset) && (newPassword.length === 0 || !(newPassword.length >= 8 && /[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword) && /[0-9]/.test(newPassword) && /[^A-Za-z0-9]/.test(newPassword)))) ? "border-red-500" : "border-border"}`} />
                    </div>
                    {((touched.resetPassword || submittedReset) && newPassword.length === 0) ? (
                      <p className="text-xs text-red-400 mt-1">New Password is required</p>
                    ) : ((touched.resetPassword || submittedReset) && !(newPassword.length >= 8 && /[A-Z]/.test(newPassword) && /[a-z]/.test(newPassword) && /[0-9]/.test(newPassword) && /[^A-Za-z0-9]/.test(newPassword))) ? (
                      <p className="text-xs text-red-400 mt-1">Password does not meet security requirements</p>
                    ) : null}
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground font-mono">CONFIRM PASSWORD</label>
                    <div className="relative">
                      <Lock className="absolute left-3.5 top-3.5 w-4 h-4 text-muted-foreground" />
                      <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} onBlur={() => setTouched(t => ({...t, resetConfirm: true}))} className={`w-full pl-10 pr-4 py-3 rounded-2xl bg-background border text-sm text-foreground focus:border-primary outline-none placeholder:text-muted-foreground/60 ${((touched.resetConfirm || submittedReset) && (confirmPassword !== newPassword || confirmPassword.length === 0)) ? "border-red-500" : "border-border"}`} />
                    </div>
                    {((touched.resetConfirm || submittedReset) && confirmPassword.length === 0) ? (
                      <p className="text-xs text-red-400 mt-1">Confirm Password is required</p>
                    ) : ((touched.resetConfirm || submittedReset) && confirmPassword !== newPassword) ? (
                      <p className="text-xs text-red-400 mt-1">Passwords do not match</p>
                    ) : null}
                    {touched.resetConfirm && confirmPassword.length > 0 && confirmPassword === newPassword && (
                      <p className="text-xs text-green-500 mt-1">Passwords match ✓</p>
                    )}
                  </div>
                  <button type="submit" disabled={isLoading} className="w-full py-3.5 rounded-2xl bg-primary text-white font-bold text-sm shadow-sm transition-all hover:scale-105 active:scale-95 duration-200">
                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Save Password"}
                  </button>
                </form>
              </div>
            ) : showForgotForm ? (
              <div>
                <button onClick={() => setShowForgotForm(false)} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mb-6"><ArrowLeft className="w-3.5 h-3.5" /> Back</button>
                <div className="mb-6"><h3 className="text-2xl font-black text-foreground">Reset Password</h3></div>
                <form onSubmit={handleForgotSubmit} className="space-y-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground font-mono">EMAIL</label>
                    <div className="relative">
                      <Mail className="absolute left-3.5 top-3.5 w-4 h-4 text-muted-foreground" />
                      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} onBlur={() => setTouched(t => ({...t, forgotEmail: true}))} className={`w-full pl-10 pr-4 py-3 rounded-2xl bg-background border text-sm text-foreground focus:border-primary outline-none placeholder:text-muted-foreground/60 ${((touched.forgotEmail || submittedForgot) && (email.trim().length === 0 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))) ? "border-red-500" : "border-border"}`} />
                    </div>
                    {((touched.forgotEmail || submittedForgot) && email.trim().length === 0) ? (
                      <p className="text-xs text-red-400 mt-1">Email is required</p>
                    ) : ((touched.forgotEmail || submittedForgot) && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) ? (
                      <p className="text-xs text-red-400 mt-1">Please enter a valid email address</p>
                    ) : null}
                  </div>
                  <button type="submit" disabled={isLoading} className="w-full py-3.5 rounded-2xl bg-primary text-white font-bold text-sm shadow-sm transition-all hover:scale-105 active:scale-95 duration-200">
                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Send Reset Link"}
                  </button>
                </form>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="space-y-1">
                  <h3 className="text-2xl font-black text-foreground">Access EduSim</h3>
                  <p className="text-xs text-muted-foreground">Sign in to continue your learning journey</p>
                </div>

                {/* Role Segmented Picker */}
                <div className="p-1 bg-secondary rounded-2xl flex gap-1 border border-border/60">
                  <button
                    type="button"
                    onClick={() => setSelectedRole("student")}
                    className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all duration-200 cursor-pointer ${
                      selectedRole === "student"
                        ? "bg-primary text-white shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Student
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedRole("teacher")}
                    className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all duration-200 cursor-pointer ${
                      selectedRole === "teacher"
                        ? "bg-primary text-white shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Teacher
                  </button>
                </div>

                <form onSubmit={handleEmailLogin} className="space-y-4">
                  <div>
                    <div className="relative">
                      <Mail className="absolute left-3.5 top-3.5 w-4 h-4 text-muted-foreground" />
                      <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} onBlur={() => setTouched(t => ({...t, loginEmail: true}))} className={`w-full pl-10 pr-4 py-3 rounded-2xl bg-background border text-sm text-foreground focus:border-primary outline-none placeholder:text-muted-foreground/60 ${((touched.loginEmail || submittedLogin) && (email.trim().length === 0 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))) ? "border-red-500" : "border-border"}`} />
                    </div>
                    {((touched.loginEmail || submittedLogin) && email.trim().length === 0) ? (
                      <p className="text-xs text-red-400 mt-1">Email is required</p>
                    ) : ((touched.loginEmail || submittedLogin) && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) ? (
                      <p className="text-xs text-red-400 mt-1">Please enter a valid email</p>
                    ) : null}
                  </div>
                  <div>
                    <div className="relative">
                      <Lock className="absolute left-3.5 top-3.5 w-4 h-4 text-muted-foreground" />
                      <input type={showPassword ? "text" : "password"} placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} onBlur={() => setTouched(t => ({...t, loginPassword: true}))} className={`w-full pl-10 pr-10 py-3 rounded-2xl bg-background border text-sm text-foreground focus:border-primary outline-none placeholder:text-muted-foreground/60 ${((touched.loginPassword || submittedLogin) && password.length === 0) ? "border-red-500" : "border-border"}`} />
                      <button type="button" onClick={() => { setShowPassword(!showPassword); }} className="absolute right-3.5 top-3.5 text-muted-foreground hover:text-foreground">{showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button>
                    </div>
                    {((touched.loginPassword || submittedLogin) && password.length === 0) && (
                      <p className="text-xs text-red-400 mt-1">Password is required</p>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <label className="flex items-center gap-2 text-muted-foreground select-none cursor-pointer">
                      <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="h-4 w-4 rounded border-border bg-background text-primary focus:ring-primary" />
                      Remember me
                    </label>
                    <button type="button" onClick={() => { setShowForgotForm(true); toast.success("Redirected to Forgot Password page"); }} className="text-primary hover:underline transition-colors font-medium">Forgot password?</button>
                  </div>
                  <button type="submit" disabled={isLoading} className="w-full py-3.5 rounded-2xl bg-primary text-white font-bold text-sm shadow-sm transition-all hover:scale-105 active:scale-95 duration-200">{isLoading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Sign In"}</button>
                </form>

                <div className="relative flex items-center justify-center my-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-border/60"></div>
                  </div>
                  <span className="relative px-3 text-[10px] uppercase font-bold text-muted-foreground bg-card">or</span>
                </div>

                <div className="w-full flex justify-center">
                  <div id="google-signin-button" className="w-full max-w-[360px] flex justify-center"></div>
                </div>

                <div className="text-center pt-2 text-xs font-medium">
                  <span className="text-muted-foreground">New to EduSim? </span>
                  <Link to="/signup" className="text-primary hover:underline transition-colors font-bold">
                    Create an account
                  </Link>
                </div>
              </div>
            )}
          
        </div>
      </div>


      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes slideInLeft { from { opacity: 0; transform: translateX(-30px); } to { opacity: 1; transform: translateX(0); } }
      `}</style>
    </div>
  );
}
