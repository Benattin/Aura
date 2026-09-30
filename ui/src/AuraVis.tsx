import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  seed: number;
  size: number;
  kind: "edge" | "inner" | "drift" | "base";
};

function motion(state: string) {
  switch (state) {
    case "thinking": return { pulse: 5, glow: 0.82, mesh: 1, particles: 1.15 };
    case "speaking": return { pulse: 6, glow: 0.9, mesh: 0.95, particles: 1.1 };
    case "listening": return { pulse: 4.5, glow: 0.75, mesh: 1.05, particles: 1.2 };
    case "paused": return { pulse: 1, glow: 0.12, mesh: 0.15, particles: 0.12 };
    default: return { pulse: 2.5, glow: 0.5, mesh: 0.6, particles: 0.55 };
  }
}

/** Silhueta frontal ampla — cabeça até quadris */
function halfW(y: number): number {
  const headCy = 0.13;
  const headR = 0.108;
  const dy = (y - headCy) / headR;
  if (y < 0.27) {
    if (dy < -1 || dy > 1) return 0;
    return headR * Math.sqrt(Math.max(0, 1 - dy * dy));
  }
  if (y < 0.32) return 0.07 - (y - 0.27) * 0.32;
  if (y < 0.37) return 0.054 + (y - 0.32) * 4.6;
  if (y < 0.43) return 0.284 + (y - 0.37) * 0.06;
  if (y < 0.56) return 0.32 - (y - 0.43) * 0.22;
  if (y < 0.68) return 0.294 - (y - 0.56) * 0.55;
  if (y < 0.8) return 0.228 - (y - 0.68) * 0.42;
  if (y < 0.9) return 0.178 - (y - 0.8) * 1.15;
  if (y < 0.96) return 0.063 - (y - 0.9) * 0.9;
  return 0;
}

function edge(y: number, side: -1 | 1): [number, number] {
  return [0.5 + side * halfW(y), y];
}

function insideBody(x: number, y: number): boolean {
  return Math.abs(x - 0.5) <= halfW(y) * 0.96 && y >= 0.06 && y <= 0.95;
}

function spawnInner(seed: number): Particle {
  let x = 0.5;
  let y = 0.15 + (seed % 80) / 80 * 0.78;
  for (let i = 0; i < 12; i++) {
    const hw = halfW(y) * 0.88;
    x = 0.5 + ((seed * 17 + i * 13) % 1000 / 1000 - 0.5) * hw * 2;
    if (insideBody(x, y)) break;
    y = 0.1 + ((seed + i * 7) % 100) / 100 * 0.84;
  }
  return {
    x, y,
    vx: (Math.sin(seed) * 0.0012),
    vy: (Math.cos(seed * 1.3) * 0.001),
    life: seed * 0.1,
    seed,
    size: 0.4 + (seed % 5) * 0.22,
    kind: "inner",
  };
}

type Props = { state: string; label?: string };

