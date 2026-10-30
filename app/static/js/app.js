const studentDialog = document.querySelector("#student-dialog");
const profileDialog = document.querySelector("#profile-dialog");
const studentForm = document.querySelector("#student-form");
const rowsElement = document.querySelector("#student-rows");
const previewRowsElement = document.querySelector("#overview-student-rows");
const searchInput = document.querySelector("#student-search");
const departmentFilter = document.querySelector("#department-filter");
const formError = document.querySelector("#form-error");

let students = [];
let currentProfile = null;
let searchTimer;
const minAdmissionYear = 1900;

const avatarColors = [
  ["#e8f3ed", "#438464"],
  ["#eeeafa", "#7663a5"],
  ["#fbf0e4", "#ae7c3e"],
  ["#e8eff9", "#5579a8"],
  ["#faeaea", "#ae6666"],
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function initials(name) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
}

function avatarStyle(name) {
  const index = [...name].reduce((sum, character) => sum + character.charCodeAt(0), 0) % avatarColors.length;
  const [background, color] = avatarColors[index];
  return `style="background:${background};color:${color}"`;
}

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast${type === "error" ? " error" : ""}`;
  toast.textContent = message;
  document.querySelector("#toast-region").append(toast);
  window.setTimeout(() => toast.remove(), 3600);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error || `Request failed (${response.status})`);
    error.details = body.details || {};
    error.status = response.status;
    throw error;
  }
  return body;
}

function formatDate(value) {
  if (!value) return "—";
  const year = String(value).match(/^\d{4}/)?.[0];
  return year || String(value);
}

function setLoading(message = "Loading student records…") {
  rowsElement.innerHTML = `<tr><td class="loading-cell" colspan="6"><span class="spinner"></span>${escapeHtml(message)}</td></tr>`;
}

function studentRow(student, includeActions = true) {
  return `
    <tr>
      <td><div class="student-cell"><div class="avatar" ${avatarStyle(student.full_name)}>${escapeHtml(initials(student.full_name))}</div><div class="student-info"><strong>${escapeHtml(student.full_name)}</strong><span>${escapeHtml(student.email)}</span></div></div></td>
      <td><code class="roll-code">${escapeHtml(student.roll_number)}</code></td>
      <td><div class="department-cell"><strong>${escapeHtml(student.department)}</strong><span>${escapeHtml(student.course)}</span></div></td>
      <td><span class="year-badge">Year ${escapeHtml(student.year_of_study)}</span></td>
      <td>${escapeHtml(formatDate(student.date_of_admission))}</td>
      ${includeActions ? `<td><div class="row-actions">
        <button class="row-action" type="button" data-action="view" data-id="${student.id}" aria-label="View ${escapeHtml(student.full_name)}" title="View profile">↗</button>
        <button class="row-action" type="button" data-action="edit" data-id="${student.id}" aria-label="Edit ${escapeHtml(student.full_name)}" title="Edit student">✎</button>
        <button class="row-action delete" type="button" data-action="delete" data-id="${student.id}" aria-label="Delete ${escapeHtml(student.full_name)}" title="Delete student">×</button>
      </div></td>` : ""}
    </tr>`;
}

function renderStudents() {
  document.querySelector("#directory-count").textContent = String(students.length);
  document.querySelector("#results-label").textContent = `${students.length} student${students.length === 1 ? "" : "s"} shown`;

  if (!students.length) {
    const filtered = searchInput.value.trim() || departmentFilter.value;
    rowsElement.innerHTML = `<tr><td class="empty-cell" colspan="6"><span class="empty-title">${filtered ? "No matching students" : "Your directory is ready"}</span>${filtered ? "Try another search or department." : "Add your first student to get started."}${filtered ? "" : '<br><button class="button button-primary" type="button" data-open-create><span aria-hidden="true">＋</span> Add student</button>'}</td></tr>`;
    return;
  }

  rowsElement.innerHTML = students.map((student) => studentRow(student)).join("");
}

async function loadOverviewPreview() {
  try {
    const result = await api("/api/students");
    const preview = result.data.slice(0, 5);
    if (!preview.length) {
      previewRowsElement.innerHTML = '<tr><td class="empty-cell" colspan="5"><span class="empty-title">No students yet</span>Add a student to get started.</td></tr>';
      return;
    }
    previewRowsElement.innerHTML = preview
      .map((student) => studentRow(student, false))
      .join("");
  } catch (error) {
    previewRowsElement.innerHTML = `<tr><td class="empty-cell" colspan="5"><span class="empty-title">Couldn’t load student preview</span>${escapeHtml(error.message)}</td></tr>`;
  }
}

async function loadStudents() {
  setLoading();
  const params = new URLSearchParams();
  if (searchInput.value.trim()) params.set("search", searchInput.value.trim());
  if (departmentFilter.value) params.set("department", departmentFilter.value);
  try {
    const result = await api(`/api/students${params.size ? `?${params}` : ""}`);
    students = result.data;
    renderStudents();
  } catch (error) {
    rowsElement.innerHTML = `<tr><td class="empty-cell" colspan="6"><span class="empty-title">Couldn’t load students</span>${escapeHtml(error.message)}<br><button class="button button-quiet" type="button" data-retry>Try again</button></td></tr>`;
    document.querySelector("#results-label").textContent = "Directory unavailable";
  }
}

function renderDepartmentFilter(departments) {
  const selected = departmentFilter.value;
  departmentFilter.innerHTML = '<option value="">All departments</option>' + departments.map(({ department }) => `<option value="${escapeHtml(department)}">${escapeHtml(department)}</option>`).join("");
  if (departments.some(({ department }) => department === selected)) departmentFilter.value = selected;
}

function renderDepartmentChart(items) {
  const container = document.querySelector("#department-chart");
  if (!items.length) {
    container.innerHTML = '<div class="chart-empty">Add students to see department insights.</div>';
    return;
  }
  const max = Math.max(...items.map((item) => item.count));
  container.innerHTML = items.slice(0, 5).map((item) => `
    <div class="bar-row"><span class="bar-name" title="${escapeHtml(item.department)}">${escapeHtml(item.department)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(7, item.count / max * 100)}%"></div></div><span class="bar-count">${item.count}</span></div>`).join("");
}

