import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import useTrafficStore from '../../store/useTrafficStore';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#1F1F1F] bg-[#0B0B0B] px-4 py-3 shadow-xl">
      <p className="mb-2 text-xs font-semibold text-[#A0A0A0]">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-xs flex items-center justify-between gap-4" style={{ color: entry.color }}>
          <span className="font-medium text-[#A0A0A0]">{entry.name}</span>
          <span className="font-bold text-white tracking-wide">{entry.value.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
};

const TrafficPanel = () => {
  const hourlyTraffic = useTrafficStore((s) => s.hourlyTraffic);

  return (
    <div className="rounded-xl border border-[#1F1F1F] bg-[#121212] p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white tracking-wide">Traffic Flow</h3>
          <p className="text-xs font-medium text-[#666666]">Hourly vehicle count &amp; average speed</p>
        </div>
        <span className="rounded-md border border-[#1F1F1F] bg-[#0B0B0B] px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-[#D4AF37]">
          Live
        </span>
      </div>

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={hourlyTraffic} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="vehicleGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#D4AF37" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#D4AF37" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="speedGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#A0A0A0" stopOpacity={0.1} />
                <stop offset="100%" stopColor="#A0A0A0" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" vertical={false} />
            <XAxis
              dataKey="hour"
              tick={{ fill: '#666666', fontSize: 11, fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
              dy={10}
            />
            <YAxis
              tick={{ fill: '#666666', fontSize: 11, fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
              dx={-10}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#333333', strokeWidth: 1, strokeDasharray: '3 3' }} />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 10, color: '#A0A0A0' }}
              iconType="circle"
              iconSize={6}
            />
            <Area
              type="basis"
              dataKey="vehicles"
              name="Vehicles"
              stroke="#D4AF37"
              strokeWidth={2}
              fill="url(#vehicleGrad)"
              activeDot={{ r: 4, fill: '#D4AF37', stroke: '#0B0B0B', strokeWidth: 2 }}
            />
            <Area
              type="basis"
              dataKey="speed"
              name="Avg Speed (km/h)"
              stroke="#A0A0A0"
              strokeWidth={2}
              fill="url(#speedGrad)"
              activeDot={{ r: 4, fill: '#A0A0A0', stroke: '#0B0B0B', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TrafficPanel;
