import { useCallback, useEffect, useState } from "react";
import {
  AURA_COLORS, ANTENNA, CalendarCfg, CalEvent, EmailCfg, EmailItem, NewsItem,
  antennaOk, fmtTime, loadJson, relTime, saveJson,
} from "../lib/auraHub";
import { countdown, fetchCalendarEvents, nextEvent, speechToday, todayEvents } from "../lib/calendar";
import { bucket, fetchEmails, triageNew } from "../lib/emails";
import { fetchAllNews, newsLine } from "../lib/news";
import { weatherSaoPaulo } from "../lib/weather";

type Tab = "agenda" | "emails" | "news" | "digest" | "settings";

type Props = {
  send: (p: object) => void;
  onDigestText?: (t: string) => void;
};

const CAL_KEY = "aura_calendars";
const EMAIL_KEY = "aura_emails";
const LAST_DIGEST = "aura_last_digest";

export default function CommandCenter({ send, onDigestText }: Props) {
  const [tab, setTab] = useState<Tab>("agenda");
  const [online, setOnline] = useState(false);
  const [cals, setCals] = useState<CalendarCfg[]>(() => loadJson(CAL_KEY, []));
  const [emailsCfg, setEmailsCfg] = useState<EmailCfg[]>(() => loadJson(EMAIL_KEY, []));
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [emails, setEmails] = useState<EmailItem[]>([]);
  const [news, setNews] = useState<Record<string, NewsItem[]>>({});
  const [digest, setDigest] = useState("");
  const [loading, setLoading] = useState(false);
  const [noiseOpen, setNoiseOpen] = useState(false);

  const buckets = bucket(emails);
  const actionCount = buckets.acao.length;
  const nxt = nextEvent(events);

  const syncContext = useCallback(async () => {
    const today = todayEvents(events);
    const todayCompact = today.slice(0, 15).map((e) =>
      e.allDay ? `DIA TODO ${e.title}` : `${fmtTime(e.start)} ${e.title}`
    ).join(" · ");
    const newsSpeech = Object.entries(news).map(([k, v]) =>
      `${k}: ${v.slice(0, 2).map((n) => n.title).join("; ")}`
    ).join(" | ");
    const weather = await weatherSaoPaulo().catch(() => "");
    send({
      type: "briefing_context",
      ctx: {
        todayCompact,
        actionCount,
        todaySpeech: speechToday(events),
        weekSpeech: events.slice(0, 12).map((e) => e.title).join(", "),
        emailSpeech: `${emails.length} e-mails. Ação: ${actionCount}, info: ${buckets.info.length}, ruído: ${buckets.ruido.length}.`,
        actionSpeech: actionCount
          ? buckets.acao.map((e) => e.resumo).join("; ")
          : "Nenhum e-mail pedindo ação, senhor.",
        newsSpeech,
        nextEvent: nxt ? `Próximo: ${nxt.title}, ${countdown(nxt)}` : "",
        digestPkg: {
          weather,
          agenda: speechToday(events),
          emails: `${actionCount} e-mails pedem ação.`,
          news: newsSpeech,
          focus: "Foco no que importa hoje, senhor.",
        },
      },
    });
  }, [events, emails, news, actionCount, buckets, nxt, send]);

  const refreshAll = useCallback(async () => {
    if (!(await antennaOk())) { setOnline(false); return; }
    setOnline(true);
    setLoading(true);
    try {
      const ev = await fetchCalendarEvents(cals);
      setEvents(ev);
      const raw = await fetchEmails(emailsCfg);
      const triaged = await triageNew(raw);
      setEmails(triaged);
      const n = await fetchAllNews(6);
      setNews(n);
      await syncContext();
    } finally {
      setLoading(false);
    }
  }, [cals, emailsCfg, syncContext]);

  useEffect(() => {
    antennaOk().then(setOnline);
    if (cals.length) refreshAll();
    const t = setInterval(refreshAll, 15 * 60000);
    const onRefresh = () => refreshAll();
    window.addEventListener("aura-refresh", onRefresh);
    return () => {
      clearInterval(t);
      window.removeEventListener("aura-refresh", onRefresh);
    };
  }, []);

  useEffect(() => { saveJson(CAL_KEY, cals); }, [cals]);
  useEffect(() => { saveJson(EMAIL_KEY, emailsCfg); }, [emailsCfg]);
  useEffect(() => { syncContext(); }, [syncContext]);

  const runDigest = async (force = false) => {
    const today = new Date().toISOString().slice(0, 10);
    if (!force && loadJson(LAST_DIGEST, "") === today) return;
    const weather = await weatherSaoPaulo().catch(() => "");
    const pkg = {
      weather,
      agenda: speechToday(events),
      emails: buckets.acao.map((e) => e.resumo).join("; ") || "Nenhum e-mail de ação.",
      news: Object.entries(news).map(([k, v]) => `${k}: ${v[0]?.title || "—"}`).join(" | "),
      focus: "Priorize o essencial hoje, senhor.",
    };
    const r = await fetch("/api/digest", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pkg }) });
    const j = await r.json();
    setDigest(j.text || "");
    onDigestText?.(j.text || "");
    saveJson(LAST_DIGEST, today);
    setTab("digest");
  };

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    if (loadJson(LAST_DIGEST, "") !== today && online) runDigest();
  }, [online]);

  const addCal = () => {
    const i = cals.length;
    setCals([...cals, { id: `cal-${Date.now()}`, name: `Agenda ${i + 1}`, color: AURA_COLORS[i % AURA_COLORS.length], url: "" }]);
  };

  const addEmail = () => {
    const i = emailsCfg.length;
    setEmailsCfg([...emailsCfg, { id: `em-${Date.now()}`, label: "Gmail", color: AURA_COLORS[i % AURA_COLORS.length], email: "", appPassword: "" }]);
  };

  return (
    <section className="command-center">
      {!online && (
        <div className="cmd-offline">
          <p>ANTENA OFFLINE — abra <code>start-antenna.bat</code> (ou <code>node antenna/server.js</code>)</p>
          <p className="muted">A AURA continua funcionando (voz, chat, memória).</p>
        </div>
      )}
      <nav className="cmd-tabs">
        {(["agenda", "emails", "news", "digest", "settings"] as Tab[]).map((t) => (
          <button key={t} type="button" className={tab === t ? "on" : ""} onClick={() => { setTab(t); if (t !== "settings") refreshAll(); }}>
            {t === "agenda" ? "Agenda" : t === "emails" ? `E-mails${actionCount ? ` (${actionCount})` : ""}` : t === "news" ? "Notícias" : t === "digest" ? "Digest" : "⚙"}
          </button>
        ))}
        <button type="button" className="cmd-refresh" onClick={() => refreshAll()} disabled={loading}>↻</button>
      </nav>

      {tab === "agenda" && (
        <div className="cmd-panel">
          {nxt && <p className="cmd-highlight">Próximo: <strong>{nxt.title}</strong> · {countdown(nxt)}</p>}
          <h3>Hoje</h3>
          {todayEvents(events).map((e) => (
            <div key={e.id} className="cmd-row" style={{ borderLeftColor: e.color }}>
              <span>{e.allDay ? "DIA TODO" : fmtTime(e.start)}</span>
              <span>{e.title}</span>
            </div>
          ))}
          {!todayEvents(events).length && <p className="muted">Nenhum evento hoje.</p>}
          <h3>Próximos dias</h3>
          {events.filter((e) => !todayEvents(events).includes(e)).slice(0, 20).map((e) => (
            <div key={e.id} className="cmd-row dim" style={{ borderLeftColor: e.color }}>
              <span>{e.start.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" })} {e.allDay ? "" : fmtTime(e.start)}</span>
              <span>{e.title}</span>
            </div>
          ))}
        </div>
      )}

      {tab === "emails" && (
        <div className="cmd-panel">
          <h3>⚡ Ação</h3>
          {buckets.acao.map((e) => <EmailRow key={e.id} e={e} />)}
          <h3>Info</h3>
          {buckets.info.map((e) => <EmailRow key={e.id} e={e} />)}
          <button type="button" className="btn-text" onClick={() => setNoiseOpen(!noiseOpen)}>Ruído ({buckets.ruido.length})</button>
          {noiseOpen && buckets.ruido.map((e) => <EmailRow key={e.id} e={e} dim />)}
        </div>
      )}

      {tab === "news" && (
        <div className="cmd-panel">
          {Object.entries(news).map(([topic, items]) => (
            <div key={topic}>
              <h3>{topic}</h3>
              {items.map((n, i) => (
                <a key={i} className="cmd-news" href={n.link} target="_blank" rel="noreferrer">{newsLine(n)}</a>
              ))}
            </div>
          ))}
        </div>
      )}

      {tab === "digest" && (
        <div className="cmd-panel">
          <p className="digest-text">{digest || "Clique em Gerar ou diga «bom dia»."}</p>
          <button type="button" className="btn" onClick={() => runDigest(true)}>Gerar Digest</button>
        </div>
      )}

      {tab === "settings" && (
        <div className="cmd-panel settings">
          <EngineSettings />
          <h3>Agendas Google (iCal)</h3>
          <p className="hint">Google Agenda → ⚙ → agenda → Integrar → Endereço secreto iCal. Salvo só aqui.</p>
          {cals.map((c, i) => (
            <div key={c.id} className="cfg-row">
              <input value={c.name} onChange={(e) => { const n = [...cals]; n[i] = { ...c, name: e.target.value }; setCals(n); }} placeholder="Nome" />
              <input value={c.url} onChange={(e) => { const n = [...cals]; n[i] = { ...c, url: e.target.value }; setCals(n); }} placeholder="Link iCal secreto" />
            </div>
          ))}
          <button type="button" className="btn-text" onClick={addCal}>+ adicionar agenda</button>
          <h3>E-mail Gmail</h3>
          <p className="hint">Senha de app em myaccount.google.com/apppasswords (2 etapas ativa). Só no navegador + antena local.</p>
          {emailsCfg.map((c, i) => (
            <div key={c.id} className="cfg-row">
              <input value={c.email} onChange={(e) => { const n = [...emailsCfg]; n[i] = { ...c, email: e.target.value }; setEmailsCfg(n); }} placeholder="email@gmail.com" />
              <input type="password" value={c.appPassword} onChange={(e) => { const n = [...emailsCfg]; n[i] = { ...c, appPassword: e.target.value }; setEmailsCfg(n); }} placeholder="Senha de app (16 letras)" />
            </div>
          ))}
          <button type="button" className="btn-text" onClick={addEmail}>+ adicionar conta</button>
          <p className="hint">Antena: {ANTENNA}</p>
        </div>
      )}
    </section>
  );
}