function renderYearChart(items) {
  const container = document.querySelector("#year-chart");
  if (!items.length) {
    container.innerHTML = '<div class="chart-empty">Year data will appear here.</div>';
    return;
  }
  const counts = new Map(items.map((item) => [item.year, item.count]));
  const max = Math.max(...items.map((item) => item.count));
  container.innerHTML = Array.from({ length: 4 }, (_, index) => {
    const year = index + 1;
    const count = counts.get(year) || 0;
    const height = count ? Math.max(6, count / max * 100) : 0;
    return `<div class="year-column"><span class="year-count">${count || ""}</span><div class="year-bar-wrap"><div class="year-bar" style="height:${height}%"></div></div><span class="year-label">Y${year}</span></div>`;
  }).join("");
}

async function loadStats() {
  try {
    const { data } = await api("/api/dashboard/stats");
    document.querySelector("#total-students").textContent = data.total_students;
    document.querySelector("#department-count").textContent = data.department_count;
    const top = data.by_department[0];
    document.querySelector("#top-department").textContent = top?.department || "—";
    document.querySelector("#top-department-count").textContent = top ? `${top.count} student${top.count === 1 ? "" : "s"} enrolled` : "No department data yet";
    renderDepartmentFilter(data.by_department);
    renderDepartmentChart(data.by_department);
    renderYearChart(data.by_year);
  } catch (error) {
    showToast(`Couldn’t load dashboard statistics: ${error.message}`, "error");
  }
}

async function refreshDashboard() {
  await Promise.all([loadStats(), loadStudents(), loadOverviewPreview()]);
}

function clearValidation() {
  formError.hidden = true;
  formError.textContent = "";
  studentForm.querySelectorAll("[aria-invalid='true']").forEach((input) => input.removeAttribute("aria-invalid"));
  studentForm.querySelectorAll(".field-error").forEach((element) => { element.textContent = ""; });
  studentForm.elements.namedItem("date_of_admission").setCustomValidity("");
}

function validateAdmissionYear(showMessage = false) {
  const input = studentForm.elements.namedItem("date_of_admission");
  const value = input.value;
  const currentYear = new Date().getFullYear();
  let message = "";

  if (!/^[0-9]{4}$/.test(value)) {
    message = "Enter a four-digit admission year using numbers only.";
  } else {
    const year = Number(value);
    if (year < minAdmissionYear || year > currentYear) {
      message = `Enter an admission year between ${minAdmissionYear} and ${currentYear}.`;
    }
  }

  input.setCustomValidity(message);
  if (showMessage) {
    const fieldError = studentForm.querySelector('[data-error-for="date_of_admission"]');
    input.toggleAttribute("aria-invalid", Boolean(message));
    fieldError.textContent = message;
  }
  return !message;
}

function applyValidationErrors(details) {
  clearValidation();
  const messages = [];
  for (const [field, message] of Object.entries(details)) {
    const input = studentForm.elements.namedItem(field);
    const fieldError = studentForm.querySelector(`[data-error-for="${CSS.escape(field)}"]`);
    if (input && fieldError) {
      input.setAttribute("aria-invalid", "true");
      fieldError.textContent = message;
    } else {
      messages.push(message);
    }
  }
  if (messages.length || !Object.keys(details).length) {
    formError.textContent = messages.join(". ") || "Please check the form and try again.";
    formError.hidden = false;
  }
}

function openCreateDialog() {
  studentForm.reset();
  clearValidation();
  studentForm.dataset.studentId = "";
  document.querySelector("#student-dialog-title").textContent = "Add a student";
  document.querySelector(".modal-subtitle").textContent = "Enter the student’s details below.";
  document.querySelector("#save-student").textContent = "Save student";
  studentDialog.showModal();
  studentForm.elements.full_name.focus();
}

