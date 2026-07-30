const elements = {
  form: document.querySelector("#task-form"),
  input: document.querySelector("#task-title"),
  addButton: document.querySelector("#add-button"),
  list: document.querySelector("#task-list"),
  loading: document.querySelector("#loading-state"),
  empty: document.querySelector("#empty-state"),
  error: document.querySelector("#error-state"),
  retry: document.querySelector("#retry-button"),
  total: document.querySelector("#total-count"),
  pending: document.querySelector("#pending-count"),
  completed: document.querySelector("#completed-count"),
  summary: document.querySelector("#task-summary"),
  toast: document.querySelector("#toast"),
  authOverlay: document.querySelector("#auth-overlay"),
  authForm: document.querySelector("#auth-form"),
  apiKey: document.querySelector("#api-key"),
  authError: document.querySelector("#auth-error"),
  logout: document.querySelector("#logout-button"),
  search: document.querySelector("#task-search"),
  statusFilter: document.querySelector("#status-filter"),
};

let tasks = [];
let toastTimer;
let apiKey = window.sessionStorage.getItem("taskflow-api-key") || "";

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...options.headers,
    },
    ...options,
  });

  if (response.status === 401) {
    lockWorkspace();
    throw new Error("The API key was not accepted.");
  }

  if (!response.ok) {
    let message = "The request could not be completed.";
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Keep the friendly fallback when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}

function lockWorkspace() {
  apiKey = "";
  window.sessionStorage.removeItem("taskflow-api-key");
  elements.authOverlay.hidden = false;
  elements.authError.hidden = true;
  elements.logout.hidden = true;
  window.setTimeout(() => elements.apiKey.focus(), 0);
}

async function unlockWorkspace(event) {
  event.preventDefault();
  apiKey = elements.apiKey.value.trim();
  elements.authError.hidden = true;

  try {
    await apiRequest("/api/info");
    window.sessionStorage.setItem("taskflow-api-key", apiKey);
    elements.apiKey.value = "";
    elements.authOverlay.hidden = true;
    elements.logout.hidden = false;
    await loadTasks();
  } catch {
    elements.authError.hidden = false;
    elements.apiKey.select();
  }
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.classList.add("visible");
  toastTimer = window.setTimeout(() => elements.toast.classList.remove("visible"), 2600);
}

function formatCreatedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Recently added";
  }
  return `Added ${new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(date)}`;
}

function updateStats() {
  const completed = tasks.filter((task) => task.completed).length;
  const pending = tasks.length - completed;
  elements.total.textContent = tasks.length;
  elements.pending.textContent = pending;
  elements.completed.textContent = completed;
  elements.summary.textContent = `${pending} ${pending === 1 ? "task" : "tasks"} remaining`;
}

function createTaskElement(task) {
  const item = document.createElement("li");
  item.className = `task-item${task.completed ? " completed" : ""}`;
  item.dataset.taskId = task.id;

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "task-toggle";
  toggle.setAttribute(
    "aria-label",
    task.completed ? `Mark ${task.title} as pending` : `Mark ${task.title} as completed`,
  );
  toggle.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"></path></svg>';
  toggle.addEventListener("click", () => toggleTask(task, item, toggle));

  const content = document.createElement("div");
  content.className = "task-content";
  const title = document.createElement("p");
  title.className = "task-title";
  title.textContent = task.title;
  const meta = document.createElement("p");
  meta.className = "task-meta";
  meta.textContent = `${formatCreatedAt(task.created_at)} · ${task.completed ? "Complete" : "In progress"}`;
  content.append(title, meta);

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "delete-button";
  remove.setAttribute("aria-label", `Delete ${task.title}`);
  remove.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"></path></svg>';
  remove.addEventListener("click", () => deleteTask(task, item, remove));

  item.append(toggle, content, remove);
  return item;
}

function renderTasks() {
  const search = elements.search.value.trim().toLocaleLowerCase();
  const status = elements.statusFilter.value;
  const visibleTasks = tasks.filter((task) => {
    const matchesSearch = task.title.toLocaleLowerCase().includes(search);
    const matchesStatus =
      status === "all" ||
      (status === "completed" && task.completed) ||
      (status === "pending" && !task.completed);
    return matchesSearch && matchesStatus;
  });

  elements.list.replaceChildren(...visibleTasks.map(createTaskElement));
  elements.loading.hidden = true;
  elements.error.hidden = true;
  elements.empty.hidden = visibleTasks.length !== 0;
  elements.empty.querySelector("strong").textContent =
    tasks.length === 0 ? "Your queue is clear" : "No matching tasks";
  elements.empty.querySelector("p").textContent =
    tasks.length === 0
      ? "Add your first task above and start building momentum."
      : "Try another search or status filter.";
  updateStats();
}

async function loadTasks() {
  elements.loading.hidden = false;
  elements.error.hidden = true;
  elements.empty.hidden = true;
  elements.list.replaceChildren();

  try {
    tasks = await apiRequest("/tasks");
    renderTasks();
  } catch {
    elements.loading.hidden = true;
    elements.error.hidden = false;
    elements.total.textContent = "—";
    elements.pending.textContent = "—";
    elements.completed.textContent = "—";
    elements.summary.textContent = "Unable to sync";
  }
}

async function addTask(event) {
  event.preventDefault();
  const title = elements.input.value.trim();
  if (!title) {
    elements.input.focus();
    return;
  }

  elements.addButton.disabled = true;
  try {
    const task = await apiRequest("/tasks", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
    tasks.push(task);
    elements.input.value = "";
    renderTasks();
    elements.input.focus();
    showToast("Task added to your workspace.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    elements.addButton.disabled = false;
  }
}

async function toggleTask(task, item, button) {
  button.disabled = true;
  try {
    const updated = await apiRequest(`/tasks/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({ completed: !task.completed }),
    });
    tasks = tasks.map((current) => (current.id === task.id ? updated : current));
    renderTasks();
    showToast(updated.completed ? "Task completed. Nice work." : "Task moved back to progress.");
  } catch (error) {
    button.disabled = false;
    item.classList.add("action-error");
    showToast(error.message, true);
  }
}

async function deleteTask(task, item, button) {
  button.disabled = true;
  try {
    await apiRequest(`/tasks/${task.id}`, { method: "DELETE" });
    tasks = tasks.filter((current) => current.id !== task.id);
    renderTasks();
    showToast("Task removed.");
  } catch (error) {
    button.disabled = false;
    showToast(error.message, true);
  }
}

elements.form.addEventListener("submit", addTask);
elements.retry.addEventListener("click", loadTasks);
elements.authForm.addEventListener("submit", unlockWorkspace);
elements.logout.addEventListener("click", lockWorkspace);
elements.search.addEventListener("input", renderTasks);
elements.statusFilter.addEventListener("change", renderTasks);

if (apiKey) {
  elements.authOverlay.hidden = true;
  elements.logout.hidden = false;
  loadTasks();
} else {
  lockWorkspace();
}
