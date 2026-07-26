const elements = {
  requests: document.querySelector("#request-count"),
  successRate: document.querySelector("#success-rate"),
  latency: document.querySelector("#average-latency"),
  memory: document.querySelector("#memory-usage"),
  cpu: document.querySelector("#cpu-time"),
  uptime: document.querySelector("#process-uptime"),
  updated: document.querySelector("#last-updated"),
  refresh: document.querySelector("#refresh-button"),
  rows: document.querySelector("#endpoint-rows"),
  table: document.querySelector("#endpoint-table"),
  loading: document.querySelector("#metrics-loading"),
  error: document.querySelector("#metrics-error"),
  empty: document.querySelector("#metrics-empty"),
  statusDot: document.querySelector("#status-dot"),
  statusLabel: document.querySelector("#status-label"),
};

function parseLabels(value) {
  return Object.fromEntries(
    [...value.matchAll(/(\w+)="((?:\\.|[^"])*)"/g)].map((match) => [
      match[1],
      match[2].replaceAll("\\\"", '"').replaceAll("\\\\", "\\"),
    ]),
  );
}

function parseMetrics(text) {
  const samples = [];
  for (const line of text.split("\n")) {
    if (!line || line.startsWith("#")) {
      continue;
    }
    const match = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+([^\s]+)$/);
    if (match) {
      samples.push({
        name: match[1],
        labels: parseLabels(match[2] || ""),
        value: Number(match[3]),
      });
    }
  }
  return samples;
}

function sum(samples, name, predicate = () => true) {
  return samples
    .filter((sample) => sample.name === name && predicate(sample))
    .reduce((total, sample) => total + sample.value, 0);
}

function single(samples, name) {
  return samples.find((sample) => sample.name === name)?.value;
}

function formatBytes(value) {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit < 2 ? 0 : 1)} ${units[unit]}`;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "—";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m`;
  }
  return `${Math.floor(seconds)}s`;
}

function renderRows(requestSamples) {
  elements.rows.replaceChildren(
    ...requestSamples
      .sort((left, right) => right.value - left.value)
      .map((sample) => {
        const row = document.createElement("tr");
        const path = document.createElement("td");
        const method = document.createElement("td");
        const status = document.createElement("td");
        const count = document.createElement("td");
        const badge = document.createElement("span");

        path.textContent = sample.labels.path || "unknown";
        method.textContent = sample.labels.method || "—";
        badge.className = `status-code${Number(sample.labels.status) >= 400 ? " error" : ""}`;
        badge.textContent = sample.labels.status || "—";
        status.append(badge);
        count.textContent = Math.round(sample.value).toLocaleString();
        row.append(path, method, status, count);
        return row;
      }),
  );
}

function renderMetrics(samples) {
  const requestSamples = samples.filter((sample) => sample.name === "http_requests_total");
  const requests = requestSamples.reduce((total, sample) => total + sample.value, 0);
  const successful = requestSamples
    .filter((sample) => Number(sample.labels.status) < 400)
    .reduce((total, sample) => total + sample.value, 0);
  const latencyCount = sum(samples, "http_request_duration_seconds_count");
  const latencySum = sum(samples, "http_request_duration_seconds_sum");
  const processStarted = single(samples, "process_start_time_seconds");

  elements.requests.textContent = Math.round(requests).toLocaleString();
  elements.successRate.textContent = requests ? `${((successful / requests) * 100).toFixed(1)}%` : "—";
  elements.latency.textContent = latencyCount
    ? `${((latencySum / latencyCount) * 1000).toFixed(1)} ms`
    : "—";
  elements.memory.textContent = formatBytes(single(samples, "process_resident_memory_bytes"));
  elements.cpu.textContent = `${(single(samples, "process_cpu_seconds_total") || 0).toFixed(2)}s`;
  elements.uptime.textContent = formatDuration(Date.now() / 1000 - processStarted);
  elements.updated.textContent = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());

  renderRows(requestSamples);
  elements.loading.hidden = true;
  elements.error.hidden = true;
  elements.empty.hidden = requestSamples.length !== 0;
  elements.table.hidden = requestSamples.length === 0;
  elements.statusLabel.textContent = "Live";
  elements.statusDot.classList.remove("offline");
}

async function loadMetrics() {
  elements.refresh.disabled = true;
  try {
    const response = await fetch("/metrics", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Metrics request failed");
    }
    renderMetrics(parseMetrics(await response.text()));
  } catch {
    elements.loading.hidden = true;
    elements.table.hidden = true;
    elements.empty.hidden = true;
    elements.error.hidden = false;
    elements.statusLabel.textContent = "Unavailable";
    elements.statusDot.classList.add("offline");
  } finally {
    elements.refresh.disabled = false;
  }
}

elements.refresh.addEventListener("click", loadMetrics);
loadMetrics();
window.setInterval(loadMetrics, 5000);
