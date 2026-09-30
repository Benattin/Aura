import { useEffect, useRef } from "react";

const GOLD_HI = "#e8c84a";
const GOLD_LO = "rgba(212,175,55,";

type Particle = { lon: number; lat: number; seed: number; orbit: number };

const PARTICLES: Particle[] = Array.from({ length: 110 }, (_, i) => ({
  lon: (i / 110) * Math.PI * 2 + 0.3,
  lat: ((i % 11) / 10 - 0.5) * Math.PI * 0.94,
  seed: (i * 13) % 10,
  orbit: 0.85 + (i % 5) * 0.04,
}));

const HALO = Array.from({ length: 36 }, (_, i) => ({
  angle: (i / 36) * Math.PI * 2,
  dist: 1.12 + (i % 3) * 0.02,
  size: 0.8 + (i % 4) * 0.3,
}));

function smoothstep(t: number): number {
  const x = Math.max(0, Math.min(1, t));
  return x * x * (3 - 2 * x);
}

/** Ciclo 0→1: estável → desfaz → refaz → estável */
function cycleDissolve(phase: number, max: number, base: number): number {
  if (phase < 0.22) return base;
  if (phase < 0.48) {
    const t = smoothstep((phase - 0.22) / 0.26);
    return base + t * max;
  }
  if (phase < 0.78) {
    const t = smoothstep((phase - 0.48) / 0.3);
    return base + (1 - t) * max;
  }
  return base;
}

