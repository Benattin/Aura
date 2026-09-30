import { loadJson, saveJson } from "./auraHub";

const GEO_KEY = "aura_weather_geo";

export async function weatherSaoPaulo(): Promise<string> {
  let geo = loadJson<{ lat: number; lon: number } | null>(GEO_KEY, null);
  if (!geo) {
    const r = await fetch("https://geocoding-api.open-meteo.com/v1/search?name=São Paulo&count=1&language=pt&country=BR");
    const j = await r.json();
    const hit = j.results?.[0];
    if (!hit) return "";
    geo = { lat: hit.latitude, lon: hit.longitude };
    saveJson(GEO_KEY, geo);
  }
  const w = await fetch(
    `https://api.open-meteo.com/v1/forecast?latitude=${geo.lat}&longitude=${geo.lon}&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=America%2FSao_Paulo&forecast_days=1`
  );
  const d = await w.json();
  const max = d.daily?.temperature_2m_max?.[0];
  const min = d.daily?.temperature_2m_min?.[0];
  if (max == null) return "";
  return `Em São Paulo, máxima de ${Math.round(max)} e mínima de ${Math.round(min)} graus.`;
}
