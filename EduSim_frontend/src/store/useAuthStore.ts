import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { getApiUrl } from "@/config/api";
import { fetchJsonWithRetry } from "@/services/apiClient";
import { toast } from "sonner";

export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: "student" | "teacher";
  mobile_number?: string;
  is_email_verified: boolean;
  is_mobile_verified: boolean;
  created_at?: string;
  auth_provider?: "password" | "google" | string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  hasHydrated: boolean;
  
  // Actions
  login: (credentials: { email: string; password: string }) => Promise<boolean>;
  loginWithGoogle: (idToken: string) => Promise<boolean>;
  register: (data: { name: string; email: string; password: string; role?: string; mobile?: string; mobile_number?: string }) => Promise<boolean>;
  logout: () => void;
  checkAuth: () => Promise<boolean>;
  
  // OTP Verification
  sendOtp: (countryCode: string, mobileNumber: string) => Promise<boolean>;
  verifyOtp: (mobileNumber: string, otpCode: string) => Promise<boolean>;
  
  // Password Reset & Email Verification
  forgotPassword: (email: string) => Promise<boolean>;
  resetPassword: (token: string, newPassword: string) => Promise<boolean>;
  verifyEmail: (token: string) => Promise<boolean>;
  setHasHydrated: (hydrated: boolean) => void;
}

const authStorage =
  typeof window !== "undefined"
    ? createJSONStorage<AuthState>(() => localStorage)
    : undefined;

const TOKEN_STORAGE_KEY = "token";

const isUnauthorizedError = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const normalized = message.toLowerCase();
  return normalized.includes("401") || normalized.includes("unauthorized") || normalized.includes("token");
};