export default function Globe({ state }: { state: string }) {
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

    let rotY = 0;
    let pulse = 0;
    let cycle = 0;
    let raf = 0;
    let last = 0;
    let dead = false;
    let mx = 0.5;
    let my = 0.5;

    const onMove = (e: PointerEvent) => {
      const b = wrap.getBoundingClientRect();
      mx = (e.clientX - b.left) / b.width;
      my = (e.clientY - b.top) / b.height;
    };
    wrap.addEventListener("pointermove", onMove);

    const draw = (now: number) => {
      if (dead) return;
      const m = motion(stateRef.current);
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0.016;
      if (last && dt < (m.busy ? 0.032 : 0.04)) {
        raf = requestAnimationFrame(draw);
        return;
      }
      last = now;
      rotY += m.speed * dt;
      cycle = (cycle + dt * m.cycleSpeed) % 1;
      const rotX = 0.2 + Math.sin(now / 2200) * m.wobble + (my - 0.5) * 0.08;
      const rotBias = (mx - 0.5) * 0.35;
      pulse += m.pulseSpeed * dt;
      const beat = 0.5 + 0.5 * Math.sin(pulse);
      const heartbeat = 0.5 + 0.5 * Math.sin(pulse * 1.6);
      const dissolve = cycleDissolve(cycle, m.maxDissolve, m.baseDissolve);

      const size = Math.floor(Math.min(wrap.clientWidth, wrap.clientHeight));
      if (size < 8) {
        raf = requestAnimationFrame(draw);
        return;
      }

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const px = Math.round(size * dpr);
      if (canvas.width !== px || canvas.height !== px) {
        canvas.width = px;
        canvas.height = px;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size, size);

      const cx = size / 2;
      const cy = size / 2;
      const pulseScale = 1 + m.amp * beat + m.amp * 0.35 * heartbeat;
      const r = size * 0.36 * pulseScale;

      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, size / 2 - 1, 0, Math.PI * 2);
      ctx.clip();

      const bg = ctx.createRadialGradient(cx, cy, r * 0.1, cx, cy, size * 0.5);
      bg.addColorStop(0, "#0e0c08");
      bg.addColorStop(0.55, "#080807");
      bg.addColorStop(1, "#030303");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, size, size);

      // anéis — expandem ao desfazer
      const ringExpand = 1 + dissolve * 0.35;
      for (let ri = 1; ri <= 3; ri++) {
        const ringR = r * (1.18 + ri * 0.1) * ringExpand * (1 + beat * 0.03);
        ctx.strokeStyle = `${GOLD_LO}${(0.04 + ri * 0.02) * m.glow * (1 - dissolve * 0.4)})`;
        ctx.lineWidth = 0.6;
        ctx.beginPath();
        ctx.ellipse(cx, cy, ringR, ringR * 0.32, rotY * 0.15 + ri * 0.4, 0, Math.PI * 2);
        ctx.stroke();
      }

      const outer = ctx.createRadialGradient(cx, cy, r * 0.85, cx, cy, r * (1.55 + dissolve * 0.4));
      outer.addColorStop(0, `${GOLD_LO}0)`);
      outer.addColorStop(0.5, `${GOLD_LO}${0.07 * m.glow * (0.6 + beat * 0.4) * (1 + dissolve * 0.5)})`);
      outer.addColorStop(1, `${GOLD_LO}0)`);
      ctx.fillStyle = outer;
      ctx.beginPath();
      ctx.arc(cx, cy, r * (1.55 + dissolve * 0.4), 0, Math.PI * 2);
      ctx.fill();

      const coreAlpha = m.glow * (0.7 + beat * 0.3) * (1 - dissolve * 0.6);
      const core = ctx.createRadialGradient(cx - r * 0.12, cy - r * 0.1, r * 0.05, cx, cy, r * 0.95);
      core.addColorStop(0, `rgba(255,220,140,${0.22 * coreAlpha})`);
      core.addColorStop(0.35, `rgba(212,175,55,${0.12 * coreAlpha})`);
      core.addColorStop(0.7, `rgba(80,60,30,${0.15 * coreAlpha})`);
      core.addColorStop(1, "rgba(0,0,0,0.35)");
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 0.92 * (1 + dissolve * 0.08), 0, Math.PI * 2);
      ctx.fill();

      const mesh = (1 - dissolve * (0.55 + 0.45 * beat)) * (1 - dissolve * 0.35);

      if (mesh > 0.04) {
        const lineNoise = dissolve * 0.12;
        for (let mer = 0; mer < 10; mer++) {
          const lon0 = (mer / 10) * Math.PI * 2 + rotY + rotBias;
          const line: ReturnType<typeof project>[] = [];
          for (let i = 0; i <= 32; i++) {
            const lat = (i / 32 - 0.5) * Math.PI;
            const wobble = Math.sin(i * 0.8 + mer + now * 0.002) * lineNoise;
            line.push(project(lat + wobble, lon0, rotX, r, cx, cy));
          }
          const front = line.reduce((s, p) => s + (p.z > 0 ? 1 : 0), 0) / line.length;
          strokeLine(ctx, line, `${GOLD_LO}${(0.12 + front * 0.35) * mesh})`, 0.7 + front * 0.5);
        }

        for (let p = 1; p < 7; p++) {
          const lat = (p / 7 - 0.5) * Math.PI * 0.92;
          const line: ReturnType<typeof project>[] = [];
          for (let i = 0; i <= 40; i++) {
            const wobble = Math.sin(i * 0.5 + p + now * 0.002) * lineNoise;
            line.push(project(lat, (i / 40) * Math.PI * 2 + rotY + rotBias + wobble, rotX, r, cx, cy));
          }
          strokeLine(ctx, line, `${GOLD_LO}${0.14 * mesh})`, 0.55);
        }

        const eq: ReturnType<typeof project>[] = [];
        for (let i = 0; i <= 48; i++) {
          eq.push(project(0, (i / 48) * Math.PI * 2 + rotY + rotBias, rotX, r, cx, cy));
        }
        strokeLine(ctx, eq, `${GOLD_LO}${0.42 * mesh * (0.7 + beat * 0.3)})`, 1.1);
      }

      ctx.strokeStyle = `${GOLD_LO}${0.35 * mesh})`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      const rim = ctx.createRadialGradient(cx, cy, r * 0.88, cx, cy, r * 1.04);
      rim.addColorStop(0, "rgba(0,0,0,0)");
      rim.addColorStop(0.7, `${GOLD_LO}${0.1 * m.glow * (1 + beat * 0.5)})`);
      rim.addColorStop(1, `${GOLD_LO}${0.25 * m.glow * (1 + heartbeat * 0.3)})`);
      ctx.fillStyle = rim;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 1.04, 0, Math.PI * 2);
      ctx.fill();

      const scatter = dissolve * (0.45 + 0.9 * beat);
      for (const p of PARTICLES) {
        const base = project(p.lat, p.lon + rotY + rotBias, rotX, r, cx, cy);
        const spread = scatter * (0.4 + p.seed * 0.12);
        const drift = Math.sin(now * 0.002 + p.seed) * scatter * 8;
        const pt = {
          x: base.x + (base.x - cx) * spread + drift,
          y: base.y + (base.y - cy) * spread + drift * 0.6,
          z: base.z,
        };
        if (pt.z < -r * 0.15) continue;
        const depth = (pt.z + r) / (2 * r);
        const a = (0.15 + 0.7 * depth) * (0.35 + dissolve * 0.65) * (0.55 + beat * 0.45);
        const sz = (0.8 + depth * 1.5) * (1 + scatter * 0.8);
        ctx.fillStyle = `${GOLD_LO}${a})`;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, sz, 0, Math.PI * 2);
        ctx.fill();
      }

      for (const h of HALO) {
        const pull = 1 - dissolve * 0.5;
        const a = h.angle + rotY * 0.4 + now * 0.0003;
        const dist = r * h.dist * (1 + scatter * 0.5) * pull;
        const hx = cx + Math.cos(a) * dist;
        const hy = cy + Math.sin(a) * dist * 0.35;
        const flick = 0.4 + 0.6 * Math.sin(now * 0.003 + h.angle * 5);
        ctx.fillStyle = `${GOLD_LO}${0.22 * m.glow * flick * (0.5 + dissolve * 0.5)})`;
        ctx.beginPath();
        ctx.arc(hx, hy, h.size * (1 + scatter * 0.4), 0, Math.PI * 2);
        ctx.fill();
      }

      if (m.scan) {
        const lat = Math.sin(now / 280) * 0.85;
        const scan: ReturnType<typeof project>[] = [];
        for (let i = 0; i <= 36; i++) {
          scan.push(project(lat, (i / 36) * Math.PI * 2 + rotY, rotX, r * 1.01, cx, cy));
        }
        strokeLine(ctx, scan, GOLD_HI, 1.5);
      }

      ctx.globalCompositeOperation = "lighter";
      const bloom = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * (0.55 + dissolve * 0.2));
      bloom.addColorStop(0, `rgba(255,200,100,${0.1 * m.glow * (0.5 + beat * 0.5) * (1 + heartbeat * 0.3)})`);
      bloom.addColorStop(1, "rgba(255,200,100,0)");
      ctx.fillStyle = bloom;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 0.6, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalCompositeOperation = "source-over";

      ctx.restore();
      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => {
      dead = true;
      wrap.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={wrapRef} className={`globe-wrap ${state}`}>
      <canvas ref={canvasRef} className="globe" aria-hidden="true" />
    </div>
  );
}

