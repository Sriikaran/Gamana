import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

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

const TrafficChart = ({ data }) => {
  return (
    <div className="rounded-xl border border-[#1F1F1F] bg-[#121212] p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white tracking-wide">Traffic Trend</h3>
          <p className="text-xs font-medium text-[#666666]">Recent 5-minute interval snapshot</p>
        </div>
        <span className="rounded-md border border-[#1F1F1F] bg-[#0B0B0B] px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-[#A0A0A0]">
          Real-time
        </span>
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" vertical={false} />
            <XAxis
              dataKey="time"
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
            <Line
              type="basis"
              dataKey="vehicles"
              name="Vehicles"
              stroke="#D4AF37"
              strokeWidth={2}
              dot={{ fill: '#121212', stroke: '#D4AF37', strokeWidth: 1.5, r: 3 }}
              activeDot={{ r: 5, fill: '#D4AF37', stroke: '#0B0B0B', strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TrafficChart;
