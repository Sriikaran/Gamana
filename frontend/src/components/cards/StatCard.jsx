import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const StatCard = ({ title, value, unit, trend, icon: Icon }) => {
  const isPositive = trend > 0;
  const isNegative = trend < 0;

  const trendIcon = isPositive ? (
    <TrendingUp size={14} className="text-[#4AD986]" />
  ) : isNegative ? (
    <TrendingDown size={14} className="text-[#D94A4A]" />
  ) : (
    <Minus size={14} className="text-[#666666]" />
  );

  const trendColor = isPositive ? 'text-[#4AD986]' : isNegative ? 'text-[#D94A4A]' : 'text-[#666666]';

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -4 }}
      className={`
        relative overflow-hidden rounded-xl border border-[#1F1F1F]
        bg-[#121212]
        p-6 shadow-sm
        transition-all duration-300 hover:border-[#333333] hover:shadow-lg hover:shadow-black/50
      `}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-[#A0A0A0]">
            {title}
          </p>
          <div className="flex items-baseline gap-1.5">
            <motion.span
              key={value}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="text-3xl font-bold tracking-tight text-white"
            >
              {typeof value === 'number' ? value.toLocaleString() : value}
            </motion.span>
            {unit && <span className="text-sm font-medium text-[#666666]">{unit}</span>}
          </div>
          {trend !== undefined && (
            <div className={`flex items-center gap-1.5 text-xs font-semibold ${trendColor}`}>
              {trendIcon}
              <span>{Math.abs(trend)}%</span>
              <span className="text-[#666666] font-medium tracking-wide">vs last hour</span>
            </div>
          )}
        </div>

        {Icon && (
          <div className="text-[#666666]">
            <Icon size={20} strokeWidth={1.5} />
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default StatCard;
