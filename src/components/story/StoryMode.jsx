import { Canvas } from '@react-three/fiber';
import { PerspectiveCamera } from '@react-three/drei';
import Intersection3D from './Intersection3D';

export default function StoryMode({ onLaunch }) {
  return (
    <div className="relative w-full h-screen bg-[#0a0a0a] overflow-hidden m-0 p-0">

      {/* 3D Scene — all story text is rendered INSIDE the canvas in 3D space */}
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

      {/* Dashboard button — only non-3D UI element */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10">
        <button
          onClick={onLaunch}
          className="rounded-lg border border-[#333333] bg-[#121212]/80 backdrop-blur-sm px-6 py-3 text-sm font-semibold tracking-widest text-[#A0A0A0] transition-colors hover:border-[#D4AF37] hover:text-white"
        >
          ENTER DASHBOARD
        </button>
      </div>
    </div>
  );
}
