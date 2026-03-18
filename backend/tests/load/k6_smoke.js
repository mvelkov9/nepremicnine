/**
 * k6 smoke / load test for the nepremicnine-v2 API.
 *
 * Usage:
 *   k6 run backend/tests/load/k6_smoke.js
 *   k6 run --env BASE_URL=http://staging:8000 backend/tests/load/k6_smoke.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },  // ramp up to 10 VUs
    { duration: '1m',  target: 10 },  // steady state
    { duration: '10s', target: 0 },   // ramp down
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500'],  // 95th percentile under 500ms
    'http_req_failed':   ['rate<0.01'],  // < 1% errors
  },
};

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const EMAIL = __ENV.TEST_EMAIL || 'admin@test.com';
const PASSWORD = __ENV.TEST_PASSWORD || 'Test1234!';

export default function () {
  // Login
  const loginRes = http.post(`${BASE}/api/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  check(loginRes, { 'login 200': (r) => r.status === 200 });

  if (loginRes.status !== 200) {
    sleep(1);
    return;
  }

  const token = loginRes.json('access_token');
  const authHeaders = { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } };

  // Health check
  const health = http.get(`${BASE}/api/health`);
  check(health, { 'health 200': (r) => r.status === 200 });

  // Stats overview (most-called endpoint)
  const stats = http.get(`${BASE}/api/stats/overview`, authHeaders);
  check(stats, {
    'stats 200': (r) => r.status === 200,
    'stats fast': (r) => r.timings.duration < 500,
  });

  // Regions
  const regions = http.get(`${BASE}/api/regions`, authHeaders);
  check(regions, { 'regions 200': (r) => r.status === 200 });

  // Prediction history
  const history = http.get(`${BASE}/api/predict/history?page=1&per_page=10`, authHeaders);
  check(history, { 'history 200': (r) => r.status === 200 });

  sleep(1);
}
