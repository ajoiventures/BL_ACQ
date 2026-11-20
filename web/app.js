import { modules, workflows, coverage } from "./fixtures.js";

const $ = (id) => document.getElementById(id);
const smallScreen = matchMedia("(max-width: 760px)");
const selectionKey = "br-review-fixtures:scope:v1";
const validScopes = ["commercial", "family", "civic"];
let scope = localStorage.getItem(selectionKey) || "commercial";
if (!validScopes.includes(scope)) scope = "commercial";
let page = "Command";
let phoneView = "queue";
let pending = false;

function el(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}
function button(text, action, className) {
  const item = el("button", text, className);
  item.type = "button";
  item.addEventListener("click", action);
  return item;
}
function key(domain) {
  return "br-review-fixtures:v1:" + domain;
}
function visible(domain) {
  return Object.keys(workflows).filter((id) => workflows[id].scope === domain);
}
function validCheckpoint(value, flow) {
  return (
    value &&
    Number.isInteger(value.count) &&
    value.count >= 0 &&
    value.count <= flow.steps.length &&
    value.lastStep === (flow.steps[value.count - 1] ?? "")
  );
}
function state(domain = scope) {
  // Walkthrough 1. Restore only records that belong to the selected workspace.
  // Check their saved steps against this fixture version before rendering them.
  const saved = localStorage.getItem(key(domain));
  if (saved === null) return { selected: visible(domain)[0], records: {} };
  const data = JSON.parse(saved);
  const ids = visible(domain);
  if (
    !data ||
    !ids.includes(data.selected) ||
    !data.records ||
    Array.isArray(data.records) ||
    typeof data.records !== "object"
  )
    throw Error("Invalid workspace snapshot.");
  for (const [id, item] of Object.entries(data.records)) {
    const flow = workflows[id];
    if (
      !ids.includes(id) ||
      !item ||
      typeof item.note !== "string" ||
      item.note.length > 1500 ||
      typeof item.cash !== "boolean" ||
      !Array.isArray(item.events) ||
      item.events.length > flow.steps.length ||
      (item.origin && !validCheckpoint(item.origin, flow)) ||
      item.events.some(
        (event, i) =>
          !event ||
          event.action !== flow.steps[i] ||
          event.version !== flow.version ||
          !Number.isFinite(Date.parse(event.at)),
      )
    )
      throw Error("Invalid record snapshot.");
  }
  return data;
}
function record(data, id) {
  return data.records[id] ?? { events: [], note: "", cash: false };
}
function say(message) {
  $("feedback").textContent = message;
}

