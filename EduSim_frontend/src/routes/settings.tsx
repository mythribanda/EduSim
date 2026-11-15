import { createFileRoute, Link } from "@tanstack/react-router";
import { PageWrapper } from "@/components/Card";
import { Switch } from "@/components/ui/switch";
import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import { 
  Moon, 
  ArrowLeft, 
  User, 
  Bell, 
  Laptop, 
  Trash2, 
  ShieldAlert, 
  KeyRound, 
  Lock, 
  Loader2, 
  Check, 
  X, 
  Globe, 
  Phone, 
  HelpCircle,
  Eye,
  EyeOff
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/useAuthStore";
import { fetchJsonWithRetry } from "@/services/apiClient";
import { getApiUrl } from "@/config/api";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

type TabType = "account" | "notifications" | "appearance" | "sessions" | "danger";

function SettingsPage() {
  const { user: authUser, logout } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabType>("account");

  // State for Account (Change Password)
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPass, setShowPass] = useState({ current: false, new: false, confirm: false });
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // State for Account (Mobile & OTP)
  const [mobileNumber, setMobileNumber] = useState(authUser?.mobile_number || "");
  const [otpCode, setOtpCode] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [isSendingOtp, setIsSendingOtp] = useState(false);
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false);

  // State for Account (Connected Accounts)
  const [googleConnected, setGoogleConnected] = useState(true);
  const [isTogglingGoogle, setIsTogglingGoogle] = useState(false);

  // State for Notifications
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [hintFrequency, setHintFrequency] = useState("medium");
  const [isSavingPrefs, setIsSavingPrefs] = useState(false);

  // State for Sessions
  const [sessions, setSessions] = useState<any[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [isRevokingSession, setIsRevokingSession] = useState<string | null>(null);
  const [isRevokingOthers, setIsRevokingOthers] = useState(false);

  // State for Danger Zone
  const [confirmEmail, setConfirmEmail] = useState("");
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);

  const hasPasswordSet = authUser?.auth_provider !== "google";

  // Password strength meter logic (similar to signup.tsx)
  const passwordStrength = useMemo(() => {
    let score = 0;
    if (!newPassword) return { score: 0, label: "None", color: "bg-border/60", width: "0%" };
    if (newPassword.length >= 8) score++;
    if (/[A-Z]/.test(newPassword)) score++;
    if (/[a-z]/.test(newPassword)) score++;
    if (/[0-9]/.test(newPassword)) score++;
    if (/[^A-Za-z0-9]/.test(newPassword)) score++;
    
    let label = "Very Weak";
    let color = "bg-red-500";
    let width = "20%";
    if (score === 2) { label = "Weak"; color = "bg-orange-500"; width = "40%"; }
    else if (score === 3) { label = "Fair"; color = "bg-yellow-500"; width = "60%"; }
    else if (score === 4) { label = "Good"; color = "bg-blue-500"; width = "80%"; }
    else if (score === 5) { label = "Strong"; color = "bg-emerald-500"; width = "100%"; }
    
    return { score, label, color, width };
  }, [newPassword]);

  // Load preferences, connected status, and active sessions on mount/tab change
  useEffect(() => {
    if (activeTab === "notifications") {
      fetchPreferences();
    } else if (activeTab === "sessions") {
      fetchSessions();
    } else if (activeTab === "account") {
      fetchPreferences(); // Checks Google connection status from settings
    }
  }, [activeTab]);

  const fetchPreferences = async () => {
    try {
      const token = useAuthStore.getState().token;
      const response = await fetchJsonWithRetry<any>(getApiUrl("/api/auth/settings"), {
        headers: { Authorization: `Bearer ${token}` }
      });
      setEmailNotifications(response.email_notifications);
      setHintFrequency(response.hint_frequency);
      setGoogleConnected(response.google_connected);
    } catch (err: any) {
      console.error("Failed to load user settings preferences:", err);
    }
  };

  const fetchSessions = async () => {
    setSessionsLoading(true);
    try {
      const token = useAuthStore.getState().token;
      const refreshToken = useAuthStore.getState().refreshToken;
      const response = await fetchJsonWithRetry<any[]>(getApiUrl("/api/auth/sessions"), {
        headers: { 
          Authorization: `Bearer ${token}`,
          "X-Refresh-Token": refreshToken || ""
        }
      });
      setSessions(response);
    } catch (err: any) {
      console.error("Failed to load sessions:", err);
      toast.error("Failed to load active sessions");
    } finally {
      setSessionsLoading(false);
    }
  };

  // Change password handler
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (hasPasswordSet && !currentPassword) {
      toast.warning("Current password is required");
      return;
    }
    if (newPassword.length < 8) {
      toast.warning("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.warning("Passwords do not match");
      return;
    }

    setIsChangingPassword(true);
    try {
      const token = useAuthStore.getState().token;
      await fetchJsonWithRetry<any>(getApiUrl("/api/auth/change-password"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      });
      toast.success("Password updated successfully!");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      
      // Update auth provider locally if setting password for the first time
      if (!hasPasswordSet && authUser) {
        useAuthStore.setState({
          user: {
            ...authUser,
            auth_provider: "both"
          }
        });
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to change password");
    } finally {
      setIsChangingPassword(false);
    }
  };

  // Send OTP handler
  const handleSendOtp = async () => {
    const trimmedMobile = mobileNumber.trim();
    if (!/^\d+$/.test(trimmedMobile) || trimmedMobile.length !== 10) {
      toast.warning("Please enter a valid 10-digit mobile number");
      return;
    }

    setIsSendingOtp(true);
    try {
      const token = useAuthStore.getState().token;
      // We trigger the verification endpoint
      await fetchJsonWithRetry<any>(getApiUrl("/api/auth/send-otp"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          country_code: "+91",
          mobile_number: trimmedMobile
        })
      });
      setOtpSent(true);
      toast.success("Verification code sent! (Simulated)");
    } catch (err: any) {
      toast.error(err.message || "Failed to send verification code");
    } finally {
      setIsSendingOtp(false);
    }
  };

  // Verify OTP handler
  const handleVerifyOtp = async () => {
    if (otpCode.length !== 6 || !/^\d+$/.test(otpCode)) {
      toast.warning("Please enter the 6-digit verification code");
      return;
    }

    setIsVerifyingOtp(true);
    try {
      const token = useAuthStore.getState().token;
      await fetchJsonWithRetry<any>(getApiUrl("/api/auth/verify-otp"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          mobile_number: mobileNumber.trim(),
          otp_code: otpCode
        })
      });

      if (authUser) {
        useAuthStore.setState({
          user: {
            ...authUser,
            mobile_number: mobileNumber.trim(),
            is_mobile_verified: true
          }
        });
      }
      setOtpSent(false);
      setOtpCode("");
      toast.success("Mobile number verified successfully!");
    } catch (err: any) {
      toast.error(err.message || "Verification code is incorrect");
    } finally {
      setIsVerifyingOtp(false);
    }
  };

  // Google connect/disconnect handler
  const handleToggleGoogle = async () => {
    if (googleConnected) {
      // Disconnect Google
      if (!hasPasswordSet) {
        toast.error("Cannot disconnect Google. It is your only login method. Please set a password first.");
        return;
      }
      setIsTogglingGoogle(true);
      try {
        const token = useAuthStore.getState().token;
        await fetchJsonWithRetry<any>(getApiUrl("/api/auth/google/disconnect"), {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` }
        });
        setGoogleConnected(false);
        toast.success("Google Sign-In disconnected successfully.");
      } catch (err: any) {
        toast.error(err.message || "Failed to disconnect Google");
      } finally {
        setIsTogglingGoogle(false);
      }
    } else {
      // Connect Google
      setIsTogglingGoogle(true);
      try {
        const token = useAuthStore.getState().token;
        await fetchJsonWithRetry<any>(getApiUrl("/api/auth/google/connect"), {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` }
        });
        setGoogleConnected(true);
        toast.success("Google Sign-In connected successfully.");
      } catch (err: any) {
        toast.error(err.message || "Failed to connect Google");
      } finally {
        setIsTogglingGoogle(false);
      }
    }
  };

  // Save Notification/Hint preferences
  const handleSavePreferences = async (newEmailNotif?: boolean, newHintFreq?: string) => {
    setIsSavingPrefs(true);
    const emailVal = newEmailNotif !== undefined ? newEmailNotif : emailNotifications;
    const hintVal = newHintFreq !== undefined ? newHintFreq : hintFrequency;

    try {
      const token = useAuthStore.getState().token;
      await fetchJsonWithRetry<any>(getApiUrl("/api/auth/settings"), {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          email_notifications: emailVal,
          hint_frequency: hintVal
        })
      });
      setEmailNotifications(emailVal);
      setHintFrequency(hintVal);
      toast.success("Preferences updated successfully!");
    } catch (err: any) {
      toast.error(err.message || "Failed to save preferences");
    } finally {
      setIsSavingPrefs(false);
    }
  };

  // Revoke single session
  const handleRevokeSession = async (sessId: string) => {
    setIsRevokingSession(sessId);
    try {
      const token = useAuthStore.getState().token;
      await fetchJsonWithRetry<any>(getApiUrl(`/api/auth/sessions/${sessId}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Session revoked successfully.");
      setSessions(prev => prev.filter(s => s.id !== sessId));
    } catch (err: any) {
      toast.error(err.message || "Failed to revoke session");
    } finally {
      setIsRevokingSession(null);
    }
  };

  // Revoke other sessions
  const handleRevokeOtherSessions = async () => {
    setIsRevokingOthers(true);
    try {
      const token = useAuthStore.getState().token;
      const currentSession = sessions.find(s => s.is_current);
      
      await fetchJsonWithRetry<any>(getApiUrl("/api/auth/sessions/other"), {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          current_session_id: currentSession?.id || null
        })
      });
      toast.success("All other sessions logged out!");
      setSessions(prev => prev.filter(s => s.is_current));
    } catch (err: any) {
      toast.error(err.message || "Failed to revoke other sessions");
    } finally {
      setIsRevokingOthers(false);
    }
  };

  // Delete account handler
  const handleDeleteAccount = async () => {
    if (confirmEmail.trim().toLowerCase() !== authUser?.email.trim().toLowerCase()) {
      toast.error("The email address you entered does not match");
      return;
    }

    setIsDeletingAccount(true);
    try {
      const token = useAuthStore.getState().token;
      await fetchJsonWithRetry<any>(getApiUrl("/api/auth/me"), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Your account has been deleted. We are sorry to see you go.");
      setShowDeleteModal(false);
      logout();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete account");
    } finally {
      setIsDeletingAccount(false);
    }
  };

  return (
    <PageWrapper>
      <div className="max-w-5xl mx-auto space-y-6 px-4 py-8">
        
        {/* Header Title block */}
        <div className="flex items-center gap-4">
          <Link to="/profile">
            <Button variant="ghost" size="icon" className="rounded-full hover:bg-secondary shrink-0">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <h1 className="text-4xl font-extrabold text-foreground tracking-tight">Settings</h1>
        </div>

        {/* Outer scannable layout grid (sidebar + panels) */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          
          {/* Sub-sidebar for settings categories */}
          <div className="flex flex-col gap-2 shrink-0">
            {[
              { id: "account", label: "Account", icon: User },
              { id: "notifications", label: "Notifications", icon: Bell },
              { id: "appearance", label: "Appearance", icon: Moon },
              { id: "sessions", label: "Sessions", icon: Laptop },
              { id: "danger", label: "Danger Zone", icon: ShieldAlert, danger: true },
            ].map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold transition-all duration-200 cursor-pointer ${
                    active 
                      ? tab.danger 
                        ? "bg-red-500/20 text-red-400 border border-red-500/35"
                        : "bg-primary/20 text-cyan-400 border border-primary/35"
                      : tab.danger
                        ? "text-red-400/75 hover:bg-red-500/5 hover:text-red-400 border border-transparent"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground border border-transparent"
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${active ? "" : "opacity-60"}`} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Active Settings Panel */}
          <div className="md:col-span-3 space-y-6">
            
            {/* 1. ACCOUNT PANEL */}
            {activeTab === "account" && (
              <div className="space-y-6 animate-fade-in">
                
                {/* Change Password Form */}
                <div className="glass-strong rounded-3xl overflow-hidden border border-border">
                  <div className="px-6 py-4 border-b border-border bg-secondary/20 flex items-center gap-2">
                    <KeyRound className="w-5 h-5 text-cyan-400" />
                    <h2 className="text-lg font-bold text-foreground">Change Password</h2>
                  </div>
                  <div className="p-6">
                    <form onSubmit={handleChangePassword} className="space-y-4">
                      {!hasPasswordSet && (
                        <div className="p-4 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-xs text-slate-300">
                          Since you log in via Google OAuth, you don't have a password set yet. Setting one below allows you to use both Google and Password login.
                        </div>
                      )}
                      {hasPasswordSet && (
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-bold text-slate-400 tracking-wider">CURRENT PASSWORD</label>
                          <div className="relative">
                            <input
                              type={showPass.current ? "text" : "password"}
                              value={currentPassword}
                              onChange={(e) => setCurrentPassword(e.target.value)}
                              className="w-full bg-background border border-border rounded-xl pl-4 pr-12 py-2.5 outline-none focus:border-primary text-foreground text-sm"
                              placeholder="••••••••"
                            />
                            <button
                              type="button"
                              onClick={() => setShowPass(p => ({ ...p, current: !p.current }))}
                              className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                            >
                              {showPass.current ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-[11px] font-bold text-slate-400 tracking-wider">NEW PASSWORD</label>
                          <div className="relative">
                            <input
                              type={showPass.new ? "text" : "password"}
                              value={newPassword}
                              onChange={(e) => setNewPassword(e.target.value)}
                              className="w-full bg-background border border-border rounded-xl pl-4 pr-12 py-2.5 outline-none focus:border-primary text-foreground text-sm"
                              placeholder="Min 8 characters"
                            />
                            <button
                              type="button"
                              onClick={() => setShowPass(p => ({ ...p, new: !p.new }))}
                              className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                            >
                              {showPass.new ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[11px] font-bold text-slate-400 tracking-wider">CONFIRM NEW PASSWORD</label>
                          <div className="relative">
                            <input
                              type={showPass.confirm ? "text" : "password"}
                              value={confirmPassword}
                              onChange={(e) => setConfirmPassword(e.target.value)}
                              className="w-full bg-background border border-border rounded-xl pl-4 pr-12 py-2.5 outline-none focus:border-primary text-foreground text-sm"
                              placeholder="Repeat new password"
                            />
                            <button
                              type="button"
                              onClick={() => setShowPass(p => ({ ...p, confirm: !p.confirm }))}
                              className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                            >
                              {showPass.confirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Password strength meter segment layout */}
                      {newPassword && (
                        <div className="space-y-2 pt-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">Password strength:</span>
                            <span className={`font-semibold ${passwordStrength.color.replace("bg-", "text-")}`}>
                              {passwordStrength.label}
                            </span>
                          </div>
                          <div className="flex gap-1.5">
                            {[1, 2, 3, 4, 5].map((idx) => (
                              <div
                                key={idx}
                                className={`h-1.5 flex-1 rounded-full transition-all duration-300 ${
                                  idx <= passwordStrength.score ? passwordStrength.color : "bg-border/60"
                                }`}
                              />
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex justify-end pt-2">
                        <Button 
                          type="submit" 
                          disabled={isChangingPassword}
                          className="rounded-xl bg-primary text-white font-bold cursor-pointer"
                        >
                          {isChangingPassword ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save Password"}
                        </Button>
                      </div>
                    </form>
                  </div>
                </div>

                {/* Mobile OTP verify flow */}
                <div className="glass-strong rounded-3xl overflow-hidden border border-border">
                  <div className="px-6 py-4 border-b border-border bg-secondary/20 flex items-center gap-2">
                    <Phone className="w-5 h-5 text-cyan-400" />
                    <h2 className="text-lg font-bold text-foreground">Mobile Phone Settings</h2>
                  </div>
                  <div className="p-6 space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-3 items-end gap-4">
                      <div className="sm:col-span-2 space-y-1.5">
                        <label className="text-[11px] font-bold text-slate-400 tracking-wider">PHONE NUMBER</label>
                        <input
                          type="text"
                          value={mobileNumber}
                          onChange={(e) => setMobileNumber(e.target.value)}
                          className="w-full bg-background border border-border rounded-xl px-4 py-2.5 outline-none focus:border-primary text-foreground text-sm"
                          placeholder="10-digit number"
                          maxLength={10}
                        />
                      </div>
                      <Button
                        onClick={handleSendOtp}
                        disabled={isSendingOtp || otpSent}
                        className="rounded-xl bg-secondary border border-border text-foreground hover:bg-card shrink-0 cursor-pointer h-10"
                      >
                        {isSendingOtp ? "Sending..." : otpSent ? "OTP Sent" : "Send Verification"}
                      </Button>
                    </div>

                    {/* OTP verification inline segment */}
                    {otpSent && (
                      <div className="p-4 rounded-2xl bg-secondary/40 border border-border/60 space-y-3">
                        <div className="space-y-1">
                          <label className="text-[11px] font-bold text-slate-400 tracking-wider">ENTER 6-DIGIT CODE</label>
                          <input
                            type="text"
                            value={otpCode}
                            onChange={(e) => setOtpCode(e.target.value)}
                            className="w-full bg-background border border-border rounded-xl px-4 py-2 outline-none focus:border-primary text-foreground text-sm tracking-widest font-mono text-center font-bold"
                            placeholder="000000"
                            maxLength={6}
                          />
                        </div>
                        <div className="flex justify-end gap-2">
                          <Button 
                            onClick={() => setOtpSent(false)} 
                            variant="outline" 
                            size="sm" 
                            className="rounded-lg border-border"
                          >
                            Cancel
                          </Button>
                          <Button 
                            onClick={handleVerifyOtp} 
                            disabled={isVerifyingOtp}
                            size="sm" 
                            className="rounded-lg bg-primary text-white font-bold"
                          >
                            {isVerifyingOtp ? "Verifying..." : "Verify Code"}
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Mobile Verified Status Display */}
                    {authUser?.mobile_number && (
                      <div className="flex items-center gap-2 text-xs font-semibold">
                        <span>Status: </span>
                        {authUser.is_mobile_verified ? (
                          <span className="text-emerald-400 flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Verified</span>
                        ) : (
                          <span className="text-amber-400 flex items-center gap-1"><X className="w-3.5 h-3.5" /> Unverified</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Connected accounts card */}
                <div className="glass-strong rounded-3xl overflow-hidden border border-border">
                  <div className="px-6 py-4 border-b border-border bg-secondary/20">
                    <h2 className="text-lg font-bold text-foreground">Connected Accounts</h2>
                  </div>
                  <div className="p-6">
                    <div className="flex items-center justify-between p-4 rounded-2xl bg-secondary/50 border border-border">
                      <div className="flex items-center gap-3">
                        <svg className="w-6 h-6 shrink-0" viewBox="0 0 24 24">
                          <path
                            fill="#4285F4"
                            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                          />
                          <path
                            fill="#34A853"
                            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                          />
                          <path
                            fill="#FBBC05"
                            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                          />
                          <path
                            fill="#EA4335"
                            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                          />
                        </svg>
                        <div>
                          <p className="text-sm font-semibold text-foreground">Google Account</p>
                          <p className="text-xs text-muted-foreground">
                            {googleConnected ? "Connected" : "Disconnected"}
                          </p>
                        </div>
                      </div>
                      <Button
                        onClick={handleToggleGoogle}
                        disabled={isTogglingGoogle || (!googleConnected ? false : !hasPasswordSet)}
                        className={`rounded-xl border border-border text-xs px-3 py-1.5 font-bold h-fit cursor-pointer ${
                          googleConnected 
                            ? "bg-red-500/10 text-red-400 hover:bg-red-500/20" 
                            : "bg-primary/10 text-cyan-400 hover:bg-primary/20"
                        }`}
                      >
                        {isTogglingGoogle ? "Processing..." : googleConnected ? "Disconnect" : "Connect"}
                      </Button>
                    </div>
                  </div>
                </div>

              </div>
            )}

            {/* 2. NOTIFICATIONS PANEL */}
            {activeTab === "notifications" && (
              <div className="glass-strong rounded-3xl overflow-hidden border border-border animate-fade-in">
                <div className="px-6 py-4 border-b border-border bg-secondary/20 flex items-center gap-2">
                  <Bell className="w-5 h-5 text-cyan-400" />
                  <h2 className="text-lg font-bold text-foreground">Notification Preferences</h2>
                </div>
                <div className="p-6 space-y-6">
                  
                  {/* Email Toggle */}
                  <div className="flex items-center justify-between p-4 rounded-2xl bg-secondary/50 border border-border">
                    <div>
                      <p className="text-sm font-semibold text-foreground">Email Notifications</p>
                      <p className="text-xs text-muted-foreground">Receive progress reports, study summaries, and new interactive simulation releases.</p>
                    </div>
                    <Switch 
                      checked={emailNotifications} 
                      onCheckedChange={(checked) => handleSavePreferences(checked, undefined)} 
                    />
                  </div>

                  {/* Hint Frequency Select */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-2xl bg-secondary/50 border border-border gap-4">
                    <div>
                      <p className="text-sm font-semibold text-foreground">Tutor Hint Frequency</p>
                      <p className="text-xs text-muted-foreground">Adjust how frequently the AI Tutor prompts you with helpful hints or calculation tips during chat session.</p>
                    </div>
                    <select
                      value={hintFrequency}
                      onChange={(e) => handleSavePreferences(undefined, e.target.value)}
                      className="bg-background border border-border text-foreground text-xs font-semibold rounded-xl px-3 py-2 outline-none focus:border-primary shrink-0"
                    >
                      <option value="low">Low (Only when stuck)</option>
                      <option value="medium">Medium (Standard guidelines)</option>
                      <option value="high">High (Frequent suggestions)</option>
                    </select>
                  </div>

                </div>
              </div>
            )}

            {/* 3. APPEARANCE PANEL */}
            {activeTab === "appearance" && (
              <div className="glass-strong rounded-3xl overflow-hidden border border-border animate-fade-in">
                <div className="px-6 py-4 border-b border-border bg-secondary/20 flex items-center gap-2">
                  <Moon className="w-5 h-5 text-cyan-400" />
                  <h2 className="text-lg font-bold text-foreground">Appearance</h2>
                </div>
                <div className="p-6 space-y-4">
                  <div className="p-4 rounded-2xl bg-secondary/50 border border-border flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-foreground">Theme</p>
                      <p className="text-xs text-muted-foreground">Customise the look of your EduSim application.</p>
                    </div>
                    <div className="text-xs font-semibold bg-primary/20 text-cyan-400 px-3 py-1.5 rounded-xl border border-primary/30">
                      Dark Mode (Default)
                    </div>
                  </div>
                  <div className="p-4 rounded-2xl bg-amber-500/5 border border-amber-500/20 text-xs text-amber-400 flex items-center gap-2">
                    <HelpCircle className="w-4 h-4 shrink-0" />
                    <span>Theme support is currently limited. Light Mode and Custom HSL Themes are in development and will be available soon!</span>
                  </div>
                </div>
              </div>
            )}

            {/* 4. PRIVACY & SESSIONS PANEL */}
            {activeTab === "sessions" && (
              <div className="glass-strong rounded-3xl overflow-hidden border border-border animate-fade-in">
                <div className="px-6 py-4 border-b border-border bg-secondary/20 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Laptop className="w-5 h-5 text-cyan-400" />
                    <h2 className="text-lg font-bold text-foreground">Active Sessions</h2>
                  </div>
                  <Button
                    onClick={handleRevokeOtherSessions}
                    disabled={isRevokingOthers || sessions.length <= 1}
                    variant="outline"
                    size="sm"
                    className="rounded-xl border-red-500/20 text-red-400 hover:border-red-500/50 hover:bg-red-500/10 text-xs cursor-pointer"
                  >
                    {isRevokingOthers ? "Revoking..." : "Revoke All Others"}
                  </Button>
                </div>
                
                <div className="p-6">
                  {sessionsLoading ? (
                    <div className="space-y-4">
                      {[1, 2].map((i) => (
                        <div key={i} className="h-16 rounded-2xl bg-secondary/30 animate-pulse border border-border/20" />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {sessions.map((sess) => (
                        <div 
                          key={sess.id} 
                          className="flex items-center justify-between p-4 rounded-2xl bg-secondary/50 border border-border gap-4"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-10 h-10 rounded-xl bg-primary/10 text-cyan-400 flex items-center justify-center shrink-0 border border-primary/20">
                              <Laptop className="w-5 h-5" />
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <p className="text-sm font-semibold text-foreground truncate">
                                  {sess.user_agent ? sess.user_agent.split(" ")[0] : "Browser Session"}
                                </p>
                                {sess.is_current && (
                                  <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 uppercase tracking-wide">
                                    Current
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground truncate">
                                IP: {sess.ip_address || "Unknown"} • Last seen: {new Date(sess.last_login_at || sess.created_at).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                          <Button
                            onClick={() => handleRevokeSession(sess.id)}
                            disabled={isRevokingSession === sess.id || sess.is_current}
                            variant="ghost"
                            size="sm"
                            className="rounded-xl hover:bg-red-500/15 text-muted-foreground hover:text-red-400 transition-all shrink-0 cursor-pointer h-8 text-xs border border-transparent hover:border-red-500/20"
                          >
                            {isRevokingSession === sess.id ? "Revoking..." : "Revoke"}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 5. DANGER ZONE PANEL */}
            {activeTab === "danger" && (
              <div className="glass-strong rounded-3xl overflow-hidden border border-red-500/30 animate-fade-in shadow-[0_0_40px_-15px_rgba(239,68,68,0.25)]">
                <div className="px-6 py-4 border-b border-red-500/20 bg-red-500/5 flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-red-400" />
                  <h2 className="text-lg font-bold text-red-400">Danger Zone</h2>
                </div>
                <div className="p-6 space-y-6">
                  
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-foreground">Delete Account</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Permanently delete your EduSim account. Once completed, this action cannot be undone. All your learning history, simulations run, and personal information will be completely erased.
                    </p>
                  </div>

                  <div className="pt-4 border-t border-border flex justify-end">
                    <Button
                      onClick={() => setShowDeleteModal(true)}
                      className="rounded-xl bg-red-500 hover:bg-red-400 text-white font-bold text-sm cursor-pointer shadow-lg shadow-red-500/15"
                    >
                      Delete Account
                    </Button>
                  </div>

                </div>
              </div>
            )}

          </div>
        </div>

      </div>

      {/* Delete Account confirmation modal dialog */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-strong rounded-[2rem] border border-red-500/20 shadow-2xl overflow-hidden animate-fade-in">
            <div className="px-6 py-5 border-b border-border bg-red-500/5 flex items-center gap-2.5">
              <ShieldAlert className="w-5 h-5 text-red-400" />
              <h3 className="text-lg font-bold text-red-400">Delete Account Permanently</h3>
            </div>
            
            <div className="p-6 space-y-4">
              <p className="text-xs text-slate-300 leading-relaxed">
                This operation is <span className="font-extrabold text-red-400 uppercase">irreversible</span>. To confirm, please enter your email address (<span className="font-semibold text-foreground select-all">{authUser?.email}</span>) below:
              </p>

              <input
                type="email"
                value={confirmEmail}
                onChange={(e) => setConfirmEmail(e.target.value)}
                placeholder="Enter your email to confirm"
                className="w-full bg-background border border-border rounded-xl px-4 py-2.5 outline-none focus:border-red-500 text-foreground text-sm"
              />

              <div className="flex justify-end gap-3 pt-2">
                <Button 
                  onClick={() => { setShowDeleteModal(false); setConfirmEmail(""); }} 
                  variant="outline"
                  className="rounded-xl border-border hover:bg-secondary cursor-pointer"
                >
                  Cancel
                </Button>
                <Button 
                  onClick={handleDeleteAccount} 
                  disabled={isDeletingAccount || confirmEmail.trim().toLowerCase() !== authUser?.email.trim().toLowerCase()} 
                  className="rounded-xl bg-red-500 hover:bg-red-400 text-white font-bold cursor-pointer"
                >
                  {isDeletingAccount ? "Deleting..." : "Permanently Delete"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

    </PageWrapper>
  );
}
