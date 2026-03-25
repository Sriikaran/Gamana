import { useRef, useState, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import { motion, useScroll, useTransform, useSpring } from 'framer-motion';
import Intersection3D from './Intersection3D';
import SolutionIntersection3D from './SolutionIntersection3D';

export default function StoryMode({ onLaunch }) {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"]
  });

  // Track window size in pixels so Framer Motion interpolates purely over pixels, 
  // preventing the "jump" associated with mixing "50vh" and "24px".
  const [win, setWin] = useState({ w: 1200, h: 800 });
  useEffect(() => {
    setWin({ w: window.innerWidth, h: window.innerHeight });
    const handleResize = () => setWin({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Smooth scroll progress for buttery transitions
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });

  // ── LOGO TRANSITION MAPPINGS ─────────────────────────────
  // 0.0 -> 0.15: Transition from center of screen to top-left (24px)
  const logoLeft = useTransform(smoothProgress, [0, 0.15], [win.w / 2, 24]);
  const logoTop = useTransform(smoothProgress, [0, 0.15], [win.h / 2, 24]);

  // Smoothly align the center of the text initially, then shift to standard top-left origin
  const logoTranslateX = useTransform(smoothProgress, [0, 0.15], ["-50%", "0%"]);
  const logoTranslateY = useTransform(smoothProgress, [0, 0.15], ["-50%", "0%"]);

  // Scale down the entire block from the large hero size
  const logoScale = useTransform(smoothProgress, [0, 0.15], [2, 1]);

  // Sub-caption fade/scale so it feels softer out of the hero view
  const subOpacity = useTransform(smoothProgress, [0, 0.15], [0.8, 0.5]);
  const subScale = useTransform(smoothProgress, [0, 0.15], [1, 0.9]);

  // Section 2 Insight Text Fade (0.15 -> 0.3)
  const insightOpacity = useTransform(smoothProgress, [0.18, 0.25, 0.35], [0, 1, 0]);
  const insightY = useTransform(smoothProgress, [0.18, 0.35], [20, -20]);

  return (
    <div ref={containerRef} className="relative w-full bg-[#0a0a0a] m-0 p-0 font-sans">
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .story-text-enter {
          animation: fadeInUp 0.7s ease forwards;
        }
      `}</style>

      {/* ── STICKY NAV/HERO LOGO ──────────────────────────────── */}
      <motion.div
        className="fixed z-50 pointer-events-none flex flex-col items-start"
        style={{
          top: logoTop,
          left: logoLeft,
          x: logoTranslateX,
          y: logoTranslateY,
          scale: logoScale,
          transformOrigin: "top left"
        }}
      >
        <div className="text-white text-4xl tracking-tight font-bold pointer-events-auto">
          Gamana
        </div>
        <motion.div
          className="text-sm text-gray-500 font-medium tracking-widest mt-1 uppercase"
          style={{ opacity: subOpacity, scale: subScale, originX: 0 }}
        >
          Traffic Intelligence System
        </motion.div>
      </motion.div>

      {/* ── SECTION 1: HERO INTRO (EMPTY SPACE FOR CENTER LOGO) ── */}
      <section className="relative w-full h-screen flex items-center justify-center pointer-events-none">
        {/* Just padding for the scroll container */}
      </section>

      {/* ── SECTION 2: INSIGHT TEXT ────────────────────────────── */}
      <section className="relative w-full h-screen flex flex-col items-center justify-center bg-[#0a0a0a]">
        <motion.h2
          className="text-4xl md:text-5xl font-semibold text-slate-200 text-center leading-tight max-w-3xl"
          style={{ opacity: insightOpacity, y: insightY }}
        >
          Behind every traffic jam,<br />
          there's a hidden pattern.
        </motion.h2>
      </section>

      {/* ── SECTION 3: RIPPLE STORY ───────────────────────────── */}
      <section className="relative w-full min-h-screen overflow-hidden">
        <div className="absolute inset-0 z-0">
          <Canvas shadows dpr={[1, 2]} gl={{ antialias: true }}>
            <color attach="background" args={['#0a0a0a']} />
            <fog attach="fog" args={['#0a0a0a', 30, 120]} />
            <PerspectiveCamera
              makeDefault
              position={[-38, 11, 22]}
              fov={60}
              near={0.1}
              far={300}
              onUpdate={(c) => c.lookAt(-18, 0, -2)}
            />
            <Intersection3D />
          </Canvas>
        </div>

        {/* Gradient fade — blends bottom of canvas into the text section */}
        <div
          className="absolute bottom-0 left-0 w-full z-10 pointer-events-none"
          style={{ height: '180px', background: 'linear-gradient(to bottom, transparent, #0a0a0a)' }}
        />
      </section>

      {/* ── SECTION 4: SOLUTION INTRO TEXT ────────────────────── */}
      <div className="relative w-full min-h-screen flex flex-col items-center justify-center bg-[#0a0a0a]">
        <h1 className="story-text-enter text-4xl md:text-5xl font-semibold text-slate-200 text-center leading-snug">
          Traffic isn't random.<br />
          It's predictable.
        </h1>
      </div>

      {/* ── SECTION 5: SOLUTION STORY ─────────────────────────── */}
      <section className="relative w-full min-h-screen bg-[#0a0a0a] overflow-hidden">
        <div className="absolute inset-0 z-0">
          <Canvas shadows dpr={[1, 2]} gl={{ antialias: true }}>
            <color attach="background" args={['#0a0a0a']} />
            <fog attach="fog" args={['#0a0a0a', 30, 120]} />
            <PerspectiveCamera
              makeDefault
              position={[-38, 11, 22]}
              fov={60}
              near={0.1}
              far={300}
              onUpdate={(c) => c.lookAt(-18, 0, -2)}
            />
            <SolutionIntersection3D />
          </Canvas>
        </div>

        {/* Grand Finale CTA Gradient fade */}
        <div
          className="absolute bottom-0 left-0 w-full z-10 pointer-events-none"
          style={{ height: '300px', background: 'linear-gradient(to bottom, transparent, #0a0a0a)' }}
        />

        {/* Dashboard button at the very end of the scroll */}
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
          <motion.button
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.8, delay: 0.5 }}
            onClick={onLaunch}
            className="rounded-lg border border-[#D4AF37]/40 bg-[#0B0B0B]/90 backdrop-blur-md px-10 py-5 text-sm font-bold tracking-[0.2em] text-[#D4AF37] transition-all hover:bg-[#D4AF37] hover:text-black pointer-events-auto shadow-[0_0_40px_rgba(212,175,55,0.15)] hover:shadow-[0_0_60px_rgba(212,175,55,0.4)] hover:scale-105"
          >
            ENTER DASHBOARD
          </motion.button>
        </div>
      </section>

    </div>
  );
}