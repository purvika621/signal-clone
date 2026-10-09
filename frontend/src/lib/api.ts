export type HealthResponse = { status: "ok"; database: "ok" };

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiBaseUrl(): string {
  const value = process.env.NEXT_PUBLIC_API_URL;
  if (value === "same-origin") {
    if (typeof window === "undefined") throw new ApiError("Same-origin API requests require a browser.");
    return window.location.origin;
  }
  if (!value) throw new ApiError("NEXT_PUBLIC_API_URL is not configured.");
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new ApiError("NEXT_PUBLIC_API_URL must use HTTP or HTTPS.");
  }
  return value.replace(/\/$/, "");
}

// Decode unknown JSON at the boundary; a generic cast alone is not validation.
export async function apiRequest<T>(
  path: string,
  decode: (data: unknown) => T,
  options: RequestInit = {},
): Promise<T> {
  if (!path.startsWith("/")) throw new ApiError("API paths must start with /.");
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...options,
    signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(10000)]) : AbortSignal.timeout(10000),
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null);
    let message = `API request failed (${response.status}).`;
    if (typeof error === "object" && error !== null && "message" in error && typeof error.message === "string") {
      message = error.message;
      if ("field_errors" in error && typeof error.field_errors === "object" && error.field_errors !== null) {
        message += `: ${Object.values(error.field_errors).filter((value) => typeof value === "string").join("; ")}`;
      }
    }
    throw new ApiError(message, response.status);
  }
  return decode(await response.json());
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest("/health", (data) => {
    if (typeof data !== "object" || data === null ||
        !("status" in data) || data.status !== "ok" ||
        !("database" in data) || data.database !== "ok") {
      throw new ApiError("Unexpected health response.");
    }
    return { status: "ok", database: "ok" };
  }, { signal });
}
