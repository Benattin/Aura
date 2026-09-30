import type { EmailCfg, EmailItem } from "./auraHub";
import { ANTENNA, loadJson, saveJson } from "./auraHub";

const TRIAGE_KEY = "aura_email_triage";

export async function fetchEmails(cfg: EmailCfg[], limit = 20): Promise<EmailItem[]> {
  const out: EmailItem[] = [];
  for (const c of cfg) {
    if (!c.email || !c.appPassword) continue;
    try {
      const r = await fetch(`${ANTENNA}/emails`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: "imap.gmail.com",
          usuario: c.email,
          senhaApp: c.appPassword,
          quantidade: limit,
        }),
      });
      if (!r.ok) throw new Error(String(r.status));
      const rows = (await r.json()) as Array<Record<string, string>>;
      for (const row of rows) {
        out.push({
          id: row.id || row.assunto,
          conta: c.label,
          remetente: row.remetente || "?",
          assunto: row.assunto || "(sem assunto)",
          data: row.data || "",
          trecho: row.trecho || "",
          color: c.color,
        });
      }
    } catch {
      /* conta falhou */
    }
  }
  return out;
}

export function loadTriageCache(): Record<string, { balde: string; resumo: string }> {
  return loadJson(TRIAGE_KEY, {});
}

export function saveTriageCache(cache: Record<string, { balde: string; resumo: string }>) {
  saveJson(TRIAGE_KEY, cache);
}

export async function triageNew(items: EmailItem[]): Promise<EmailItem[]> {
  const cache = loadTriageCache();
  const fresh = items.filter((e) => !cache[e.id]);
  if (fresh.length) {
    try {
      const r = await fetch("/api/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emails: fresh }),
      });
      if (r.ok) {
        const data = (await r.json()) as { items: Array<{ id: string; balde: string; resumo: string }> };
        for (const t of data.items || []) cache[t.id] = { balde: t.balde, resumo: t.resumo };
        saveTriageCache(cache);
      }
    } catch {
      for (const e of fresh) {
        const blob = `${e.assunto} ${e.trecho}`.toLowerCase();
        cache[e.id] = {
          balde: /unsubscribe|promo|noreply/.test(blob) ? "ruido" : /\?|prazo|fatura/.test(blob) ? "acao" : "info",
          resumo: e.assunto,
        };
      }
      saveTriageCache(cache);
    }
  }
  return items.map((e) => ({
    ...e,
    balde: (cache[e.id]?.balde as EmailItem["balde"]) || "info",
    resumo: cache[e.id]?.resumo || e.assunto,
  }));
}

export function bucket(items: EmailItem[]) {
  return {
    acao: items.filter((e) => e.balde === "acao"),
    info: items.filter((e) => e.balde === "info"),
    ruido: items.filter((e) => e.balde === "ruido"),
  };
}
