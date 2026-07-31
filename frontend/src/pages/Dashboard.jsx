import React from 'react';
import { motion } from 'framer-motion';
import AIRecommendationCard from '../components/panels/AIRecommendationCard';

const Dashboard = () => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
      className="flex flex-col xl:flex-row h-full w-full gap-4 pb-4"
    >
      {/* Live Video / Legacy Dashboard Panel (70%) */}
      <div className="w-full xl:w-[70%] h-[800px] xl:h-[calc(100vh-85px)] rounded-xl overflow-hidden border border-[#1F1F1F] bg-black shadow-lg">
        <iframe
          src="/backend"
          className="w-full h-full border-none"
          title="Pragati AI Backend Dashboard"
        />
      </div>

      {/* AI Command Center (30%) */}
      <div className="w-full xl:w-[30%] h-auto xl:h-[calc(100vh-85px)]">
        <AIRecommendationCard />
      </div>
    </motion.div>
  );
};

export default Dashboard;
