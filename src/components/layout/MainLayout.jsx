import { useState } from 'react';
import {
  LayoutDashboard,
  TrafficCone,
  Radio,
  AlertTriangle,
  Menu,
  X,
  Activity,
} from 'lucide-react';

const NAV_ITEMS = [
  { label: 'Dashboard', icon: LayoutDashboard },
  { label: 'Traffic', icon: TrafficCone },
  { label: 'Signals', icon: Radio },
  { label: 'Alerts', icon: AlertTriangle },
];

const MainLayout = ({ children, activePage, onNavigate }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen w-full bg-[#0B0B0B] text-white overflow-hidden">
        {/* ── Mobile overlay ── */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/80 lg:hidden backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* ── Sidebar ── */}
        <aside
          className={`
            fixed inset-y-0 left-0 z-40 flex w-64 flex-col
            border-r border-[#1F1F1F] bg-[#0B0B0B]
            transition-transform duration-300 ease-in-out
            lg:static lg:translate-x-0
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          `}
        >
          {/* Brand */}
          <div className="flex items-center gap-3 px-6 py-8">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[#121212] border border-[#1F1F1F]">
              <Activity size={18} className="text-[#D4AF37]" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white tracking-tight">Gamana</h1>
            </div>
          </div>

          {/* Nav links */}
          <nav className="flex-1 space-y-2 px-4 py-2">
            {NAV_ITEMS.map((item) => {
              const active = activePage === item.label;
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  onClick={() => {
                    onNavigate(item.label);
                    setSidebarOpen(false);
                  }}
                  className={`
                    group flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium
                    transition-all duration-300 ease-out cursor-pointer
                    ${
                      active
                        ? 'bg-[#121212] text-white border border-[#1F1F1F]'
                        : 'text-[#A0A0A0] border border-transparent hover:text-white hover:bg-[#121212]'
                    }
                  `}
                >
                  <Icon
                    size={18}
                    className={`transition-colors duration-300 ${
                      active ? 'text-[#D4AF37]' : 'text-[#666666] group-hover:text-[#A0A0A0]'
                    }`}
                  />
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="px-6 py-6 mt-auto">
            <div className="flex items-center gap-3 p-3 rounded-xl bg-[#121212] border border-[#1F1F1F]">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#1F1F1F] text-[#A0A0A0] text-xs font-semibold">
                OP
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">Operator</p>
                <p className="text-xs text-[#666666] truncate">Control Room</p>
              </div>
            </div>
          </div>
        </aside>

        {/* ── Main ── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top bar (mobile) */}
          <header className="flex items-center justify-between border-b border-[#1F1F1F] bg-[#0B0B0B] px-4 py-4 lg:hidden">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-[#A0A0A0] hover:bg-[#121212] hover:text-white transition-colors"
            >
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <h1 className="text-sm font-semibold text-white tracking-tight">Gamana</h1>
            <div className="w-9" /> {/* spacer */}
          </header>

          {/* Content */}
          <main className="flex-1 overflow-y-auto outline-none p-4 sm:p-8 lg:p-10 xl:p-12">
            <div className="mx-auto max-w-7xl">
              {children}
            </div>
          </main>
        </div>
      </div>
  );
};

export default MainLayout;
