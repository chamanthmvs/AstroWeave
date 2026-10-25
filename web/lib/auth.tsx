"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setToken } from "./api";
import type { BirthDetails, User } from "./types";

type AuthResult = { user: User; token: string; email_verification?: { sent: boolean; required: boolean } };

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  readingsEnabled: boolean;
  readingsMessage: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  register: (payload: {
    email: string;
    name: string;
    password: string;
    gender?: string;
    birth_details: BirthDetails;
  }) => Promise<AuthResult>;
  signOut: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [readingsEnabled, setReadingsEnabled] = useState(true);
  const [readingsMessage, setReadingsMessage] = useState<string | null>(null);

  useEffect(() => {
    api<{ readings_enabled: boolean; readings_disabled_message: string | null }>("/config", { auth: false })
      .then((c) => {
        setReadingsEnabled(c.readings_enabled);
        setReadingsMessage(c.readings_disabled_message);
      })
      .catch(() => {
        /* default to enabled on failure */
      });
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await api<{ user: User }>("/auth/me");
      setUser(data.user);
    } catch {
      setUser(null);
      setToken(null);
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const data = await api<AuthResult>("/auth/sign-in", {
      method: "POST",
      auth: false,
      body: { email: email.trim().toLowerCase(), password },
    });
    setToken(data.token);
    setUser(data.user);
  }, []);

  const register = useCallback<AuthContextValue["register"]>(async (payload) => {
    const data = await api<AuthResult>("/auth/register", {
      method: "POST",
      auth: false,
      body: payload,
    });
    setToken(data.token);
    setUser(data.user);
    return data;
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, readingsEnabled, readingsMessage, signIn, register, signOut, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
