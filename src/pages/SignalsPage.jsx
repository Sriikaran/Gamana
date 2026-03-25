import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Radio } from 'lucide-react';
import useTrafficStore from '../store/useTrafficStore';
import SignalPanel from '../components/panels/SignalPanel';

const SignalsPage = () => {
  const { signals, isLoading, fetchAll, startSimulation, stopSimulation } = useTrafficStore();

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (signals.length > 0 && !isLoading) {
      startSimulation();
      return () => stopSimulation();
    }
  }, [signals.length > 0 && !isLoading]);

  if (isLoading || signals.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-[2px] border-[#333333] border-t-[#D4AF37]" />
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
            <Radio size={20} className="text-[#D4AF37]" />
            <h2 className="text-2xl font-bold tracking-tight text-white mb-1">Signal Control</h2>
          </div>
          <p className="text-sm font-medium text-[#A0A0A0]">
            Real-time traffic signal monitoring across all active zones
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        <SignalPanel />
      </div>
    </motion.div>
  );
};

export default SignalsPage;