// Acquire a same-origin lock before reading current state. Two open tabs can never consume the same step twice.
async function change(id, edit) {
  if (pending) return;
  const domain = scope;
  pending = true;
  try {
    if (!navigator.locks)
      throw Error(
        "Use a loopback server and a browser with Web Locks to save changes.",
      );
    await navigator.locks.request(key(domain), () => {
      const data = state(domain);
      if (!visible(domain).includes(id))
        throw Error("Record is outside this workspace.");
      const current = record(data, id);
      edit(current, data);
      data.records[id] = current;
      localStorage.setItem(key(domain), JSON.stringify(data));
    });
    render();
  } catch (error) {
    say(error.message);
  } finally {
    pending = false;
  }
}
function openPage(name) {
  page = name;
  phoneView = "queue";
  if (smallScreen.matches) $("navigation").open = false;
  render();
  $("workspace").focus();
}
function openTask(id) {
  phoneView = "task";
  change(id, (_, data) => {
    data.selected = id;
  }).then(() => {
    if (smallScreen.matches) $("workspace").focus();
  });
}
function advance(id, step) {
  // Walkthrough 2. Re-read the current event count under the lock, then check
  // the funding evidence. Only after both pass can we append a review event.
  change(id, (current) => {
    if (current.events.length !== step)
      throw Error("This step has already changed. Reload the review.");
    if (id === "parcel" && step === 2 && !current.cash)
      throw Error("Verified funding evidence is required.");
    current.events.push({
      action: workflows[id].steps[step],
      version: workflows[id].version,
      at: new Date().toISOString(),
    });
    say("Recorded in the simulation.");
  });
}
function notes(panel, id, current) {
  const label = el("label", "Review note");
  label.htmlFor = "note";
  const input = el("textarea");
  input.id = "note";
  input.maxLength = 1500;
  input.value = current.note;
  panel.append(
    label,
    input,
    button("Save draft", () =>
      change(id, (draft) => {
        draft.note = input.value;
        say("Draft saved.");
      }),
    ),
  );
}
function exportDraft(id) {
  const note = $("note").value;
  const count = record(state(), id).events.length;
  const checkpoint = { count, lastStep: workflows[id].steps[count - 1] ?? "" };
  const payload = {
    format: "br-review-draft-v1",
    scope,
    id,
    version: workflows[id].version,
    note,
    checkpoint,
  };
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
  );
  const anchor = el("a");
  anchor.href = url;
  anchor.download = "founder-review-draft.json";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  say("Draft exported. Import it in the same workspace on the other device.");
}
async function importDraft(file) {
  if (!file) return;
  const domain = scope;
  try {
    if (file.size > 16000) throw Error("Draft file is too large.");
    const draft = JSON.parse(await file.text());
    if (
      scope !== domain ||
      draft.format !== "br-review-draft-v1" ||
      draft.scope !== scope ||
      !visible(scope).includes(draft.id)
    )
      throw Error("Choose a draft for this workspace.");
    if (draft.version !== workflows[draft.id].version)
      throw Error("The evidence version has changed. Review a current source.");
    if (typeof draft.note !== "string" || draft.note.length > 1500)
      throw Error("Draft note is invalid.");
    if (!validCheckpoint(draft.checkpoint, workflows[draft.id]))
      throw Error("Originating checkpoint is invalid.");
    // Walkthrough 3. Show where the other device stopped. Its decisions stay
    // in its own history, so importing a note cannot approve anything here.
    phoneView = "task";
    await change(draft.id, (current, data) => {
      current.note = draft.note;
      current.origin = draft.checkpoint;
      data.selected = draft.id;
      page = "Command";
      say("Draft imported.");
    });
  } catch (error) {
    say(error.message);
  }
}
function task(panel, id, current) {
  const flow = workflows[id],
    step = current.events.length,
    complete = step >= flow.steps.length;
  panel.append(
    el("small", "Selected record"),
    el("h2", flow.title),
    el(
      "p",
      complete
        ? "Simulation complete"
        : "Step " + (step + 1) + " of " + flow.steps.length,
    ),
  );
  if (current.origin)
    panel.append(
      el(
        "p",
        "Originating device recorded " +
          current.origin.count +
          " of " +
          flow.steps.length +
          " steps. Last step: " +
          (current.origin.lastStep || "None") +
          ". This device keeps its own review history.",
      ),
    );
  const proof = el("details", undefined, "evidence");
  proof.open = !smallScreen.matches;
  proof.append(
    el("summary", "Evidence and status"),
    el("p", flow.source),
    el("p", "Evidence version " + flow.version),
  );
  if (id === "parcel") {
    proof.append(
      el(
        "p",
        current.cash
          ? "Funding verified in the synthetic fixture."
          : "Available cash is unknown. Bid review is on hold.",
      ),
    );
    if (!current.cash)
      proof.append(
        button("Load verified funding fixture", () =>
          change(id, (d) => {
            d.cash = true;
            say("Funding fixture loaded.");
          }),
        ),
      );
  }
  panel.append(proof);
  const actions = el("div", undefined, "controls");
  if (!complete) {
    const next = button(flow.steps[step], () => advance(id, step), "action");
    next.disabled = id === "parcel" && step === 2 && !current.cash;
    if (next.disabled)
      panel.append(
        el("p", "Open Evidence and status to resolve the funding hold."),
      );
    actions.append(next);
  }
  panel.append(actions);
  if (step) {
    const list = el("ol");
    current.events.forEach((e) => list.append(el("li", e.action)));
    panel.append(list);
  }
  notes(panel, id, current);
  const handoff = el("details", undefined, "evidence");
  handoff.append(
    el("summary", "Device handoff"),
    el(
      "p",
      "Transfer a synthetic note and its evidence reference. Review events stay on the originating device.",
    ),
    button("Export draft", () => exportDraft(id)),
  );
  const upload = el("input");
  upload.type = "file";
  upload.id = "upload";
  upload.accept = ".json,application/json";
  const label = el("label", "Import draft");
  label.htmlFor = upload.id;
  upload.addEventListener("change", () => importDraft(upload.files[0]));
  handoff.append(label, upload);
  panel.append(handoff);
}
// A schematic cell opens the same record as the queue. Its placement is illustrative.
function schematic(id) {
  const figure = el("figure", undefined, "schematic");
  const field = el("div", undefined, "field");
  const pin = button(
    "Inspect " + workflows[id].title,
    () => openTask(id),
    "pin",
  );
  field.append(pin);
  figure.append(
    field,
    el("figcaption", "Illustrative location · " + workflows[id].version),
  );
  return figure;
}
function workspace(ids, data) {
  if (!ids.length)
    return el(
      "p",
      "This workspace has no demonstration records for this module.",
      "panel",
    );
  const id = ids.includes(data.selected) ? data.selected : ids[0];
  const columns = el("div", undefined, "columns");
  columns.dataset.phone = phoneView;
  const queue = el("section", undefined, "panel queue-panel");
  queue.append(el("h2", "Review queue"));
  const mapped = ids.find((item) => ["parcel", "district"].includes(item));
  if (mapped) queue.append(schematic(mapped));
  for (const item of ids.slice(0, 3)) {
    const pick = button("", () => openTask(item), "queue"),
      flow = workflows[item],
      count = record(data, item).events.length;
    pick.setAttribute("aria-pressed", String(item === id));
    pick.append(
      el("strong", flow.title),
      el("small", count === flow.steps.length ? "Complete" : flow.steps[count]),
    );
    queue.append(pick);
  }
  const detail = el("section", undefined, "panel task-panel");
  task(detail, id, record(data, id));
  columns.append(queue, detail);
  return columns;
}
function render() {
  const ids = visible(scope);
  $("scope").value = scope;
  $("title").textContent = page;
  $("modules").replaceChildren(
    ...modules.map((name) => {
      const item = button(name, () => openPage(name));
      if (name === page) item.setAttribute("aria-current", "page");
      return item;
    }),
  );
  const body = $("body");
  body.replaceChildren();
  let data;
  try {
    data = state();
  } catch {
    const domain = scope,
      storageKey = key(domain),
      broken = localStorage.getItem(storageKey);
    const panel = el("section", undefined, "panel");
    panel.append(
      el("h2", "Workspace recovery"),
      el(
        "p",
        "This saved workspace could not be read. You can archive the original snapshot and start a fresh simulation.",
      ),
    );
    panel.append(
      button("Archive snapshot and restart", async () => {
        try {
          await navigator.locks.request(storageKey, () => {
            if (localStorage.getItem(storageKey) !== broken)
              throw Error("Workspace changed. Reload before repairing.");
            localStorage.setItem(
              storageKey + ":recovery:" + crypto.randomUUID(),
              broken,
            );
            localStorage.removeItem(storageKey);
          });
          say("Original snapshot archived in this browser.");
          render();
        } catch (error) {
          say(error.message);
        }
      }),
    );
    body.append(panel);
    return;
  }
  if (page === "System") {
    const panel = el("section", undefined, "panel");
    panel.append(
      el("h2", "Journey coverage"),
      el(
        "p",
        "Fixtures run in this browser. Maps, email, accounting and identity providers are disconnected.",
      ),
    );
    const list = el("ol");
    coverage.forEach(([name, service, status]) =>
      list.append(el("li", name + " — " + service + " · " + status)),
    );
    panel.append(list);
    body.append(panel);
    return;
  }
  if (page === "Agents") {
    const panel = el("section", undefined, "panel");
    panel.append(el("h2", "Workspace activity"));
    const events = ids
      .flatMap((id) => record(data, id).events.map((e) => ({ ...e, id })))
      .sort((a, b) => a.at.localeCompare(b.at));
    if (!events.length) panel.append(el("p", "No local events yet."));
    else {
      const list = el("ol");
      events.forEach((e) =>
        list.append(
          el(
            "li",
            workflows[e.id].title + " — " + e.action + " · " + e.version,
          ),
        ),
      );
      panel.append(list);
    }
    body.append(panel);
    return;
  }
  if (page === "Network") {
    body.append(el("p", "Contact lookup is a future service.", "panel"));
    return;
  }
  let subset = ids.filter((id) => workflows[id].module === page);
  if (page === "Command") subset = ids;
  if (page === "World Map") {
    subset = ids.filter((id) => ["district", "parcel"].includes(id));
    body.append(
      el(
        "p",
        "Spatial preview uses synthetic records. Live geometry and geographic overlays are unavailable.",
        "panel",
      ),
    );
  }
  if (page === "Family Office") subset = scope === "family" ? ids : [];
  body.append(workspace(subset, data));
}
$("scope").addEventListener("change", (e) => {
  scope = e.target.value;
  localStorage.setItem(selectionKey, scope);
  say("");
  openPage("Command");
});
$("home").addEventListener("click", () => openPage("Command"));
$("current").addEventListener("click", () => {
  page = "Command";
  phoneView = "task";
  render();
  $("workspace").focus();
});
$("more").addEventListener("click", () => {
  $("navigation").open = true;
  $("navigation").querySelector("summary").focus();
});
window.addEventListener("storage", (e) => {
  if (e.key === key(scope)) {
    say("Workspace changed in another tab. Reload to refresh.");
  }
});
smallScreen.addEventListener("change", () => {
  $("navigation").open = !smallScreen.matches;
  render();
});
$("navigation").open = !smallScreen.matches;
render();
