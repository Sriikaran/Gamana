// ── Mock Signal Data ──

const MOCK_SIGNALS = [
  { id: 'SIG-001', intersection: 'MG Road × Brigade Rd', status: 'green', timer: 45, zone: 'Central' },
  { id: 'SIG-002', intersection: 'Silk Board Junction', status: 'red', timer: 30, zone: 'South' },
  { id: 'SIG-003', intersection: 'Hebbal Flyover', status: 'yellow', timer: 5, zone: 'North' },
  { id: 'SIG-004', intersection: 'KR Puram Signal', status: 'green', timer: 38, zone: 'East' },
  { id: 'SIG-005', intersection: 'Mysore Road × Chord Rd', status: 'red', timer: 22, zone: 'West' },
  { id: 'SIG-006', intersection: 'Indiranagar 100ft Rd', status: 'green', timer: 52, zone: 'East' },
  { id: 'SIG-007', intersection: 'Koramangala Forum', status: 'yellow', timer: 3, zone: 'South' },
  { id: 'SIG-008', intersection: 'Whitefield Main Rd', status: 'green', timer: 40, zone: 'East' },
  { id: 'SIG-009', intersection: 'Jayanagar 4th Block', status: 'red', timer: 18, zone: 'South' },
  { id: 'SIG-010', intersection: 'Yeshwantpur Circle', status: 'green', timer: 33, zone: 'North' },
];

/**
 * Simulate an API call to fetch signal statuses.
 * @returns {Promise<Array>}
 */
export const fetchSignals = () =>
  new Promise((resolve) => {
    setTimeout(() => resolve(MOCK_SIGNALS), 350);
  });
