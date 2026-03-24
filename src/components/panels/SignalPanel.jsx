import useTrafficStore from '../../store/useTrafficStore';
import { Radio } from 'lucide-react';

const statusStyles = {
  green: {
    dot: 'bg-[#4AD986]',
    text: 'text-[#4AD986]',
    label: 'Green',
  },
  red: {
    dot: 'bg-[#D94A4A]',
    text: 'text-[#D94A4A]',
    label: 'Red',
  },
  yellow: {
    dot: 'bg-[#D9A04A]',
    text: 'text-[#D9A04A]',
    label: 'Yellow',
  },
};

const SignalPanel = () => {
  const signals = useTrafficStore((s) => s.signals);

  return (
    <div className="rounded-xl border border-[#1F1F1F] bg-[#121212] p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#1F1F1F] bg-[#0B0B0B]">
            <Radio size={16} className="text-[#D4AF37]" />
          </div>
          <h3 className="text-sm font-semibold text-white tracking-wide">Signal Status</h3>
        </div>
        <span className="text-xs font-medium text-[#666666]">{signals.length} signals</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead>
            <tr className="border-b border-[#1F1F1F] text-[10px] uppercase tracking-widest text-[#A0A0A0]">
              <th className="pb-4 pr-6 font-semibold">ID</th>
              <th className="pb-4 pr-6 font-semibold">Intersection</th>
              <th className="pb-4 pr-6 font-semibold">Zone</th>
              <th className="pb-4 pr-6 font-semibold">Status</th>
              <th className="pb-4 font-semibold text-right">Timer</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1F1F1F]">
            {signals.map((signal) => {
              const s = statusStyles[signal.status] || statusStyles.green;
              return (
                <tr
                  key={signal.id}
                  className="transition-colors hover:bg-[#161616]"
                >
                  <td className="py-4 pr-6 font-mono text-xs text-[#666666]">{signal.id}</td>
                  <td className="py-4 pr-6 text-sm font-medium text-white">{signal.intersection}</td>
                  <td className="py-4 pr-6 text-xs text-[#A0A0A0]">{signal.zone}</td>
                  <td className="py-4 pr-6">
                    <div className="flex items-center gap-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
                      <span className={`text-xs font-semibold uppercase tracking-wider ${s.text}`}>
                        {s.label}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 font-mono text-xs text-[#A0A0A0] text-right">{signal.timer}s</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SignalPanel;
