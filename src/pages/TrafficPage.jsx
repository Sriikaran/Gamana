import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { TrafficCone } from 'lucide-react';
import useTrafficStore from '../store/useTrafficStore';
import TrafficPanel from '../components/panels/TrafficPanel';
import TrafficChart from '../components/charts/TrafficChart';
import TrafficMap from '../components/maps/TrafficMap';

const TrafficPage = () => {
  const { stats, trafficTrend, isLoading, fetchAll, startSimulation, stopSimulation } =
    useTrafficStore();

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

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
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-8 pb-8"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between border-b border-[#1F1F1F] pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <TrafficCone size={20} className="text-[#D4AF37]" />
            <h2 className="text-2xl font-bold tracking-tight text-white mb-1">Traffic Analytics</h2>
          </div>
          <p className="text-sm font-medium text-[#A0A0A0]">
            Live traffic flow monitoring & deep analysis
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-8">
        <div className="space-y-8 min-w-0">
          <TrafficPanel />
          <TrafficChart data={trafficTrend} />
          <div className="h-[400px]">
            <TrafficMap />
          </div>
        </div>

        <div className="space-y-8 xl:sticky xl:top-8 xl:self-start">
          <div className="bg-[#121212] rounded-xl border border-[#1F1F1F] p-6 shadow-sm">
             <h3 className="text-xs font-bold text-white uppercase tracking-[0.2em] mb-4">Traffic Insights</h3>
             <p className="text-sm text-[#A0A0A0] leading-relaxed">
               Average speeds and congestion levels are monitored continuously. The neural engine models predictive flow mapping to route emergency vehicles efficiently.
             </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default TrafficPage;
