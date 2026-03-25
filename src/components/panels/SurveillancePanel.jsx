import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Video, Circle, MonitorPlay, Maximize2, Minimize2, AlertTriangle } from 'lucide-react';
import useTrafficStore from '../../store/useTrafficStore';

const SurveillancePanel = () => {
  const { lanes, stats } = useTrafficStore();
  const [isExpanded, setIsExpanded] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const frameCount = stats ? Math.floor(Date.now() / 100) % 999 : 0;
  const mockAlert = { type: 'Stopped Vehicle', lane: 'RIGHT' };

  return (
    <div className="bg-[#121212] rounded-xl border border-[#1F1F1F] shadow-lg overflow-hidden relative group">
      {/* Header bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#1F1F1F] bg-[#0B0B0B]/80 relative z-10">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#D4AF37]/10 border border-[#D4AF37]/20">
            <Video size={16} className="text-[#D4AF37]" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">CCTV Surveillance</h3>
            <p className="text-[10px] text-[#A0A0A0] font-medium uppercase tracking-wider">Live Intersection</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2 rounded bg-[#D94A4A]/10 border border-[#D94A4A]/20 px-2 py-1 shadow-[0_0_10px_rgba(217,74,74,0.1)]">
            <Circle size={8} className="text-[#D94A4A] fill-[#D94A4A] animate-pulse" />
            <span className="text-[10px] font-bold text-[#D94A4A] tracking-[0.2em] uppercase">REC</span>
          </span>
          <span className="text-[11px] text-[#A0A0A0] font-mono font-bold">
            {currentTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded hover:bg-[#1F1F1F] text-[#666666] hover:text-[#FFFFFF] transition-colors cursor-pointer"
          >
            {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </div>

      {/* Single video feed area */}
      <div className="relative z-10 p-4" style={{ aspectRatio: isExpanded ? '16/8' : '16/6' }}>
        <div className="absolute inset-4 rounded-lg overflow-hidden bg-black border border-[#1F1F1F] shadow-inner font-mono">
          {/* Grid overlay */}
          <div className="absolute inset-0 opacity-20" style={{
            backgroundImage: `
              linear-gradient(rgba(212,175,55,0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(212,175,55,0.1) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px',
          }} />

          {/* Lane dividers */}
          {[25, 50, 75].map((pct) => (
            <div
              key={pct}
              className="absolute top-0 bottom-0 w-[1px] bg-[#D4AF37]/20 shadow-[0_0_10px_rgba(212,175,55,0.2)]"
              style={{ left: `${pct}%` }}
            />
          ))}

          {/* Scan line animation */}
          <motion.div
            className="absolute left-0 right-0 h-[2px] bg-[#D4AF37]/30 shadow-[0_0_15px_rgba(212,175,55,0.5)]"
            animate={{ top: ['0%', '100%'] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
          />

          {/* Center placeholder content */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4 opacity-70 relative">
              <div className="absolute inset-0 bg-[#D4AF37]/5 blur-[40px] rounded-full" />
              <MonitorPlay size={40} className="text-[#D4AF37] drop-shadow-[0_0_10px_rgba(212,175,55,0.4)]" />
              <span className="text-[10px] font-bold tracking-[0.3em] uppercase text-[#D4AF37]/80">
                Video Feed — Connect Backend
              </span>
            </div>
          </div>

          {/* Corner brackets */}
          <div className="absolute top-3 left-3 w-6 h-6 border-l border-t border-[#D4AF37]/30 rounded-tl" />
          <div className="absolute top-3 right-3 w-6 h-6 border-r border-t border-[#D4AF37]/30 rounded-tr" />
          <div className="absolute bottom-3 left-3 w-6 h-6 border-l border-b border-[#D4AF37]/30 rounded-bl" />
          <div className="absolute bottom-3 right-3 w-6 h-6 border-r border-b border-[#D4AF37]/30 rounded-br" />
        </div>

        {/* Floating lane status overlays */}
        <div className="absolute top-8 right-8 space-y-3 z-10 w-[180px]">
          {(lanes || [{ id: 1, label: 'LANE 1', pressure: 85 }, { id: 2, label: 'LANE 2', pressure: 40 }]).slice(0, 2).map((lane) => {
            const isHigh = lane.pressure > 70;
            const color = isHigh ? '#D94A4A' : '#4AD986';
            return (
              <div key={lane.id} className="rounded bg-[#0B0B0B]/90 backdrop-blur-md border border-[#1F1F1F] shadow-xl px-3 py-2.5">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full animate-pulse shadow-[0_0_6px_currentColor]" style={{ backgroundColor: color, color: color }} />
                    <span className="text-[10px] font-bold text-white tracking-widest uppercase">{lane.label}</span>
                  </div>
                  <span className={`text-[9px] font-bold tracking-widest px-1.5 py-0.5 rounded border ${
                    isHigh ? 'bg-[#D94A4A]/10 border-[#D94A4A]/20 text-[#D94A4A]' : 'bg-[#4AD986]/10 border-[#4AD986]/20 text-[#4AD986]'
                  }`}>
                    {isHigh ? 'HIGH' : 'LOW'}
                  </span>
                </div>
                <div className="h-1 rounded-full bg-[#333333] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: lane.pressure > 70 ? '#D94A4A' : lane.pressure > 45 ? '#D9A04A' : '#4AD986' }}
                    animate={{ width: `${lane.pressure}%` }}
                    transition={{ duration: 0.6 }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Alert banner at bottom */}
        {frameCount % 200 > 150 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10"
          >
            <div className="px-4 py-2 rounded bg-[#D9A04A]/10 backdrop-blur-md border border-[#D9A04A]/30 flex items-center gap-2">
              <AlertTriangle size={14} className="text-[#D9A04A]" />
              <span className="text-[10px] font-bold text-[#D9A04A] tracking-[0.2em] uppercase mt-0.5">
                {mockAlert.type} in {mockAlert.lane}
              </span>
            </div>
          </motion.div>
        )}
      </div>

      {/* Bottom status bar */}
      <div className="flex items-center justify-between px-6 py-3 border-t border-[#1F1F1F] bg-[#0B0B0B]/80 relative z-10 text-[9px] font-mono text-[#666666] uppercase tracking-widest">
        <span>Frame: {frameCount} <span className="mx-2 text-[#333333]">|</span> Vehicles: {stats?.totalVehicles || 0}</span>
        <span>Pragati AI <span className="mx-2 text-[#333333]">|</span> Spatial Feed</span>
      </div>
    </div>
  );
};

export default SurveillancePanel;
