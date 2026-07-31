import React from 'react';
import { motion } from 'framer-motion';

const ConfidenceBar = ({ confidence }) => {
  const clampedConfidence = Math.max(0, Math.min(100, confidence || 0));
  
  // Determine color based on confidence level
  let color = '#D4AF37'; // Gold
  if (clampedConfidence < 50) color = '#EF4444'; // Red
  else if (clampedConfidence > 80) color = '#10B981'; // Green

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs font-semibold text-[#A0A0A0] uppercase tracking-wider">AI Confidence</span>
        <span className="text-xs font-bold text-white">{clampedConfidence}%</span>
      </div>
      <div className="h-1.5 w-full bg-[#1F1F1F] rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${clampedConfidence}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
        />
      </div>
    </div>
  );
};

export default ConfidenceBar;
