import { useRef, forwardRef, useMemo, useEffect, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════
// TUNING CONSTANTS
// ═══════════════════════════════════════════════════════════════
const COLORS = ['#FFFFFF', '#D1D1D1', '#8A8A8A', '#525252', '#3B4D61', '#546A7B'];
const MAX_SPEED = 10;
const ACCEL_RATE = 5;       // units/s² for speeding up
const BRAKE_RATE = 14;      // units/s² for slowing down (higher = snappier brakes)
const MIN_GAP = 4.2;        // absolute minimum bumper-to-bumper distance
const DESIRED_GAP = 6.0;    // comfortable following distance
const CARS_PER_LANE = 6;    // exactly ~40% reduction from 10

// Intersection geometry (must match Intersection3D.jsx)
const IX_HALF_X = 6;   // verticalRoadWidth/2 + 1  (buffer)
const IX_HALF_Z = 11;  // horizontalRoadWidth/2 + 1 (buffer)

// ═══════════════════════════════════════════════════════════════
// LANE DEFINITIONS — 6 lanes, no lane-change logic
// ═══════════════════════════════════════════════════════════════
const LANES = [
  { id: 'NS', dir: [0, 0, -1], start: [2.5, 0, 95], stopLine: 12, signal: 'ns' },
  { id: 'SN', dir: [0, 0, 1], start: [-2.5, 0, -95], stopLine: -12, signal: 'ns' },
  { id: 'EWo', dir: [-1, 0, 0], start: [95, 0, -7.5], stopLine: 6.5, signal: 'ew' },
  { id: 'EWi', dir: [-1, 0, 0], start: [95, 0, -2.5], stopLine: 6.5, signal: 'ew' },
  { id: 'WEi', dir: [1, 0, 0], start: [-95, 0, 2.5], stopLine: -6.5, signal: 'ew' },
  { id: 'WEo', dir: [1, 0, 0], start: [-95, 0, 7.5], stopLine: -6.5, signal: 'ew' },
].map(l => ({
  ...l,
  dir: new THREE.Vector3(...l.dir),
  start: new THREE.Vector3(...l.start),
}));

// ═══════════════════════════════════════════════════════════════
// PURE HELPERS (no side-effects)
// ═══════════════════════════════════════════════════════════════

/** Scalar projection along travel direction */
const prog = (pos, dir) => pos.x * dir.x + pos.z * dir.z;

/** Is world position inside the intersection box? */
const insideIX = (pos) => Math.abs(pos.x) < IX_HALF_X && Math.abs(pos.z) < IX_HALF_Z;

// ═══════════════════════════════════════════════════════════════
// CAR MESH
// ═══════════════════════════════════════════════════════════════
const SmallCar = forwardRef(({ color, scale }, ref) => {
  const paint = useMemo(() => <meshStandardMaterial color={color} roughness={0.6} metalness={0.2} />, [color]);
  const glass = useMemo(() => <meshStandardMaterial color="#020202" roughness={0.1} metalness={0.8} />, []);
  const tire = useMemo(() => <meshStandardMaterial color="#0A0A0A" roughness={0.9} />, []);
  return (
    <group ref={ref} scale={scale}>
      <group rotation={[0, Math.PI, 0]}>
        <mesh position={[0, 0.55, 0]} castShadow receiveShadow><boxGeometry args={[1.6, 0.4, 3.8]} />{paint}</mesh>
        <mesh position={[0, 0.9, 0.5]} castShadow receiveShadow><boxGeometry args={[1.4, 0.3, 2.0]} />{glass}</mesh>
        {[[-0.8, 1.2], [0.8, 1.2], [-0.8, -1.2], [0.8, -1.2]].map(([x, z], i) => (
          <mesh key={i} position={[x, 0.35, z]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.15, 0.15, 0.1, 16]} />{tire}
          </mesh>
        ))}
      </group>
    </group>
  );
});

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════
export default function Vehicles3D({ nsLight, ewLight }) {
  const meshRefs = useRef([]);
  const glowRefs = useRef([]);
  const GLOW_COUNT = 8;

  // ── EVENT-DRIVEN TEXT STATE MACHINE ──────────────────────
  const lastStage = useRef(0);
  const pendingStage = useRef(0);
  const textPhase = useRef('visible');  // 'visible' | 'fading-out' | 'fading-in'
  const fadeTimer = useRef(0);
  const stepTimer = useRef(0);          // how long current step has been visible
  const MIN_STEP_VISIBLE = 2.5;        // seconds each step must stay readable
  const [storyStage, setStoryStage] = useState(0);
  const [textVisible, setTextVisible] = useState(true);

  // ── INIT VEHICLES (synchronous, runs once) ──────────────────
  const data = useRef(null);
  if (!data.current) {
    let id = 0;
    const cars = [];
    for (const lane of LANES) {
      for (let i = 0; i < CARS_PER_LANE; i++) {
        const p = lane.start.clone().addScaledVector(lane.dir, -i * DESIRED_GAP);
        cars.push({
          id: id++,
          lane: lane.id,
          dir: lane.dir.clone(),
          pos: p,
          speed: 0,
          stopLine: lane.stopLine,
          signal: lane.signal,

          // Human-like variance
          prefSpeed: MAX_SPEED * (0.8 + Math.random() * 0.2),
          rxDelay: 0.4 + Math.random() * 0.5,
          rxTimer: 0,
          perceivedGap: DESIRED_GAP * 2,
          perceivedSpeed: MAX_SPEED,

          // State flags
          crossedStop: false,
          inIX: false,

          // Visual
          scale: 0.95 + Math.random() * 0.1,
          color: COLORS[id % COLORS.length],
        });
      }
    }
    data.current = cars;
  }

  // Set initial mesh orientation
  useEffect(() => {
    for (const c of data.current) {
      const m = meshRefs.current[c.id];
      if (m) { m.position.copy(c.pos); m.lookAt(c.pos.clone().add(c.dir)); }
    }
  }, []);

  // ── DISTURBANCE SYSTEM (P5 behavior layer) ─────────────────
  // Periodic micro-slowdown on hero lane — respects all safety rules
  const distTimer = useRef(0);
  const DIST_LANE = 'WEi';       // hero lane (bottom-left road)
  const DIST_CAR_IDX = 1;        // place disturbance nearer to front of fixed queue
  const DIST_INTERVAL = 3;       // seconds of normal flow
  const DIST_DURATION = 8;       // seconds the slowdown lasts (longer for ripple)
  const DIST_FACTOR = 0.15;      // deep slowdown for visible wave

  // ── SIMULATION TICK ─────────────────────────────────────────
  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const cars = data.current;
    if (!cars || cars.length === 0) return;

    // Disturbance cycle
    distTimer.current += dt;
    const cycle = distTimer.current % (DIST_INTERVAL + DIST_DURATION);
    const distActive = cycle >= DIST_INTERVAL;

    // Build sorted per-lane arrays: index 0 = leader (highest progression)
    const lanes = {};
    for (const l of LANES) lanes[l.id] = [];
    for (const c of cars) lanes[c.lane].push(c);
    for (const arr of Object.values(lanes)) {
      arr.sort((a, b) => prog(b.pos, b.dir) - prog(a.pos, a.dir));
    }

    // Process each lane front-to-back
    for (const [laneId, sorted] of Object.entries(lanes)) {
      const laneDef = LANES.find(l => l.id === laneId);
      if (!laneDef) continue;

      for (let i = 0; i < sorted.length; i++) {
        const car = sorted[i];
        const myProg = prog(car.pos, car.dir);

        // Update state flags
        const stopProg = car.dir.x !== 0
          ? car.stopLine * car.dir.x
          : car.stopLine * car.dir.z;
        car.crossedStop = myProg > stopProg;
        car.inIX = insideIX(car.pos);

        // ════════════════════════════════════════════════════
        // TARGET SPEED starts at driver's preference
        // Each priority layer can ONLY REDUCE this value
        // ════════════════════════════════════════════════════
        let target = car.prefSpeed;

        // ── P5a: MICRO-DISTURBANCE ────────────────────────
        //    One specific car on the hero lane smoothly slows
        //    down periodically. This is a P5 behavior so it
        //    can only REDUCE target — P3/P2/P1 override it.
        if (distActive && laneId === DIST_LANE && i === DIST_CAR_IDX) {
          target = Math.min(target, car.prefSpeed * DIST_FACTOR);
        }

        // ── P5b: RIPPLE / GENTLE FOLLOWING ─────────────────
        //    Softly match perceived speed of car ahead
        //    (delayed perception creates the backward ripple)
        if (i > 0) {
          const ahead = sorted[i - 1];

          // Delayed perception: update awareness of gap periodically
          car.rxTimer += dt;
          if (car.rxTimer >= car.rxDelay) {
            car.rxTimer = 0;
            car.perceivedGap = car.pos.distanceTo(ahead.pos);
            car.perceivedSpeed = ahead.speed;
          }

          // If perceived gap is below comfortable range, ease off
          if (car.perceivedGap < DESIRED_GAP * 1.8) {
            const ratio = Math.max(0, car.perceivedGap - MIN_GAP) / (DESIRED_GAP * 1.8 - MIN_GAP);
            const eased = Math.pow(ratio, 1.5); // smoother power curve for compression
            const followV = car.perceivedSpeed + (car.prefSpeed - car.perceivedSpeed) * eased;
            target = Math.min(target, followV);
          }
        }

        // ── P3: SIGNAL RULES ──────────────────────────────
        //    Stop before stop line on red/yellow
        //    BUT only if we haven't crossed it yet
        const sig = car.signal === 'ns' ? nsLight : ewLight;
        if (sig !== 'green' && !car.crossedStop) {
          const distToStop = stopProg - myProg;
          if (distToStop > 0 && distToStop < 20) {
            // Smooth quadratic brake: hard near line, gentle far away
            const frac = Math.min(1, distToStop / 12);
            target = Math.min(target, car.prefSpeed * frac * frac);
            if (distToStop < 0.4) target = 0;
          }
        }

        // ── P2: INTERSECTION SAFETY ───────────────────────
        //    If inside IX: MUST keep moving (override signal stop)
        if (car.inIX) {
          target = Math.max(target, car.prefSpeed * 0.4);
        }
        //    If approaching IX and it's blocked, don't enter
        if (!car.crossedStop && !car.inIX) {
          // Check if any car in our lane is stopped inside IX
          let ixBlocked = false;
          for (const other of sorted) {
            if (other.id === car.id) continue;
            if (prog(other.pos, other.dir) > myProg && insideIX(other.pos) && other.speed < 1) {
              ixBlocked = true;
              break;
            }
          }
          if (ixBlocked) {
            const distToStop2 = stopProg - myProg;
            if (distToStop2 > 0 && distToStop2 < 10) {
              target = Math.min(target, distToStop2 * 0.4);
              if (distToStop2 < 0.5) target = 0;
            }
          }
        }

        // ── P1: COLLISION AVOIDANCE (HIGHEST PRIORITY) ────
        //    Real-time distance check, overrides everything
        if (i > 0) {
          const ahead = sorted[i - 1];
          const realDist = car.pos.distanceTo(ahead.pos);

          const COMPRESS_GAP = MIN_GAP + 1.2;
          if (realDist < COMPRESS_GAP) {
            // Linear ramp: full speed at COMPRESS_GAP, zero at MIN_GAP
            // Uses real speed but only engages when close, allowing compression
            const t = Math.max(0, (realDist - MIN_GAP) / (COMPRESS_GAP - MIN_GAP));
            target = Math.min(target, ahead.speed * t);
          }
        }

        // ════════════════════════════════════════════════════
        // APPLY SPEED (smooth lerp)
        // ════════════════════════════════════════════════════
        const rate = target > car.speed ? ACCEL_RATE : BRAKE_RATE;
        car.speed = THREE.MathUtils.lerp(car.speed, target, rate * dt);
        if (car.speed < 0.02) car.speed = 0;
        car.speed = Math.max(0, Math.min(car.speed, MAX_SPEED * 1.05));

        // Move
        car.pos.addScaledVector(car.dir, car.speed * dt);

        // ── NO OVERLAP GUARANTEE / SMOOTH DECELERATION ──
        if (i > 0) {
          const ahead = sorted[i - 1];
          const currentDist = car.pos.distanceTo(ahead.pos);
          if (currentDist < MIN_GAP) {
            car.pos.copy(ahead.pos).addScaledVector(car.dir, -MIN_GAP);
            car.speed = car.speed * 0.9;
          }
        }

        // ── RECYCLE ───────────────────────────────────────
        if (myProg > 120) {
          const tail = sorted[sorted.length - 1];
          const startProg = prog(laneDef.start, laneDef.dir);
          let newProg = startProg;
          if (tail && tail.id !== car.id) {
            newProg = Math.min(prog(tail.pos, tail.dir) - DESIRED_GAP, startProg);
          }
          car.pos.x = car.dir.x !== 0 ? newProg * car.dir.x : laneDef.start.x;
          car.pos.y = 0;
          car.pos.z = car.dir.z !== 0 ? newProg * car.dir.z : laneDef.start.z;
          car.speed = car.prefSpeed;
          car.crossedStop = false;
          car.inIX = false;
          car.perceivedGap = DESIRED_GAP * 2;
          car.rxTimer = 0;
        }

        // ── DEBUG CHECKS (console warnings) ───────────────
        if (i > 0) {
          const realDist = car.pos.distanceTo(sorted[i - 1].pos);
          if (realDist < MIN_GAP * 0.5) {
            console.warn(`[OVERLAP] car ${car.id} dist=${realDist.toFixed(2)} to car ${sorted[i - 1].id} in lane ${laneId}`);
          }
        }
        if (car.inIX && car.speed === 0 && !car.crossedStop) {
          // This shouldn't happen — car stuck in intersection
          console.warn(`[IX-STUCK] car ${car.id} stopped inside intersection in lane ${laneId}`);
        }

        // ── COMMIT TO MESH ────────────────────────────────
        const mesh = meshRefs.current[car.id];
        if (mesh) {
          mesh.position.copy(car.pos);
          mesh.lookAt(car.pos.clone().add(car.dir));
        }
      }
    }

    // ── GLOW MARKERS (hero lane affected vehicles) ──────────
    let glowIdx = 0;
    const heroSorted = lanes[DIST_LANE] || [];
    for (const car of heroSorted) {
      // Car is "affected" if noticeably below preferred speed
      if (car.speed < car.prefSpeed * 0.85 && glowIdx < GLOW_COUNT) {
        const glow = glowRefs.current[glowIdx];
        if (glow) {
          glow.position.set(car.pos.x, 0.22, car.pos.z);
          glow.visible = true;
          // Intensity scales with how slowed the car is
          const slowness = 1 - car.speed / car.prefSpeed;
          glow.material.opacity = Math.min(0.15, slowness * 0.2); // subtle glow
        }
        glowIdx++;
      }
    }
    // Hide unused glows
    for (let g = glowIdx; g < GLOW_COUNT; g++) {
      if (glowRefs.current[g]) glowRefs.current[g].visible = false;
    }

    // ── EVENT-DRIVEN STORY STAGE ─────────────────────────────
    // 1. Detect stage from simulation state
    let detectedStage = 0;
    if (glowIdx >= 4) detectedStage = 3;
    else if (glowIdx >= 2) detectedStage = 2;
    else if (glowIdx >= 1) detectedStage = 1;

    // 2. Compute eventProgress (0-1) for current detected stage
    let eventProgress = 0;
    if (detectedStage === 1) eventProgress = Math.min(1, glowIdx / 1.5);
    else if (detectedStage === 2) eventProgress = Math.min(1, glowIdx / 3);
    else if (detectedStage === 3) eventProgress = Math.min(1, glowIdx / 5);
    else eventProgress = glowIdx === 0 ? 1 : 0;

    // 3. State machine with step lock
    //    'visible': accumulate stepTimer, block transitions until MIN_STEP_VISIBLE
    //    'fading-out': wait 0.4s then swap content
    //    'fading-in': wait 0.5s then unlock

    if (textPhase.current === 'visible') {
      stepTimer.current += dt;

      // Only allow next transition after minimum display time
      if (detectedStage !== lastStage.current
        && eventProgress > 0.5
        && stepTimer.current >= MIN_STEP_VISIBLE) {
        pendingStage.current = detectedStage;
        textPhase.current = 'fading-out';
        fadeTimer.current = 0;
        setTextVisible(false);  // triggers CSS opacity transition
      }
    }

    // Phase: fading-out → wait 0.4s → update content
    if (textPhase.current === 'fading-out') {
      fadeTimer.current += dt;
      if (fadeTimer.current >= 0.4) {
        lastStage.current = pendingStage.current;
        setStoryStage(pendingStage.current);
        setTextVisible(true);  // triggers CSS fade-in
        textPhase.current = 'fading-in';
        fadeTimer.current = 0;
      }
    }

    // Phase: fading-in → wait 0.5s → reset stepTimer → ready
    if (textPhase.current === 'fading-in') {
      fadeTimer.current += dt;
      if (fadeTimer.current >= 0.5) {
        textPhase.current = 'visible';
        stepTimer.current = 0;  // reset — new step starts its 2.5s lock
      }
    }
  });

  // ── RENDER ──────────────────────────────────────────────────
  return (
    <group>
      {data.current && data.current.map(c => (
        <SmallCar
          key={c.id}
          ref={el => (meshRefs.current[c.id] = el)}
          color={c.color}
          scale={c.scale}
        />
      ))}

      {/* Glow circles for ripple visualization */}
      {Array.from({ length: GLOW_COUNT }).map((_, i) => (
        <mesh
          key={`glow-${i}`}
          ref={el => (glowRefs.current[i] = el)}
          rotation={[-Math.PI / 2, 0, 0]}
          visible={false}
        >
          <circleGeometry args={[2.2, 32]} />
          <meshBasicMaterial
            color="#D4AF37"
            transparent
            opacity={0.2}
            depthWrite={false}
          />
        </mesh>
      ))}

      {/* ── CINEMATIC STORY TEXT — event-driven, no box ── */}
      <group position={[-25, 1.2, -15]} rotation={[-0.25, -0.1, 0]}>
        <Html
          transform
          distanceFactor={14}
          style={{
            pointerEvents: 'none',
            opacity: textVisible ? 0.9 : 0,
            transform: textVisible ? 'translateX(0)' : 'translateX(-20px)',
            transition: 'opacity 0.4s ease, transform 0.4s ease',
          }}
        >
          <div style={{ whiteSpace: 'nowrap' }}>
            <style>{`
              @keyframes softGlow {
                0%, 100% { text-shadow: 0 0 8px rgba(255,255,255,0.25), 0 0 30px rgba(255,255,255,0.08); }
                50%      { text-shadow: 0 0 14px rgba(255,255,255,0.4), 0 0 40px rgba(255,255,255,0.12); }
              }
            `}</style>
            <p style={{
              animation: 'softGlow 3.5s ease-in-out infinite',
              color: '#f5f5f5',
              fontSize: 26,
              fontWeight: 600,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              textShadow: '0 0 8px rgba(255,255,255,0.25), 0 0 30px rgba(255,255,255,0.08)',
            }}>
              {[
                'Traffic is flowing normally',
                'A single vehicle slows down',
                'This creates a ripple effect',
                'Small disturbances lead to congestion',
              ][storyStage]}
            </p>
          </div>
        </Html>
      </group>
    </group>
  );
}