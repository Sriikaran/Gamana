// ── Mock Violations / Alerts Data ──

const MOCK_VIOLATIONS = [
  {
    id: 'VIO-1001',
    type: 'Red Light Violation',
    location: 'Silk Board Junction',
    timestamp: '2026-03-21T12:45:00',
    severity: 'high',
    vehicleId: 'KA-01-AB-1234',
    status: 'open',
  },
  {
    id: 'VIO-1002',
    type: 'Over Speeding',
    location: 'Outer Ring Road',
    timestamp: '2026-03-21T12:30:00',
    severity: 'critical',
    vehicleId: 'KA-03-CD-5678',
    status: 'open',
  },
  {
    id: 'VIO-1003',
    type: 'Wrong Lane Driving',
    location: 'MG Road',
    timestamp: '2026-03-21T12:15:00',
    severity: 'medium',
    vehicleId: 'KA-05-EF-9012',
    status: 'acknowledged',
  },
  {
    id: 'VIO-1004',
    type: 'Illegal Parking',
    location: 'Brigade Road',
    timestamp: '2026-03-21T11:50:00',
    severity: 'low',
    vehicleId: 'KA-02-GH-3456',
    status: 'resolved',
  },
  {
    id: 'VIO-1005',
    type: 'Signal Jumping',
    location: 'Hebbal Flyover',
    timestamp: '2026-03-21T11:30:00',
    severity: 'high',
    vehicleId: 'KA-04-IJ-7890',
    status: 'open',
  },
  {
    id: 'VIO-1006',
    type: 'Over Speeding',
    location: 'NICE Road',
    timestamp: '2026-03-21T11:10:00',
    severity: 'critical',
    vehicleId: 'KA-01-KL-2345',
    status: 'open',
  },
  {
    id: 'VIO-1007',
    type: 'No Helmet',
    location: 'Koramangala 5th Block',
    timestamp: '2026-03-21T10:45:00',
    severity: 'medium',
    vehicleId: 'KA-03-MN-6789',
    status: 'acknowledged',
  },
  {
    id: 'VIO-1008',
    type: 'Zebra Crossing Violation',
    location: 'Indiranagar',
    timestamp: '2026-03-21T10:20:00',
    severity: 'low',
    vehicleId: 'KA-05-OP-0123',
    status: 'resolved',
  },
];

/**
 * Simulate an API call to fetch violations / alerts.
 * @returns {Promise<Array>}
 */
export const fetchViolations = () =>
  new Promise((resolve) => {
    setTimeout(() => resolve(MOCK_VIOLATIONS), 300);
  });
