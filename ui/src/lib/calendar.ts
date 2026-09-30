import type { CalEvent, CalendarCfg } from "./auraHub";
import { proxyFetch, TZ } from "./auraHub";

function unfold(text: string): string {
  return text.replace(/\r\n/g, "\n").replace(/\n[ \t]/g, "");
}

function parseDt(raw: string, tz: string): { d: Date; allDay: boolean } {
  const line = raw.split(":").pop() || raw;
  if (line.length === 8) {
    const y = +line.slice(0, 4), m = +line.slice(4, 6) - 1, d = +line.slice(6, 8);
    return { d: new Date(y, m, d), allDay: true };
  }
  const clean = line.replace("Z", "");
  const y = +clean.slice(0, 4), mo = +clean.slice(4, 6) - 1, da = +clean.slice(6, 8);
  const h = +clean.slice(9, 11) || 0, mi = +clean.slice(11, 13) || 0;
  if (line.endsWith("Z")) return { d: new Date(Date.UTC(y, mo, da, h, mi)), allDay: false };
  return { d: new Date(new Date(y, mo, da, h, mi).toLocaleString("en-US", { timeZone: tz })), allDay: false };
}

export async function fetchCalendarEvents(cals: CalendarCfg[]): Promise<CalEvent[]> {
  const out: CalEvent[] = [];
  const now = new Date();
  const end = new Date(now.getTime() + 8 * 86400000);
  for (const cal of cals) {
    if (!cal.url.trim()) continue;
    try {
      const ics = await proxyFetch(cal.url);
      const body = unfold(ics);
      const chunks = body.split("BEGIN:VEVENT").slice(1).map((b) => b.split("END:VEVENT")[0]);
      const moved = new Set<string>();
      for (const c of chunks) {
        const rid = c.match(/^RECURRENCE-ID[^:]*:(.+)$/m);
        const u = c.match(/^UID[^:]*:(.+)$/m);
        if (rid && u) moved.add(`${u[1].trim()}|${parseDt(rid[1].trim(), TZ).d.getTime()}`);
      }
      for (const chunk of chunks) {
        const get = (k: string) => {
          const m = chunk.match(new RegExp(`^${k}[^:]*:(.+)$`, "m"));
          return m ? m[1].trim() : "";
        };
        const title = get("SUMMARY") || "(sem título)";
        const startRaw = get("DTSTART");
        const endRaw = get("DTEND");
        if (!startRaw || get("STATUS") === "CANCELLED") continue;
        const start = parseDt(startRaw, TZ);
        const endP = endRaw ? parseDt(endRaw, TZ) : start;
        const duration = endP.d.getTime() - start.d.getTime();
        const uid = get("UID") || `${cal.id}-${title}-${startRaw}`;
        const recurrenceId = get("RECURRENCE-ID");
        const exdates = new Set(
          [...chunk.matchAll(/^EXDATE[^:]*:(.+)$/gm)]
            .flatMap((m) => m[1].split(","))
            .map((v) => parseDt(v.trim(), TZ).d.getTime())
        );
        const rrule = get("RRULE");
        const starts = rrule && !recurrenceId ? expandRRule(start.d, rrule, now, end, duration) : [start.d];
        for (const s of starts) {
          if (exdates.has(s.getTime()) || (!recurrenceId && moved.has(`${uid}|${s.getTime()}`))) continue;
          const evEnd = new Date(s.getTime() + duration);
          if (evEnd < now || s > end) continue;
          out.push({
            id: `${uid}-${s.getTime()}`,
            title, start: s, end: evEnd, allDay: start.allDay,
            location: get("LOCATION"), calId: cal.id, color: cal.color,
          });
        }
      }
    } catch {
      /* agenda individual falhou — segue */
    }
  }
  const unique = new Map(out.map((e) => [e.id, e]));
  return [...unique.values()].sort((a, b) => a.start.getTime() - b.start.getTime());
}

const WEEKDAYS = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];

/** Expande DAILY/WEEKLY/MONTHLY/YEARLY com INTERVAL, COUNT, UNTIL e BYDAY (semanal). */
export function expandRRule(dtstart: Date, rule: string, from: Date, to: Date, duration = 0): Date[] {
  const p = Object.fromEntries(rule.split(";").map((kv) => kv.split("=")));
  const freq = p.FREQ;
  const interval = Math.max(1, +(p.INTERVAL || 1));
  const count = p.COUNT ? +p.COUNT : Infinity;
  const until = p.UNTIL ? parseDt(p.UNTIL, TZ).d : null;
  const byDay: number[] = p.BYDAY && freq === "WEEKLY"
    ? p.BYDAY.split(",").map((d: string) => WEEKDAYS.indexOf(d.slice(-2))).filter((i: number) => i >= 0)
    : [];
  const out: Date[] = [];
  let n = 0;
  const emit = (d: Date): boolean => {
    if (d < dtstart) return true;
    if ((until && d > until) || n >= count || d > to) return false;
    n++;
    if (d.getTime() + duration >= from.getTime()) out.push(new Date(d));
    return true;
  };
  for (let i = 0; i < 5000; i++) {
    const base = new Date(dtstart);
    if (freq === "DAILY") base.setDate(base.getDate() + i * interval);
    else if (freq === "WEEKLY") base.setDate(base.getDate() + i * 7 * interval);
    else if (freq === "MONTHLY") base.setMonth(base.getMonth() + i * interval);
    else if (freq === "YEARLY") base.setFullYear(base.getFullYear() + i * interval);
    else return [dtstart];
    if (byDay.length) {
      const weekStart = new Date(base);
      weekStart.setDate(base.getDate() - base.getDay());
      for (const wd of byDay.sort((a, b) => a - b)) {
        const d = new Date(weekStart);
        d.setDate(weekStart.getDate() + wd);
        if (!emit(d)) return out;
      }
    } else if (!emit(base)) {
      return out;
    }
  }
  return out;
}

export function todayEvents(events: CalEvent[]): CalEvent[] {
  const t = new Date();
  return events.filter((e) => sameDay(e.start, t));
}

export function nextEvent(events: CalEvent[]): CalEvent | null {
  const now = Date.now();
  return events.find((e) => e.end.getTime() > now) || null;
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function speechToday(events: CalEvent[]): string {
  const today = todayEvents(events);
  if (!today.length) return "Sua agenda de hoje está livre, senhor.";
  return today.map((e) =>
    e.allDay ? `dia todo, ${e.title}` : `${fmt(e.start)}, ${e.title}`
  ).join("; ");
}

function fmt(d: Date): string {
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
}

export function countdown(ev: CalEvent): string {
  const ms = ev.start.getTime() - Date.now();
  if (ms <= 0) return "agora";
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return h > 0 ? `em ${h}h ${m}min` : `em ${m}min`;
}
