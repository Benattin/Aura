export const ANTENNA = "http://127.0.0.1:4242";
export const TZ = "America/Sao_Paulo";
export const AURA_COLORS = ["#c4a85a", "#8fb89a", "#7aa8c4", "#b48fd4", "#c47a6a", "#9ab88f"];
export const NEWS_TOPICS = [
  "inteligência artificial",
  "investimentos",
  "tendências",
  "criptomoedas",
  "mundo",
];

export type CalendarCfg = { id: string; name: string; color: string; url: string };
export type EmailCfg = { id: string; label: string; color: string; email: string; appPassword: string };
export type CalEvent = {
  id: string; title: string; start: Date; end: Date; allDay: boolean;
  location: string; calId: string; color: string;
};
export type EmailItem = {
  id: string; conta: string; remetente: string; assunto: string; data: string;
  trecho: string; balde?: "acao" | "info" | "ruido"; resumo?: string; color: string;
};
export type NewsItem = { title: string; source: string; link: string; pubDate: Date };

export function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) as T : fallback;
  } catch {
    return fallback;
  }
}

export function saveJson(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function relTime(d: Date): string {
  const m = Math.round((Date.now() - d.getTime()) / 60000);
  if (m < 1) return "agora";
  if (m < 60) return `há ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `há ${h} h`;
  return d.toLocaleDateString("pt-BR");
}

export function fmtTime(d: Date): string {
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
}

export async function antennaOk(): Promise<boolean> {
  try {
    const r = await fetch(`${ANTENNA}/health`, { signal: AbortSignal.timeout(1500) });
    return r.ok;
  } catch {
    return false;
  }
}

export async function proxyFetch(url: string): Promise<string> {
  const r = await fetch(`${ANTENNA}/proxy?url=${encodeURIComponent(url)}`);
  if (!r.ok) throw new Error(`Proxy ${r.status}`);
  return r.text();
}
