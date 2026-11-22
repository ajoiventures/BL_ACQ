// The browser edits and presents a research packet. Every finance calculation runs on the server.
const $ = (id) => document.getElementById(id);
const clone = (value) => JSON.parse(JSON.stringify(value));
const state = {
  examples: [], packet: null, report: null, evaluatedPacket: null, assetType: "public-equity",
  authenticated: false, actor: null, dirty: false, advancedDirty: false, revision: 0,
  busy: false, saveBusy: false, saveBody: null, savedRun: null, annualPaths: {}, feedbackTimer: null,
  sessionEpoch: 0, runSequence: 0,
};
const PATH_KEYS = ["growth_path", "margin_path", "tax_path", "discount_path"];
const SHOCK_FIELDS = [
  ["near_term_growth_delta", "Near-term growth change", "delta", "Percentage-point change in growth during the event. The resulting revenue or NOI level can remain changed afterward."],
  ["near_term_margin_delta", "Near-term margin change", "delta", "Percentage-point change in operating margin while the event lasts."],
  ["long_term_growth_delta", "Ongoing growth change", "delta", "Percentage-point change across the explicit forecast. The model's terminal assumptions still apply."],
  ["long_term_margin_delta", "Ongoing margin change", "delta", "Percentage-point change to operating margins, including the terminal margin."],
  ["discount_rate_delta", "Discount rate change", "delta", "Percentage points added to the discount rate. This changes the present value of each scenario's cash flows."],
  ["reinvestment_multiplier", "Reinvestment multiplier", "multiple", "1× keeps modeled reinvestment unchanged; 1.2× increases it by 20%."],
  ["one_time_cost", "One-time cost (USD)", "money", "An additional first-year cash outflow. Do not also include the same obligation in debt or claims."],
  ["duration_years", "Near-term duration", "integer", "Number of forecast years affected by near-term growth and margin changes."],
];
const ASSUMPTIONS = {
  revenue: ["Current annual revenue", "money", "Latest annual revenue in actual dollars. Revenue is the starting level, before forecast growth."],
  operating_margin: ["Current operating margin", "rate", "Operating profit divided by revenue before financing costs. The scalar model transitions toward the target margin."],
  growth_rate: ["Initial growth rate", "rate", "Initial annual revenue growth for businesses, or annual NOI growth for properties. Corporate growth fades toward terminal growth unless explicit annual paths are supplied."],
  target_margin: ["Target operating margin", "rate", "Sustainable operating margin reached at the end of the explicit forecast; the terminal model also uses this margin."],
  tax_rate: ["Operating tax rate", "rate", "Tax rate on positive operating profit. The model does not credit operating losses with cash tax benefits."],
  wacc: ["Discount rate · WACC", "rate", "Weighted average cost of capital used for operating cash flows. It must exceed perpetual growth."],
  terminal_growth: ["Terminal growth", "rate", "Perpetual growth after the explicit forecast. Sustainable terminal reinvestment is modeled using terminal return on capital."],
  sales_to_capital: ["Sales-to-capital ratio", "multiple", "Additional annual revenue generated for each dollar of incremental invested capital. A higher ratio reduces modeled reinvestment."],
  terminal_roic: ["Terminal return on capital", "rate", "Sustainable return on new invested capital. This determines the reinvestment needed to fund terminal growth."],
  years: ["Forecast years", "integer", "Explicit forecast horizon. Annual paths, when used, must each contain exactly this many values."],
  cash: ["Excess cash (USD)", "money", "Cash added to operating-asset value in the equity bridge. Exclude cash already needed in the modeled operating cash flows."],
  non_operating_assets: ["Non-operating assets", "money", "Value of assets outside the cash-flow forecast that are available to equity holders."],
  debt: ["Debt (USD)", "money", "Outstanding debt deducted from operating-asset value to reach equity value. Financing cash flows must be excluded from operating inputs."],
  debt_like_claims: ["Other senior claims", "money", "Debt-like claims deducted in the equity bridge. Do not deduct a claim again if it is already included in forecast cash flow."],
  units: ["Equity units / shares", "number", "Diluted share count or ownership units. Public-equity values are per share. Property models require 1 for the whole property."],
  noi: ["Current annual NOI", "money", "Net operating income before debt service, investor income taxes, and the capital expenditure separately modeled below."],
  discount_rate: ["Asset discount rate", "rate", "Required return for the property's operating cash flows before financing."],
  terminal_cap_rate: ["Exit capitalization rate", "rate", "The next year's NOI divided by this rate sets the modeled exit value before selling costs."],
  annual_capex: ["Annual capital reserve", "money", "Annual capital expenditure deducted from NOI. Exclude these costs from NOI to avoid counting them twice."],
  selling_cost_rate: ["Exit selling costs", "rate", "Transaction costs as a percentage of modeled gross exit value."],
};
const CORPORATE_ORDER = ["revenue", "growth_rate", "operating_margin", "target_margin", "tax_rate", "wacc", "terminal_growth", "terminal_roic", "sales_to_capital", "years", "cash", "non_operating_assets", "debt", "debt_like_claims", "units"];
const PROPERTY_ORDER = ["noi", "growth_rate", "discount_rate", "terminal_cap_rate", "annual_capex", "selling_cost_rate", "years", "debt", "cash", "units"];
const MODEL_LABELS = { corporate_dcf: "Corporate cash-flow model", property_dcf: "Property cash-flow model" };
const POLICY_DEFAULTS = Object.freeze({ margin_of_safety: .3, max_downside_probability: .35, max_source_age_days: 365, max_quote_age_days: 7 });
const human = (value) => String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, (s) => s.toUpperCase());
const finite = (value) => typeof value === "number" && Number.isFinite(value);
const number = (value, digits = 0) => finite(value) ? new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value) : "—";
const money = (value, digits) => finite(value) ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: digits ?? (Math.abs(value) < 1000 ? 2 : 0), minimumFractionDigits: digits ?? (Math.abs(value) < 1000 ? 2 : 0) }).format(value) : "—";
const percent = (value, digits = 1) => finite(value) ? new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value) : "—";
const axisMoney = (value) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(value);
function dateLabel(value) {
  if (!value) return "Date not supplied";
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
}
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}
function say(message) {
  clearTimeout(state.feedbackTimer);
  $("feedback").textContent = message;
  state.feedbackTimer = setTimeout(() => { $("feedback").textContent = ""; }, 6500);
}
function showError(message) { $("evaluation-error").textContent = message; $("evaluation-error").hidden = !message; }
async function request(path, body) {
  const options = { credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" } };
  if (body !== undefined) { options.method = "POST"; options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error("The workspace could not be reached. Check the connection and try again."); }
  if (!response.headers.get("Content-Type")?.includes("application/json")) {
    const error = new Error("The valuation service is unavailable at this address. Open this page through the running Black River workspace.");
    error.status = response.status; throw error;
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error("The workspace returned an unreadable response. Your inputs are still in this tab."); }
  if (!response.ok) {
    const error = new Error(data.error || data.message || `The request could not be completed (${response.status}).`);
    error.status = response.status; throw error;
  }
  return data;
}
function updateControls() {
  const hasPacket = Boolean(state.packet);
  $("evaluate-button").disabled = !hasPacket || state.busy || state.saveBusy || state.advancedDirty;
  $("evaluate-button").firstElementChild.textContent = state.busy ? "Calculating…" : "Calculate value";
  $("export-button").disabled = !state.report || state.dirty || state.busy || state.advancedDirty;
  $("save-button").disabled = !state.report || state.dirty || state.busy || state.saveBusy || state.advancedDirty || Boolean(state.savedRun);
  $("save-button").textContent = state.saveBusy ? "Saving…" : state.savedRun ? "Valuation saved" : state.saveBody ? "Retry save" : "Save valuation";
  $("refresh-history").disabled = !state.authenticated;
  $("add-scenario").disabled = !hasPacket || (state.packet?.scenarios?.length ?? 0) >= 12;
  $("add-source").disabled = !hasPacket || (state.packet?.sources?.length ?? 0) >= 30;
  $("stale-notice").hidden = !(state.report && state.dirty);
  document.body.classList.toggle("is-stale", Boolean(state.report && state.dirty));
  $("input-status").textContent = state.advancedDirty ? "Apply or discard JSON edits before calculating." : state.busy ? "Calculating from this set of inputs…" : !hasPacket ? "Choose an example to begin." : state.dirty ? "Inputs changed · Calculation needed" : state.report ? "Inputs match the displayed calculation." : "Ready to calculate · USD in actual dollars";
}
function syncAdvanced() {
  if (!state.advancedDirty) $("advanced-packet").value = state.packet ? JSON.stringify(state.packet, null, 2) : "";
}
function changed() {
  state.revision += 1;
  state.dirty = true;
  state.savedRun = null;
  state.saveBody = null;
  $("save-status").textContent = "Inputs changed. Recalculate before saving.";
  syncAdvanced(); updateControls();
}
function info(text) {
  const node = el("span", "info", "i");
  node.tabIndex = 0; node.dataset.tip = text; node.setAttribute("aria-label", text);
  return node;
}
let fieldCount = 0;
function field({ label, value, type = "text", help, onChange, wide = false, options, required = false, disabled = false, min, max, placeholder }) {
  const wrapper = el("div", `field${wide ? " field-wide" : ""}`);
  const id = `valuation-field-${++fieldCount}`;
  const labelNode = el("label", "", label); labelNode.htmlFor = id;
  if (help) labelNode.append(info(help));
  const input = document.createElement(options ? "select" : type === "textarea" ? "textarea" : "input");
  input.id = id; input.required = required; input.disabled = disabled;
  if (options) {
    for (const option of options) { const item = el("option", "", option.label); item.value = option.value; input.append(item); }
  } else if (type !== "textarea") {
    input.type = ["rate", "delta", "money", "number", "integer", "multiple"].includes(type) ? "number" : type;
    if (input.type === "number") { input.step = type === "integer" ? "1" : "any"; input.inputMode = "decimal"; }
  }
  if (min !== undefined) input.min = min;
  if (max !== undefined) input.max = max;
  if (placeholder) input.placeholder = placeholder;
  const scaled = type === "rate" || type === "delta";
  input.value = value === null || value === undefined ? "" : scaled && finite(value) ? Number((value * 100).toPrecision(13)) : String(value);
  input.addEventListener(options || type === "date" ? "change" : "input", () => {
    let next = input.value;
    if (input.type === "number") next = next === "" ? null : Number(next) / (scaled ? 100 : 1);
    else if (type === "date") next = next || null;
    onChange(next); changed();
  });
  wrapper.append(labelNode);
  if (scaled || type === "multiple") { const unitWrap = el("div", "input-with-suffix"); unitWrap.append(input, el("span", "", type === "delta" ? "pp" : type === "multiple" ? "×" : "%")); wrapper.append(unitWrap); }
  else wrapper.append(input);
  return wrapper;
}
function putField(container, packetPart, key, descriptor, options = {}) {
  const [label, type, help] = descriptor;
  container.append(field({ label, type, help, value: packetPart[key], onChange: (value) => { packetPart[key] = value; }, ...options }));
}
function setText(element, value) { $(element).textContent = value; }
function unitLabel() {
  if (state.packet?.model_type === "property_dcf") return "Whole-property equity";
  return state.assetType === "public-equity" ? "Per diluted share" : "Per ownership unit";
}
function inferAssetType(example) {
  if (example.request?.model_type === "property_dcf") return "property";
  return /business|private|operating[-_ ]business/i.test(`${example.id} ${example.label} ${example.asset_type || ""}`) ? "operating-business" : "public-equity";
}
function renderExamples() {
  const select = $("example-select"); select.replaceChildren();
  const matches = state.examples.filter((example) => inferAssetType(example) === state.assetType);
  const available = matches.length ? matches : state.examples.filter((example) => state.assetType !== "property" && example.request?.model_type === "corporate_dcf");
  for (const example of available) { const option = el("option", "", example.label); option.value = example.id; select.append(option); }
  if (!available.length) { const option = el("option", "", "No example available"); option.value = ""; select.append(option); }
  return available;
}
function assertPacketStructure(packet) {
  // Protect the editor's shape assumptions before replacing its current packet.
  // Numeric ranges, financial consistency, enums, and evidence rules belong to the server.
  const record = (value, path) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${path} must be a JSON object, not an array or null.`);
  };
  const array = (value, path) => {
    if (!Array.isArray(value)) throw new Error(`${path} must be an array.`);
  };
  const strings = (value, path) => {
    array(value, path);
    if (value.some((item) => typeof item !== "string")) throw new Error(`${path} must contain only strings.`);
  };
  const optionalRefs = (object, key, path) => {
    if (key in object) strings(object[key], `${path}.${key}`);
  };
  record(packet, "Packet"); record(packet.assumptions, "assumptions");
  if (!["corporate_dcf", "property_dcf"].includes(packet.model_type)) throw new Error("Supply a supported model_type: corporate_dcf or property_dcf.");
  for (const key of ["market", "policy", "qualification", "qualification_source_ids"]) if (key in packet) record(packet[key], key);
  for (const key of ["capital", "reference_values"]) if (key in packet && packet[key] !== null) record(packet[key], key);
  for (const key of PATH_KEYS) if (key in packet.assumptions) array(packet.assumptions[key], `assumptions.${key}`);
  optionalRefs(packet, "input_source_ids", "packet");
  if (packet.qualification_source_ids) for (const [key, refs] of Object.entries(packet.qualification_source_ids)) strings(refs, `qualification_source_ids.${key}`);
  if ("sources" in packet) {
    array(packet.sources, "sources");
    packet.sources.forEach((source, index) => { const path = `sources[${index}]`; record(source, path); optionalRefs(source, "issues", path); });
  }
  if ("scenarios" in packet) {
    array(packet.scenarios, "scenarios");
    packet.scenarios.forEach((scenario, index) => {
      const path = `scenarios[${index}]`; record(scenario, path); optionalRefs(scenario, "source_ids", path);
      for (const key of ["shock", "assumptions_override"]) if (key in scenario) record(scenario[key], `${path}.${key}`);
      if (scenario.assumptions_override) for (const key of PATH_KEYS) if (key in scenario.assumptions_override) array(scenario.assumptions_override[key], `${path}.assumptions_override.${key}`);
    });
  }
  if ("claims" in packet) { array(packet.claims, "claims"); packet.claims.forEach((claim, index) => record(claim, `claims[${index}]`)); }
}
function loadPacket(packet, options = {}) {
  assertPacketStructure(packet);
  state.packet = clone(packet);
  state.packet.market ??= { price: null, as_of: null, source_id: "" };
  state.packet.policy = { ...POLICY_DEFAULTS, ...state.packet.policy };
  state.packet.sources ??= []; state.packet.scenarios ??= []; state.packet.qualification ??= {};
  state.packet.qualification_source_ids ??= {}; state.packet.input_source_ids ??= [];
  state.annualPaths = Object.fromEntries(PATH_KEYS.filter((key) => key in state.packet.assumptions).map((key) => [key, clone(state.packet.assumptions[key])]));
  state.advancedDirty = false; state.revision += 1; state.dirty = options.clean !== true;
  state.saveBody = null; state.savedRun = options.runId || null;
  if (options.assetType) state.assetType = options.assetType;
  else if (state.packet.model_type === "property_dcf") state.assetType = "property";
  else if (state.assetType === "property") state.assetType = "operating-business";
  $("asset-type").value = state.assetType;
  if (!options.preserveExample) { renderExamples(); $("example-select").selectedIndex = -1; }
  $("example-description").textContent = state.packet.illustrative ? "Illustrative inputs · No live quote" : "User-supplied inputs · Source review required";
  setText("model-description", MODEL_LABELS[state.packet.model_type] || "Valuation model");
  renderForm(); syncAdvanced(); showError(""); updateControls();
}
function loadExample(id) {
  const example = state.examples.find((item) => item.id === id);
  if (!example) return;
  loadPacket(example.request, { preserveExample: true });
  $("example-select").value = id;
  $("example-description").textContent = `${example.description || "Illustrative inputs"} · No live quote`;
  say(`${example.label} loaded. Review the inputs before calculating.`);
}
function renderForm() {
  if (!state.packet) return;
  const p = state.packet;
  const identity = $("identity-fields"); identity.replaceChildren();
  putField(identity, p, "asset_id", ["Asset reference", "text", "A stable reference for the company or property being valued."], { required: true });
  putField(identity, p, "deal_id", ["Deal reference", "text", "Links this valuation to a distinct investment opportunity."], { required: true });
  const market = $("market-fields"); market.replaceChildren();
  putField(market, p, "as_of", ["Analysis date", "date", "The information cutoff for this valuation. Future or stale sources are flagged by the engine."], { required: true });
  putField(market, p.market, "price", [p.model_type === "property_dcf" ? "Equity price (USD)" : "Equity price / unit (USD)", "money", "Observed market or proposed transaction price on the same equity-per-unit basis as the model. Leave empty if no price is available."], { min: 0 });
  putField(market, p.market, "as_of", ["Price observed on", "date", "Date of the price observation. Missing dates remain missing; they are never treated as a live quote."]);
  putField(market, p.market, "source_id", ["Price source ID", "text", "The ID of the price source listed under Evidence & sources."]);
  renderAssumptions(); renderScenarios(); renderPolicy(); renderEvidence();
}
function renderAssumptions() {
  const p = state.packet; const a = p.assumptions; const container = $("assumption-fields"); container.replaceChildren();
  const corporate = p.model_type === "corporate_dcf";
  const activePaths = PATH_KEYS.filter((key) => Array.isArray(a[key]));
  $("annual-path-control").hidden = !corporate || (!activePaths.length && !Object.keys(state.annualPaths).length);
  $("use-annual-paths").checked = activePaths.length > 0;
  setText("path-warning", activePaths.length ? `Explicit paths are active: ${activePaths.map(human).join(", ")}. They override matching forecast-period scalars; terminal assumptions remain explicit below. Edit the arrays in Advanced packet, or turn this off to use scalar assumptions.` : "Scalar assumptions are active. Turn this on to restore the example's annual paths.");
  setText("assumptions-note", corporate ? "Operating cash flows value the business; cash and senior claims then bridge to equity. Amounts below are actual USD." : "NOI excludes debt service and the capital reserve below. Debt is deducted after valuing the property; the result is whole-property equity.");
  const overridden = { growth_rate: "growth_path", target_margin: "margin_path", tax_rate: "tax_path", wacc: "discount_path" };
  for (const key of corporate ? CORPORATE_ORDER : PROPERTY_ORDER) {
    const descriptor = [...ASSUMPTIONS[key]];
    if (key === "units" && !corporate) descriptor[0] = "Whole-property units";
    const disabled = key === "units" && !corporate;
    const pathActive = overridden[key] && Array.isArray(a[overridden[key]]);
    // Terminal margin, terminal tax and terminal discount still use some scalar values.
    // Growth and discount scalars are superseded; terminal margin and tax remain explicit.
    if (pathActive) descriptor[0] += key === "growth_rate" ? " · path active" : " · annual path active";
    const node = field({ label: descriptor[0], type: descriptor[1], help: descriptor[2], value: a[key], required: true, disabled: disabled || (["growth_rate", "wacc"].includes(key) && pathActive), onChange: (value) => { a[key] = value; }, min: key === "years" ? 1 : undefined, max: key === "years" ? 30 : undefined });
    if (pathActive && key !== "growth_rate") node.append(el("p", "field-help", key === "target_margin" ? "Annual margin path applies to forecast years; this scalar still sets terminal margin." : key === "tax_rate" ? "Annual tax path applies to forecast years; this scalar still sets terminal tax." : "Annual discount path applies, including its final rate in terminal valuation."));
    container.append(node);
  }
  if (corporate) container.append(field({ label: "Reinvestment timing", value: a.reinvestment_timing || "same_year", wide: true, help: "Select the year in which capital is committed to support revenue growth. Use the source model's convention.", options: [{ value: "same_year", label: "Same year as revenue growth" }, { value: "next_year", label: "Fund next year's revenue growth" }], onChange: (value) => { a.reinvestment_timing = value; } }));
}
function sourceRefsField(value, label, onChange, help) {
  return field({ label, value: (value || []).join(", "), wide: true, help: help || "Enter source IDs separated by commas. Each ID must exist in the source list.", onChange: (text) => onChange(text.split(",").map((v) => v.trim()).filter(Boolean)) });
}
function renderScenarios() {
  const list = $("scenario-fields"); list.replaceChildren();
  const p = state.packet;
  p.scenarios.forEach((scenario, index) => {
    scenario.shock ??= {};
    const card = el("div", "scenario-editor");
    const heading = el("div", "editor-card-heading"); heading.append(el("h3", "", `Scenario ${index + 1}`));
    const remove = el("button", "remove-button", "Remove"); remove.type = "button"; remove.setAttribute("aria-label", `Remove scenario ${index + 1}`);
    remove.addEventListener("click", () => { p.scenarios.splice(index, 1); changed(); renderScenarios(); updateControls(); });
    heading.append(remove); card.append(heading);
    const grid = el("div", "field-grid");
    putField(grid, scenario, "label", ["Scenario name", "text"], { required: true });
    putField(grid, scenario, "probability", ["Assumed weight", "rate", "Your assumed weight for this mutually exclusive scenario. The complete scenario set must total exactly 100%."], { min: 0, max: 100, required: true });
    const details = el("details", "scenario-overrides"); details.append(el("summary", "", "Cash-flow changes & source references"));
    const shockGrid = el("div", "field-grid");
    SHOCK_FIELDS.forEach(([key, label, type, help]) => {
      if (p.model_type === "property_dcf" && key.includes("margin")) return;
      const defaultValue = key === "reinvestment_multiplier" || key === "duration_years" ? 1 : 0;
      shockGrid.append(field({ label, type, help, value: scenario.shock[key] ?? defaultValue, onChange: (value) => { scenario.shock[key] = value; }, required: true, min: ["duration_years", "one_time_cost", "reinvestment_multiplier"].includes(key) ? 0 : undefined }));
    });
    shockGrid.append(sourceRefsField(scenario.source_ids, "Scenario source IDs", (value) => { scenario.source_ids = value; }));
    if (scenario.assumptions_override && Object.keys(scenario.assumptions_override).length) shockGrid.append(el("p", "field-help field-wide", "This scenario also has explicit assumption overrides. Review them in Advanced packet; those overrides remain active."));
    details.append(shockGrid); card.append(grid, details); list.append(card);
  });
  setText("scenario-note", `${p.scenarios.length} of 12 scenarios. Assumed weights are checked by the engine and are never rescaled automatically.`);
}
function renderPolicy() {
  const p = state.packet; const container = $("decision-fields"); container.replaceChildren();
  putField(container, p.policy, "margin_of_safety", ["Margin of safety", "rate", "Required discount from event-adjusted value. Applied once, after scenario weighting, to set the entry ceiling."], { min: 0, max: 95, required: true });
  putField(container, p.policy, "max_downside_probability", ["Scenario weight below price limit", "rate", "Maximum total assumed weight of scenarios whose current modeled intrinsic value is below the reference price. This does not estimate the probability of a realized loss over a holding period."], { min: 0, max: 100, required: true });
  putField(container, p.policy, "max_source_age_days", ["Source age limit", "integer", "Maximum number of days between a source's observation and the analysis date."], { min: 1, max: 3650, required: true });
  putField(container, p.policy, "max_quote_age_days", ["Price age limit", "integer", "Maximum age in days of the reference price observation."], { min: 0, max: 365, required: true });
  const q = $("qualification-fields"); q.replaceChildren();
  for (const key of ["buyable", "fundable", "sellable"]) q.append(field({ label: human(key), value: p.qualification[key] || "unknown", options: [{ value: "unknown", label: "Unknown" }, { value: "confirmed", label: "Confirmed" }, { value: "failed", label: "Failed" }], onChange: (value) => { p.qualification[key] = value; } }));
}
function renderEvidence() {
  const p = state.packet; const container = $("evidence-fields"); container.replaceChildren();
  container.append(field({ label: "Input basis", value: p.illustrative ? "illustrative" : "research", wide: true, help: "Illustrative inputs always remain on hold. Choosing research does not verify the sources or approve an investment.", options: [{ value: "illustrative", label: "Illustrative inputs" }, { value: "research", label: "Research inputs for source review" }], onChange: (value) => { p.illustrative = value === "illustrative"; $("example-description").textContent = p.illustrative ? "Illustrative inputs · No live quote" : "User-supplied inputs · Source review required"; } }));
  container.append(sourceRefsField(p.input_source_ids, "Financial input source IDs", (value) => { p.input_source_ids = value; }));
  for (const key of ["buyable", "fundable", "sellable"]) container.append(sourceRefsField(p.qualification_source_ids[key], `${human(key)} source IDs`, (value) => { p.qualification_source_ids[key] = value; }, "A confirmed qualification also requires reviewed source references. A declaration alone does not clear the gate."));
  putField(container, p, "notes", ["Research notes", "textarea", "Record context, uncertainties, and how you interpreted source material."], { wide: true });
  renderSources();
}
function renderSources() {
  const list = $("source-fields"); list.replaceChildren();
  const p = state.packet;
  p.sources.forEach((source, index) => {
    const card = el("div", "source-editor"); const heading = el("div", "editor-card-heading"); heading.append(el("h3", "", `Source ${index + 1}`));
    const remove = el("button", "remove-button", "Remove"); remove.type = "button"; remove.setAttribute("aria-label", `Remove source ${index + 1}`);
    remove.addEventListener("click", () => { p.sources.splice(index, 1); changed(); renderSources(); updateControls(); say("Source removed. Review any references to its ID before calculating."); });
    heading.append(remove); card.append(heading);
    const grid = el("div", "field-grid");
    putField(grid, source, "id", ["Source ID", "text", "A unique identifier used by financial inputs, price, scenarios, and qualifications."], { required: true });
    grid.append(field({ label: "Source kind", value: source.kind, options: ["financials", "quote", "event", "assumptions", "qualification"].map((kind) => ({ value: kind, label: human(kind) })), onChange: (value) => { source.kind = value; } }));
    putField(grid, source, "title", ["Title", "text"], { required: true, wide: true });
    putField(grid, source, "url", ["Source URL", "url", "An HTTP or HTTPS reference to the source, without credentials."], { required: true, wide: true });
    putField(grid, source, "observed_on", ["Observed on", "date", "Date the information was observed. A missing date remains an evidence issue."]);
    grid.append(field({ label: "Source review", value: source.verified ? "reviewed" : "unreviewed", options: [{ value: "unreviewed", label: "Needs review" }, { value: "reviewed", label: "I reviewed this source" }], help: "This is your source-review assertion. The engine does not independently fetch or verify the linked material.", onChange: (value) => { source.verified = value === "reviewed"; } }));
    putField(grid, source, "notes", ["Source notes", "textarea"], { wide: true });
    if (source.issues?.length) grid.append(el("p", "field-help field-wide", `Recorded source issues: ${source.issues.join(" · ")}. Edit these explicitly in Advanced packet after resolving them.`));
    card.append(grid); list.append(card);
  });
}
function setSession(authenticated, actor = null) {
  if (!authenticated && state.authenticated) { state.sessionEpoch += 1; state.revision += 1; }
  state.authenticated = authenticated;
  if (actor) state.actor = actor;
  if (!authenticated) state.actor = null;
  setText("session-state", authenticated ? state.actor ? `${human(state.actor)} session` : "Signed in" : "Not signed in");
  setText("session-button", authenticated ? "Sign out" : "Sign in");
  $("sign-in-panel").hidden = authenticated;
  updateControls();
}
function openSignIn() { $("sign-in-panel").hidden = false; $("sign-in-panel").scrollIntoView({ behavior: "smooth", block: "nearest" }); $("access-key").focus(); }
async function evaluate() {
  if (!state.packet || state.busy || state.advancedDirty) return;
  if (!state.authenticated) { openSignIn(); say("Sign in to calculate this valuation."); return; }
  state.busy = true; showError(""); updateControls();
  state.runSequence += 1;
  const packet = clone(state.packet); const revision = state.revision;
  try {
    const data = await request("/api/valuation/evaluate", packet);
    if (revision !== state.revision) { say("Inputs changed during calculation. Recalculate the current inputs."); return; }
    const report = data.report || data;
    if (!report.baseline || !report.decision) throw new Error("The workspace did not return a complete valuation report.");
    state.report = report; state.evaluatedPacket = packet; state.dirty = false; state.saveBody = null; state.savedRun = null;
    renderReport(); setText("save-status", "Save a dated record of this valuation and its inputs.");
    say(`Calculation complete. ${statusLabel(report.decision.status)}.`);
  } catch (error) { if (revision !== state.revision) return; showError(error.message); if (error.status === 401) { setSession(false); openSignIn(); } }
  finally { state.busy = false; updateControls(); }
}
function statusLabel(status) { return { review_candidate: "Ready for independent review", watch: "Watch price & risk", hold: "On hold · Review needed" }[status] || human(status); }
function renderReport() {
  const r = state.report; if (!r) return;
  $("report").hidden = false; $("empty-state").hidden = true;
  $("report").classList.toggle("whole-asset", r.model_type === "property_dcf" || state.evaluatedPacket?.assumptions?.units === 1);
  setText("report-title", r.asset_id || "The investment case");
  setText("report-meta", `${MODEL_LABELS[r.model_type] || human(r.model_type)} · As of ${dateLabel(r.as_of)} · ${unitLabel()}`);
  const status = $("decision-status"); status.textContent = statusLabel(r.decision.status); status.className = `status-pill status-${r.decision.status === "hold" ? "hold" : r.decision.status === "watch" ? "watch" : "ready"}`;
  $("illustrative-notice").hidden = !state.evaluatedPacket?.illustrative;
  setText("baseline-value", money(r.baseline.value_per_unit)); setText("adjusted-value", money(r.decision.adjusted_value)); setText("entry-value", money(r.decision.entry_ceiling));
  setText("baseline-unit", unitLabel()); setText("entry-margin", `${percent(r.decision.margin_of_safety, 0)} margin of safety`);
  setText("reference-price", money(r.decision.market_price));
  $("reference-price").title = `Observed ${dateLabel(r.decision.price_as_of || state.evaluatedPacket?.market?.as_of)}. No live feed.`;
  const priceDate = r.decision.price_as_of || state.evaluatedPacket?.market?.as_of;
  const historical = !priceDate || state.evaluatedPacket?.illustrative;
  setText("upside-label", historical ? "Input gap to value" : "Upside to value");
  setText("price-context-note", !finite(r.decision.market_price) ? "No reference price supplied. Price comparisons and scenario weight below price are unavailable." : !priceDate ? "Historical input comparison — price unverified. The reference price has no observation date; these percentages are input comparisons, not current market upside." : state.evaluatedPacket?.illustrative ? `Illustrative input comparison. Reference price dated ${dateLabel(priceDate)}; no live quote is connected.` : `Reference price observed ${dateLabel(priceDate)}. Comparisons use that observation; no live quote is connected.`);
  setText("upside-value", percent(r.decision.upside)); setText("discount-value", percent(r.decision.discount_to_value)); setText("downside-value", percent(r.decision.downside_probability, 0));
  for (const [id, value] of [["upside-value", r.decision.upside], ["discount-value", r.decision.discount_to_value]]) $(id).className = finite(value) ? value >= 0 ? "positive" : "negative" : "";
  setText("value-unit-label", `USD · ${unitLabel().toLowerCase()}`);
  renderComparison(); renderEntryReferences(); renderQualifications(); renderCapital(); renderForecast(); renderScenarioResults(); renderSensitivity(); renderEvidenceResults();
  setText("packet-digest", r.packet_digest || "Not supplied");
  const reasons = $("decision-reasons"); reasons.replaceChildren(...(r.decision.reasons || []).map((reason) => el("li", "", reason)));
  if (!r.decision.reasons?.length) reasons.append(el("li", "", "The modeled price, risk policy, and supplied evidence qualify for independent review. Execution is not authorized by this report."));
  updateControls();
}
function renderComparison() {
  const r = state.report; const values = [["Reference price", r.decision.market_price, "market"], ["Entry ceiling", r.decision.entry_ceiling, "entry"], ["Baseline value", r.baseline.value_per_unit, "baseline"], ["Event-adjusted value", r.decision.adjusted_value, "adjusted"]];
  const maxValue = Math.max(1, ...values.map(([, value]) => finite(value) ? Math.abs(value) : 0));
  const container = $("price-comparison"); container.replaceChildren();
  for (const [label, value, kind] of values) {
    const row = el("div", "comparison-row"); row.append(el("span", "comparison-label", label));
    const track = el("div", "comparison-track"); track.setAttribute("aria-hidden", "true");
    if (finite(value)) { const bar = el("div", `comparison-bar ${kind}`); bar.style.width = `${Math.max(0, value) / maxValue * 100}%`; track.append(bar); }
    row.append(track, el("span", "comparison-number", money(value))); container.append(row);
  }
}
function renderQualifications() {
  const container = $("qualification-results"); container.replaceChildren();
  const q = state.report.decision.qualification || {};
  for (const key of ["buyable", "fundable", "sellable"]) {
    const result = typeof q[key] === "object" && q[key] ? q[key] : { status: q[key] || "unknown" };
    const card = el("article", `qualification-card ${result.status}`); card.append(el("h4", "", human(key)), el("strong", "", result.status === "confirmed" ? "Source-supported" : result.status === "failed" ? "Criterion failed" : "Evidence needed"));
    if (result.reason) card.append(el("p", "", result.reason)); container.append(card);
  }
}
function renderEntryReferences() {
  const r = state.report; const container = $("entry-references"); container.replaceChildren();
  const references = [
    ["Baseline policy reference", r.decision.baseline_entry_reference, "Unchanged baseline value after the selected margin of safety. The headline entry ceiling uses event-adjusted value."],
    ["Historical author threshold", r.reference_values?.author_entry_threshold, "Threshold recorded in the source analysis. Preserved for comparison; it does not update with this scenario model."],
  ];
  for (const [label, value, description] of references) {
    if (!finite(value)) continue;
    const note = el("article", "reference-note"); note.append(el("p", "small-label", label), el("strong", "", money(value)), el("p", "", description)); container.append(note);
  }
}
function renderCapital() {
  const capital = state.report.capital; const container = $("capital-results"); container.replaceChildren(); container.hidden = !capital;
  if (!capital) return;
  container.append(el("h4", "", "Capital sizing for review")); const grid = el("div", "capital-grid");
  for (const [label, value] of [["Proposed units", number(capital.proposed_units, 4)], ["Indicative cost", money(capital.proposed_cost)], ["Cash committed", money(capital.cash_committed)]]) { const item = el("div"); item.append(el("span", "small-label", label), el("strong", "", value)); grid.append(item); }
  container.append(grid, el("p", "field-help", capital.reason || capital.limitation || "Research sizing only. This calculation does not commit cash or authorize a transaction."));
}
function svgNode(tag, attributes = {}, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text; return node;
}
function renderForecast() {
  const rows = state.report.baseline.forecast || []; const property = state.report.model_type === "property_dcf";
  const columns = [["year", "Year", "year"], [property ? "noi" : "revenue", property ? "NOI" : "Revenue", "money"], ["growth_rate", "Growth", "rate"], ...(!property ? [["operating_margin", "Margin", "rate"]] : []), ["reinvestment", property ? "Capital reserve" : "Reinvestment", "money"], ["fcf", "Free cash flow", "money"], ["pv", "Present value", "money"]];
  const head = $("forecast-table").querySelector("thead"); const body = $("forecast-table").querySelector("tbody"); const tr = el("tr");
  for (const [, label] of columns) { const th = el("th", "", label); th.scope = "col"; tr.append(th); } head.replaceChildren(tr); body.replaceChildren();
  for (const row of rows) { const line = el("tr"); for (const [key, , kind] of columns) { const cell = el(key === "year" ? "th" : "td", "", kind === "year" ? `Y${row[key]}` : kind === "rate" ? percent(row[key]) : money(row[key], 0)); if (key === "year") cell.scope = "row"; line.append(cell); } body.append(line); }
  setText("forecast-units", "USD · Chart: K / M / B / T");
  const chart = $("forecast-chart"); chart.replaceChildren();
  if (rows.length) {
    const width = 720, height = 210, left = 68, right = 18, top = 18, bottom = 32;
    const values = rows.flatMap((row) => [row.fcf, row.pv]).filter(finite);
    const lower = Math.min(0, ...values), upper = Math.max(1, ...values);
    const x = (index) => left + (rows.length === 1 ? .5 : index / (rows.length - 1)) * (width - left - right);
    const y = (value) => top + (upper - value) / (upper - lower || 1) * (height - top - bottom);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });
    for (let i = 0; i <= 3; i++) { const value = lower + (upper - lower) * i / 3; const position = y(value); svg.append(svgNode("line", { x1: left, y1: position, x2: width - right, y2: position, stroke: "#dfe4db", "stroke-width": "1" }), svgNode("text", { x: left - 10, y: position + 4, "text-anchor": "end" }, axisMoney(value))); }
    for (const [key, color] of [["fcf", "#216d65"], ["pv", "#a7843e"]]) {
      const points = rows.map((row, index) => `${x(index)},${y(row[key])}`).join(" ");
      svg.append(svgNode("polyline", { points, fill: "none", stroke: color, "stroke-width": "2.5", "stroke-linejoin": "round" }));
      rows.forEach((row, index) => { svg.append(svgNode("circle", { cx: x(index), cy: y(row[key]), r: rows.length > 15 ? 2 : 3, fill: color })); });
    }
    rows.forEach((row, index) => { if (rows.length <= 12 || index % 3 === 0 || index === rows.length - 1) svg.append(svgNode("text", { x: x(index), y: height - 8, "text-anchor": "middle" }, `Y${row.year}`)); });
    chart.append(svg); const legend = el("div", "chart-legend"); legend.append(el("span", "", "Free cash flow"), el("span", "", "Present value")); chart.append(legend);
    chart.setAttribute("aria-label", "Baseline free cash flow and discounted cash flow by year. The table below supplies each forecast year in actual USD rounded to the nearest dollar; JSON export preserves calculation precision.");
  } else chart.append(el("p", "section-note", "No annual forecast was returned."));
  const terminal = $("terminal-summary"); terminal.replaceChildren();
  for (const [label, value] of [["Operating-asset value", money(state.report.baseline.enterprise_value)], ["Terminal share of value", percent(state.report.baseline.terminal_share)], ["Net senior claims", money(state.report.baseline.net_claims)]]) { const item = el("div", "terminal-item"); item.append(el("span", "small-label", label), el("strong", "", value)); terminal.append(item); }
}
function renderScenarioResults() {
  const container = $("scenario-results"); container.replaceChildren();
  for (const scenario of state.report.scenarios || []) {
    const card = el("article", "scenario-card"); const top = el("div", "scenario-card-top"); top.append(el("h4", "", scenario.label || scenario.id), el("span", "probability", `${percent(scenario.probability, 0)} weight`));
    card.append(top, el("strong", "scenario-value", money(scenario.valuation?.value_per_unit)), el("p", "", `${unitLabel()}${finite(scenario.change_from_baseline) ? ` · ${percent(scenario.change_from_baseline)} vs baseline` : ""}`));
    const changes = el("ul");
    for (const [key, label, type] of SHOCK_FIELDS) {
      const value = scenario.shock?.[key];
      if (!finite(value) || key === "duration_years" || value === 0 || (key === "reinvestment_multiplier" && value === 1)) continue;
      changes.append(el("li", "", `${label}: ${type === "delta" ? `${number(value * 100, 2)} percentage points` : type === "money" ? money(value) : `${number(value, 2)}×`}`));
    }
    if (scenario.assumptions_override && Object.keys(scenario.assumptions_override).length) changes.append(el("li", "", "Includes explicit assumption overrides from the packet."));
    if (changes.children.length) card.append(changes); else card.append(el("p", "", "No operating shock applied."));
    container.append(card);
  }
  setText("scenario-result-note", "Scenario weights are assumptions you supply. The engine calculates event-adjusted value from this complete set of mutually exclusive scenarios. Scenario weight below price compares current modeled intrinsic values with the reference price; it does not estimate the probability of a realized loss over a holding period.");
}
function renderSensitivity() {
  const sensitivity = state.report.sensitivity || {}; const head = $("sensitivity-table").querySelector("thead"); const body = $("sensitivity-table").querySelector("tbody"); head.replaceChildren(); body.replaceChildren();
  const rowLabel = ASSUMPTIONS[sensitivity.row_parameter]?.[0] || human(sensitivity.row_parameter);
  const columnLabel = ASSUMPTIONS[sensitivity.column_parameter]?.[0] || human(sensitivity.column_parameter);
  setText("sensitivity-description", `${rowLabel} in rows; ${columnLabel.toLowerCase()} in columns. Values are baseline equity per unit, before event weighting or margin of safety.`);
  if (sensitivity.cells?.length) {
    const tr = el("tr"); const corner = el("th", "", `${rowLabel} ↓`); corner.scope = "col"; tr.append(corner);
    for (const value of sensitivity.column_values || []) { const th = el("th", "", percent(value)); th.scope = "col"; tr.append(th); } head.append(tr);
    const values = sensitivity.cells.flat().map((cell) => cell.value_per_unit).filter(finite).sort((a, b) => a - b);
    sensitivity.cells.forEach((row, index) => {
      const line = el("tr"); const label = el("th", "", percent(sensitivity.row_values?.[index])); label.scope = "row"; line.append(label);
      row.forEach((cell) => { const td = el("td", "", money(cell.value_per_unit)); if (finite(cell.value_per_unit)) { const rank = values.indexOf(cell.value_per_unit); td.dataset.tone = String(Math.min(5, Math.floor(rank / Math.max(1, values.length) * 5) + 1)); td.title = money(cell.value_per_unit, 2); } else { td.className = "sensitivity-invalid"; td.title = cell.reason || "Invalid assumptions"; td.tabIndex = 0; td.setAttribute("aria-label", cell.reason || "Invalid assumptions"); } line.append(td); }); body.append(line);
    });
  }
  setText("sensitivity-note", `${sensitivity.row_definition || ""} Darker cells indicate higher modeled value. A dash marks an invalid combination; focus or inspect its description for the reason.`);
  const reverse = state.report.reverse_dcf || {}; setText("implied-growth", reverse.status === "solved" ? percent(reverse.implied_growth_rate ?? reverse.implied_rate, 2) : "—");
  const descriptions = { unsupported_explicit_path: "An explicit annual growth path is active, so a single implied growth rate is not defined. Turn off the path to test a scalar growth assumption.", missing_price: "Add a dated reference price to calculate the growth rate implied by that price.", non_monotonic: "The tested growth/value relationship changes direction or is flat. The engine cannot establish a unique implied rate.", out_of_range: "The reference price is outside the model's tested growth range, or a verified solution was not found." };
  setText("reverse-note", reverse.status === "solved" ? "Initial growth needed to support the reference equity price, holding other baseline assumptions fixed. This is an implied assumption, not a growth forecast." : descriptions[reverse.status] || reverse.reason || "Reverse valuation is not available for these inputs.");
}
function safeURL(value) { try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null; } catch { return null; } }
function renderEvidenceResults() {
  const evidence = state.report.evidence || {}; const status = $("evidence-status"); status.textContent = evidence.status === "verified" ? "Source assertions complete" : "Source review required"; status.className = `status-pill${evidence.status === "verified" ? "" : " status-hold"}`;
  const holds = $("evidence-holds"); holds.replaceChildren();
  if (evidence.issues?.length) { const notice = el("div", "notice notice-warning"); notice.append(el("strong", "", `${evidence.issues.length} evidence or qualification hold${evidence.issues.length === 1 ? "" : "s"}`)); const list = el("ul", "reason-list"); evidence.issues.forEach((issue) => list.append(el("li", "", issue))); notice.append(list); holds.append(notice); }
  const obligations = state.report.obligations; const reconciliation = $("obligation-results"); reconciliation.replaceChildren(); reconciliation.hidden = !obligations;
  if (obligations) {
    reconciliation.append(el("h4", "", obligations.status === "reconciled" ? "Senior claims reconciled" : "Senior claims need reconciliation"));
    const grid = el("div", "obligation-grid");
    for (const [label, value] of [["Declared debt & claims", obligations.declared_bridge_total], ["Itemized obligations", obligations.reconciled_bridge_total], ["Unreconciled amount", obligations.unreconciled_bridge_total]]) { const item = el("div"); item.append(el("span", "small-label", label), el("strong", "", money(value))); grid.append(item); }
    reconciliation.append(grid, el("p", "field-help", "The obligation schedule is checked against deductions from operating-asset value to equity. A cash-flow cost must not be deducted a second time here."));
  }
  const sources = $("source-results"); sources.replaceChildren();
  for (const source of evidence.sources || []) {
    const row = el("li"); const main = el("div"); const url = safeURL(source.url);
    if (url) { const link = el("a", "", source.title || source.id); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; main.append(link); }
    else main.append(el("strong", "", source.title || source.id));
    main.append(el("p", "", `${source.id} · ${human(source.kind)} · ${source.verified ? "Marked reviewed by user" : "Needs review"}`));
    if (source.notes) main.append(el("p", "", source.notes));
    row.append(main, el("span", "source-date", dateLabel(source.observed_on))); sources.append(row);
  }
  if (!sources.children.length) sources.append(el("li", "", "No sources were supplied."));
  const notes = $("model-notes"); notes.replaceChildren();
  if (state.report.explanation) notes.append(el("p", "", state.report.explanation));
  const warnings = evidence.warnings || state.report.baseline.warnings || [];
  const list = el("ul"); warnings.forEach((warning) => list.append(el("li", "", warning))); notes.append(list);
  notes.append(el("p", "", evidence.verification_scope || "Source review records are user-supplied assertions. Linked material is not independently verified by this calculation."));
}
async function refreshHistory({ quiet = false } = {}) {
  const epoch = state.sessionEpoch;
  try {
    const data = await request("/api/valuation/runs"); if (epoch !== state.sessionEpoch) return;
    setSession(true, data.actor || null);
    renderHistory(data.runs || []); if (!quiet) say("Saved valuations refreshed.");
  } catch (error) {
    if (epoch !== state.sessionEpoch) return;
    if (error.status === 401) { setSession(false); setText("history-empty", "Sign in to see saved valuations."); $("history-empty").hidden = false; $("history-list").replaceChildren(); updateControls(); }
    else if (!quiet) say(error.message);
  }
}
function renderHistory(runs) {
  const list = $("history-list"); list.replaceChildren();
  $("history-empty").hidden = runs.length > 0;
  setText("history-empty", runs.length ? "" : "No saved valuations yet. Calculate a case and save it to start a record.");
  for (const run of runs) {
    const button = el("button", "history-item"); button.type = "button";
    const main = el("span"); main.append(el("strong", "", run.asset_id || run.deal_id || run.run_id), el("small", "", `${dateLabel(run.as_of || run.created_at)} · ${MODEL_LABELS[run.model_type] || human(run.model_type || "Saved valuation")}`));
    const value = run.adjusted_value ?? run.decision?.adjusted_value ?? run.summary?.adjusted_value;
    const right = el("span", "history-value", finite(value) ? money(value) : "Open ↗");
    if (run.status) right.append(el("small", "", human(run.status)));
    button.append(main, right); button.addEventListener("click", () => openRun(run.run_id || run.id)); list.append(button);
  }
}
async function openRun(id) {
  if (!id) return;
  const revision = state.revision, epoch = state.sessionEpoch, sequence = ++state.runSequence;
  try {
    const data = await request(`/api/valuation/runs/${encodeURIComponent(id)}`);
    if (revision !== state.revision || epoch !== state.sessionEpoch || sequence !== state.runSequence) { say("Saved record was not loaded because the workspace changed while it was opening."); return; }
    const run = data.run || data; const report = run.report; const packet = run.request || run.packet || report?.request;
    if (!report?.decision || !packet?.assumptions) throw new Error("This saved valuation does not contain a complete input packet and report.");
    const example = state.examples.find((item) => item.request?.asset_id === packet.asset_id && item.request?.model_type === packet.model_type);
    const assetType = example ? inferAssetType(example) : packet.model_type === "property_dcf" ? "property" : packet.assumptions.units === 1 ? "operating-business" : "public-equity";
    loadPacket(packet, { clean: true, runId: run.run_id || id, assetType }); state.report = report; state.evaluatedPacket = clone(packet); state.dirty = false;
    renderReport(); setText("save-status", `Saved valuation ${run.run_id || id}. Editing creates a new calculation; this record stays unchanged.`);
    say("Saved valuation loaded with its original inputs."); $("report").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { if (revision !== state.revision || epoch !== state.sessionEpoch || sequence !== state.runSequence) return; say(error.message); if (error.status === 401) { setSession(false); openSignIn(); } }
}
async function saveValuation() {
  if (!state.report || state.dirty || state.saveBusy || state.savedRun || state.advancedDirty) return;
  state.saveBusy = true; updateControls(); const revision = state.revision;
  const body = state.saveBody || { request_id: crypto.randomUUID(), packet: clone(state.evaluatedPacket) };
  state.saveBody = body;
  try {
    const data = await request("/api/valuation/runs", body);
    if (revision === state.revision) {
      state.savedRun = data.run_id; state.saveBody = null;
      if (data.report) { state.report = data.report; renderReport(); }
      setText("save-status", `Saved as ${data.run_id}. This record preserves the inputs and valuation together.`);
    }
    say("Valuation saved."); await refreshHistory({ quiet: true });
  } catch (error) {
    if (revision !== state.revision) return;
    if (error.status && error.status < 500) state.saveBody = null;
    setText("save-status", `${error.message}${state.saveBody ? " Retry save will send the same request, preventing a duplicate record." : ""}`);
    if (error.status === 401) { setSession(false); openSignIn(); }
  } finally { state.saveBusy = false; updateControls(); }
}
function exportPacket() {
  if (!state.report || state.dirty || state.advancedDirty) return;
  const content = { export_schema_version: "1.0", run_id: state.savedRun || null, packet_digest: state.report.packet_digest, request: clone(state.evaluatedPacket), report: clone(state.report) };
  const blob = new Blob([JSON.stringify(content, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob); const anchor = el("a"); anchor.href = url;
  anchor.download = `black-river-valuation-${String(state.report.asset_id || "case").replace(/[^a-zA-Z0-9._-]/g, "-")}-${state.report.as_of}.json`;
  document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); say("Valuation packet exported with its inputs and report.");
}
$("valuation-form").addEventListener("submit", (event) => { event.preventDefault(); evaluate(); });
$("valuation-form").addEventListener("invalid", (event) => { let ancestor = event.target.parentElement; while (ancestor && ancestor !== $("valuation-form")) { if (ancestor.tagName === "DETAILS") ancestor.open = true; ancestor = ancestor.parentElement; } }, true);
$("asset-type").addEventListener("change", () => {
  state.assetType = $("asset-type").value; const examples = renderExamples();
  if (examples.length) loadExample(examples[0].id);
  else { say("No example is available for this model yet."); }
});
$("example-select").addEventListener("change", () => loadExample($("example-select").value));
$("use-annual-paths").addEventListener("change", () => {
  if (!state.packet) return;
  if ($("use-annual-paths").checked) Object.assign(state.packet.assumptions, clone(state.annualPaths));
  else { for (const key of PATH_KEYS) if (key in state.packet.assumptions) { state.annualPaths[key] = clone(state.packet.assumptions[key]); delete state.packet.assumptions[key]; } }
  changed(); renderAssumptions(); say($("use-annual-paths").checked ? "Explicit annual paths restored. Review the scalar and terminal assumptions." : "Annual paths removed from this calculation. Scalar assumptions now drive the forecast.");
});
$("add-scenario").addEventListener("click", () => {
  if (!state.packet || state.packet.scenarios.length >= 12) return;
  const id = `scenario-${crypto.randomUUID().slice(0, 8)}`;
  state.packet.scenarios.push({ id, label: "New scenario", probability: 0, shock: {}, source_ids: [] }); changed(); renderScenarios(); updateControls();
});
$("add-source").addEventListener("click", () => {
  if (!state.packet || state.packet.sources.length >= 30) return;
  state.packet.sources.push({ id: `source-${crypto.randomUUID().slice(0, 8)}`, title: "", url: "", observed_on: null, verified: false, kind: "assumptions", notes: "" }); changed(); renderSources(); updateControls();
});
$("advanced-packet").addEventListener("input", () => { state.advancedDirty = true; state.dirty = true; state.revision += 1; setText("advanced-status", "JSON edits are unapplied. Apply them, or discard them to return to the form inputs."); updateControls(); });
$("apply-packet").addEventListener("click", () => {
  try {
    const packet = JSON.parse($("advanced-packet").value);
    assertPacketStructure(packet);
    if (packet.currency && packet.currency !== "USD") throw new Error("This workspace displays USD. Convert and document inputs in USD before applying the packet.");
    loadPacket(packet); setText("advanced-status", "JSON edits applied to the form. Recalculate to validate and update results."); say("Packet edits applied. The server will validate all financial assumptions.");
  } catch (error) { setText("advanced-status", `Cannot apply: ${error.message}`); say("Check the advanced packet JSON."); }
});
$("reset-packet").addEventListener("click", () => { state.advancedDirty = false; syncAdvanced(); setText("advanced-status", "JSON edits discarded. The form inputs are shown below."); updateControls(); });
$("session-button").addEventListener("click", async () => {
  if (!state.authenticated) { openSignIn(); return; }
  state.sessionEpoch += 1; state.revision += 1;
  try {
    await request("/api/logout", {}); setSession(false); $("sign-in-panel").hidden = true;
    state.report = null; state.evaluatedPacket = null; state.savedRun = null; state.saveBody = null; state.dirty = true;
    $("report").hidden = true; $("empty-state").hidden = false; $("history-list").replaceChildren(); $("history-empty").hidden = false; setText("history-empty", "Sign in to see saved valuations."); updateControls(); say("Signed out. Your unsaved inputs remain in this tab.");
  } catch (error) { say(error.message); }
});
$("close-sign-in").addEventListener("click", () => { $("sign-in-panel").hidden = true; $("session-button").focus(); });
$("sign-in-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setText("sign-in-error", ""); const button = event.currentTarget.querySelector('button[type="submit"]'); button.disabled = true;
  const epoch = ++state.sessionEpoch, actor = $("actor").value; state.revision += 1;
  try { await request("/api/session", { actor, token: $("access-key").value }); if (epoch !== state.sessionEpoch) return; $("access-key").value = ""; setSession(true, actor); await refreshHistory({ quiet: true }); say("Signed in. Your inputs are ready to calculate."); $("evaluate-button").focus(); }
  catch (error) { setText("sign-in-error", error.message); }
  finally { button.disabled = false; }
});
$("save-button").addEventListener("click", saveValuation);
$("export-button").addEventListener("click", exportPacket);
$("refresh-history").addEventListener("click", () => refreshHistory());
async function start() {
  updateControls();
  const epoch = state.sessionEpoch;
  const results = await Promise.allSettled([request("/api/valuation/examples"), request("/api/valuation/runs")]);
  if (results[0].status === "fulfilled") {
    state.examples = results[0].value.examples || [];
    if (state.examples.length) { state.assetType = inferAssetType(state.examples[0]); $("asset-type").value = state.assetType; renderExamples(); loadExample(state.examples[0].id); }
    else { setText("connection-notice", "No starting examples are available. The valuation service may need its example files."); $("connection-notice").hidden = false; }
  } else { setText("connection-notice", results[0].reason.message); $("connection-notice").hidden = false; $("example-select").replaceChildren(el("option", "", "Examples unavailable")); }
  if (epoch === state.sessionEpoch) {
    if (results[1].status === "fulfilled") { setSession(true, results[1].value.actor); renderHistory(results[1].value.runs || []); }
    else { state.authenticated = false; setText("history-empty", results[1].reason.status === 401 ? "Sign in to see saved valuations." : "Saved valuations are currently unavailable."); }
  }
  updateControls();
}
start();
