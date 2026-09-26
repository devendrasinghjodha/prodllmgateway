import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 100 },   // Warm-up to 100 VUs
    { duration: '1m', target: 1000 },    // Ramp-up to 1,000 VUs
    { duration: '2m', target: 5000 },    // Scale to 5,000 VUs
    { duration: '2m', target: 10000 },   // Peak at 10,000 concurrent requests
    { duration: '1m', target: 0 },       // Cool-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95% under 500ms, 99% under 1s
    http_req_failed: ['rate<0.01'],                  // Error rate < 1%
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // Test alternating between distinct queries and identical cached queries
  const isCached = Math.random() < 0.4;
  const prompt = isCached
    ? 'What is TCP transmission control protocol?'
    : `Tell me a unique fact about number ${Math.floor(Math.random() * 100000)}`;

  const payload = JSON.stringify({
    model: 'mock', // Target fast mock provider to benchmark pure gateway throughput
    messages: [
      { role: 'user', content: prompt }
    ],
    temperature: 0.7,
    stream: false,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer pllm_admin_secret_key_prodllm',
      'X-Priority': Math.random() < 0.2 ? 'high' : 'normal',
    },
  };

  const res = http.post(`${BASE_URL}/v1/chat/completions`, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has choices': (r) => {
      try {
        const json = r.json();
        return json.choices && json.choices.length > 0;
      } catch (e) {
        return false;
      }
    },
  });

  sleep(0.1);
}
