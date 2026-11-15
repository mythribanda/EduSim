import { createFileRoute, Link } from "@tanstack/react-router";
import { PageWrapper } from "@/components/Card";
import { 
  Mail, 
  Calendar, 
  Shield, 
  Camera, 
  Edit2, 
  Check, 
  X, 
  User, 
  LogOut, 
  Phone, 
  Lock, 
  AlertCircle, 
  CheckCircle2, 
  Atom, 
  FlaskConical, 
  Activity, 
  Sparkles,
  ArrowRight
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuthStore } from "@/store/useAuthStore";
import { useRef, useState, useEffect } from "react";
import { fetchJsonWithRetry } from "@/services/apiClient";
import { getApiUrl } from "@/config/api";
import { toast } from "sonner";

export const Route = createFileRoute("/profile")({
  component: ProfilePage,
});

function ProfilePage() {
  const { user: authUser, logout } = useAuthStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [mobileInput, setMobileInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const [stats, setStats] = useState<any>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [resendingVerification, setResendingVerification] = useState(false);

  useEffect(() => {
    if (authUser) {
      setNameInput(authUser.name || "");
      setMobileInput(authUser.mobile_number || "");
    }
  }, [authUser]);

  const loadStats = async () => {
    try {
      const token = useAuthStore.getState().token;
      const response = await fetchJsonWithRetry<any>(
        getApiUrl("/api/auth/profile/stats"),
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setStats(response);
    } catch (err: any) {
      console.error("Failed to load profile stats:", err);
    } finally {
      setStatsLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const handleResendEmailVerification = async () => {
    setResendingVerification(true);
    try {
      const token = useAuthStore.getState().token;
      const response = await fetchJsonWithRetry<{ success: boolean; message: string }>(
        getApiUrl("/api/auth/resend-verification"),
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      if (response.success) {
        toast.success(response.message || "Verification email sent successfully!");
      } else {
        toast.error(response.message || "Failed to resend verification email.");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to resend verification email.");
    } finally {
      setResendingVerification(false);
    }
  };

  const handleSaveProfile = async () => {
    const trimmedName = nameInput.trim();
    const trimmedMobile = mobileInput.trim();

    if (!trimmedName) {
      toast.warning("Name cannot be empty");
      return;
    }

    if (trimmedMobile !== "" && (!/^\d+$/.test(trimmedMobile) || trimmedMobile.length !== 10)) {
      toast.warning("Mobile number must be a 10-digit number");
      return;
    }

    setIsSaving(true);
    try {
      const token = useAuthStore.getState().token;
      
      const response = await fetchJsonWithRetry<any>(
        getApiUrl("/api/auth/me"),
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            name: trimmedName,
            mobile_number: trimmedMobile === "" ? "" : trimmedMobile,
          }),
        }
      );

      // Also sync it to persistence profile display name
      await fetchJsonWithRetry<any>(
        getApiUrl("/api/persistence/profile"),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            display_name: trimmedName,
          }),
        }
      );

      if (authUser) {
        useAuthStore.setState({
          user: {
            ...authUser,
            name: response.name,
            mobile_number: response.mobile_number,
            is_mobile_verified: response.is_mobile_verified,
          },
        });
      }
      setIsEditing(false);
      toast.success("Profile updated successfully!");
    } catch (err: any) {
      toast.error(err.message || "Failed to update profile");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCameraClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      toast.error("File rejected: Only image uploads are allowed");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error("File rejected: Image size must be less than 5MB");
      return;
    }

    const reader = new FileReader();
    reader.onload = async () => {
      const base64String = reader.result as string;
      try {
        const token = useAuthStore.getState().token;
        const response = await fetchJsonWithRetry<{ success: boolean; profile: any }>(
          getApiUrl("/api/persistence/profile"),
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              avatar: base64String,
            }),
          }
        );

        if (response.success) {
          if (authUser) {
            useAuthStore.setState({
              user: {
                ...authUser,
                avatar: base64String,
              },
            });
          }
          toast.success("Avatar updated successfully!");
        } else {
          toast.error("Failed to update avatar");
        }
      } catch (err: any) {
        toast.error(err.message || "Failed to update avatar");
      }
    };
    reader.readAsDataURL(file);
  };

  const getInitials = (name: string) => {
    if (!name) return "U";
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  const getFormattedJoinedDate = (createdAtStr?: string) => {
    if (!createdAtStr) return "N/A";
    try {
      const date = new Date(createdAtStr);
      if (isNaN(date.getTime())) return "N/A";
      return date.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
    } catch (e) {
      return "N/A";
    }
  };

  const getFormattedLastActiveDate = (lastActiveStr?: string) => {
    if (!lastActiveStr) return "Just now";
    try {
      const date = new Date(lastActiveStr);
      if (isNaN(date.getTime())) return "Just now";
      return date.toLocaleDateString("en-US", { 
        month: "short", 
        day: "numeric", 
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch (e) {
      return "Just now";
    }
  };

  return (
    <PageWrapper>
      <div className="max-w-4xl mx-auto space-y-8 pb-12">
        
        {/* Profile Card Header */}
        <div className="glass-strong rounded-[2.5rem] p-8 relative overflow-hidden border border-border shadow-2xl">
          <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-[var(--neon-purple)]/20 to-[var(--neon-blue)]/20 blur-3xl -z-10" />
          
          <div className="absolute top-6 right-6 hidden md:block">
            <Button
              variant="outline"
              size="sm"
              onClick={logout}
              className="rounded-xl border-red-500/20 text-muted-foreground hover:border-red-500/50 hover:bg-red-500/10 hover:text-red-400 transition-all duration-300 flex items-center gap-2"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </Button>
          </div>
          
          <div className="flex flex-col md:flex-row items-center gap-8">
            <div className="relative group shrink-0">
              <Avatar className="w-32 h-32 border-4 border-border shadow-2xl animate-fade-in">
                <AvatarImage src={authUser?.avatar} />
                <AvatarFallback className="text-4xl bg-gradient-to-br from-[var(--neon-purple)]/20 to-[var(--neon-blue)]/20 text-foreground font-bold">
                  {getInitials(authUser?.name || "User")}
                </AvatarFallback>
              </Avatar>
              <button 
                onClick={handleCameraClick}
                className="absolute bottom-0 right-0 p-2.5 rounded-xl bg-primary text-primary-foreground shadow-lg hover:scale-110 transition-transform cursor-pointer"
                aria-label="Upload profile picture"
              >
                <Camera className="w-4 h-4" />
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="image/*"
                className="hidden"
              />
            </div>
            
            <div className="flex-1 text-center md:text-left w-full space-y-4">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-3 justify-center md:justify-start">
                  <h1 className="text-3xl font-extrabold text-foreground tracking-tight">{authUser?.name}</h1>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-primary/20 text-cyan-400 border border-primary/30 uppercase tracking-wider">
                    {authUser?.role || "student"}
                  </span>
                </div>
                <div className="flex items-center gap-2 justify-center md:justify-start text-sm text-muted-foreground">
                  <Mail className="w-4 h-4 text-muted-foreground/60" />
                  <span>{authUser?.email}</span>
                </div>
              </div>

              {/* Status Badges */}
              <div className="flex flex-wrap gap-2.5 justify-center md:justify-start">
                {/* Email Verification Badge */}
                {authUser?.is_email_verified ? (
                  <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Email Verified
                  </span>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <AlertCircle className="w-3.5 h-3.5" /> Email Unverified
                    </span>
                    <button 
                      onClick={handleResendEmailVerification}
                      disabled={resendingVerification}
                      className="text-xs font-bold text-cyan-400 hover:text-cyan-300 hover:underline transition-colors disabled:opacity-50"
                    >
                      {resendingVerification ? "Sending..." : "Resend verification"}
                    </button>
                  </div>
                )}

                {/* Mobile Verification Badge */}
                {authUser?.mobile_number && (
                  authUser.is_mobile_verified ? (
                    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Mobile Verified
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <AlertCircle className="w-3.5 h-3.5" /> Mobile Unverified
                    </span>
                  )
                )}
              </div>

              {/* Joined Date & Auth Method */}
              <div className="flex flex-wrap justify-center md:justify-start gap-x-6 gap-y-2 pt-2 border-t border-border/40 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <Calendar className="w-4 h-4 text-muted-foreground/60" /> 
                  Member since {getFormattedJoinedDate(authUser?.created_at)}
                </span>
                <span className="flex items-center gap-1.5">
                  <Lock className="w-4 h-4 text-muted-foreground/60" /> 
                  Auth Method: <span className="font-semibold text-slate-300 capitalize">{authUser?.auth_provider === "google" ? "Google OAuth" : "Password / Both"}</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Stats Grid Section */}
        <div className="space-y-4">
          <h2 className="text-xl font-bold text-gradient flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" /> Learning Stats
          </h2>
          
          {statsLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="glass-strong rounded-3xl p-6 h-28 animate-pulse bg-secondary/20 border border-border/20" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Simulations Card */}
              <div className="glass-strong rounded-3xl p-6 border border-border/40 hover:border-cyan-400/40 transition-all duration-300 hover:scale-[1.02] flex items-center gap-4 shadow-lg">
                <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20">
                  <Atom className="w-6 h-6 text-cyan-400" />
                </div>
                <div>
                  <h3 className="text-2xl font-black text-foreground">{stats?.simulations_run || 0}</h3>
                  <p className="text-xs text-muted-foreground font-medium">Interactive Simulations Run</p>
                </div>
              </div>

              {/* Formulas Card */}
              <div className="glass-strong rounded-3xl p-6 border border-border/40 hover:border-pink-500/40 transition-all duration-300 hover:scale-[1.02] flex items-center gap-4 shadow-lg">
                <div className="w-12 h-12 rounded-2xl bg-pink-500/10 flex items-center justify-center border border-pink-500/20">
                  <FlaskConical className="w-6 h-6 text-pink-400" />
                </div>
                <div>
                  <h3 className="text-2xl font-black text-foreground">{stats?.formulas_explored || 0}</h3>
                  <p className="text-xs text-muted-foreground font-medium">Formulas Explored</p>
                </div>
              </div>

              {/* Topics Completed Card */}
              <div className="glass-strong rounded-3xl p-6 border border-border/40 hover:border-[var(--neon-purple)]/40 transition-all duration-300 hover:scale-[1.02] flex items-center gap-4 shadow-lg">
                <div className="w-12 h-12 rounded-2xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20">
                  <CheckCircle2 className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-2xl font-black text-foreground">
                    {stats?.topics_completed || 0} / {stats?.total_topics || 0}
                  </h3>
                  <p className="text-xs text-muted-foreground font-medium">Curriculum Progress</p>
                </div>
              </div>
            </div>
          )}

          {/* Zero Data Case Handling */}
          {!statsLoading && (stats?.simulations_run || 0) === 0 && (
            <div className="glass-strong rounded-3xl p-8 border border-border/40 text-center space-y-4 max-w-xl mx-auto mt-4">
              <Sparkles className="w-10 h-10 text-cyan-400 mx-auto animate-pulse" />
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-foreground">You haven't run any simulations yet!</h3>
                <p className="text-sm text-muted-foreground">Physics is best learned through visual interaction. Go and explore topics in the simulator library!</p>
              </div>
              <Button asChild className="rounded-2xl bg-primary text-white hover:scale-105 transition-transform flex items-center gap-2 w-fit mx-auto cursor-pointer">
                <Link to="/library">
                  Browse Simulations <ArrowRight className="w-4 h-4" />
                </Link>
              </Button>
            </div>
          )}

          {/* Last Active Indicator */}
          {!statsLoading && (
            <div className="text-center text-xs text-muted-foreground/60 pt-2 font-medium">
              Last active: {getFormattedLastActiveDate(stats?.last_active_at)}
            </div>
          )}
        </div>

        {/* Profile Settings (Inline Edit mode) */}
        <div className="glass-strong rounded-3xl border border-border overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-border bg-secondary/20 flex items-center justify-between">
            <h2 className="text-lg font-bold text-gradient flex items-center gap-2">
              <User className="w-5 h-5 text-cyan-400" /> Profile Settings
            </h2>
            {!isEditing && (
              <Button 
                onClick={() => setIsEditing(true)} 
                variant="outline" 
                size="sm" 
                className="rounded-xl border-cyan-500/20 text-cyan-400 hover:border-cyan-500/50 hover:bg-cyan-500/10 transition-all cursor-pointer flex items-center gap-1.5"
              >
                <Edit2 className="w-3.5 h-3.5" /> Edit Profile
              </Button>
            )}
          </div>
          
          <div className="p-6">
            {isEditing ? (
              <div className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-slate-400 tracking-wider">FULL NAME</label>
                    <input
                      type="text"
                      value={nameInput}
                      onChange={(e) => setNameInput(e.target.value)}
                      className="w-full bg-background border border-border rounded-xl px-4 py-2.5 outline-none focus:border-primary text-foreground text-sm"
                      maxLength={100}
                      placeholder="Your Full Name"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-slate-400 tracking-wider">MOBILE NUMBER</label>
                    <input
                      type="text"
                      value={mobileInput}
                      onChange={(e) => setMobileInput(e.target.value)}
                      className="w-full bg-background border border-border rounded-xl px-4 py-2.5 outline-none focus:border-primary text-foreground text-sm"
                      maxLength={10}
                      placeholder="10-digit Mobile Number"
                    />
                  </div>
                </div>

                {/* Email (Read only notice) */}
                <div className="p-4 rounded-2xl bg-secondary/30 border border-border/40 space-y-1">
                  <p className="text-[11px] font-bold text-slate-400 tracking-wider">EMAIL ADDRESS (READ-ONLY)</p>
                  <p className="text-sm text-muted-foreground">{authUser?.email}</p>
                  <p className="text-[10px] text-muted-foreground/60 italic font-mono pt-1">
                    * Email cannot be edited directly here. Please contact support to initiate an email update and verification flow.
                  </p>
                </div>

                {/* Save & Cancel buttons */}
                <div className="flex justify-end gap-3 pt-2">
                  <Button 
                    onClick={() => { setIsEditing(false); setNameInput(authUser?.name || ""); setMobileInput(authUser?.mobile_number || ""); }} 
                    variant="outline" 
                    className="rounded-xl border-border hover:bg-secondary cursor-pointer"
                  >
                    Cancel
                  </Button>
                  <Button 
                    onClick={handleSaveProfile} 
                    disabled={isSaving} 
                    className="rounded-xl bg-primary text-white font-bold cursor-pointer"
                  >
                    {isSaving ? "Saving..." : "Save Changes"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Name field display */}
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold text-muted-foreground/60 font-mono tracking-wider">FULL NAME</p>
                    <p className="text-sm font-semibold text-foreground">{authUser?.name || "Not set"}</p>
                  </div>

                  {/* Mobile field display */}
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold text-muted-foreground/60 font-mono tracking-wider">MOBILE NUMBER</p>
                    <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                      <Phone className="w-4 h-4 text-muted-foreground/60" />
                      {authUser?.mobile_number || <span className="text-muted-foreground/50 font-normal italic">Not set</span>}
                    </p>
                  </div>
                </div>

                {/* Email field display */}
                <div className="space-y-1 pt-3 border-t border-border/40">
                  <p className="text-[10px] font-bold text-muted-foreground/60 font-mono tracking-wider">EMAIL ADDRESS</p>
                  <p className="text-sm font-semibold text-foreground">{authUser?.email}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Account Security Option Link */}
        <div className="glass-strong rounded-3xl overflow-hidden border border-border shadow-xl">
          <div className="px-6 py-4 border-b border-border bg-secondary/20">
            <h2 className="text-lg font-bold text-gradient flex items-center gap-2">
              <Shield className="w-5 h-5 text-cyan-400" /> Account Security & Options
            </h2>
          </div>
          <div className="p-6 space-y-4">
            <div className="p-4 rounded-2xl bg-secondary/50 border border-border flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-foreground">Account Settings & Passwords</p>
                <p className="text-xs text-muted-foreground">Manage your settings and other account preferences</p>
              </div>
              <Link
                to="/settings"
                className="inline-flex items-center justify-center rounded-xl border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary transition-all duration-300 hover:scale-105 active:scale-95"
              >
                Settings
              </Link>
            </div>
          </div>
        </div>

      </div>
    </PageWrapper>
  );
}
