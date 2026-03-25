import React from 'react';
import { motion } from 'framer-motion';

const Dashboard = () => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
      // Use negative margins to perfectly counteract the padding in MainLayout so it goes edge-to-edge
      className="-m-4 sm:-m-8 lg:-m-10 xl:-m-12 h-[calc(100vh-65px)] lg:h-screen"
    >
      <iframe
        src="/backend"
        className="w-full h-full border-none"
        title="Pragati AI Backend Dashboard"
      />
    </motion.div>
  );
};

export default Dashboard;
