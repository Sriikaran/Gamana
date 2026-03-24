import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Car, Gauge, AlertTriangle, Radio, BrainCircuit } from 'lucide-react';
import useTrafficStore from '../store/useTrafficStore';
import StatCard from '../components/cards/StatCard';
import TrafficPanel from '../components/panels/TrafficPanel';
import SignalPanel from '../components/panels/SignalPanel';
import AlertsPanel from '../components/panels/AlertsPanel';
import TrafficChart from '../components/charts/TrafficChart';
import TrafficMap from '../components/maps/TrafficMap';

const getSystemStatus = (congestion) => {
  if (congestion > 70) return { label: 'CRITICAL', dot: 'bg-[#D94A4A]' };
  if (congestion > 40) return { label: 'WARNING', dot: 'bg-[#D9A04A]' };
  return { label: 'STABLE', dot: 'bg-[#4AD986]' };
};

const Dashboard = () => {
  const { stats, trafficTrend, isLoading, fetchAll, startSimulation, stopSimulation } =
    useTrafficStore();

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Start simulation after data is loaded
  useEffect(() => {
    if (stats && !isLoading) {
      startSimulation();
      return () => stopSimulation();
    }
  }, [stats !== null && !isLoading]);

  if (isLoading || !stats) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-[2px] border-[#333333] border-t-[#D4AF37]" />
          <p className="text-sm font-medium text-[#A0A0A0]">Initializing systems</p>
        </div>
      </div>
    );
  }

  const status = getSystemStatus(stats.congestionLevel);

  const statCards = [
    {
      title: 'Total Vehicles',
      value: stats.totalVehicles,
      trend: stats.trends.totalVehicles,
      icon: Car,
    },
    {
      title: 'Avg Speed',
      value: stats.avgSpeed,
      unit: 'km/h',
      trend: stats.trends.avgSpeed,
      icon: Gauge,
    },
    {
      title: 'Congestion',
      value: stats.congestionLevel,
      unit: '%',
      trend: stats.trends.congestionLevel,
      icon: AlertTriangle,
    },
    {
      title: 'Active Signals',
      value: stats.activeSignals,
      trend: stats.trends.activeSignals,
      icon: Radio,
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-10 pb-8"
    >
      {/* Header with AI status */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between border-b border-[#1F1F1F] pb-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white mb-1">Dashboard</h2>
          <p className="text-sm font-medium text-[#A0A0A0]">
            System Overview & Analytics
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-md bg-[#121212] border border-[#1F1F1F] px-4 py-2 opacity-90">
          <BrainCircuit size={14} className="text-[#D4AF37]" />
          <span className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider">Status</span>
          <div className="w-px h-3 bg-[#333333] mx-1"></div>
          <span className="flex items-center gap-2 text-xs font-bold text-white tracking-widest uppercase">
            {status.label}
            <span className={`h-1.5 w-1.5 rounded-full ${status.dot} shadow-[0_0_8px_rgba(255,255,255,0.2)]`} />
          </span>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {statCards.map((card) => (
          <StatCard key={card.title} {...card} />
        ))}
      </div>

      {/* Traffic chart */}
      <TrafficPanel />

      {/* Bottom panels */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <SignalPanel />
        <AlertsPanel />
      </div>

      {/* Short-term traffic trend (live updating) */}
      <TrafficChart data={trafficTrend} />

      {/* Live Map */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <TrafficMap />
      </motion.div>
    </motion.div>
  );
};

export default Dashboard;
