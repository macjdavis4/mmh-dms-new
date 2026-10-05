/** Runtime config injected by Django into index.html (<meta name="mmh-config">). */
export interface RuntimeConfig {
  env: string;
  version: string;
  sentryDsn: string;
}

export function readRuntimeConfig(): RuntimeConfig {
  const fallback: RuntimeConfig = { env: "development", version: "dev", sentryDsn: "" };
  const raw = document.querySelector<HTMLMetaElement>('meta[name="mmh-config"]')?.content;
  if (!raw || raw.includes("{{")) return fallback; // Vite dev server: not rendered by Django
  try {
    return { ...fallback, ...(JSON.parse(raw) as Partial<RuntimeConfig>) };
  } catch {
    return fallback;
  }
}