function motion(state: string) {
  switch (state) {
    case "thinking":
      return { speed: 2.6, wobble: 0.12, pulseSpeed: 8.5, amp: 0.14, scan: false, busy: true, baseDissolve: 0.15, maxDissolve: 0.92, glow: 1, cycleSpeed: 0.14 };
    case "speaking":
      return { speed: 1.4, wobble: 0.14, pulseSpeed: 10, amp: 0.16, scan: false, busy: true, baseDissolve: 0.12, maxDissolve: 0.78, glow: 1.1, cycleSpeed: 0.18 };
    case "listening":
      return { speed: 1.1, wobble: 0.07, pulseSpeed: 6, amp: 0.12, scan: true, busy: true, baseDissolve: 0.1, maxDissolve: 0.7, glow: 0.95, cycleSpeed: 0.12 };
    case "paused":
      return { speed: 0.03, wobble: 0, pulseSpeed: 0.2, amp: 0.02, scan: false, busy: false, baseDissolve: 0, maxDissolve: 0.2, glow: 0.12, cycleSpeed: 0.04 };
    default:
      return { speed: 0.5, wobble: 0.035, pulseSpeed: 2.8, amp: 0.08, scan: false, busy: false, baseDissolve: 0.05, maxDissolve: 0.55, glow: 0.6, cycleSpeed: 0.08 };
  }
}

function project(lat: number, lon: number, rotX: number, r: number, cx: number, cy: number) {
  const x = r * Math.cos(lat) * Math.sin(lon);
  let y = r * Math.sin(lat);
  let z = r * Math.cos(lat) * Math.cos(lon);
  const cosX = Math.cos(rotX);
  const sinX = Math.sin(rotX);
  const y2 = y * cosX - z * sinX;
  const z2 = y * sinX + z * cosX;
  const persp = 0.52 + 0.48 * ((z2 + r) / (2 * r));
  return { x: cx + x * persp, y: cy + y2 * persp, z: z2 };
}

function strokeLine(
  ctx: CanvasRenderingContext2D,
  line: { x: number; y: number; z: number }[],
  color: string,
  width: number,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  let started = false;
  for (const p of line) {
    if (p.z < -4) {
      started = false;
      continue;
    }
    if (!started) {
      ctx.moveTo(p.x, p.y);
      started = true;
    } else ctx.lineTo(p.x, p.y);
  }
  ctx.stroke();
}
