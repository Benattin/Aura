import type { NewsItem } from "./auraHub";
import { NEWS_TOPICS, loadJson, proxyFetch, relTime, saveJson } from "./auraHub";

const CACHE_KEY = "aura_news_cache";

export async function fetchTopic(topic: string, limit = 6): Promise<NewsItem[]> {
  const url = `https://news.google.com/rss/search?q=${encodeURIComponent(topic)}&hl=pt-BR&gl=BR&ceid=BR:pt-419`;
  const xml = await proxyFetch(url);
  const doc = new DOMParser().parseFromString(xml, "text/xml");
  const items = [...doc.querySelectorAll("item")].slice(0, limit);
  return items.map((it) => {
    const title = (it.querySelector("title")?.textContent || "").replace(/\s+-\s+[^-]+$/, "");
    const link = it.querySelector("link")?.textContent || "#";
    const pub = it.querySelector("pubDate")?.textContent || "";
    const source = it.querySelector("source")?.textContent || "";
    return { title, link, source, pubDate: pub ? new Date(pub) : new Date() };
  });
}

export async function fetchAllNews(limit = 6): Promise<Record<string, NewsItem[]>> {
  const cached = loadJson<{ ts: number; data: Record<string, NewsItem[]> }>(CACHE_KEY, { ts: 0, data: {} });
  if (Date.now() - cached.ts < 30 * 60000 && Object.keys(cached.data).length) {
    return cached.data;
  }
  const data: Record<string, NewsItem[]> = {};
  for (const t of NEWS_TOPICS) {
    try {
      data[t] = await fetchTopic(t, limit);
    } catch {
      data[t] = [];
    }
  }
  saveJson(CACHE_KEY, { ts: Date.now(), data });
  return data;
}

export function newsSpeech(data: Record<string, NewsItem[]>): string {
  const lines: string[] = [];
  for (const [topic, items] of Object.entries(data)) {
    if (!items.length) continue;
    lines.push(`${topic}: ${items.slice(0, 2).map((n) => n.title).join("; ")}`);
  }
  return lines.length ? lines.join(". ") : "Sem manchetes no momento, senhor.";
}

export function newsLine(n: NewsItem): string {
  return `${n.title}${n.source ? ` — ${n.source}` : ""} (${relTime(n.pubDate)})`;
}
