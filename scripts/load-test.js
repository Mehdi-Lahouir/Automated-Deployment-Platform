import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("task_api_errors");
const taskLatency = new Trend("task_api_latency", true);
const baseUrl = __ENV.BASE_URL || "http://127.0.0.1:8000";
const apiKey = __ENV.APP_API_KEY;

if (!apiKey) {
  throw new Error("APP_API_KEY must be provided to the load test");
}

export const options = {
  scenarios: {
    steady_load: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "15s", target: 10 },
        { duration: "30s", target: 10 },
        { duration: "15s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
    task_api_errors: ["rate<0.01"],
    task_api_latency: ["p(95)<500"],
  },
};

const params = {
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": apiKey,
  },
};

export default function () {
  const started = Date.now();
  const response = http.get(`${baseUrl}/tasks?limit=20`, params);
  taskLatency.add(Date.now() - started);
  const passed = check(response, {
    "task list returns 200": (result) => result.status === 200,
    "task list is JSON": (result) =>
      (result.headers["Content-Type"] || "").includes("application/json"),
  });
  errorRate.add(!passed);
  sleep(1);
}