const syncLegacyToken = (token: string | null) => {
  if (typeof window === "undefined") {
    return;
  }

  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      hasHydrated: false,

      setHasHydrated: (hydrated) => {
        set({ hasHydrated: hydrated });
      },

      login: async ({ email, password }) => {
        set({ isLoading: true });
        
        try {
          const response = await fetchJsonWithRetry<any>(getApiUrl("/api/auth/login"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
          });

          const { access_token, refresh_token, user } = response;

          let bootstrapUser = user as User;
          try {
            bootstrapUser = await fetchJsonWithRetry<User>(getApiUrl("/api/auth/me"), {
              headers: { Authorization: `Bearer ${access_token}` },
              scope: "authBootstrap",
            });
          } catch (meError) {
            if (isUnauthorizedError(meError)) {
              set({
                user: null,
                token: null,
                refreshToken: null,
                isAuthenticated: false,
                isLoading: false,
              });
              syncLegacyToken(null);
              toast.error("Session is invalid. Please sign in again.");
              return false;
            }
          }

          set({
            user: bootstrapUser,
            token: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
          syncLegacyToken(access_token);
          return true;
        } catch (error: any) {
          set({ isLoading: false });
          let msg = error.message || "Unable to login. Please try again";
          const lowerMsg = msg.toLowerCase();
          if (lowerMsg.includes("invalid") || lowerMsg.includes("wrong") || lowerMsg.includes("credential")) {
            msg = "Invalid email or password";
          } else if (lowerMsg.includes("not found") || lowerMsg.includes("does not exist") || lowerMsg.includes("no account")) {
            msg = "Account does not exist";
          } else if (lowerMsg.includes("disabled") || lowerMsg.includes("banned") || lowerMsg.includes("suspended")) {
            msg = "Account has been disabled";
          } else if (lowerMsg.includes("too many") || lowerMsg.includes("attempt") || lowerMsg.includes("rate limit") || lowerMsg.includes("locked")) {
            msg = "Account locked due to multiple failed attempts";
          } else if (lowerMsg.includes("fetch") || lowerMsg.includes("network")) {
            msg = "Network error. Check your connection";
          } else if (!error.message || lowerMsg.includes("internal server") || lowerMsg.includes("http 5")) {
            msg = "Unable to login. Please try again";
          }
          toast.error(msg);
          return false;
        }
      },

      loginWithGoogle: async (idToken) => {
        set({ isLoading: true });
        
        try {
          const response = await fetchJsonWithRetry<any>(getApiUrl("/api/auth/google"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: idToken }),
          });

          const { access_token, refresh_token, user } = response;

          let bootstrapUser = user as User;
          try {
            bootstrapUser = await fetchJsonWithRetry<User>(getApiUrl("/api/auth/me"), {
              headers: { Authorization: `Bearer ${access_token}` },
              scope: "authBootstrap",
            });
          } catch (meError) {
            if (isUnauthorizedError(meError)) {
              set({
                user: null,
                token: null,
                refreshToken: null,
                isAuthenticated: false,
                isLoading: false,
              });
              syncLegacyToken(null);
              toast.error("Session is invalid. Please sign in again.");
              return false;
            }
          }

          set({
            user: bootstrapUser,
            token: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
          syncLegacyToken(access_token);
          return true;
        } catch (error: any) {
          set({ isLoading: false });
          let msg = error.message || "Unable to sign in with Google. Please try again";
          toast.error(msg);
          return false;
        }
      },

      register: async (registerData) => {
        set({ isLoading: true });
        const payload = {
          ...registerData,
          role: registerData.role ?? "student",
          mobile_number: registerData.mobile_number ?? registerData.mobile,
        };

        try {
          console.log("register request", payload);

          const response = await fetchJsonWithRetry<any>(getApiUrl("/api/auth/register"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });

          console.log("register response", response);
          return true;
        } catch (error: any) {
          console.error("register failed", error);
          let errMsg = error.message || "Something went wrong. Please try again";
          const lowerMsg = errMsg.toLowerCase();
          if (lowerMsg.includes("email") && (lowerMsg.includes("registered") || lowerMsg.includes("exist") || lowerMsg.includes("taken"))) {
            errMsg = "Email already registered";
          } else if (lowerMsg.includes("username") && (lowerMsg.includes("exist") || lowerMsg.includes("taken"))) {
            errMsg = "Username already taken";
          } else if (lowerMsg.includes("fetch") || lowerMsg.includes("network")) {
            errMsg = "Network error. Check your connection";
          } else if (!error.message || lowerMsg.includes("internal server") || lowerMsg.includes("http 5")) {
            errMsg = "Something went wrong. Please try again";
          }
          toast.error(errMsg);
          return false;
        } finally {
          set({ isLoading: false });
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          refreshToken: null,
          isAuthenticated: false,
        });
        syncLegacyToken(null);
        toast.success("Logged out successfully");
      },

      checkAuth: async () => {
        let token = get().token;
        if (!token && typeof window !== "undefined") {
          token = window.localStorage.getItem(TOKEN_STORAGE_KEY);
          if (token) {
            set({ token });
          }
        }

        if (!token) {
          set({ isAuthenticated: false, user: null, refreshToken: null });
          syncLegacyToken(null);
          return false;
        }

        try {
          const user = await fetchJsonWithRetry<User>(getApiUrl("/api/auth/me"), {
            headers: { Authorization: `Bearer ${token}` },
            scope: "authCheck",
          });

          set({ user, isAuthenticated: true });
          return true;
        } catch (error: any) {
          const rToken = get().refreshToken;
          if (rToken) {
            try {
              const response = await fetchJsonWithRetry<any>(getApiUrl("/api/auth/refresh"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh_token: rToken }),
                scope: "authRefresh",
              });

              const { access_token, refresh_token } = response;

              const refreshedUser = await fetchJsonWithRetry<User>(getApiUrl("/api/auth/me"), {
                headers: { Authorization: `Bearer ${access_token}` },
                scope: "authRefreshMe",
              });

              set({
                user: refreshedUser,
                token: access_token,
                refreshToken: refresh_token,
                isAuthenticated: true,
              });
              syncLegacyToken(access_token);
              return true;
            } catch (refreshErr) {
              get().logout();
              if (isUnauthorizedError(refreshErr)) {
                toast.error("Your session has expired. Please login again");
              }
              return false;
            }
          }

          get().logout();
          if (isUnauthorizedError(error)) {
            toast.error("Your session has expired. Please login again");
          }
          return false;
        }
      },

      sendOtp: async (countryCode, mobileNumber) => {
        set({ isLoading: true });
        try {
          await fetchJsonWithRetry<any>(getApiUrl("/api/auth/send-otp"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ country_code: countryCode, mobile_number: mobileNumber }),
          });
          set({ isLoading: false });
          return true;
        } catch (error: any) {
          set({ isLoading: false });
          toast.error(error.message || "Failed to send OTP");
          return false;
        }
      },

      verifyOtp: async (mobileNumber, otpCode) => {
        set({ isLoading: true });
        try {
          const response = await fetchJsonWithRetry<any>(getApiUrl("/api/auth/verify-otp"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mobile_number: mobileNumber, otp_code: otpCode }),
          });

          const { access_token, refresh_token, user } = response;

          set({
            user,
            token: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
          syncLegacyToken(access_token);
          return true;
        } catch (error: any) {
          set({ isLoading: false });
          toast.error(error.message || "Invalid OTP or verification failed");
          return false;
        }
      },

      forgotPassword: async (email) => {
        set({ isLoading: true });
        try {
          await fetchJsonWithRetry<any>(getApiUrl("/api/auth/forgot-password"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
          });
          set({ isLoading: false });
          return true;
        } catch (error: any) {
          set({ isLoading: false });
          let errMsg = error.message || "Unable to send reset link";
          const lowerMsg = errMsg.toLowerCase();
          if (lowerMsg.includes("not found") || lowerMsg.includes("no account") || lowerMsg.includes("does not exist")) {
            errMsg = "No account found with this email";
          } else if (lowerMsg.includes("too many") || lowerMsg.includes("rate limit") || lowerMsg.includes("429")) {
            errMsg = "Too many requests. Please try again later";
          } else if (!error.message || lowerMsg.includes("internal server") || lowerMsg.includes("http 5")) {
            errMsg = "Unable to send reset link";
          }
          toast.error(errMsg);
          return false;
        }
      },

      resetPassword: async (token, newPassword) => {
        set({ isLoading: true });
        try {
          await fetchJsonWithRetry<any>(getApiUrl("/api/auth/reset-password"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token, new_password: newPassword }),
          });
          set({ isLoading: false });
          return true;
        } catch (error: any) {
          set({ isLoading: false });
          let errMsg = error.message || "Unable to reset password";
          const lowerMsg = errMsg.toLowerCase();
          if (lowerMsg.includes("expired")) {
            errMsg = "Reset link has expired";
          } else if (lowerMsg.includes("invalid") || lowerMsg.includes("token")) {
            errMsg = "Invalid reset link";
          } else if (!error.message || lowerMsg.includes("internal server") || lowerMsg.includes("http 5")) {
            errMsg = "Unable to reset password";
          }
          toast.error(errMsg);
          return false;
        }
      },

      verifyEmail: async (token) => {
        set({ isLoading: true });
        try {
          await fetchJsonWithRetry<any>(getApiUrl("/api/auth/verify-email"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
          });
          set({ isLoading: false });
          return true;
        } catch (error: any) {
          set({ isLoading: false });
          toast.error(error.message || "Verification failed or token expired");
          return false;
        }
      },
    }),
    {
      name: "edusim-auth",
      storage: authStorage,
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
      version: 2,
      migrate: (persistedState: any) => {
        if (!persistedState) {
          return persistedState;
        }

        return {
          ...persistedState,
          token: persistedState.token ?? persistedState.accessToken ?? null,
          accessToken: undefined,
        };
      },
      onRehydrateStorage: () => (state) => {
        syncLegacyToken(state?.token ?? null);
        if (state) {
          state.setHasHydrated(true);
          return;
        }

        useAuthStore.setState({ hasHydrated: true });
      },
    }
  )
);