function openEditDialog(student) {
  studentForm.reset();
  clearValidation();
  studentForm.dataset.studentId = student.id;
  for (const [field, value] of Object.entries(student)) {
    if (studentForm.elements.namedItem(field)) studentForm.elements.namedItem(field).value = value;
  }
  document.querySelector("#student-dialog-title").textContent = "Edit student";
  document.querySelector(".modal-subtitle").textContent = "Update this student’s information.";
  document.querySelector("#save-student").textContent = "Save changes";
  profileDialog.close();
  studentDialog.showModal();
  studentForm.elements.full_name.focus();
}

function renderProfile(student) {
  currentProfile = student;
  document.querySelector("#profile-name").textContent = student.full_name;
  document.querySelector("#profile-roll").textContent = student.roll_number;
  document.querySelector("#profile-avatar").textContent = initials(student.full_name);
  document.querySelector("#profile-avatar").setAttribute("style", avatarStyle(student.full_name).slice(7, -1));
  document.querySelector("#profile-id").textContent = `Student ID · ${student.id}`;
  const details = [
    ["Email address", student.email],
    ["Phone number", student.phone_number],
    ["Department", student.department],
    ["Course", student.course],
    ["Year of study", `Year ${student.year_of_study}`],
    ["Date of entry", formatDate(student.date_of_admission)],
  ];
  document.querySelector("#profile-details").innerHTML = details.map(([label, value]) => `<div class="detail-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
  profileDialog.showModal();
}

async function handleRowAction(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const student = students.find((item) => item.id === Number(button.dataset.id));
  if (!student) return;

  if (button.dataset.action === "view") {
    try {
      const { data } = await api(`/api/students/${student.id}`);
      renderProfile(data);
    } catch (error) {
      showToast(error.message, "error");
    }
  } else if (button.dataset.action === "edit") {
    openEditDialog(student);
  } else if (button.dataset.action === "delete") {
    if (!window.confirm(`Delete ${student.full_name} (${student.roll_number})? This action cannot be undone.`)) return;
    try {
      await api(`/api/students/${student.id}`, { method: "DELETE" });
      showToast(`${student.full_name} was deleted.`);
      await refreshDashboard();
    } catch (error) {
      showToast(`Couldn’t delete student: ${error.message}`, "error");
    }
  }
}

studentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearValidation();
  const admissionYearIsValid = validateAdmissionYear(true);
  if (!admissionYearIsValid || !studentForm.reportValidity()) return;

  const formData = new FormData(studentForm);
  const payload = Object.fromEntries(formData.entries());
  payload.year_of_study = Number(payload.year_of_study);
  const studentId = studentForm.dataset.studentId;
  const saveButton = document.querySelector("#save-student");
  saveButton.disabled = true;
  saveButton.textContent = "Saving…";

  try {
    const result = await api(studentId ? `/api/students/${studentId}` : "/api/students", {
      method: studentId ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    studentDialog.close();
    showToast(studentId ? `${result.data.full_name}’s record was updated.` : `${result.data.full_name} was added.`);
    await refreshDashboard();
  } catch (error) {
    if (error.status === 400) applyValidationErrors(error.details);
    else {
      formError.textContent = error.message;
      formError.hidden = false;
    }
  } finally {
    saveButton.disabled = false;
    saveButton.textContent = studentId ? "Save changes" : "Save student";
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-open-create]")) openCreateDialog();
  if (event.target.closest("[data-close-dialog]")) event.target.closest("dialog")?.close();
  if (event.target.closest("[data-retry]")) loadStudents();
});

document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});

document.querySelector("#profile-edit").addEventListener("click", () => {
  if (currentProfile) openEditDialog(currentProfile);
});
rowsElement.addEventListener("click", handleRowAction);
searchInput.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadStudents, 220);
});
departmentFilter.addEventListener("change", loadStudents);
studentForm.addEventListener("input", (event) => {
  if (event.target.name === "date_of_admission" && event.target.value) {
    validateAdmissionYear(true);
  }
  if (event.target.matches("[aria-invalid='true']")) {
    if (event.target.name !== "date_of_admission") {
      event.target.removeAttribute("aria-invalid");
      const message = studentForm.querySelector(`[data-error-for="${CSS.escape(event.target.name)}"]`);
      if (message) message.textContent = "";
    }
  }
});

function updateNavigation() {
  const allowedHashes = new Set(["#overview", "#students"]);
  if (!allowedHashes.has(window.location.hash)) {
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#overview`);
  }
  const activeHash = window.location.hash;
  document.querySelectorAll("[data-page-section]").forEach((section) => {
    section.hidden = section.dataset.pageSection !== activeHash.slice(1);
  });
  document.querySelectorAll("[data-page-control]").forEach((control) => {
    control.hidden = control.dataset.pageControl !== activeHash.slice(1);
  });
  document.querySelectorAll(".side-nav .nav-link").forEach((link) => {
    const active = link.hash === activeHash;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.querySelector("#current-page-name").textContent =
    activeHash === "#students" ? "Students" : "Overview";
  document.title = `${activeHash === "#students" ? "Students" : "Overview"} | Campus Desk`;
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", updateNavigation);
updateNavigation();
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    searchInput.focus();
  }
});

document.querySelector("#today-label").textContent = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  month: "short",
  day: "numeric",
}).format(new Date());

refreshDashboard();
