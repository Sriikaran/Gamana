// ── Mock Traffic Data ──

const MOCK_STATS = {
  totalVehicles: 14_832,
  avgSpeed: 42,
  congestionLevel: 68,
  activeSignals: 127,
  trends: {
    totalVehicles: +5.2,
    avgSpeed: -2.1,
    congestionLevel: +3.8,
    activeSignals: 0,
  },
};

const MOCK_HOURLY_TRAFFIC = [
  { hour: '00:00', vehicles: 320, speed: 58 },
  { hour: '01:00', vehicles: 210, speed: 62 },
  { hour: '02:00', vehicles: 150, speed: 65 },
  { hour: '03:00', vehicles: 120, speed: 67 },
  { hour: '04:00', vehicles: 200, speed: 63 },
  { hour: '05:00', vehicles: 480, speed: 55 },
  { hour: '06:00', vehicles: 950, speed: 45 },
  { hour: '07:00', vehicles: 1_620, speed: 32 },
  { hour: '08:00', vehicles: 2_100, speed: 25 },
  { hour: '09:00', vehicles: 1_850, speed: 28 },
  { hour: '10:00', vehicles: 1_400, speed: 35 },
  { hour: '11:00', vehicles: 1_250, speed: 38 },
  { hour: '12:00', vehicles: 1_500, speed: 33 },
  { hour: '13:00', vehicles: 1_350, speed: 36 },
  { hour: '14:00', vehicles: 1_200, speed: 39 },
  { hour: '15:00', vehicles: 1_450, speed: 34 },
  { hour: '16:00', vehicles: 1_780, speed: 30 },
  { hour: '17:00', vehicles: 2_250, speed: 22 },
  { hour: '18:00', vehicles: 2_050, speed: 24 },
  { hour: '19:00', vehicles: 1_600, speed: 31 },
  { hour: '20:00', vehicles: 1_100, speed: 40 },
  { hour: '21:00', vehicles: 780, speed: 48 },
  { hour: '22:00', vehicles: 520, speed: 54 },
  { hour: '23:00', vehicles: 400, speed: 57 },
];

/**
 * Simulate an API call to fetch dashboard stats.
 * @returns {Promise<object>}
 */
export const fetchTrafficStats = () =>
  new Promise((resolve) => {
    setTimeout(() => resolve(MOCK_STATS), 400);
  });

/**
 * Simulate an API call for hourly traffic data.
 * @returns {Promise<Array>}
 */
export const fetchHourlyTraffic = () =>
  new Promise((resolve) => {
    setTimeout(() => resolve(MOCK_HOURLY_TRAFFIC), 500);
  });

// ── Mock 5-min interval trend ──

const MOCK_TRAFFIC_TREND = [
  { time: '10:00', vehicles: 200 },
  { time: '10:05', vehicles: 350 },
  { time: '10:10', vehicles: 500 },
  { time: '10:15', vehicles: 420 },
  { time: '10:20', vehicles: 600 },
  { time: '10:25', vehicles: 550 },
  { time: '10:30', vehicles: 720 },
  { time: '10:35', vehicles: 680 },
  { time: '10:40', vehicles: 810 },
  { time: '10:45', vehicles: 750 },
];

/**
 * Simulate an API call for short-term traffic trend data.
 * @returns {Promise<Array>}
 */
export const fetchTrafficTrend = () =>
  new Promise((resolve) => {
    setTimeout(() => resolve(MOCK_TRAFFIC_TREND), 300);
  });
