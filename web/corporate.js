/* All financial calculations and source selection belong to the local service. */
const $ = (id) => document.getElementById(id);
const state = { actor: null, draft: null, bundle: null, revision: 0, dirty: true, busy: false, request: 0 };
const decimal = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const percentage = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });
const finite = (value) => typeof value === "number" && Number.isFinite(value);
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const millions = (value) => finite(value) ? decimal.format(value / 1e6) : "n.a.";
const money = (value) => finite(value) ? currency.format(value) : "Not available";
const pct = (value) => finite(value) ? percentage.format(value) : "Not available";
const multiple = (value) => finite(value) ? `${decimal.format(value)}×` : "Not available";
const title = (value) => String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const text = (id, value) => { $(id).textContent = String(value ?? ""); };
function node(tag, value, className) {
  const element = document.createElement(tag);
  if (value !== undefined) element.textContent = String(value);
  if (className) element.className = className;
  return element;
}
function errorMessage(error) { return error instanceof Error ? error.message : "The calculation could not be completed."; }
function showError(error) {
  text("service-error", error ? errorMessage(error) : "");
  $("service-error").hidden = !error;
}
function controls() {
  const available = Boolean(state.actor && state.draft);
  $("calculate-case").disabled = !available || state.busy;
  $("selected-case").disabled = !available || state.busy;
  $("reload-case").disabled = !state.actor || state.busy;
  $("case-json").disabled = !available;
  $("download-json").disabled = !state.actor || !state.bundle || state.dirty || state.busy;
  $("session-button").disabled = state.busy;
  $("stale-notice").hidden = !state.bundle || !state.dirty;
  text("session-state", state.actor ? `Signed in as ${state.actor}` : "Not signed in");
  text("session-button", state.actor ? "Sign out" : "Sign in");
  text("calculate-case", state.busy ? "Working…" : "Calculate case");
}
function markChanged() {
  state.revision += 1;
  state.dirty = true;
  text("editor-note", "Edits are unapplied. Calculate to validate the complete packet.");
  controls();
}
function parseDraft() {
  let draft;
  try { draft = JSON.parse($("case-json").value); }
  catch { throw new Error("Case JSON is not valid. Correct the JSON before calculating."); }
  if (!object(draft) || !object(draft.cases) || typeof draft.selected_case !== "string"
      || !Object.prototype.hasOwnProperty.call(draft.cases, draft.selected_case)
      || !Array.isArray(draft.cases[draft.selected_case])) {
    throw new Error("The case must contain a cases object and a selected_case naming an annual driver array.");
  }
  if (new TextEncoder().encode(JSON.stringify(draft)).length > 65536) {
    throw new Error("The case exceeds the 65,536-byte request limit.");
  }
  return draft;
}
function populateSelector(draft) {
  const select = $("selected-case");
  select.replaceChildren();
  for (const key of Object.keys(draft.cases)) {
    const option = node("option", title(key));
    option.value = key;
    select.append(option);
  }
  select.value = draft.selected_case;
}
async function api(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      credentials: "same-origin", cache: "no-store", signal: controller.signal,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(typeof result.error === "string" ? result.error : `Request failed (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return result;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The local service did not respond within 30 seconds. Retry the calculation.");
    throw error;
  } finally { clearTimeout(timer); }
}
function setCase(draft, facts) {
  if (!object(draft) || !object(draft.cases) || !object(facts)) throw new Error("The service returned an incomplete case.");
  state.draft = draft;
  state.bundle = null;
  state.dirty = true;
  state.revision += 1;
  $("case-json").value = JSON.stringify(draft, null, 2);
  populateSelector(draft);
  text("case-identity", `${facts.entity?.name || "Corporate case"} (${facts.entity?.ticker || ""})`);
  text("case-dates", `Historical cutoff ${draft.analysis_cutoff}. Model opening ${draft.model_start_date}. Reported fiscal year ends ${facts.entity?.fiscal_year_end || "as shown in source records"}.`);
  text("editor-note", "Amounts in this packet are actual USD. Calculate to validate the case.");
  text("case-progress", "Case loaded. Review the assumptions, then calculate.");
  $("corporate-report").hidden = true;
  $("empty-state").hidden = false;
  controls();
}
async function loadOriginal() {
  const request = ++state.request;
  state.busy = true;
  controls(); showError(null);
  try {
    const result = await api("/api/corporate/case");
    if (request !== state.request) return;
    state.actor = result.actor;
    setCase(result.case, result.facts);
    $("sign-in-panel").hidden = true;
  } catch (error) {
    if (request !== state.request) return;
    if (error.status === 401) {
      state.actor = null;
      $("sign-in-panel").hidden = false;
      text("case-progress", "Sign in to load the corporate case.");
    } else showError(error);
  } finally {
    if (request === state.request) { state.busy = false; controls(); }
  }
}

function table(id, headings, data, rowLabels = false) {
  const target = $(id), head = target.querySelector("thead"), body = target.querySelector("tbody");
  head.replaceChildren(); body.replaceChildren();
  const header = node("tr");
  for (const label of headings) { const cell = node("th", label); cell.scope = "col"; header.append(cell); }
  head.append(header);
  for (const record of data) {
    const line = node("tr");
    if (record.total) line.className = "corporate-total";
    for (const [index, value] of record.cells.entries()) {
      const cell = node(rowLabels && index === 0 ? "th" : "td", value);
      if (rowLabels && index === 0) cell.scope = "row";
      line.append(cell);
    }
    body.append(line);
  }
}
function statement(id, forecast, lines) {
  table(id, ["Measure", ...forecast.map((row) => row.period_end)], lines.map(([label, key, format = millions, total = false]) => ({
    total, cells: [label, ...forecast.map((row) => format(row[key]))],
  })), true);
}
function summaries(id, items) {
  const container = $(id); container.replaceChildren();
  for (const [label, value] of items) {
    const item = node("div", undefined, "corporate-summary-item");
    item.append(node("span", label, "small-label"), node("strong", value));
    container.append(item);
  }
}
function list(id, values) {
  const target = $(id); target.replaceChildren();
  for (const value of values) target.append(node("li", value));
}
function safeSourceLink(source) {
  try {
    const url = new URL(source.url);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) throw new Error("Unsupported source URL");
    const link = node("a", source.title || source.id || url.hostname);
    link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer";
    return link;
  } catch { return node("span", source.title || source.id || "Source URL unavailable"); }
}
function renderSources(report, facts) {
  const target = $("sources-list"); target.replaceChildren();
  for (const source of report.sources || []) {
    const item = node("li");
    item.append(safeSourceLink(source));
    const metadata = [];
    if (source.published_on) metadata.push(`Published ${source.published_on}`);
    if (source.period_end) metadata.push(`Period ended ${source.period_end}`);
    if (source.market_event_date) metadata.push(`Market date ${source.market_event_date}`);
    if (source.retrieved_on) metadata.push(`Retrieved ${source.retrieved_on}`);
    if (metadata.length) item.append(node("p", metadata.join(". ") + "."));
    if (source.vintage_status) item.append(node("p", source.vintage_status));
    target.append(item);
  }
  text("source-review", facts.review_status || "Source facts require independent review.");
  text("input-digest", report.input_digest);
}
function renderHistorical(facts, report) {
  const periods = Object.keys(facts.periods || {}).sort().map((key) => facts.periods[key]);
  const rows = [
    ["Revenue", "income_statement", "revenue"], ["Operating income", "income_statement", "operating_income"],
    ["Net income", "income_statement", "net_income"], ["Cash", "balance_sheet", "cash"],
    ["Total assets", "balance_sheet", "total_assets"], ["Total liabilities", "balance_sheet", "total_liabilities"],
    ["Shareholders' equity", "balance_sheet", "total_equity"],
    ["Operating cash flow", "cash_flow", "operating_cash_flow"],
    ["Investing cash flow", "cash_flow", "investing_cash_flow"],
    ["Financing cash flow", "cash_flow", "financing_cash_flow"],
    ["FX effect on cash", "cash_flow", "fx_cash_effect"], ["Ending cash", "cash_flow", "ending_cash"],
  ];
  table("historical-table", ["Reported measure", ...periods.map((period) => period.period_end)], rows.map(([label, section, key]) => ({
    cells: [label, ...periods.map((period) => finite(period[section]?.[key]) ? millions(period[section][key] * 1000) : "n.a.")],
  })), true);
  const checks = report.historical_checks;
  const failed = (checks?.items || []).filter((check) => !check.passed);
  text("historical-checks", checks?.all_reconciled
    ? `${checks.items.length} reported source-control reconciliations passed. Arithmetic agreement does not establish independent source verification.`
    : `Reported source reconciliation has ${failed.length} unresolved checks.`);
}
function renderFinance(acquisition) {
  const funding = acquisition.sources_uses, schedule = acquisition.schedule, exit = acquisition.exit, returns = acquisition.returns;
  const feasible = acquisition.feasibility?.status === "modeled_feasible";
  text("financing-state", feasible ? "The modeled financing conditions are met under the stated assumptions. Funding commitments and transaction terms remain unverified." : "The modeled financing or exit conditions fail. Investor returns are withheld; review the shortfalls below.");
  $("financing-state").className = feasible ? "section-note" : "notice notice-error";
  const uses = [
    ["Seller equity purchase", "seller_equity_purchase"], ["Existing debt payoff", "existing_debt_payoff"],
    ["Other claims payoff", "existing_other_claims_payoff"], ["Transaction fees", "transaction_fees"],
    ["Financing fees", "financing_fees"], ["Operating cash top-up", "cash_top_up"],
  ];
  const sources = [["Sponsor equity", "sponsor_equity"], ["New term debt", "new_term_debt"], ["Acquired cash used", "acquired_cash_used"]];
  table("funding-table", ["Funding item", "Uses", "Sources"], [
    ...uses.map(([label, key]) => ({ cells: [label, millions(funding[key]), "—"] })),
    ...sources.map(([label, key]) => ({ cells: [label, "—", millions(funding[key])] })),
    { total: true, cells: ["Total", millions(funding.total_uses), millions(funding.total_sources)] },
  ], true);
  statement("debt-table", schedule, [
    ["EBITDA", "ebitda"], ["Cash interest", "interest"], ["Cash taxes", "cash_taxes"],
    ["Cash available for debt service", "cash_flow_available_for_debt_service"],
    ["Scheduled principal", "scheduled_principal_due"],
    ["Maturity principal due before exit", "maturity_principal_due_before_exit"],
    ["Mandatory principal due", "mandatory_principal_due"], ["Mandatory principal paid", "mandatory_principal_paid"],
    ["Unpaid mandatory principal", "mandatory_principal_shortfall"], ["Revolver draw", "revolver_draw"],
    ["Revolver repayment", "revolver_repayment"], ["Term debt cash sweep", "term_cash_sweep"],
    ["Closing term debt before exit", "closing_term_debt", millions, true], ["Closing revolver before exit", "closing_revolver"],
    ["Maturity balloon settled at exit", "maturity_balloon_due_at_exit"],
    ["Closing cash", "closing_cash", millions, true], ["Liquidity shortfall", "liquidity_shortfall"],
    ["Net leverage", "net_leverage", multiple], ["Interest coverage", "interest_coverage", multiple],
    ["Debt-service coverage", "debt_service_coverage", multiple],
  ]);
  list("financing-issues", (acquisition.feasibility?.issues || []).map((issue) => {
    const parts = [`Year ${issue.year}: ${title(issue.kind)}`];
    if (finite(issue.amount)) parts.push(money(issue.amount));
    if (Object.prototype.hasOwnProperty.call(issue, "observed")) parts.push(`Observed ${multiple(issue.observed)}`);
    if (finite(issue.limit)) parts.push(`Limit ${multiple(issue.limit)}`);
    return parts.join(". ");
  }));
  summaries("exit-summary", [
    ["Initial sponsor equity, USD m", millions(funding.sponsor_equity)],
    ["Exit enterprise value, USD m", millions(exit.enterprise_value)],
    ["Term debt payoff at exit, USD m", millions(exit.term_debt_payoff)],
    ["Of which maturity settlement, USD m", millions(exit.term_maturity_settlement)],
    ["Investor proceeds, USD m", millions(returns.proceeds)],
    ["Annual IRR", pct(returns.annual_irr)], ["Equity multiple", multiple(returns.moic)],
    ["Sources less uses, USD m", millions(funding.sources_less_uses)],
  ]);
  const flows = returns.sponsor_cash_flows, dates = returns.cash_flow_dates;
  if (Array.isArray(flows) && Array.isArray(dates)) {
    table("investor-table", ["Cash-flow date", ...dates], [{ cells: ["Investor contribution / receipt", ...flows.map(millions)] }], true);
  } else {
    table("investor-table", ["Investor cash flows", "Result"], [{ cells: ["Financing / exit conditions", "Returns unavailable"] }], true);
  }
  text("returns-note", `${returns.timing} ${exit.maturity_coincides_with_exit ? "Final-year maturity is settled once within the exit term-debt payoff. The maturity-settlement figure is a subset of that payoff, not an additional deduction." : "Debt maturing before exit is due in the annual funding schedule. Any remaining debt is deducted once at exit."}`);
}
function render(bundle) {
  const report = bundle.report, projection = report.projection, forecast = projection.forecast;
  const valuation = report.valuation, comparables = report.comparables, acquisition = report.acquisition;
  text("report-title", `${report.entity.name} · ${title(report.selected_case)}`);
  text("report-meta", `${report.entity.ticker} · analysis cutoff ${report.analysis_cutoff} · ${report.model_version}`);
  text("report-status", report.status === "research_requires_review" ? "Research requires review" : `Research status: ${report.status || "unavailable"}`);
  text("date-convention", `Reported balance sheet: ${report.source_balance_date}. Hypothetical model opening: ${report.model_start_date}. Reported balances are carried forward without an interim operating bridge. Forecast columns are model-year anniversaries, not the issuer's reported fiscal years.`);
  text("dcf-price", money(valuation.value_per_share));
  text("dcf-rate", `WACC ${pct(valuation.wacc)}`);
  text("reference-price", money(report.market_quote.close));
  text("reference-date", `Historical close ${report.market_quote.date}; no live quote`);
  text("acquisition-irr", pct(acquisition.returns.annual_irr));
  text("acquisition-multiple", finite(acquisition.returns.moic) ? `${multiple(acquisition.returns.moic)} equity multiple` : "Return calculation unavailable; see financing conditions");
  const critical = [];
  if (acquisition.feasibility?.status !== "modeled_feasible") critical.push("The acquisition financing or exit conditions fail. Investor returns are withheld. Review the financing exceptions below.");
  if (!projection.checks.all_minimum_cash_requirements_met) critical.push("The standalone forecast falls below its minimum cash requirement. Acquisition financing is evaluated separately.");
  text("financing-alert", critical.join(" "));
  $("financing-alert").hidden = critical.length === 0;
  const notes = Array.isArray(report.assumption_notes) ? report.assumption_notes : Object.values(report.assumption_notes || {});
  list("review-items", report.review_items || []);
  list("assumption-notes", notes);
  list("model-conventions", [...(projection.warnings || []), ...(acquisition.conventions || [])]);
  statement("income-table", forecast, [
    ["Revenue", "revenue", millions, true], ["COGS before D&A", "cogs_before_da"],
    ["Gross profit before D&A", "gross_profit_before_da"], ["Operating expense before D&A", "operating_expenses_before_da"],
    ["EBITDA", "ebitda", millions, true], ["Depreciation", "depreciation"], ["Amortization", "amortization"],
    ["EBIT", "ebit", millions, true], ["Interest expense", "interest_expense"],
    ["Pretax income", "pretax_income"], ["Tax expense", "tax_expense"], ["Net income", "net_income", millions, true],
    ["Weighted-average shares, millions", "weighted_average_shares", millions], ["EPS, USD", "eps", money],
  ]);
  statement("balance-table", forecast, [
    ["Cash", "cash"], ["Accounts receivable", "accounts_receivable"], ["Inventory", "inventory"],
    ["Other operating current assets", "operating_other_current_assets"], ["Other current assets", "other_current_assets"],
    ["Net PPE", "net_ppe"], ["Net finite intangibles", "net_intangibles"], ["Other noncurrent assets", "other_noncurrent_assets"],
    ["Total assets", "total_assets", millions, true], ["Accounts payable", "accounts_payable"],
    ["Operating accruals", "operating_accruals"], ["Other current liabilities", "other_current_liabilities"],
    ["Aggregate funded debt", "debt"], ["Other noncurrent liabilities", "other_noncurrent_liabilities"],
    ["Total liabilities", "total_liabilities", millions, true], ["Retained earnings", "retained_earnings"],
    ["Other shareholders' equity", "other_equity"], ["Total equity", "equity", millions, true],
    ["Liabilities and equity", "total_liabilities_and_equity", millions, true],
  ]);
  statement("cash-table", forecast, [
    ["Net income", "net_income"], ["Depreciation", "depreciation"], ["Amortization", "amortization"],
    ["Stock compensation addback", "stock_compensation"], ["Increase in operating NWC", "delta_nwc"],
    ["Cash from operations", "cash_from_operations", millions, true], ["PPE investment", "ppe_capex"],
    ["Intangible investment", "intangible_capex"], ["Cash from investing", "cash_from_investing", millions, true],
    ["Debt issued", "debt_issued"], ["Debt repaid", "debt_repaid"], ["Dividends", "dividends"],
    ["Cash equity issued", "equity_issued"], ["Share repurchase cost", "repurchases"],
    ["Cash from financing", "cash_from_financing", millions, true], ["Change in cash", "change_in_cash", millions, true],
    ["Opening cash", "opening_cash"], ["Closing cash", "cash", millions, true],
    ["Minimum cash", "minimum_cash"], ["Unfunded cash shortfall", "funding_shortfall"],
    ["Economic FCFF; SBC retained as expense", "fcff", millions, true],
  ]);
  text("statement-checks", `Accounting identities: ${projection.checks.all_reconciled ? "reconciled" : "unresolved"}. Minimum cash: ${projection.checks.all_minimum_cash_requirements_met ? "met under the assumptions" : "not met"}. These checks do not validate the forecast assumptions.`);
  summaries("valuation-bridge", [
    ["Operating value, USD m", millions(valuation.enterprise_value)], ["Cash added, USD m", millions(valuation.cash)],
    ["Debt deducted, USD m", millions(valuation.debt)], ["Other claims, USD m", millions(valuation.other_claims)],
    ["Equity value, USD m", millions(valuation.equity_value)], ["Terminal value share", pct(valuation.terminal_share_of_enterprise_value)],
  ]);
  table("comparables-table", ["Company", "Close", "Quote date", "Financial period", "EV, USD m", "Operating EBIT, USD m", "EV / EBIT"], comparables.peers.map((peer) => ({
    cells: [peer.ticker, money(peer.price), peer.price_date, peer.financial_period_end, millions(peer.enterprise_value), millions(peer.operating_ebit), multiple(peer.ev_ebit)],
  })));
  text("comparables-note", comparables.basis);
  summaries("comparable-range", Object.entries(comparables.implied_values).map(([label, result]) => [
    `${title(label)} comparable value / share`, money(result.value_per_share),
  ]));
  renderFinance(acquisition);
  renderHistorical(bundle.facts, report);
  renderSources(report, bundle.facts);
  text("calculation-status", "Calculated for review. No approval, saved run or transaction was created.");
  $("empty-state").hidden = true;
  $("corporate-report").hidden = false;
}

$("case-json").addEventListener("input", markChanged);
$("selected-case").addEventListener("change", () => {
  const chosen = $("selected-case").value;
  try {
    const draft = parseDraft();
    if (!Object.prototype.hasOwnProperty.call(draft.cases, chosen)) throw new Error("Apply a valid case set before selecting another case.");
    draft.selected_case = chosen;
    state.draft = draft;
    $("case-json").value = JSON.stringify(draft, null, 2);
    markChanged(); showError(null);
  } catch (error) { $("selected-case").value = state.draft?.selected_case || ""; showError(error); }
});
$("case-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || !state.actor) return;
  let draft;
  try { draft = parseDraft(); } catch (error) { showError(error); return; }
  state.draft = draft; populateSelector(draft);
  const revision = state.revision, request = ++state.request;
  state.busy = true; state.dirty = true;
  controls(); showError(null); text("case-progress", "Calculating linked statements, valuation and acquisition finance…");
  try {
    const bundle = await api("/api/corporate/evaluate", draft);
    if (request !== state.request) return;
    if (revision !== state.revision) {
      text("case-progress", "Inputs changed during calculation. Calculate again to use the updated case.");
      return;
    }
    if (!object(bundle.case) || !object(bundle.facts) || !object(bundle.report)) throw new Error("The service returned an incomplete research packet.");
    render(bundle);
    state.bundle = bundle; state.dirty = false;
    text("editor-note", "This assumption packet matches the displayed calculation.");
    text("case-progress", "Calculation complete. Research requires review.");
  } catch (error) {
    if (request !== state.request) return;
    showError(error); text("case-progress", "Calculation not completed. Correct the input or service error.");
    if (error.status === 401) { state.actor = null; $("sign-in-panel").hidden = false; }
  } finally { if (request === state.request) { state.busy = false; controls(); } }
});
$("reload-case").addEventListener("click", loadOriginal);
$("sign-in-form").addEventListener("submit", async (event) => {
  event.preventDefault(); text("sign-in-error", "");
  const credentials = { actor: $("actor").value, token: $("access-key").value };
  $("access-key").value = "";
  try { await api("/api/session", credentials); await loadOriginal(); }
  catch (error) { text("sign-in-error", errorMessage(error)); }
});
$("close-sign-in").addEventListener("click", () => { $("sign-in-panel").hidden = true; });
$("session-button").addEventListener("click", async () => {
  if (!state.actor) { $("sign-in-panel").hidden = false; $("access-key").focus(); return; }
  try {
    await api("/api/logout", {});
    state.request += 1; state.actor = null; state.draft = null; state.bundle = null; state.dirty = true;
    $("case-json").value = ""; $("selected-case").replaceChildren(node("option", "No case loaded"));
    $("corporate-report").hidden = true; $("empty-state").hidden = false;
    text("case-identity", "Sign in to load the case."); text("case-dates", "");
    text("case-progress", "Signed out."); controls();
  } catch (error) { showError(error); }
});
$("download-json").addEventListener("click", () => {
  if (!state.bundle || state.dirty || state.busy || !state.actor) return;
  const blob = new Blob([JSON.stringify(state.bundle, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob), anchor = node("a");
  const slug = `${state.bundle.report.case_id}-${state.bundle.report.selected_case}`.replace(/[^a-zA-Z0-9._-]/g, "_");
  anchor.href = url; anchor.download = `black-river-${slug}.json`;
  document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
controls();
if (location.protocol === "file:") showError(new Error("Open this page through the local founder service, not directly as a file."));
else loadOriginal();