export default function AuraVis({ state, label }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let raf = 0;
    let last = 0;
    let t = 0;
    let dead = false;

    const particles: Particle[] = [
      ...Array.from({ length: 200 }, (_, i) => spawnInner(i)),
      ...Array.from({ length: 180 }, (_, i) => ({
        x: 0.5,
        y: 0.15 + (i / 180) * 0.8,
        vx: 0,
        vy: 0,
        life: i * 0.07,
        seed: i + 300,
        size: 0.5 + (i % 4) * 0.2,
        kind: "edge" as const,
      })),
      ...Array.from({ length: 120 }, (_, i) => ({
        x: Math.random(),
        y: 0.72 + Math.random() * 0.26,
        vx: (Math.random() - 0.5) * 0.0015,
        vy: -0.001 - Math.random() * 0.002,
        life: Math.random() * 10,
        seed: i + 500,
        size: 0.35 + Math.random() * 0.7,
        kind: "base" as const,
      })),
      ...Array.from({ length: 80 }, (_, i) => ({
        x: 0.2 + Math.random() * 0.6,
        y: 0.1 + Math.random() * 0.85,
        vx: (Math.random() - 0.5) * 0.0008,
        vy: (Math.random() - 0.5) * 0.0008,
        life: Math.random() * 8,
        seed: i + 700,
        size: 0.3 + Math.random() * 0.5,
        kind: "drift" as const,
      })),
    ];

    const draw = (now: number) => {
      if (dead) return;
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0.016;
      last = now;
      t += dt;
      const m = motion(stateRef.current);
      const beat = 0.5 + 0.5 * Math.sin(t * m.pulse);

      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      if (w < 8 || h < 8) {
        raf = requestAnimationFrame(draw);
        return;
      }

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const cw = Math.round(w * dpr);
      const ch = Math.round(h * dpr);
      if (canvas.width !== cw || canvas.height !== ch) {
        canvas.width = cw;
        canvas.height = ch;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const cx = w * 0.5;
      const top = h * 0.02;
      const figH = h * 0.92;
      const sc = Math.min(w * 0.78, figH);
      const tx = (x: number) => cx + (x - 0.5) * sc;
      const ty = (y: number) => top + y * figH;

      const bg = ctx.createLinearGradient(0, 0, 0, h);
      bg.addColorStop(0, "#0b0c10");
      bg.addColorStop(0.5, "#07080a");
      bg.addColorStop(1, "#050506");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, w, h);

      // terreno denso de partículas
      for (let col = 0; col < 36; col++) {
        for (let row = 0; row < 10; row++) {
          const fx = col / 35;
          const fy = row / 9;
          const height = Math.sin(fx * 5 + 0.2) * 0.03 + Math.sin(fx * 10) * 0.015;
          const px = 0.06 + fx * 0.88;
          const py = 0.76 + fy * 0.22 - height * (1 - fy * 0.4);
          const a = (0.04 + fy * 0.1) * m.mesh * (0.5 + beat * 0.3);
          ctx.fillStyle = `rgba(190,155,90,${a})`;
          ctx.fillRect(tx(px), ty(py), 1.2, 1.2);
        }
      }

      // anéis
      for (let r = 1; r <= 6; r++) {
        ctx.strokeStyle = `rgba(185,150,85,${(0.02 + r * 0.007) * m.mesh})`;
        ctx.lineWidth = 0.6;
        ctx.beginPath();
        ctx.ellipse(cx, ty(0.38), sc * (0.17 + r * 0.05), sc * (0.22 + r * 0.065), 0, 0, Math.PI * 2);
        ctx.stroke();
      }

      const steps = 80;
      const yMin = 0.04;
      const yMax = 0.96;

      // volume corporal
      ctx.beginPath();
      for (let i = 0; i <= steps; i++) {
        const y = yMin + (i / steps) * (yMax - yMin);
        const [x] = edge(y, 1);
        if (i === 0) ctx.moveTo(tx(x), ty(y));
        else ctx.lineTo(tx(x), ty(y));
      }
      for (let i = steps; i >= 0; i--) {
        const y = yMin + (i / steps) * (yMax - yMin);
        const [x] = edge(y, -1);
        ctx.lineTo(tx(x), ty(y));
      }
      ctx.closePath();
      const fill = ctx.createLinearGradient(cx, ty(0.06), cx, ty(0.94));
      fill.addColorStop(0, `rgba(100,165,220,${0.05 * m.glow})`);
      fill.addColorStop(0.28, `rgba(210,165,95,${0.08 * m.glow})`);
      fill.addColorStop(0.52, `rgba(200,150,80,${0.07 * m.glow})`);
      fill.addColorStop(0.78, `rgba(180,140,75,${0.04 * m.glow})`);
      fill.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = fill;
      ctx.fill();

      // glow rosto + peito + abdômen
      for (const [cy, rx, ry, intensity] of [
        [0.17, 0.1, 0.12, 0.55],
        [0.48, 0.2, 0.14, 0.28],
        [0.68, 0.16, 0.1, 0.18],
      ] as const) {
        const g = ctx.createRadialGradient(tx(0.5), ty(cy), 1, tx(0.5), ty(cy), sc * rx);
        g.addColorStop(0, `rgba(210,170,100,${intensity * m.glow})`);
        g.addColorStop(0.45, `rgba(130,180,220,${intensity * 0.2 * m.glow})`);
        g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.ellipse(tx(0.5), ty(cy), sc * rx, sc * ry, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      // partículas internas e de contorno
      for (const p of particles) {
        p.life += dt;
        if (p.kind === "inner") {
          p.x += p.vx + Math.sin(t * 1.5 + p.seed) * 0.0004;
          p.y += p.vy + Math.cos(t * 1.2 + p.seed) * 0.0003;
          if (!insideBody(p.x, p.y)) {
            const repl = spawnInner(p.seed + Math.floor(t * 10));
            p.x = repl.x;
            p.y = repl.y;
          }
          const flick = 0.35 + 0.65 * Math.sin(p.life * 3 + p.seed);
          const depth = 1 - Math.abs(p.x - 0.5) / (halfW(p.y) + 0.01);
          ctx.fillStyle = p.y < 0.3
            ? `rgba(140,200,240,${0.35 * m.particles * flick * depth})`
            : `rgba(220,175,100,${0.32 * m.particles * flick * depth})`;
          ctx.beginPath();
          ctx.arc(tx(p.x), ty(p.y), p.size * (0.8 + beat * 0.4), 0, Math.PI * 2);
          ctx.fill();
        } else if (p.kind === "edge") {
          const idx = p.seed - 300;
          const y = yMin + (idx / 179) * (yMax - yMin);
          const hw = halfW(y);
          const side = idx % 2 === 0 ? 1 : -1;
          const wobble = Math.sin(t * 1.8 + idx * 0.15) * 0.008;
          p.x = 0.5 + side * (hw + wobble);
          p.y = y + Math.sin(t + idx) * 0.002;
          const flick = 0.4 + 0.6 * Math.sin(p.life * 4 + p.seed);
          ctx.fillStyle = y < 0.28
            ? `rgba(150,210,250,${0.5 * m.particles * flick})`
            : `rgba(230,185,110,${0.45 * m.particles * flick})`;
          ctx.beginPath();
          ctx.arc(tx(p.x), ty(p.y), p.size * (0.9 + beat * 0.5), 0, Math.PI * 2);
          ctx.fill();
        } else if (p.kind === "base") {
          p.x += p.vx;
          p.y += p.vy;
          if (p.y < 0.7 || p.x < 0 || p.x > 1) {
            p.x = Math.random();
            p.y = 0.78 + Math.random() * 0.2;
          }
          const flick = 0.3 + 0.7 * Math.sin(p.life * 2.5 + p.seed);
          ctx.fillStyle = `rgba(200,165,95,${0.2 * m.particles * flick})`;
          ctx.beginPath();
          ctx.arc(tx(p.x), ty(p.y), p.size, 0, Math.PI * 2);
          ctx.fill();
        } else {
          p.x += p.vx;
          p.y += p.vy;
          if (!insideBody(p.x, p.y)) {
            p.x = 0.25 + Math.random() * 0.5;
            p.y = 0.15 + Math.random() * 0.75;
          }
          const flick = 0.25 + 0.75 * Math.sin(p.life * 2 + p.seed);
          ctx.fillStyle = `rgba(180,200,230,${0.12 * m.particles * flick})`;
          ctx.fillRect(tx(p.x) - 0.5, ty(p.y) - 0.5, 1.2, 1.2);
        }
      }

      // contornos topográficos densos
      const lines = 68;
      for (let ci = 0; ci < lines; ci++) {
        const y = yMin + (ci / (lines - 1)) * (yMax - yMin);
        const hw = halfW(y);
        if (hw < 0.006) continue;

        const zone = y < 0.27 ? "head" : y < 0.43 ? "neck" : y < 0.68 ? "chest" : "hips";
        const alpha = (zone === "head" ? 0.42 : zone === "chest" ? 0.3 : 0.22) * m.mesh * (0.65 + beat * 0.2);
        ctx.strokeStyle = zone === "head"
          ? `rgba(125,195,235,${alpha})`
          : `rgba(195,160,95,${alpha})`;
        ctx.lineWidth = zone === "head" ? 0.85 : 0.55;
        ctx.beginPath();
        for (let si = 0; si <= 48; si++) {
          const frac = si / 48;
          const x = 0.5 - hw + frac * hw * 2;
          const wave = Math.sin(frac * Math.PI * 4 + t * 0.5 + ci * 0.07) * 0.005 * Math.sin(frac * Math.PI);
          const px = tx(x + wave);
          const py = ty(y);
          if (si === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();
      }

      // malha vertical densa
      for (let vi = 0; vi < 13; vi++) {
        const frac = vi / 12;
        const xBase = 0.5 + (frac - 0.5) * 0.5;
        const bright = Math.abs(frac - 0.5) < 0.06;
        ctx.strokeStyle = bright
          ? `rgba(230,190,110,${0.14 * m.glow})`
          : `rgba(190,155,90,${0.08 * m.mesh})`;
        ctx.lineWidth = bright ? 0.55 : 0.35;
        ctx.beginPath();
        let on = false;
        for (let yi = 0; yi <= 48; yi++) {
          const y = 0.3 + (yi / 48) * 0.64;
          const hw = halfW(y);
          if (hw < 0.012) { on = false; continue; }
          const x = 0.5 + (xBase - 0.5) * (hw / 0.32);
          const px = tx(x + Math.sin(y * 18 + vi) * 0.003);
          const py = ty(y);
          if (!on) { ctx.moveTo(px, py); on = true; }
          else ctx.lineTo(px, py);
        }
        ctx.stroke();
      }

      // fibras verticais
      for (let fi = 0; fi < 22; fi++) {
        const frac = fi / 21;
        const fx = 0.5 + (frac - 0.5) * 0.48;
        const bright = fi % 3 === 0;
        ctx.strokeStyle = bright
          ? `rgba(235,195,115,${(0.18 + beat * 0.2) * m.glow})`
          : `rgba(190,155,90,${0.09 * m.mesh})`;
        ctx.lineWidth = bright ? 0.7 : 0.35;
        ctx.beginPath();
        ctx.moveTo(tx(fx), ty(0.3));
        ctx.bezierCurveTo(
          tx(fx + Math.sin(fi + t) * 0.012), ty(0.48),
          tx(fx - Math.sin(fi + t * 0.8) * 0.01), ty(0.66),
          tx(fx), ty(0.82 + (fi % 4) * 0.02),
        );
        ctx.stroke();
      }

      // contorno externo
      ctx.strokeStyle = `rgba(140,190,225,${0.24 * m.mesh})`;
      ctx.lineWidth = 1;
      for (const side of [-1, 1] as const) {
        ctx.beginPath();
        for (let i = 0; i <= steps; i++) {
          const y = yMin + (i / steps) * (yMax - yMin);
          const [x] = edge(y, side);
          if (i === 0) ctx.moveTo(tx(x), ty(y));
          else ctx.lineTo(tx(x), ty(y));
        }
        ctx.stroke();
      }

      // bloom suave
      ctx.globalCompositeOperation = "lighter";
      const bloom = ctx.createRadialGradient(tx(0.5), ty(0.4), 0, tx(0.5), ty(0.42), sc * 0.38);
      bloom.addColorStop(0, `rgba(210,160,80,${0.06 * m.glow})`);
      bloom.addColorStop(0.5, `rgba(120,180,220,${0.025 * m.glow})`);
      bloom.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = bloom;
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = "source-over";

      const vig = ctx.createRadialGradient(cx, ty(0.42), sc * 0.1, cx, ty(0.42), sc * 0.68);
      vig.addColorStop(0, "rgba(0,0,0,0)");
      vig.addColorStop(1, "rgba(0,0,0,0.5)");
      ctx.fillStyle = vig;
      ctx.fillRect(0, 0, w, h);

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => {
      dead = true;
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={wrapRef} className={`aura-vis ${state}`}>
      <canvas ref={canvasRef} className="aura-vis-canvas" aria-hidden="true" />
      {label && <div className="aura-caption">{label}</div>}
    </div>
  );
}