type Engine = { installed: string[]; model: string; codeModel: string; economy: boolean };

function EngineSettings() {
  const [engine, setEngine] = useState<Engine | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch("/api/models").then((r) => r.json()).then(setEngine).catch(() => setStatus("Não consegui falar com a AURA."));
  }, []);

  const apply = async (patch: Record<string, unknown>) => {
    setStatus("Aplicando…");
    const r = await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
    }).then((x) => x.json()).catch(() => ({ ok: false, error: "Falha de rede." }));
    if (!r.ok) { setStatus(r.error); return; }
    setEngine((e) => e && {
      ...e,
      model: (patch.model as string) ?? e.model,
      codeModel: (patch.code_model as string) ?? e.codeModel,
      economy: (patch.economy_mode as boolean) ?? e.economy,
    });
    setStatus("Salvo.");
  };

  if (!engine) return <p className="muted">{status || "Carregando modelos…"}</p>;
  if (!engine.installed.length) return <p className="muted">Ollama offline ou sem modelos instalados.</p>;

  const options = (current: string) => (engine.installed.includes(current) ? engine.installed : [current, ...engine.installed])
    .map((m) => <option key={m} value={m}>{m}</option>);

  return (
    <>
      <h3>Motor</h3>
      <label className="cfg-row">
        <span className="muted">Modelo de conversa</span>
        <select value={engine.model} onChange={(e) => apply({ model: e.target.value })}>{options(engine.model)}</select>
      </label>
      <label className="cfg-row">
        <span className="muted">Modelo de código</span>
        <select value={engine.codeModel} onChange={(e) => apply({ code_model: e.target.value })}>{options(engine.codeModel)}</select>
      </label>
      <label className="cfg-toggle">
        <input type="checkbox" checked={engine.economy} onChange={(e) => apply({ economy_mode: e.target.checked })} />
        <span>Modo economia</span>
      </label>
      <p className="hint">Economia: respostas em uma passada (sem raciocínio em duas etapas) e triagem de e-mails por regras locais. Mais rápido, menos preciso.</p>
      {status && <p className="hint">{status}</p>}
    </>
  );
}

function EmailRow({ e, dim }: { e: EmailItem; dim?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`cmd-row email ${dim ? "dim" : ""}`} style={{ borderLeftColor: e.color }} onClick={() => setOpen(!open)}>
      <div><strong>{e.resumo || e.assunto}</strong><br /><span className="muted">{e.remetente}</span></div>
      {open && <p className="trecho">{e.trecho}</p>}
    </div>
  );
}
