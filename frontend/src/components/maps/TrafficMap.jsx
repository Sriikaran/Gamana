import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { MapPin } from 'lucide-react';

const INITIAL_POINTS = [
  { id: 1, name: 'MG Road Junction', position: [12.9716, 77.5946], density: 80 },
  { id: 2, name: 'Silk Board', position: [12.9172, 77.6228], density: 95 },
  { id: 3, name: 'Hebbal Flyover', position: [13.0354, 77.5971], density: 75 },
  { id: 4, name: 'Indiranagar 100ft', position: [12.9784, 77.6408], density: 45 },
  { id: 5, name: 'Koramangala Sony World', position: [12.9352, 77.6245], density: 60 },
  { id: 6, name: 'Whitefield Main', position: [12.9698, 77.7499], density: 85 },
  { id: 7, name: 'Malleswaram 8th Cross', position: [13.0068, 77.5702], density: 35 },
];

const getColor = (density) => {
  if (density > 80) return '#D94A4A'; // critical red
  if (density > 50) return '#D9A04A'; // warning yellow
  return '#4AD986'; // stable green
};

export default function TrafficMap() {
  const [points, setPoints] = useState(INITIAL_POINTS);

  // Live auto-update effect
  useEffect(() => {
    const interval = setInterval(() => {
      setPoints((prev) =>
        prev.map((p) => {
          // Random walk density by ±15%
          const delta = Math.floor(Math.random() * 31) - 15;
          return {
            ...p,
            density: Math.max(10, Math.min(100, p.density + delta)),
          };
        })
      );
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="rounded-xl border border-[#1F1F1F] bg-[#121212] p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#1F1F1F] bg-[#0B0B0B]">
            <MapPin size={16} className="text-[#D4AF37]" />
          </div>
          <h3 className="text-sm font-semibold text-white tracking-wide">Live Traffic Map</h3>
        </div>
        <span className="rounded-md border border-[#1F1F1F] bg-[#0B0B0B] px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-[#A0A0A0]">
          Tracking {points.length} nodes
        </span>
      </div>

      <div className="relative h-[400px] w-full overflow-hidden rounded-lg border border-[#1F1F1F]">
        <MapContainer
          center={[12.9716, 77.5946]} // Bangalore center
          zoom={12}
          className="h-full w-full bg-[#0B0B0B]"
          zoomControl={false}
        >
          {/* Dark theme styled map tiles */}
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />

          {points.map((point) => {
            const color = getColor(point.density);
            return (
              <CircleMarker
                key={point.id}
                center={point.position}
                radius={point.density / 4 + 4} // Pulse size based on density
                pathOptions={{
                  color: color,
                  fillColor: color,
                  fillOpacity: 0.8,
                  weight: 1.5,
                }}
              >
                <Popup className="gamana-popup">
                  <div className="m-0 p-1 text-[#121212]">
                    <p className="mb-1 text-xs font-bold leading-tight uppercase tracking-wider">{point.name}</p>
                    <p className="m-0 text-sm font-semibold" style={{ color }}>
                      {point.density}% Congestion
                    </p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>

        {/* CSS override for leaflet dark theme popup */}
        <style dangerouslySetInnerHTML={{__html: `
          .leaflet-container { background: #0B0B0B; font-family: 'Inter', sans-serif; }
          .leaflet-popup-content-wrapper { background: #ffffff; border-radius: 6px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border: 1px solid #E5E5E5; }
          .leaflet-popup-tip { background: #ffffff; }
        `}} />
      </div>
    </div>
  );
}
