import useTrafficStore from '../../store/useTrafficStore';
import { AlertTriangle, Clock, MapPin, Car } from 'lucide-react';

const severityStyles = {
  critical: {
    border: 'border-l-[#D94A4A]',
    text: 'text-[#D94A4A]',
    icon: 'text-[#D94A4A]',
  },
  high: {
    border: 'border-l-[#D9A04A]',
    text: 'text-[#D9A04A]',
    icon: 'text-[#D9A04A]',
  },
  medium: {
    border: 'border-l-[#D4AF37]',
    text: 'text-[#D4AF37]',
    icon: 'text-[#D4AF37]',
  },
  low: {
    border: 'border-l-[#666666]',
    text: 'text-[#666666]',
    icon: 'text-[#666666]',
  },
};

const statusBadge = {
  open: 'text-[#D94A4A]',
  acknowledged: 'text-[#D9A04A]',
  resolved: 'text-[#4AD986]',
};

const AlertsPanel = () => {
  const violations = useTrafficStore((s) => s.violations);

  const formatTime = (ts) => {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="rounded-xl border border-[#1F1F1F] bg-[#121212] p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#1F1F1F] bg-[#0B0B0B]">
            <AlertTriangle size={16} className="text-[#D4AF37]" />
          </div>
          <h3 className="text-sm font-semibold text-white tracking-wide">Recent Alerts</h3>
        </div>
        <span className="rounded-md border border-[#1F1F1F] bg-[#0B0B0B] px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-[#D94A4A]">
          {violations.filter((v) => v.status === 'open').length} open
        </span>
      </div>

      <div className="max-h-96 space-y-3 overflow-y-auto pr-2 custom-scrollbar">
        {violations.map((v) => {
          const sev = severityStyles[v.severity] || severityStyles.low;
          return (
            <div
              key={v.id}
              className={`rounded-lg border border-[#1F1F1F] border-l-[3px] ${sev.border} bg-[#0B0B0B] p-4 transition-colors hover:bg-[#161616]`}
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <AlertTriangle size={14} className={sev.icon} />
                  <span className="text-sm font-semibold text-white tracking-wide">{v.type}</span>
                </div>
                <span
                  className={`text-[10px] font-bold uppercase tracking-widest ${statusBadge[v.status] || statusBadge.open}`}
                >
                  {v.status}
                </span>
              </div>

              <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs font-medium text-[#666666]">
                <span className="flex items-center gap-1.5">
                  <MapPin size={12} className="text-[#333333]" />
                  <span className="text-[#A0A0A0]">{v.location}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock size={12} className="text-[#333333]" />
                  <span className="text-[#A0A0A0]">{formatTime(v.timestamp)}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <Car size={12} className="text-[#333333]" />
                  <span className="text-[#A0A0A0]">{v.vehicleId}</span>
                </span>
              </div>

              <div className="mt-3">
                <span
                  className={`text-[10px] font-bold uppercase tracking-widest ${sev.text}`}
                >
                  {v.severity}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default AlertsPanel;
