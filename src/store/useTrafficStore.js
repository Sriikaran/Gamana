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
    const id = setInterval(() => {
      set((state) => {
        if (!state.stats) return state;

        const vehicleDelta = Math.floor(Math.random() * 40) - 10;
        const speedDelta = Math.floor(Math.random() * 6) - 3;
        const congestionDelta = Math.floor(Math.random() * 4) - 1;

        const newVehicles = Math.max(0, state.stats.totalVehicles + vehicleDelta);
        const newSpeed = Math.max(5, Math.min(80, state.stats.avgSpeed + speedDelta));
        const newCongestion = Math.max(0, Math.min(100, state.stats.congestionLevel + congestionDelta));

        // Rotate signal statuses randomly
        const statusOptions = ['green', 'red', 'yellow'];
        const newSignals = state.signals.map((sig) => ({
          ...sig,
          timer: Math.max(1, sig.timer + Math.floor(Math.random() * 7) - 3),
          status:
            Math.random() < 0.15
              ? statusOptions[Math.floor(Math.random() * 3)]
              : sig.status,
        }));

        // Push new point to trend chart (keep last 12 points)
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const newTrend = [
          ...state.trafficTrend.slice(-11),
          { time: timeStr, vehicles: Math.floor(Math.random() * 600) + 200 },
        ];

        return {
          stats: {
            ...state.stats,
            totalVehicles: newVehicles,
            avgSpeed: newSpeed,
            congestionLevel: newCongestion,
          },
          signals: newSignals,
          trafficTrend: newTrend,
        };
      });
    }, 3000);

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
