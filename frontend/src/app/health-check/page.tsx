"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

type HealthState =
  | { status: "loading" }
  | { status: "success" }
  | { status: "error"; message: string };

export default function FoundationPage() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    let active = true;
    getHealth(controller.signal)
      .then(() => { if (active) setHealth({ status: "success" }); })
      .catch((error: unknown) => {
        if (active) setHealth({
          status: "error",
          message: controller.signal.aborted ? "Health request timed out." :
            error instanceof Error ? error.message : "Cannot reach the backend.",
        });
      })
      .finally(() => window.clearTimeout(timeout));
    return () => { active = false; window.clearTimeout(timeout); controller.abort(); };
  }, []);

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-20 text-slate-900">
      <section className="mx-auto max-w-xl rounded-xl border border-slate-200 bg-white p-8">
        <h1 className="text-2xl font-semibold">Signal Desktop Clone foundation</h1>
        <p className="mt-3 text-slate-600">Next.js is running. This temporary page verifies the API connection.</p>
        <div role="status" aria-live="polite" className="mt-6">
          {health.status === "loading" && <p>Checking backend health…</p>}
          {health.status === "success" && <p className="text-green-700">Backend connected. Database healthy.</p>}
          {health.status === "error" && <p className="text-red-700">Connection error: {health.message}</p>}
        </div>
      </section>
    </main>
  );
}
