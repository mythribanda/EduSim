import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuthStore } from "@/store/useAuthStore";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Atom,
  Brain,
  Check,
  Compass,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  Play,
  Smartphone,
  Sparkles,
  TrendingUp,
  User,
  X,
  FlaskConical,
  Globe,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/signup")({
  component: Signup,
});

type FieldName = "name" | "email" | "mobileNumber" | "password" | "confirmPassword" | "termsAccepted";

function Signup() {
  const navigate = useNavigate();
  const { register, loginWithGoogle, isLoading } = useAuthStore();

  const [selectedRole, setSelectedRole] = useState<"student" | "teacher">("student");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [mobileNumber, setMobileNumber] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [touched, setTouched] = useState<Record<FieldName, boolean>>({
    name: false,
    email: false,
    mobileNumber: false,
    password: false,
    confirmPassword: false,
    termsAccepted: false,
  });

  const nameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const mobileRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmPasswordRef = useRef<HTMLInputElement>(null);
  const termsRef = useRef<HTMLInputElement>(null);

  const [particles, setParticles] = useState<{ id: number; left: number; top: number; delay: number; duration: number }[]>([]);
  useEffect(() => {
    setParticles(
      Array.from({ length: 20 }, (_, index) => ({
        id: index,
        left: Math.random() * 100,
        top: Math.random() * 100,
        delay: Math.random() * 2,
        duration: 8 + Math.random() * 4,
      }))
    );
  }, []);

  const handleGoogleSignInSuccess = async (credential: string) => {
    const success = await loginWithGoogle(credential, selectedRole);
    if (success) {
      toast.success("Welcome to EduSim!");
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

  useEffect(() => {
    if (submitted) {
      setTouched({
        name: true,
        email: true,
        mobileNumber: true,
        password: true,
        confirmPassword: true,
        termsAccepted: true,
      });
    }
  }, [submitted]);

  const passwordChecks = useMemo(() => {
    const digitsOnly = mobileNumber.replace(/\D/g, "");
    const nameTrimmed = name.trim();
    const nameLen = nameTrimmed.length >= 3;
    const nameRegex = nameTrimmed.length === 0 || /^[A-Za-z0-9_]+$/.test(nameTrimmed);
    return {
      nameLen,
      nameRegex,
      name: nameLen && nameRegex,
      email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()),
      mobile: digitsOnly.length === 0 || /^\d{10}$/.test(digitsOnly),
      length: password.length >= 8,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      number: /[0-9]/.test(password),
      special: /[^A-Za-z0-9]/.test(password),
      confirm: confirmPassword.length > 0 && password === confirmPassword,
      terms: termsAccepted,
      digitsOnly,
    };
  }, [confirmPassword, email, mobileNumber, name, password, termsAccepted]);

  const isPasswordValid = (passwordChecks as any).length && passwordChecks.uppercase && passwordChecks.lowercase && passwordChecks.number && passwordChecks.special;
  const isFormValid = passwordChecks.name && passwordChecks.email && passwordChecks.mobile && isPasswordValid && passwordChecks.confirm && passwordChecks.terms;

  const showError = (field: FieldName, valid: boolean) => (touched[field] || submitted) && !valid;

  const focusFirstInvalidField = () => {
    if (!passwordChecks.name) return nameRef.current?.focus();
    if (!passwordChecks.email) return emailRef.current?.focus();
    if (!passwordChecks.mobile) return mobileRef.current?.focus();
    if (!isPasswordValid) return passwordRef.current?.focus();
    if (!passwordChecks.confirm) return confirmPasswordRef.current?.focus();
    if (!passwordChecks.terms) return termsRef.current?.focus();
  };

  const handleMobileChange = (value: string) => {
    setMobileNumber(value.replace(/\D/g, "").slice(0, 10));
  };

  const handleSignupSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitted(true);

    if (isSubmitting || isLoading) return;

    if (!isFormValid) {
      focusFirstInvalidField();
      if (!name && !email && !password && !confirmPassword) {
        toast.error("Please fill all required fields");
      } else {
        toast.error("Please correct the highlighted errors");
      }
      return;
    }

    setIsSubmitting(true);
    try {
      const success = await register({
        name: name.trim(),
        email: email.trim(),
        password,
        role: selectedRole,
        mobile: passwordChecks.digitsOnly || undefined,
      });

      if (success) {
        toast.success("Account created successfully! Please login now.");
        window.setTimeout(() => navigate({ to: "/login" } as any), 2000);
      }
    } finally {
      setIsSubmitting(false);
    }
  };


  const strengthScore = [passwordChecks.length, passwordChecks.uppercase, passwordChecks.lowercase, passwordChecks.number, passwordChecks.special].filter(Boolean).length;
  
  const getStrengthInfo = (score: number) => {
    switch (score) {
      case 0:
        return { label: "Empty Password", color: "bg-muted" };
      case 1:
        return { label: "Very Weak", color: "bg-red-500" };
      case 2:
        return { label: "Weak", color: "bg-orange-500" };
      case 3:
        return { label: "Medium", color: "bg-amber-400" };
      case 4:
        return { label: "Strong", color: "bg-emerald-400" };
      case 5:
        return { label: "Very Strong ✓", color: "bg-green-500" };
      default:
        return { label: "Weak Password", color: "bg-red-500" };
    }
  };
  const strength = getStrengthInfo(strengthScore);

  const fieldClass = (valid: boolean, error: boolean) =>
    `w-full rounded-2xl bg-background text-sm text-foreground outline-none placeholder:text-muted-foreground/60 transition-all duration-300 ${
      error
        ? "border border-red-500/70 focus:border-red-500 focus:ring-2 focus:ring-red-500/30"
        : valid
          ? "border border-green-500/60 focus:border-green-500 focus:ring-2 focus:ring-green-500/25"
          : "border border-border focus:border-primary focus:ring-2 focus:ring-primary/20"
    }`;

  return (
    <div className="relative min-h-[100svh] overflow-hidden bg-background text-foreground font-sans">
      {/* Soft Ambient Background Gradient */}
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-br from-[#FAFCFF] via-[#F4F9FF] to-[#E6F2FF] dark:from-[#030712] dark:via-[#080E1A] dark:to-[#050811]" />

      <div className="relative z-10 grid min-h-[100svh] w-full max-w-[1100px] grid-cols-1 lg:grid-cols-2 items-center gap-12 lg:gap-16 px-6 py-12 lg:py-8 mx-auto">
        
        {/* Left Hero Panel (Stacked below on mobile, first on desktop) */}
        <div className="flex flex-col justify-center gap-8 w-full order-2 lg:order-1 mt-8 lg:mt-0">
          <Link to="/" className="flex items-center gap-2.5 group relative z-10 w-fit">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-sm hover:rotate-12 transition-transform duration-300">
              <Compass className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold tracking-wider font-mono text-foreground">
              Edu<span className="text-primary">Sim</span>
            </span>
          </Link>

          <div className="space-y-4">
            <h1 className="text-4xl lg:text-5xl font-black tracking-tight text-white leading-tight">
              Explore Science <br />
              Through Immersive <br />
              Simulations <br />
              <span className="text-cyan-400 font-black tracking-wide drop-shadow-[0_0_15px_rgba(34,211,238,0.45)]">EduSim</span>
            </h1>
          </div>

          {/* Compressed Inline Features Row */}
          <div className="flex flex-wrap gap-2.5 mt-2">
            {[
              { label: "Physics", icon: Atom },
              { label: "Chemistry", icon: FlaskConical },
              { label: "Biology", icon: Brain },
              { label: "Astronomy", icon: Compass },
              { label: "Earth Science", icon: Globe },
            ].map((f, idx) => {
              const Icon = f.icon;
              return (
                <div
                  key={idx}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900/60 border border-slate-800 rounded-full text-[11px] font-semibold text-slate-300 hover:border-cyan-400/40 transition-colors cursor-pointer"
                >
                  <Icon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span>{f.label}</span>
                </div>
              );
            })}
          </div>

          {/* Beautiful 3D Animated Atom Graphic */}
          <div className="relative w-full max-w-[320px] h-[260px] mx-auto mt-6 flex items-center justify-center select-none overflow-hidden">
            {/* Ambient cyan glow behind */}
            <div className="absolute w-44 h-44 rounded-full bg-cyan-500/10 blur-[60px]" />
            
            {/* Nucleus */}
            <div className="absolute w-7 h-7 rounded-full bg-gradient-to-br from-red-500 via-orange-400 to-yellow-300 animate-pulse shadow-[0_0_20px_rgba(239,68,68,0.6)]" />

            {/* Orbit 1 */}
            <div className="absolute w-64 h-24 border-2 border-cyan-400/20 rounded-full rotate-45 animate-[orbit1_12s_linear_infinite]">
              {/* Electron 1 */}
              <div className="absolute -top-1.5 left-1/2 w-3.5 h-3.5 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.85)]" />
            </div>

            {/* Orbit 2 */}
            <div className="absolute w-64 h-24 border-2 border-cyan-400/20 rounded-full -rotate-45 animate-[orbit2_10s_linear_infinite]">
              {/* Electron 2 */}
              <div className="absolute -top-1.5 left-1/2 w-3.5 h-3.5 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.85)]" />
            </div>

            {/* Orbit 3 */}
            <div className="absolute w-64 h-24 border-2 border-cyan-400/20 rounded-full rotate-90 animate-[orbit3_14s_linear_infinite]">
              {/* Electron 3 */}
              <div className="absolute -top-1.5 left-1/2 w-3.5 h-3.5 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.85)]" />
            </div>

            {/* Floating molecules */}
            <div className="absolute top-4 left-6 w-3 h-3 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)] animate-bounce" />
            <div className="absolute bottom-6 right-8 w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse" />
          </div>
        </div>

        {/* Right Auth Card (First on mobile, second on desktop) */}
        <div className="w-full max-w-[420px] mx-auto rounded-[28px] p-8 border border-cyan-500/25 shadow-[0_0_50px_-12px_rgba(6,182,212,0.25)] relative bg-slate-950/80 backdrop-blur-md overflow-hidden group order-1 lg:order-2">
          
          <div className="mb-6 space-y-1 text-left">
            <h3 className="text-2xl font-black text-foreground tracking-tight flex items-center gap-2">
              Create Your Account
              <Sparkles className="w-5 h-5 text-primary animate-pulse" />
            </h3>
            <p className="text-xs text-muted-foreground">Unlock interactive educational simulations</p>
          </div>

          {/* Role Segmented Picker */}
          <div className="mb-4 p-1 bg-secondary rounded-2xl flex gap-1 border border-border/60">
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

          <form onSubmit={handleSignupSubmit} className="space-y-4 text-left" noValidate>
            <div className="space-y-1">
              <label className="block text-[11px] font-semibold text-slate-400 mb-1.5">Username</label>
              <div className="relative group/input">
                <input id="name" ref={nameRef} type="text" placeholder="Enter your username" value={name} onChange={(e) => setName(e.target.value)} onBlur={() => setTouched((current) => ({ ...current, name: true }))} className={fieldClass(passwordChecks.name && touched.name, showError("name", passwordChecks.name)) + " px-4 py-3"} />
                {passwordChecks.name && touched.name && (
                  <Check className="w-4 h-4 text-green-500 absolute right-3.5 top-3.5" />
                )}
              </div>
              {showError("name", passwordChecks.name) && (
                <p id="name-error" className="text-xs text-red-400 mt-1">
                  {name.trim().length === 0
                    ? "Username is required"
                    : !passwordChecks.nameLen
                      ? "Username must be at least 3 characters"
                      : "Only letters, numbers and underscores allowed"}
                </p>
              )}
              {passwordChecks.name && name.trim().length >= 3 && (
                <p className="text-xs text-green-500 mt-1">
                  Username available ✓
                </p>
              )}
            </div>

            <div className="space-y-1">
              <label className="block text-[11px] font-semibold text-slate-400 mb-1.5">Email Address</label>
              <div className="relative group/input">
                <input id="email" ref={emailRef} type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} onBlur={() => setTouched((current) => ({ ...current, email: true }))} className={fieldClass(passwordChecks.email && touched.email, showError("email", passwordChecks.email)) + " px-4 py-3"} />
                {passwordChecks.email && touched.email && (
                  <Check className="w-4 h-4 text-green-500 absolute right-3.5 top-3.5" />
                )}
              </div>
              {showError("email", passwordChecks.email) && (
                <p id="email-error" className="text-xs text-red-400">
                  {email.trim().length === 0
                    ? "Email is required"
                    : "Please enter a valid email address"}
                </p>
              )}
            </div>

            <div className="space-y-1">
              <label className="block text-[11px] font-semibold text-slate-400 mb-1.5">Mobile Number (optional)</label>
              <div className="relative group/input">
                <input id="mobile" ref={mobileRef} type="tel" inputMode="numeric" pattern="[0-9]*" maxLength={10} placeholder="10-digit mobile number" value={mobileNumber} onChange={(e) => handleMobileChange(e.target.value)} onBlur={() => setTouched((current) => ({ ...current, mobileNumber: true }))} className={fieldClass(mobileNumber.length > 0 && passwordChecks.mobile && touched.mobileNumber, showError("mobileNumber", passwordChecks.mobile)) + " px-4 py-3"} />
                {mobileNumber.length > 0 && passwordChecks.mobile && touched.mobileNumber && (
                  <Check className="w-4 h-4 text-green-500 absolute right-3.5 top-3.5" />
                )}
              </div>
              {showError("mobileNumber", passwordChecks.mobile) && <p id="mobile-error" className="text-xs text-red-400">Please enter a valid mobile number</p>}
            </div>

            <div className="space-y-1">
              <label className="block text-[11px] font-semibold text-slate-400 mb-1.5">Password</label>
              <div className="relative group/input">
                <input id="password" ref={passwordRef} type={showPassword ? "text" : "password"} placeholder="Create a strong password" value={password} onChange={(e) => setPassword(e.target.value)} onBlur={() => setTouched((current) => ({ ...current, password: true }))} className={fieldClass(isPasswordValid && touched.password, showError("password", isPasswordValid)) + " px-4 pr-12 py-3"} />
                <button type="button" onClick={() => { setShowPassword((prev) => !prev); }} className="absolute right-3.5 top-3.5 text-muted-foreground hover:text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 rounded-md" aria-label={showPassword ? "Hide password" : "Show password"}>
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {showError("password", isPasswordValid) && (
                <p id="password-error" className="text-xs text-red-400 mt-1">
                  {password.length === 0
                    ? "Password is required"
                    : !passwordChecks.length
                      ? "Password must be at least 8 characters"
                      : !passwordChecks.uppercase
                        ? "Must contain at least one uppercase letter"
                        : !passwordChecks.lowercase
                          ? "Must contain at least one lowercase letter"
                          : !passwordChecks.number
                            ? "Must contain at least one number"
                            : "Must contain at least one special character"}
                </p>
              )}

              <div className="space-y-2 pt-1">
                <div className="flex items-center justify-between text-[10px] font-semibold">
                  <span className="text-muted-foreground">Strength</span>
                  <span className={strength.color.replace("bg-", "text-")}>{strength.label}</span>
                </div>
                <div className="flex gap-1.5 mt-1.5">
                  {[1, 2, 3, 4, 5].map((segmentIndex) => {
                    const active = segmentIndex <= strengthScore;
                    const colorClass = active ? strength.color : "bg-border/60";
                    return (
                      <div
                        key={segmentIndex}
                        className={`h-1.5 flex-1 rounded-full ${colorClass} transition-all duration-300`}
                      />
                    );
                  })}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 p-3.5 rounded-2xl bg-secondary border border-border/40 text-[10px]">
                  {[
                    { met: passwordChecks.length, label: "8+ characters" },
                    { met: passwordChecks.uppercase, label: "Uppercase letter" },
                    { met: passwordChecks.lowercase, label: "Lowercase letter" },
                    { met: passwordChecks.number, label: "One number" },
                    { met: passwordChecks.special, label: "Special character" },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-2">
                      {item.met ? <Check className="w-3.5 h-3.5 text-green-500" /> : <X className="w-3.5 h-3.5 text-red-500" />}
                      <span className={item.met ? "text-green-500/90 font-medium" : "text-muted-foreground"}>{item.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <label className="block text-[11px] font-semibold text-slate-400 mb-1.5">Confirm Password</label>
              <div className="relative group/input">
                <input id="confirmPassword" ref={confirmPasswordRef} type={showConfirmPassword ? "text" : "password"} placeholder="Confirm your password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} onBlur={() => setTouched((current) => ({ ...current, confirmPassword: true }))} className={fieldClass(passwordChecks.confirm && touched.confirmPassword, showError("confirmPassword", passwordChecks.confirm)) + " px-4 pr-12 py-3"} />
                <button type="button" onClick={() => { setShowConfirmPassword((prev) => !prev); }} className="absolute right-3.5 top-3.5 text-muted-foreground hover:text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 rounded-md" aria-label={showConfirmPassword ? "Hide confirm password" : "Show confirm password"}>
                  {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {showError("confirmPassword", passwordChecks.confirm) && (
                <p id="confirm-password-error" className="text-xs text-red-400 mt-1">
                  {confirmPassword.length === 0
                    ? "Confirm Password is required"
                    : "Passwords do not match"}
                </p>
              )}
              {passwordChecks.confirm && confirmPassword.length > 0 && (
                <p className="text-xs text-green-500 mt-1">
                  Passwords match ✓
                </p>
              )}
            </div>

            <div className="space-y-2 rounded-2xl bg-secondary border border-border/40 p-4">
              <div className="flex items-start gap-3">
                <input id="termsAccepted" ref={termsRef} type="checkbox" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} onBlur={() => setTouched((current) => ({ ...current, termsAccepted: true }))} className="mt-1 h-4 w-4 rounded border-border bg-background text-primary focus:ring-primary" />
                <label htmlFor="termsAccepted" className="text-xs text-muted-foreground leading-relaxed select-none">I agree to the <span className="text-foreground font-medium">Terms of Service</span> and <span className="text-foreground font-medium">Privacy Policy</span></label>
              </div>
              {showError("termsAccepted", passwordChecks.terms) && <p className="text-xs text-red-400">Please accept the Terms of Service and Privacy Policy</p>}
            </div>

            <button type="submit" disabled={!isFormValid || isLoading || isSubmitting} className="w-full py-3.5 rounded-full bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-bold text-sm shadow-[0_4px_20px_rgba(34,211,238,0.25)] transition-all hover:scale-[1.02] active:scale-[0.98] duration-200 cursor-pointer flex items-center justify-center gap-2 mt-2 disabled:opacity-60 disabled:cursor-not-allowed">
              {isLoading || isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <span className="flex items-center gap-1.5">Create Account <ArrowRight className="w-4 h-4" /></span>}
            </button>
          </form>

          <div className="relative flex items-center justify-center my-5">
            <span className="text-[10px] uppercase font-bold text-muted-foreground/60 bg-transparent">--- or ---</span>
          </div>

          <div className="w-full flex justify-center">
            <div id="google-signin-button" className="w-full max-w-[360px] flex justify-center"></div>
          </div>


          <div className="text-center pt-4 text-xs font-medium">
            <span className="text-muted-foreground">Already have an account? </span>
            <Link to="/login" search={{ verify_token: undefined, reset_token: undefined }} className="text-cyan-400 hover:underline transition-colors font-bold">Log in</Link>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes slideInLeft { from { opacity: 0; transform: translateX(-30px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes orbit1 {
          from { transform: rotate(45deg); }
          to { transform: rotate(405deg); }
        }
        @keyframes orbit2 {
          from { transform: rotate(-45deg); }
          to { transform: rotate(-405deg); }
        }
        @keyframes orbit3 {
          from { transform: rotate(90deg); }
          to { transform: rotate(450deg); }
        }
      `}</style>
    </div>
  );
}
