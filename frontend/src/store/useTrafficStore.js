import { create } from 'zustand';
import { fetchTrafficStats, fetchHourlyTraffic, fetchTrafficTrend } from '../services/trafficService';
import { fetchSignals } from '../services/signalService';
import { fetchViolations } from '../services/violationService';

const useTrafficStore = create((set) => ({
  // ── State ──
  stats: null,
  hourlyTraffic: [],
  trafficTrend: [],
  signals: [],
  violations: [],
  isLoading: false,
  error: null,

  // ── Actions ──
  fetchAll: async () => {
    set({ isLoading: true, error: null });
    try {
      const [stats, hourlyTraffic, trafficTrend, signals, violations] = await Promise.all([
        fetchTrafficStats(),
        fetchHourlyTraffic(),
        fetchTrafficTrend(),
        fetchSignals(),
        fetchViolations(),
      ]);
      set({ stats, hourlyTraffic, trafficTrend, signals, violations, isLoading: false });
    } catch (error) {
      set({ error: error.message, isLoading: false });
    }
  },

  refreshStats: async () => {
    try {
      const stats = await fetchTrafficStats();
      set({ stats });
    } catch (error) {
      set({ error: error.message });
    }
  },

  refreshSignals: async () => {
    try {
      const signals = await fetchSignals();
      set({ signals });
    } catch (error) {
      set({ error: error.message });
    }
  },

  refreshViolations: async () => {
    try {
      const violations = await fetchViolations();
      set({ violations });
    } catch (error) {
      set({ error: error.message });
    }
  },

  // ── Live simulation ──
  _intervalId: null,

  startSimulation: () => {
    // Clear existing interval if any
    set((state) => {
      if (state._intervalId) clearInterval(state._intervalId);
      return {};
    });

    const id = setInterval(async () => {
      try {
        const res = await fetch('/api/lanes');
        if (!res.ok) return;
        const data = await res.json();
        
        let totalVehicles = 0;
        let totalPressure = 0;
        let laneCount = 0;
        let congestionScore = 10;

        if (data.lanes) {
          Object.values(data.lanes).forEach(lane => {
            totalVehicles += (lane.total || 0);
            totalPressure += (lane.pressure || 0);
            laneCount++;
            
            if (lane.congestion_level === 'CRITICAL') congestionScore = Math.max(congestionScore, 90);
            else if (lane.congestion_level === 'HIGH') congestionScore = Math.max(congestionScore, 75);
            else if (lane.congestion_level === 'MEDIUM') congestionScore = Math.max(congestionScore, 50);
          });
        }

        const avgPressure = laneCount > 0 ? (totalPressure / laneCount) : 0;
        const avgSpeed = Math.max(5, Math.floor(60 - (avgPressure * 30))); // Sync mapped logical speed

        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        set((state) => {
          if (!state.stats) return state;

          const newTrend = [
            ...state.trafficTrend.slice(-11),
            { time: timeStr, vehicles: totalVehicles },
          ];

          return {
            stats: {
              ...state.stats,
              totalVehicles: totalVehicles,
              avgSpeed: avgSpeed,
              congestionLevel: congestionScore,
            },
            trafficTrend: newTrend,
          };
        });
      } catch (err) {
        console.error("Live Simulation API sync error:", err);
      }
    }, 2000);

    set({ _intervalId: id });
  },

  stopSimulation: () => {
    set((state) => {
      if (state._intervalId) clearInterval(state._intervalId);
      return { _intervalId: null };
    });
  },
}));

export default useTrafficStore;
