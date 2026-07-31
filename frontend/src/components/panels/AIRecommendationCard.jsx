import React, { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, AlertCircle, CheckCircle2, Zap, Clock, Activity, Target, AlignLeft, Server, Cpu, Database } from 'lucide-react';
import ConfidenceBar from '../charts/ConfidenceBar';

const AIRecommendationCard = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [latency, setLatency] = useState(null);
  const [showToast, setShowToast] = useState(false);
  const lastUpdateRef = useRef(null);

  useEffect(() => {
    let intervalId;
    
    const fetchAIRecommendation = async () => {
      const startTime = performance.now();
      try {
        const response = await fetch('/api/ai_recommendation');
        if (!response.ok) {
          throw new Error('API Error');
        }
        const result = await response.json();
        const endTime = performance.now();
        setLatency(Math.round(endTime - startTime));
        
        if (result.status === "fallback" || result.error) {
          setError(result.error || "Featherless AI not connected or API key missing");
          setData(result);
        } else {
          setData(result);
          setError(null);
          
          if (lastUpdateRef.current && result.response_timestamp && result.response_timestamp !== lastUpdateRef.current) {
            setShowToast(true);
            setTimeout(() => setShowToast(false), 2500);
          }
          if (result.response_timestamp) {
            lastUpdateRef.current = result.response_timestamp;
          }
        }
      } catch (err) {
        console.error('Failed to fetch AI recommendation:', err);
        setError('Connection to AI service lost.');
      }
    };

    fetchAIRecommendation();
    intervalId = setInterval(fetchAIRecommendation, 3000);

    return () => clearInterval(intervalId);
  }, []);

  const confidencePercent = data?.confidence ? Math.round(data.confidence * 100) : 0;
  const isFallback = error || (data?.status === 'fallback');

  let statusConfig = { label: 'Offline', color: 'bg-red-500', ping: false };
  if (isFallback) {
    statusConfig = { label: 'Fallback', color: 'bg-orange-500', ping: true };
  } else if (data?.processing) {
    statusConfig = { label: 'Processing', color: 'bg-yellow-500', ping: true };
  } else if (data) {
    statusConfig = { label: 'Active', color: 'bg-[#10B981]', ping: true };
  }

  const formatTime = (ts) => {
    if (!ts) return '--';
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString();
  };

  return (
    <div className="bg-[#0B0B0B] rounded-xl border border-[#1F1F1F] shadow-2xl overflow-hidden flex flex-col h-full relative">
      {/* Premium Header */}
      <div className="p-5 border-b border-[#1F1F1F] flex items-center justify-between bg-gradient-to-r from-[#121212] via-[#1a1a1a] to-[#121212] relative">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-[#D4AF37]/10 rounded-xl border border-[#D4AF37]/20 shadow-[0_0_15px_rgba(212,175,55,0.15)]">
            <Brain size={20} className="text-[#D4AF37]" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">Featherless AI</h2>
            <p className="text-[10px] text-[#A0A0A0] uppercase tracking-[0.2em]">Command Center</p>
          </div>
        </div>
        
        {/* Status Indicator */}
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-white">
              {statusConfig.label}
            </span>
            <span className="relative flex h-3 w-3">
              {statusConfig.ping && (
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${statusConfig.color}`}></span>
              )}
              <span className={`relative inline-flex rounded-full h-3 w-3 ${statusConfig.color}`}></span>
            </span>
          </div>
        </div>

        {/* Update Toast */}
        <AnimatePresence>
          {showToast && (
            <motion.div 
              initial={{ opacity: 0, y: -20, x: '-50%' }}
              animate={{ opacity: 1, y: 0, x: '-50%' }}
              exit={{ opacity: 0, y: -20, x: '-50%' }}
              className="absolute left-1/2 top-4 bg-[#D4AF37] text-black px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider shadow-[0_0_15px_rgba(212,175,55,0.3)] flex items-center gap-2"
            >
              <Zap size={14} /> Recommendation Updated
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Main Content Area */}
      <div className="p-6 flex-1 flex flex-col overflow-y-auto custom-scrollbar">
        <AnimatePresence mode="wait">
          {isFallback ? (
            <motion.div 
              key="error"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex flex-col items-center justify-center text-center space-y-4"
            >
              <div className="p-4 bg-orange-500/10 rounded-full border border-orange-500/20">
                <AlertCircle size={40} className="text-orange-500" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-bold text-white tracking-tight">AI Offline</h3>
                <p className="text-sm text-[#A0A0A0] max-w-[250px] leading-relaxed">
                  {error || "Gamana fallback controller is currently managing intersections."}
                </p>
              </div>
            </motion.div>
          ) : !data ? (
            <motion.div 
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex flex-col items-center justify-center space-y-6"
            >
              <div className="relative">
                <div className="h-12 w-12 animate-spin rounded-full border-2 border-[#1F1F1F] border-t-[#D4AF37]" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <Brain size={16} className="text-[#D4AF37] opacity-50" />
                </div>
              </div>
              <p className="text-sm text-[#A0A0A0] animate-pulse tracking-wide">Syncing with Neural Engine...</p>
            </motion.div>
          ) : (
            <motion.div 
              key="content"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="space-y-6"
            >
              {/* Processing Overlay */}
              {data.processing && (
                <div className="bg-[#D4AF37]/10 border border-[#D4AF37]/20 rounded-lg p-3 flex items-center justify-center gap-3 animate-pulse">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-transparent border-t-[#D4AF37]" />
                  <span className="text-xs font-bold text-[#D4AF37] uppercase tracking-wider">Analyzing latest traffic...</span>
                </div>
              )}

              {/* Primary Strategy */}
              <div className="bg-[#121212] p-5 rounded-xl border border-[#1F1F1F] space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-[#A0A0A0] uppercase tracking-widest flex items-center gap-2">
                    <Target size={14} className="text-[#D4AF37]" /> Current Strategy
                  </h4>
                  <div className="flex items-center gap-4 text-[10px] uppercase tracking-wider text-[#666]">
                    <span className="flex items-center gap-1"><Clock size={12}/> Rec Age: {data.recommendation_age_s?.toFixed(1)}s</span>
                  </div>
                </div>

                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-xs text-[#666] uppercase font-bold tracking-wider mb-1">Recommended Lane</p>
                    <p className="text-2xl font-bold text-white tracking-tight">{data.recommended_lane || "Auto"}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-[#666] uppercase font-bold tracking-wider mb-1">Green Time</p>
                    <p className="text-2xl font-bold text-[#D4AF37] tracking-tight">{data.green_duration || 0}<span className="text-sm text-[#A0A0A0] ml-1">sec</span></p>
                  </div>
                </div>
              </div>

              {/* Metrics Bar */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-[#121212] p-3 rounded-lg border border-[#1F1F1F]">
                  <p className="text-[9px] text-[#666] uppercase font-bold mb-1">Response Latency</p>
                  <p className="text-sm text-white font-mono">{latency || '--'} ms</p>
                </div>
                <div className="bg-[#121212] p-3 rounded-lg border border-[#1F1F1F]">
                  <p className="text-[9px] text-[#666] uppercase font-bold mb-1">Inference Time</p>
                  <p className="text-sm text-white font-mono">{data.inference_time_ms ? (data.inference_time_ms / 1000).toFixed(2) : '--'} s</p>
                </div>
                <div className="bg-[#121212] p-3 rounded-lg border border-[#1F1F1F]">
                  <p className="text-[9px] text-[#666] uppercase font-bold mb-1">Confidence</p>
                  <p className="text-sm text-white font-mono">{confidencePercent}%</p>
                </div>
              </div>

              {/* Reasoning */}
              <div className="space-y-3 pt-2">
                <h4 className="text-xs font-bold text-[#A0A0A0] uppercase tracking-widest flex items-center gap-2">
                  <AlignLeft size={14} className="text-[#D4AF37]" /> AI Reasoning
                </h4>
                <div className="bg-[#121212] rounded-xl border border-[#1F1F1F] p-4">
                  {data.reasoning && data.reasoning.length > 0 ? (
                    <ul className="space-y-2">
                      {data.reasoning.map((point, idx) => (
                        <li key={idx} className="flex items-start gap-2.5 text-sm text-[#D1D5DB] leading-relaxed">
                          <span className="text-[#D4AF37] mt-1 text-[10px]">■</span>
                          {point}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-[#666] italic">No detailed reasoning provided.</p>
                  )}
                </div>
              </div>

              {/* Priority Factors (Chips) */}
              {data.priority_factors && data.priority_factors.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-[#A0A0A0] uppercase tracking-widest">Priority Factors</h4>
                  <div className="flex flex-wrap gap-2">
                    {data.priority_factors.map((factor, idx) => (
                      <span key={idx} className="bg-[#1a1a1a] text-[#A0A0A0] text-xs px-3 py-1.5 rounded-full border border-[#2a2a2a] shadow-sm">
                        {factor}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Future Prediction */}
              {data.future_prediction && (
                <div className="mt-4 bg-[#1a1a1a]/50 p-4 rounded-xl border border-[#D4AF37]/20 relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-1 h-full bg-[#D4AF37]"></div>
                  <h4 className="text-[10px] font-bold text-[#D4AF37] uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
                    <Activity size={12} /> Predictive Forecast
                  </h4>
                  <p className="text-sm text-white/90 leading-relaxed">
                    {data.future_prediction}
                  </p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      
      {/* System Health Footer */}
      <div className="border-t border-[#1F1F1F] bg-[#0f0f0f] p-3 text-[10px] uppercase tracking-wider grid grid-cols-2 md:grid-cols-4 gap-2">
        <div className="flex items-center gap-2">
          <Server size={10} className="text-[#666]"/>
          <span className="text-[#666]">Backend:</span>
          <span className={data?.backend_status === 'ok' ? 'text-[#10B981]' : 'text-red-500'}>
            {data?.backend_status === 'ok' ? 'Connected' : 'Error'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Activity size={10} className="text-[#666]"/>
          <span className="text-[#666]">API:</span>
          <span className={data?.api_status === 'ok' ? 'text-[#10B981]' : 'text-red-500'}>
            {data?.api_status === 'ok' ? 'Connected' : 'Error'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Cpu size={10} className="text-[#666]"/>
          <span className="text-[#666]">Model:</span>
          <span className="text-[#A0A0A0]">{data?.model || 'Unknown'}</span>
        </div>
        <div className="flex items-center gap-2">
          <Database size={10} className="text-[#666]"/>
          <span className="text-[#666]">Queue:</span>
          <span className={data?.queue_status === 'healthy' ? 'text-[#10B981]' : 'text-orange-400'}>
            {data?.queue_status || 'Unknown'}
          </span>
        </div>
        <div className="col-span-2 md:col-span-4 flex items-center gap-2 pt-1 mt-1 border-t border-[#1F1F1F]/50">
          <Clock size={10} className="text-[#666]"/>
          <span className="text-[#666]">Last Success:</span>
          <span className="text-[#A0A0A0]">{formatTime(data?.last_updated)}</span>
        </div>
      </div>
    </div>
  );
};

export default AIRecommendationCard;

