// Thin client for the AstroWeave backend. The base URL is configured at build
// time (NEXT_PUBLIC_API_BASE); the bearer token is kept in localStorage so a
// refresh keeps the session.

const BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const TOKEN_KEY = "astroweave:token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore storage failures (private mode) */
  }
}

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function describe(detail: unknown): { message: string; code?: string } {
  if (typeof detail === "string") return { message: detail };
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    return {
      message: typeof d.message === "string" ? d.message : "Something went wrong.",
      code: typeof d.code === "string" ? d.code : undefined,
    };
  }
  return { message: "Something went wrong." };
}

export async function api<T = unknown>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  // Free hosting sleeps when idle, so the first request can fail or hang while
  // the server wakes. Retry network-level failures a few times before giving up.
  let response: Response | null = null;
  const attempts = method === "GET" ? 4 : 2;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      response = await fetch(`${BASE}${path}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      break;
    } catch {
      if (attempt === attempts - 1) {
        throw new ApiError(
          "The server is waking up — our free hosting sleeps when idle. Please try again in a few seconds.",
          0,
        );
      }
      await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
    }
  }
  if (!response) {
    throw new ApiError("The server is waking up. Please try again in a few seconds.", 0);
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text; // non-JSON body (e.g. an upstream HTML error page)
    }
  }
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object"
        ? ((payload as Record<string, unknown>).detail ?? payload)
        : `Request failed (${response.status}).`;
    const { message, code } = describe(detail);
    throw new ApiError(message, response.status, code);
  }
  return payload as T;
}

export { BASE as API_BASE };
