/**
 * Build the formula-driven WD-40 corporate and acquisition research workbook.
 * Run a copy of this file from a temporary directory whose node_modules links
 * to the bundled primary runtime. See the file guide for the exact workflow.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

if (process.argv.length !== 5) throw Error("Usage: node build_corporate_workbook.mjs <bundle.json> <output-directory> <repository-directory>");
const input = path.resolve(process.argv[2]);
const outputDir = path.resolve(process.argv[3]);
const repo = path.resolve(process.argv[4]);
const bundle = JSON.parse(await fs.readFile(input, "utf8"));
const { facts, case: packet } = bundle;
const names = ["Base", "Downside", "Upside"];
const moneyScale = 1e6;
const colors = { navy: "#172C3D", blue: "#244F73", gold: "#A7824A", ink: "#17252F",
  muted: "#65717A", pale: "#F4F0E8", line: "#D4DADD", input: "#0000FF",
  link: "#008000", error: "#9C0006", errorFill: "#FCE5E5", active: "#EAF0F4" };
const fmt = {
  money: '#,##0.0;(#,##0.0);"-"', actual: '#,##0.000;(#,##0.000);"-"',
  dollars: '$0.00;($0.00);"-"', percent: '0.0%;(0.0%);"-"',
  ratio: '0.00"x";(0.00"x");"-"', shares: '0.000; (0.000);"-"',
  check: '0.00;(0.00);0.00', count: '0', date: "mm/dd/yy",
};
const wb = Workbook.create();
const sheets = Object.fromEntries(["Summary", "Assumptions", "Statements", "Valuation", "Acquisition", "Comps", "Actuals", "Review"].map(n => [n, wb.worksheets.add(n)]));
const cols = ["F", "G", "H", "I", "J"];
const q = (s, a) => "'" + s + "'!" + a;
const cell = (s, a) => sheets[s].getRange(a);
const value = (s, a, v, format) => {
  cell(s, a).values = [[v]];
  if (format) cell(s, a).setNumberFormat(format);
};
const formula = (s, a, f, format) => {
  cell(s, a).formulas = [[f]];
  cell(s, a).format.font.color = s === "Summary" ? colors.ink : f.includes("!") ? colors.link : "#000000";
  if (format) cell(s, a).setNumberFormat(format);
};
function section(s, row, title, end = "J") {
  value(s, "C" + row, title);
  const r = cell(s, "C" + row + ":" + end + row);
  r.format.fill = colors.navy; r.format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
  r.format.rowHeight = 23;
}
function rowLabel(s, row, label, numberFormat = fmt.money, total = false) {
  value(s, "C" + row, label);
  cell(s, "F" + row + ":J" + row).setNumberFormat(numberFormat);
  if (total) {
    cell(s, "C" + row + ":J" + row).format.font.bold = true;
    cell(s, "C" + row + ":J" + row).format.borders = { top: { style: "thin", color: colors.line } };
  }
  if (numberFormat === fmt.percent || numberFormat === fmt.ratio) cell(s, "C" + row + ":J" + row).format.font.italic = true;
}
function setup(s, title, lastRow = 150) {
  const sh = sheets[s];
  sh.showGridLines = false;
  sh.getRange("A1:N" + lastRow).format.font = { name: "Arial", size: 10, color: colors.ink };
  sh.getRange("A1:N" + lastRow).format.rowHeight = 19;
  sh.getRange("A1:N" + lastRow).format.verticalAlignment = "center";
  sh.getRange("A1:B" + lastRow).format.columnWidth = 2.2;
  sh.getRange("C1:C" + lastRow).format.columnWidth = 45;
  sh.getRange("D1:D" + lastRow).format.columnWidth = 2.5;
  sh.getRange("E1:E" + lastRow).format.columnWidth = 13;
  sh.getRange("F1:J" + lastRow).format.columnWidth = 14.5;
  sh.getRange("K1:K" + lastRow).format.columnWidth = 3;
  sh.getRange("L1:N" + lastRow).format.columnWidth = 14;
  sh.getRange("F1:J" + lastRow).format.horizontalAlignment = "right";
  value(s, "C2", title);
  cell(s, "C2:J2").format.font = { name: "Arial", size: 14, bold: true, color: colors.navy };
  cell(s, "C2:J2").format.rowHeight = 27;
  cell(s, "C3:J3").format.borders = { bottom: { style: "thin", color: colors.gold } };
  value(s, "C4", "Case selected:");
  if (s !== "Assumptions") formula(s, "F4", "=" + q("Assumptions", "$F$4"));
  cell(s, "F4:G4").format.borders = { preset: "outside", style: "dashed", color: colors.line };
  cell(s, "F4").format.horizontalAlignment = "center";
  cell(s, "F4").format.font.color = colors.link;
  if (s !== "Summary") {
    sh.freezePanes.freezeRows(8);
    sh.freezePanes.freezeColumns(5);
  }
}
function periodHeaders(s, row = 8) {
  cols.forEach((c, i) => formula(s, c + row, "=" + q("Assumptions", c + "$8"), fmt.date));
  cell(s, "F" + row + ":J" + row).format = { fill: colors.blue, font: { name: "Arial", size: 10, color: "#FFFFFF", bold: true }, horizontalAlignment: "center", rowHeight: 24 };
}
function note(s, row, text) {
  value(s, "C" + row, text);
  cell(s, "C" + row + ":J" + row).format.font = { name: "Arial", size: 10, italic: true, color: colors.muted };
}
function errorConditional(s, range, expression) {
  cell(s, range).conditionalFormats.addCustom(expression, { fill: colors.errorFill, font: { color: colors.error, bold: true } });
}

// Historical input records retain the source's meaning. Amounts are converted
// once from USD thousands to USD millions; exact original values remain in JSON.
setup("Actuals", "WD-40 reported financials", 250);
sheets.Actuals.tabColor = "#E8DCC7";
note("Actuals", 6, "USD millions. Shares in millions. EPS is USD per share. Source fiscal years end August 31.");
["2023", "2024", "2025"].forEach((y, i) => value("Actuals", cols[i] + "8", new Date(y + "-08-31T00:00:00Z"), fmt.date));
cell("Actuals", "F8:H8").format = { fill: colors.blue, font: { name: "Arial", size: 10, color: "#FFFFFF", bold: true }, horizontalAlignment: "center" };
const ar = {}, sup = {}, op = {}, actualSections = {};
const pretty = key => key.replaceAll("_", " ").replace(/^\w/, c => c.toUpperCase())
  .replace(/\b(ppe|nwc|nol|ebit|ebitda|roic|eps|fx|rou)\b/gi, c => c.toUpperCase());
let actualRow = 10;
const sectionNames = { income_statement: "Income statement", balance_sheet: "Balance sheet", cash_flow: "Cash-flow statement", equity_rollforward: "Equity rollforward" };
for (const [sectionKey, title] of Object.entries(sectionNames)) {
  section("Actuals", actualRow++, title);
  actualSections[sectionKey] = actualRow;
  for (const key of Object.keys(facts.periods["2025"][sectionKey])) {
    const row = actualRow++;
    ar[sectionKey + "." + key] = row;
    let nf = fmt.actual, scale = 1000, unit = "";
    if (key.endsWith("_eps")) { nf = fmt.dollars; scale = 1; unit = "USD/share"; }
    else if (key.includes("weighted_average_shares")) { nf = fmt.shares; scale = 1000; unit = "m shares"; }
    else if (sectionKey === "balance_sheet" && key.includes("shares")) { nf = fmt.shares; scale = 1e6; unit = "m shares"; }
    value("Actuals", "C" + row, pretty(key)); value("Actuals", "E" + row, unit);
    cell("Actuals", "F" + row + ":H" + row).values = [["2023", "2024", "2025"].map(y => facts.periods[y][sectionKey][key] / scale)];
    cell("Actuals", "F" + row + ":H" + row).setNumberFormat(nf);
    cell("Actuals", "F" + row + ":H" + row).format.font.color = colors.input;
  }
  actualRow += 2;
}
section("Actuals", actualRow++, "Selected note disclosures");
for (const disclosure of facts.supplemental_facts) {
  sup[disclosure.key] = actualRow;
  value("Actuals", "C" + actualRow, pretty(disclosure.key));
  cell("Actuals", "C" + actualRow).format.wrapText = true;
  cell("Actuals", "C" + actualRow + ":J" + actualRow).format.rowHeight = 30;
  cell("Actuals", "F" + actualRow + ":H" + actualRow).values = [["2023", "2024", "2025"].map(y => disclosure.values[y] == null ? null : disclosure.values[y] / 1000)];
  cell("Actuals", "F" + actualRow + ":H" + actualRow).setNumberFormat(fmt.actual);
  cell("Actuals", "F" + actualRow + ":H" + actualRow).format.font.color = colors.input;
  actualRow++;
}
actualRow += 2;
section("Actuals", actualRow++, "Model opening proxy");
const sourceBalanceDateRow = actualRow++;
value("Actuals", "C" + sourceBalanceDateRow, "Reported balance date");
value("Actuals", "F" + sourceBalanceDateRow, new Date("2025-08-31T00:00:00Z"), fmt.date);
const modelDateRow = actualRow++;
value("Actuals", "C" + modelDateRow, "Hypothetical model opening");
value("Actuals", "F" + modelDateRow, new Date(packet.model_start_date + "T00:00:00Z"), fmt.date);
const ax = (sectionKey, key, col = "H") => col + ar[sectionKey + "." + key];
const as = key => "H" + sup[key];
const openingFormulas = {
  revenue: ax("income_statement", "revenue"), cash: ax("balance_sheet", "cash"),
  accounts_receivable: ax("balance_sheet", "accounts_receivable_net"), inventory: ax("balance_sheet", "inventory"),
  operating_other_current_assets: "0", other_current_assets: ax("balance_sheet", "other_current_assets"),
  net_ppe: ax("balance_sheet", "ppe_net"), net_intangibles: ax("balance_sheet", "intangibles_net"),
  other_noncurrent_assets: ["goodwill", "right_of_use_assets", "deferred_tax_assets_net", "other_noncurrent_assets"].map(k => ax("balance_sheet", k)).join("+"),
  accounts_payable: ax("balance_sheet", "accounts_payable"),
  operating_accruals: ax("balance_sheet", "accrued_liabilities") + "+" + ax("balance_sheet", "accrued_payroll") + "-" + as("current_operating_lease_liabilities"),
  other_current_liabilities: ax("balance_sheet", "income_taxes_payable") + "+" + as("current_operating_lease_liabilities"),
  debt: ax("balance_sheet", "short_term_borrowings") + "+" + ax("balance_sheet", "long_term_borrowings"),
  other_noncurrent_liabilities: ["deferred_tax_liabilities_net", "long_term_operating_lease_liabilities", "other_long_term_liabilities"].map(k => ax("balance_sheet", k)).join("+"),
  equity: ax("balance_sheet", "total_equity"), retained_earnings: ax("balance_sheet", "retained_earnings"),
  shares: ax("balance_sheet", "shares_outstanding"), tax_loss_carryforward: "0",
};
for (const [key, expression] of Object.entries(openingFormulas)) {
  op[key] = actualRow;
  rowLabel("Actuals", actualRow, pretty(key), key === "shares" ? fmt.shares : fmt.actual);
  const sourceCells = [...expression.matchAll(/[A-Z]+\d+/g)].map(x => x[0]);
  const guarded = sourceCells.length ? "IF(AND(" + sourceCells.map(x => "ISNUMBER(" + x + ")").join(",") + ")," + expression + ",NA())" : expression;
  formula("Actuals", "F" + actualRow++, "=" + guarded);
}
const quoteRow = actualRow++;
rowLabel("Actuals", quoteRow, "Reference close on October 31, 2025", fmt.dollars);
value("Actuals", "F" + quoteRow, facts.market_quote.close, fmt.dollars);
cell("Actuals", "F" + quoteRow).format.font.color = colors.input;
const quoteDateRow = actualRow++;
value("Actuals", "C" + quoteDateRow, "Reference price date");
value("Actuals", "F" + quoteDateRow, new Date(facts.market_quote.date + "T00:00:00Z"), fmt.date);
const openingNoteRow = actualRow + 1;
note("Actuals", openingNoteRow, "August balances are carried unchanged. Interim operations, dividends and disposals require review.");
actualRow += 4;
const sourceRegistryStart = actualRow;
section("Actuals", actualRow++, "Source register and statement locators");
cell("Actuals", "L1:L250").format.columnWidth = 62;
for (const source of facts.sources) {
  value("Actuals", "C" + actualRow, source.title || source.id);
  cell("Actuals", "C" + actualRow).format.wrapText = true;
  value("Actuals", "F" + actualRow, source.published_on ? new Date(source.published_on + "T00:00:00Z") : "Not archived", source.published_on ? fmt.date : undefined);
  value("Actuals", "H" + actualRow, source.id);
  cell("Actuals", "H" + actualRow + ":J" + actualRow).format.wrapText = false;
  value("Actuals", "L" + actualRow, source.url);
  cell("Actuals", "L" + actualRow).format.wrapText = true;
  cell("Actuals", "C" + actualRow + ":L" + actualRow).format.rowHeight = 54;
  actualRow++;
}
actualRow += 2;
for (const [key, p] of Object.entries(facts.statement_provenance)) {
  value("Actuals", "C" + actualRow, pretty(key));
  value("Actuals", "F" + actualRow, p.source_id);
  value("Actuals", "L" + actualRow, p.locator);
  cell("Actuals", "L" + actualRow).format.wrapText = true;
  cell("Actuals", "C" + actualRow + ":L" + actualRow).format.rowHeight = 32;
  actualRow++;
}
for (const disclosure of facts.supplemental_facts) {
  value("Actuals", "C" + actualRow, pretty(disclosure.key));
  value("Actuals", "F" + actualRow, disclosure.source_id);
  value("Actuals", "L" + actualRow, disclosure.locator);
  cell("Actuals", "C" + actualRow).format.wrapText = true;
  cell("Actuals", "L" + actualRow).format.wrapText = true;
  cell("Actuals", "C" + actualRow + ":L" + actualRow).format.rowHeight = 42;
  actualRow++;
}
const O = key => q("Actuals", "$F$" + op[key]);

// One case selector owns every operating driver. Blank inactive cases do not
// impair a complete active case; a missing active value returns a visible NA.
setup("Assumptions", "Forecast assumptions", 220);
sheets.Assumptions.tabColor = colors.blue;
value("Assumptions", "E4", 1, fmt.count);
cell("Assumptions", "E4").format.font.color = colors.input;
cell("Assumptions", "E4").dataValidation = { rule: { type: "whole", operator: "between", formula1: 1, formula2: 3 } };
formula("Assumptions", "F4", '=CHOOSE($E$4,"Base","Downside","Upside")');
note("Assumptions", 5, "1 Base   2 Downside   3 Upside. Blue numbers are editable inputs.");
value("Assumptions", "C6", "Model years end October 31. USD millions; shares in millions; prices in USD.");
cols.forEach((c, i) => {
  value("Assumptions", c + "7", "Year " + (i + 1));
  formula("Assumptions", c + "8", "=DATE(YEAR(" + q("Actuals", "$F$" + modelDateRow) + ")+" + (i + 1) + ",10,31)", fmt.date);
});
cell("Assumptions", "F8:J8").format = { fill: colors.blue, font: { name: "Arial", size: 10, color: "#FFFFFF", bold: true }, horizontalAlignment: "center", rowHeight: 24 };
const driverLabels = {
  revenue_growth: "Revenue growth", gross_margin: "Gross margin before D&A", ebitda_margin: "EBITDA margin",
  depreciation_rate: "Depreciation / opening net PPE", amortization: "Finite-intangible amortization",
  capex_pct_revenue: "PPE capex / revenue", intangible_capex: "Intangible capex", receivable_days: "Receivable days",
  inventory_days: "Inventory days", payable_days: "Payable days",
  operating_other_current_assets_pct_revenue: "Other operating current assets / revenue",
  operating_accruals_pct_revenue: "Operating accruals / revenue", tax_rate: "Cash tax rate",
  nol_utilization_limit: "NOL use / positive taxable income", interest_rate: "Standalone debt interest rate",
  debt_issued: "Standalone debt issued", debt_repaid: "Standalone debt repaid", dividend_payout: "Dividend payout / positive net income",
  stock_compensation_pct_revenue: "Stock compensation / revenue", stock_compensation_share_price: "SBC share-issuance price",
  equity_issued: "Cash equity issued", issuance_share_price: "Cash equity issue price", shares_repurchased: "Shares repurchased",
  repurchase_share_price: "Share repurchase price", minimum_cash: "Minimum standalone cash",
};
const moneyDrivers = new Set(["amortization", "intangible_capex", "debt_issued", "debt_repaid", "equity_issued", "minimum_cash"]);
const priceDrivers = new Set(["stock_compensation_share_price", "issuance_share_price", "repurchase_share_price"]);
const dayDrivers = new Set(["receivable_days", "inventory_days", "payable_days"]);
const driverFormat = key => moneyDrivers.has(key) ? fmt.money : priceDrivers.has(key) ? fmt.dollars : dayDrivers.has(key) ? "0.0" : key === "shares_repurchased" ? fmt.shares : fmt.percent;
const scaleDriver = (key, number) => moneyDrivers.has(key) || key === "shares_repurchased" ? number / 1e6 : number;
const dr = {};
let driverRow = 10;
for (const [key, label] of Object.entries(driverLabels)) {
  dr[key] = driverRow;
  rowLabel("Assumptions", driverRow, label + " — active", driverFormat(key));
  cell("Assumptions", "C" + driverRow + ":J" + driverRow).format.fill = colors.active;
  cell("Assumptions", "C" + driverRow + ":J" + driverRow).format.font.bold = true;
  cols.forEach((c, i) => {
    const references = names.map((_, k) => c + (driverRow + k + 1));
    const chosen = "CHOOSE($E$4," + references.join(",") + ")";
    const lower = key === "revenue_growth" || key === "ebitda_margin" ? -1 : 0;
    const upper = key === "revenue_growth" ? 3 : dayDrivers.has(key) ? 3650 : moneyDrivers.has(key) || key === "shares_repurchased" ? 1e9 : priceDrivers.has(key) ? 1e15 : 1;
    const checks = ["ISNUMBER(" + chosen + ")", chosen + (key === "revenue_growth" || priceDrivers.has(key) ? ">" : ">=") + lower, chosen + "<=" + upper];
    if (key === "ebitda_margin") checks.push(chosen + "<=" + c + dr.gross_margin);
    if (key === "stock_compensation_pct_revenue") checks.push(chosen + "<=" + c + dr.gross_margin + "-" + c + dr.ebitda_margin + "+1E-12");
    formula("Assumptions", c + driverRow, "=IF(AND(" + checks.join(",") + ")," + chosen + ",NA())", driverFormat(key));
  });
  names.forEach((name, k) => {
    value("Assumptions", "C" + (driverRow + k + 1), name);
    cell("Assumptions", "C" + (driverRow + k + 1)).setNumberFormat("  @");
    cell("Assumptions", "F" + (driverRow + k + 1) + ":J" + (driverRow + k + 1)).values = [packet.cases[name].map(x => scaleDriver(key, x[key]))];
    cell("Assumptions", "F" + (driverRow + k + 1) + ":J" + (driverRow + k + 1)).setNumberFormat(driverFormat(key));
    cell("Assumptions", "F" + (driverRow + k + 1) + ":J" + (driverRow + k + 1)).format.font.color = colors.input;
  });
  driverRow += 4;
}
const d = (key, col) => q("Assumptions", col + "$" + dr[key]);
const vr = {}, tr = {};
driverRow += 2;
section("Assumptions", driverRow++, "Valuation assumptions");
for (const [key, v] of Object.entries(packet.valuation)) {
  vr[key] = driverRow;
  rowLabel("Assumptions", driverRow, pretty(key), key === "other_claims" ? fmt.money : key === "equity_beta" ? "0.00" : fmt.percent);
  value("Assumptions", "F" + driverRow, key === "other_claims" ? v / 1e6 : v);
  cell("Assumptions", "F" + driverRow).format.font.color = colors.input;
  driverRow++;
}
driverRow += 2;
section("Assumptions", driverRow++, "Acquisition terms");
const monetaryTerms = new Set(["entry_enterprise_value", "initial_term_debt", "revolver_limit", "minimum_cash"]);
for (const [key, v] of Object.entries(packet.acquisition)) {
  tr[key] = driverRow;
  const nf = monetaryTerms.has(key) ? fmt.money : key.endsWith("_multiple") || key === "max_net_leverage" || key === "min_interest_coverage" ? fmt.ratio : key === "term_maturity_year" ? fmt.count : fmt.percent;
  rowLabel("Assumptions", driverRow, pretty(key), nf);
  value("Assumptions", "F" + driverRow, monetaryTerms.has(key) ? v / 1e6 : v);
  cell("Assumptions", "F" + driverRow).format.font.color = colors.input;
  driverRow++;
}
const guardedNumber = (reference, lower, upper, positive = false, integer = false) =>
  "IF(AND(ISNUMBER(" + reference + ")," + reference + (positive ? ">" : ">=") + lower + "," + reference + "<=" + upper + (integer ? ",MOD(" + reference + ",1)=0" : "") + ")," + reference + ",NA())";
const V = key => guardedNumber(q("Assumptions", "$F$" + vr[key]), 0, key === "other_claims" ? 1e9 : key === "equity_beta" ? 5 : 1);
const T = key => guardedNumber(q("Assumptions", "$F$" + tr[key]), key === "term_maturity_year" ? 1 : 0,
  key === "term_maturity_year" ? 30 : monetaryTerms.has(key) ? 1e9 : ["exit_ebitda_multiple", "max_net_leverage", "min_interest_coverage"].includes(key) ? 100 : 1,
  ["entry_enterprise_value", "exit_ebitda_multiple", "max_net_leverage", "min_interest_coverage"].includes(key), key === "term_maturity_year");
note("Assumptions", driverRow + 2, "WACC and financing inputs are analyst assumptions. No lender commitment is implied.");
note("Assumptions", driverRow + 3, "Other claims use the rounded $1.1m uncertain-tax liability; settlement at close is assumed.");
note("Assumptions", driverRow + 4, "Forecasts retain recurring compensation expense. Tax conventions require jurisdictional review.");

// Linked statements. All forecast amount calculations are in USD millions.
setup("Statements", "Linked financial statements", 140);
note("Statements", 6, "USD millions. Model years end October 31. Forecast COGS and gross margin are before D&A.");
periodHeaders("Statements");
const sr = {
  revenue: 12, revenue_growth: 13, cogs: 14, gross_profit: 15, cash_operating_expenses_before_da: 16, stock_compensation: 17,
  operating_expenses_before_da: 18, ebitda: 19, depreciation: 20, amortization: 21, ebit: 22, interest_expense: 23,
  pretax_income: 24, tax_expense: 25, net_income: 26, eps: 27,
  cash: 32, accounts_receivable: 33, inventory: 34, operating_other_current_assets: 35, other_current_assets: 36,
  net_ppe: 37, net_intangibles: 38, other_noncurrent_assets: 39, total_assets: 40,
  accounts_payable: 42, operating_accruals: 43, other_current_liabilities: 44, debt: 45, other_noncurrent_liabilities: 46,
  total_liabilities: 47, equity: 48, total_liabilities_and_equity: 49, balance_difference: 50,
  opening_cash: 54, cf_net_income: 55, cf_da: 56, cf_sbc: 57, cf_nwc: 58, cash_from_operations: 59,
  cash_from_investing: 60, cf_debt_issue: 61, cf_debt_repayment: 62, cf_dividends: 63, cf_equity_issue: 64,
  cf_repurchases: 65, cash_from_financing: 66, change_in_cash: 67, ending_cash: 68, minimum_cash: 69, funding_shortfall: 70,
  opening_nwc: 75, nwc: 76, delta_nwc: 77,
  opening_ppe: 81, ppe_capex: 82, ppe_dep: 83, ending_ppe: 84, opening_intangibles: 86, intangible_capex: 87,
  intangible_amortization: 88, ending_intangibles: 89,
  opening_debt: 93, debt_issued: 94, debt_repaid: 95, ending_debt: 96,
  opening_nol: 100, taxable_income_before_nol: 101, nol_generated: 102, nol_used: 103, taxable_income: 104, tax_loss_carryforward: 105,
  opening_retained_earnings: 109, eq_net_income: 110, dividends: 111, retained_earnings: 112, opening_other_equity: 113,
  eq_sbc: 114, equity_issued: 115, repurchases: 116, other_equity: 117, total_equity: 118, opening_equity: 119,
  opening_shares: 121, stock_compensation_shares: 122, cash_issue_shares: 123, shares_repurchased: 124, shares: 125,
  weighted_average_shares: 126, economic_da: 129, unlevered_cash_tax_before_nol: 130, capex: 131, fcff: 132,
};
const s = (key, col) => q("Statements", col + sr[key]);
const sections = [[10, "Income statement"], [30, "Balance sheet"], [52, "Cash-flow statement"], [73, "Working capital"], [79, "Capital investment"], [91, "Debt"], [98, "Tax losses"], [107, "Equity and shares"], [128, "Economic free cash flow"]];
sections.forEach(([r, label]) => section("Statements", r, label));
const statementLabels = {
  revenue_growth: "Revenue growth", cogs: "COGS before D&A", gross_profit: "Gross profit before D&A",
  cash_operating_expenses_before_da: "Cash operating expenses", stock_compensation: "Stock compensation expense",
  operating_expenses_before_da: "Operating expenses before D&A", ebitda: "EBITDA", ebit: "EBIT", eps: "EPS (USD/share)",
  cf_net_income: "Net income", cf_da: "D&A addback", cf_sbc: "SBC addback", cf_nwc: "Change in NWC (cash effect)",
  cf_debt_issue: "Debt proceeds", cf_debt_repayment: "Debt repayment", cf_dividends: "Dividends paid",
  cf_equity_issue: "Equity proceeds", cf_repurchases: "Share repurchases", ending_cash: "Closing cash",
  ending_ppe: "Closing net PPE", ppe_dep: "PPE depreciation", ending_intangibles: "Closing finite intangibles",
  intangible_amortization: "Finite-intangible amortization", ending_debt: "Closing debt",
  eq_net_income: "Net income", eq_sbc: "SBC credited to equity", total_equity: "Closing equity",
  economic_da: "Depreciation and amortization", fcff: "FCFF (SBC remains an economic expense)",
  balance_difference: "Assets less liabilities and equity",
};
const totals = new Set(["revenue", "ebitda", "ebit", "net_income", "total_assets", "total_liabilities", "equity", "total_liabilities_and_equity",
  "cash_from_operations", "cash_from_financing", "ending_cash", "nwc", "ending_ppe", "ending_intangibles", "ending_debt", "total_equity", "shares", "fcff"]);
for (const [key, row] of Object.entries(sr)) rowLabel("Statements", row, statementLabels[key] || pretty(key),
  key === "revenue_growth" ? fmt.percent : key === "eps" ? fmt.dollars : key.includes("shares") ? fmt.shares : key === "balance_difference" ? fmt.check : fmt.money, totals.has(key));
const stm = Array.from({ length: 123 }, () => Array(5).fill(""));
cols.forEach((c, i) => {
  const prev = i ? cols[i - 1] : null;
  const r = key => c + sr[key];
  const old = key => prev ? prev + sr[key] : O(key);
  const set = (key, f) => { stm[sr[key] - 10][i] = "=" + f; };
  const activeInputs = Object.keys(dr).map(key => d(key, c));
  set("revenue", "IF(COUNT(" + activeInputs.join(",") + ")=" + activeInputs.length + "," + old("revenue") + "*(1+" + d("revenue_growth", c) + "),NA())");
  set("revenue_growth", d("revenue_growth", c));
  set("cogs", r("revenue") + "*(1-" + d("gross_margin", c) + ")");
  set("gross_profit", r("revenue") + "-" + r("cogs"));
  set("ebitda", r("revenue") + "*" + d("ebitda_margin", c));
  set("operating_expenses_before_da", r("gross_profit") + "-" + r("ebitda"));
  set("stock_compensation", r("revenue") + "*" + d("stock_compensation_pct_revenue", c));
  set("cash_operating_expenses_before_da", r("operating_expenses_before_da") + "-" + r("stock_compensation"));
  set("depreciation", r("opening_ppe") + "*" + d("depreciation_rate", c));
  set("amortization", "IF(" + d("amortization", c) + "<=" + r("opening_intangibles") + "," + d("amortization", c) + ",NA())");
  set("ebit", r("ebitda") + "-SUM(" + r("depreciation") + ":" + r("amortization") + ")");
  set("interest_expense", r("opening_debt") + "*" + d("interest_rate", c));
  set("pretax_income", r("ebit") + "-" + r("interest_expense"));
  set("tax_expense", r("taxable_income") + "*" + d("tax_rate", c));
  set("net_income", r("pretax_income") + "-" + r("tax_expense"));
  set("eps", "IF(" + r("weighted_average_shares") + ">0," + r("net_income") + "/" + r("weighted_average_shares") + ",NA())");
  set("accounts_receivable", r("revenue") + "*" + d("receivable_days", c) + "/365");
  set("inventory", r("cogs") + "*" + d("inventory_days", c) + "/365");
  set("operating_other_current_assets", r("revenue") + "*" + d("operating_other_current_assets_pct_revenue", c));
  set("accounts_payable", r("cogs") + "*" + d("payable_days", c) + "/365");
  set("operating_accruals", r("revenue") + "*" + d("operating_accruals_pct_revenue", c));
  ["other_current_assets", "other_noncurrent_assets", "other_current_liabilities", "other_noncurrent_liabilities"].forEach(k => set(k, O(k)));
  set("cash", r("ending_cash")); set("net_ppe", r("ending_ppe")); set("net_intangibles", r("ending_intangibles"));
  set("debt", r("ending_debt")); set("equity", r("total_equity"));
  set("total_assets", "SUM(" + c + "32:" + c + "39)");
  set("total_liabilities", "SUM(" + c + "42:" + c + "46)");
  set("total_liabilities_and_equity", "SUM(" + c + "47:" + c + "48)");
  set("balance_difference", r("total_assets") + "-" + r("total_liabilities_and_equity"));
  set("opening_cash", old("cash")); set("cf_net_income", r("net_income"));
  set("cf_da", "SUM(" + r("depreciation") + ":" + r("amortization") + ")");
  set("cf_sbc", r("stock_compensation")); set("cf_nwc", "-" + r("delta_nwc"));
  set("cash_from_operations", "SUM(" + c + "55:" + c + "58)");
  set("cash_from_investing", "-" + r("capex"));
  set("cf_debt_issue", r("debt_issued")); set("cf_debt_repayment", "-" + r("debt_repaid"));
  set("cf_dividends", "-" + r("dividends")); set("cf_equity_issue", r("equity_issued")); set("cf_repurchases", "-" + r("repurchases"));
  set("cash_from_financing", "SUM(" + c + "61:" + c + "65)");
  set("change_in_cash", r("cash_from_operations") + "+" + r("cash_from_investing") + "+" + r("cash_from_financing"));
  set("ending_cash", r("opening_cash") + "+" + r("change_in_cash"));
  set("minimum_cash", d("minimum_cash", c));
  set("funding_shortfall", "IF(" + r("minimum_cash") + "-" + r("ending_cash") + ">MAX(ABS(" + r("opening_cash") + "),ABS(" + r("cash_from_operations") + "),ABS(" + r("cash_from_investing") + "),ABS(" + r("cash_from_financing") + "))*1E-12,MAX(0," + r("minimum_cash") + "-" + r("ending_cash") + "),0)");
  set("opening_nwc", prev ? prev + sr.nwc : O("accounts_receivable") + "+" + O("inventory") + "+" + O("operating_other_current_assets") + "-" + O("accounts_payable") + "-" + O("operating_accruals"));
  set("nwc", r("accounts_receivable") + "+" + r("inventory") + "+" + r("operating_other_current_assets") + "-" + r("accounts_payable") + "-" + r("operating_accruals"));
  set("delta_nwc", r("nwc") + "-" + r("opening_nwc"));
  set("opening_ppe", old("net_ppe")); set("ppe_capex", r("revenue") + "*" + d("capex_pct_revenue", c)); set("ppe_dep", r("depreciation"));
  set("ending_ppe", r("opening_ppe") + "+" + r("ppe_capex") + "-" + r("ppe_dep"));
  set("opening_intangibles", old("net_intangibles")); set("intangible_capex", d("intangible_capex", c)); set("intangible_amortization", r("amortization"));
  set("ending_intangibles", r("opening_intangibles") + "+" + r("intangible_capex") + "-" + r("intangible_amortization"));
  set("opening_debt", old("debt")); set("debt_issued", d("debt_issued", c));
  set("debt_repaid", "IF(" + d("debt_repaid", c) + "<=" + r("opening_debt") + "+" + r("debt_issued") + "," + d("debt_repaid", c) + ",NA())");
  set("ending_debt", r("opening_debt") + "+" + r("debt_issued") + "-" + r("debt_repaid"));
  set("opening_nol", old("tax_loss_carryforward")); set("taxable_income_before_nol", "MAX(0," + r("pretax_income") + ")");
  set("nol_generated", "MAX(0,-" + r("pretax_income") + ")"); set("nol_used", "MIN(" + r("opening_nol") + "," + r("taxable_income_before_nol") + "*" + d("nol_utilization_limit", c) + ")");
  set("taxable_income", r("taxable_income_before_nol") + "-" + r("nol_used"));
  set("tax_loss_carryforward", r("opening_nol") + "+" + r("nol_generated") + "-" + r("nol_used"));
  set("opening_retained_earnings", old("retained_earnings")); set("eq_net_income", r("net_income"));
  set("dividends", "MAX(0," + r("net_income") + ")*" + d("dividend_payout", c));
  set("retained_earnings", r("opening_retained_earnings") + "+" + r("eq_net_income") + "-" + r("dividends"));
  set("opening_other_equity", prev ? prev + sr.other_equity : O("equity") + "-" + O("retained_earnings"));
  set("eq_sbc", r("stock_compensation")); set("equity_issued", d("equity_issued", c));
  set("repurchases", d("shares_repurchased", c) + "*" + d("repurchase_share_price", c));
  set("other_equity", r("opening_other_equity") + "+" + r("eq_sbc") + "+" + r("equity_issued") + "-" + r("repurchases"));
  set("total_equity", r("retained_earnings") + "+" + r("other_equity")); set("opening_equity", old("equity"));
  set("opening_shares", old("shares"));
  set("stock_compensation_shares", "IF(" + d("stock_compensation_share_price", c) + ">0," + r("stock_compensation") + "/" + d("stock_compensation_share_price", c) + ",NA())");
  set("cash_issue_shares", "IF(" + d("issuance_share_price", c) + ">0," + r("equity_issued") + "/" + d("issuance_share_price", c) + ",NA())");
  set("shares_repurchased", d("shares_repurchased", c));
  set("shares", r("opening_shares") + "+" + r("stock_compensation_shares") + "+" + r("cash_issue_shares") + "-" + r("shares_repurchased"));
  set("weighted_average_shares", r("opening_shares"));
  set("economic_da", r("depreciation") + "+" + r("amortization"));
  set("unlevered_cash_tax_before_nol", "MAX(0," + r("ebit") + ")*" + d("tax_rate", c));
  set("capex", r("ppe_capex") + "+" + r("intangible_capex"));
  set("fcff", r("ebit") + "-" + r("unlevered_cash_tax_before_nol") + "+" + r("economic_da") + "-" + r("capex") + "-" + r("delta_nwc"));
});
cell("Statements", "F10:J132").formulas = stm;
for (const [key, r] of Object.entries(sr)) cols.forEach((c, i) => {
  cell("Statements", c + r).format.font.color = stm[r - 10][i].includes("!") ? colors.link : "#000000";
});
errorConditional("Statements", "F50:J50", "ABS(F50)>1E-8");
errorConditional("Statements", "F70:J70", "F70>0");
note("Statements", 135, "SBC is added back to statement CFO and settled in new shares. FCFF retains its economic cost.");
note("Statements", 136, "Frozen balances have no detailed lease, deferred-tax, foreign-exchange or disposal schedules.");

// Valuation owns the WACC build and terminal reinvestment; it does not reuse the
// financing cash flows or add SBC a second time.
setup("Valuation", "Discounted cash flow", 60);
note("Valuation", 6, "USD millions except value per share. Annual end-year discounting.");
periodHeaders("Valuation");
const valRows = { ebit: 10, tax_rate: 11, nopat: 12, da: 13, capex: 14, delta_nwc: 15, fcff: 16, factor: 18, pv: 19 };
const valLabels = { ebit: "EBIT", tax_rate: "Cash tax rate", nopat: "NOPAT before levered NOL benefits", da: "Depreciation and amortization",
  capex: "Capital investment", delta_nwc: "Change in operating working capital", fcff: "Free cash flow to the firm", factor: "Discount factor", pv: "Present value of FCFF" };
for (const [key, r] of Object.entries(valRows)) {
  rowLabel("Valuation", r, valLabels[key], key === "tax_rate" ? fmt.percent : key === "factor" ? "0.0000" : fmt.money, ["fcff", "pv"].includes(key));
  cols.forEach((c, i) => {
    const expr = { ebit: s("ebit", c), tax_rate: d("tax_rate", c), nopat: c + "10-MAX(0," + c + "10)*" + c + "11",
      da: s("economic_da", c), capex: s("capex", c), delta_nwc: s("delta_nwc", c),
      fcff: c + "12+" + c + "13-" + c + "14-" + c + "15", factor: "(1+$F$27)^-" + (i + 1), pv: c + "16*" + c + "18" }[key];
    formula("Valuation", c + r, "=" + expr);
  });
}
section("Valuation", 22, "Discount rate and terminal value");
const valScalar = {
  24: ["Cost of equity", V("risk_free_rate") + "+" + V("equity_beta") + "*" + V("equity_risk_premium"), fmt.percent],
  25: ["After-tax cost of debt", V("pretax_cost_of_debt") + "*(1-" + V("tax_rate") + ")", fmt.percent],
  26: ["Target debt weight", V("target_debt_weight"), fmt.percent],
  27: ["Weighted average cost of capital", "F24*(1-F26)+F25*F26", fmt.percent],
  29: ["Terminal growth", V("terminal_growth"), fmt.percent],
  30: ["Terminal ROIC", V("terminal_roic"), fmt.percent],
  31: ["Terminal NOPAT", q("Statements", "J22") + "*(1+F29)*(1-" + V("tax_rate") + ")", fmt.money],
  32: ["Terminal reinvestment", "IF(AND(F30>0,F30>=F29),F31*F29/F30,NA())", fmt.money],
  33: ["Terminal FCFF", "F31-F32", fmt.money],
  34: ["Terminal value", "IF(AND(F27>F29,F27<=1,F29>=0,F31>0),F33/(F27-F29),NA())", fmt.money],
  35: ["Present value of terminal value", "F34*J18", fmt.money],
  37: ["Operating enterprise value", "SUM(F19:J19)+F35", fmt.money],
  38: ["Reported cash", O("cash"), fmt.money],
  39: ["Financing debt", O("debt"), fmt.money],
  40: ["Other claims", V("other_claims"), fmt.money],
  41: ["Equity value", "F37+F38-F39-F40", fmt.money],
  42: ["Current common shares (millions)", O("shares"), fmt.shares],
  43: ["DCF value per share", "IF(F42>0,F41/F42,NA())", fmt.dollars],
  44: ["Terminal share of enterprise value", "IF(F37>0,F35/F37,NA())", fmt.percent],
};
for (const [r, [label, f, nf]] of Object.entries(valScalar)) { rowLabel("Valuation", Number(r), label, nf, [27,37,41,43].includes(Number(r))); formula("Valuation", "F" + r, "=" + f, nf); }
note("Valuation", 47, "Full reported cash is included. Cash availability and existing award dilution remain review items.");
note("Valuation", 48, "No levered NOL benefit or future SBC share dilution is deducted again from this cash-equivalent DCF.");
note("Valuation", 49, "The terminal calculation assumes sustainable reinvestment at the stated ROIC.");

// Acquired cash, existing debt and other claims are reconciled exactly once.
setup("Acquisition", "Acquisition financing", 115);
note("Acquisition", 6, "USD millions. Hypothetical terms. Recurring stock awards are replaced with equal cash compensation.");
section("Acquisition", 10, "Sources and uses at the hypothetical closing");
const acqSU = {
  12: ["Entry enterprise value", T("entry_enterprise_value")],
  13: ["Seller equity consideration", "F12+" + O("cash") + "-" + O("debt") + "-" + V("other_claims")],
  14: ["Repay existing financing debt", O("debt")], 15: ["Settle identified other claims", V("other_claims")],
  16: ["Transaction fees", "F12*" + T("transaction_fee_rate")], 17: ["Financing fees", T("initial_term_debt") + "*" + T("financing_fee_rate")],
  18: ["Cash top-up", "MAX(0," + T("minimum_cash") + "-" + O("cash") + ")"],
  19: ["Total uses", "SUM(F13:F18)"], 21: ["New term debt", T("initial_term_debt")],
  22: ["Acquired cash used", "MAX(0," + O("cash") + "-" + T("minimum_cash") + ")"],
  23: ["Sponsor equity invested", "F19-F21-F22"], 24: ["Total sources", "SUM(F21:F23)"],
  25: ["Sources less uses", "F24-F19"], 26: ["Opening retained cash", O("cash") + "-F22+F18"],
  28: ["Implied seller price per share", "F13/" + O("shares")],
  29: ["Premium to historical reference price", "F28/" + q("Actuals", "$F$" + quoteRow) + "-1"],
};
for (const [r, [label, f]] of Object.entries(acqSU)) {
  const n = Number(r); rowLabel("Acquisition", n, label, n === 28 ? fmt.dollars : n === 29 ? fmt.percent : n === 25 ? fmt.check : fmt.money, [19,23,24].includes(n));
  formula("Acquisition", "F" + r, "=" + f);
}
section("Acquisition", 31, "Annual financing and cash schedule");
periodHeaders("Acquisition", 33);
const qr = { ebitda: 35, ebit: 36, da: 37, capex: 38, delta_nwc: 39, opening_cash: 40, opening_term_debt: 41,
  opening_revolver: 42, term_interest: 43, revolver_interest: 44, interest: 45, pretax_income: 46,
  opening_nol: 47, nol_generated: 48, nol_used: 49, taxable_income: 50, cash_taxes: 51, closing_nol: 52,
  cash_flow_available_for_debt_service: 53, cash_flow_after_interest: 54, cash_before_debt: 55,
  mandatory_principal_due: 56, revolver_capacity: 57, requested_draw: 58, revolver_draw: 59, cash_with_draw: 60,
  mandatory_principal_paid: 61, mandatory_principal_shortfall: 62, cash_after_mandatory: 63, revolver_before_paydown: 64,
  revolver_repayment: 65, cash_after_revolver: 66, term_after_mandatory: 67, term_cash_sweep: 68,
  closing_term_debt: 69, closing_revolver: 70, closing_cash: 71, liquidity_shortfall: 72, net_debt: 73,
  net_leverage: 74, interest_coverage: 75, contractual_debt_service: 76, debt_service_coverage: 77,
  cash_tolerance: 78, leverage_failure: 79, interest_failure: 80, annual_failures: 81,
  cash_rollforward_difference: 82, term_rollforward_difference: 83, revolver_rollforward_difference: 84,
  scheduled_principal_due: 111, maturity_principal_due_before_exit: 112, maturity_balloon_due_at_exit: 113,
};
const qm = Array.from({ length: 79 }, () => Array(5).fill(""));
for (const [key, row] of Object.entries(qr)) rowLabel("Acquisition", row, pretty(key),
  ["net_leverage","interest_coverage","debt_service_coverage"].includes(key) ? fmt.ratio :
    key.endsWith("_failure") || key === "annual_failures" ? fmt.count :
      key.endsWith("_difference") || key === "cash_tolerance" ? fmt.check : fmt.money,
  ["cash_flow_available_for_debt_service","cash_flow_after_interest","closing_term_debt","closing_revolver","closing_cash"].includes(key));
cols.forEach((c, i) => {
  const p = i ? cols[i - 1] : null, r = key => c + qr[key];
  const set = (key, f) => { qm[qr[key] - 35][i] = "=" + f; };
  ["ebitda","ebit","capex","delta_nwc"].forEach(k => set(k, s(k, c)));
  set("da", s("depreciation", c) + "+" + s("amortization", c));
  set("opening_cash", p ? p + qr.closing_cash : "$F$26");
  set("opening_term_debt", p ? p + qr.closing_term_debt : T("initial_term_debt"));
  set("opening_revolver", p ? p + qr.closing_revolver : "0");
  set("term_interest", r("opening_term_debt") + "*" + T("term_interest_rate"));
  set("revolver_interest", r("opening_revolver") + "*" + T("revolver_interest_rate"));
  set("interest", "SUM(" + c + "43:" + c + "44)");
  set("pretax_income", r("ebit") + "-" + r("interest"));
  set("opening_nol", p ? p + qr.closing_nol : O("tax_loss_carryforward"));
  set("nol_generated", "MAX(0,-" + r("pretax_income") + ")");
  set("nol_used", "MIN(" + r("opening_nol") + ",MAX(0," + r("pretax_income") + ")*" + T("nol_utilization_limit") + ")");
  set("taxable_income", "MAX(0," + r("pretax_income") + ")-" + r("nol_used"));
  set("cash_taxes", r("taxable_income") + "*" + d("tax_rate", c));
  set("closing_nol", r("opening_nol") + "+" + r("nol_generated") + "-" + r("nol_used"));
  set("cash_flow_available_for_debt_service", r("ebitda") + "-" + r("cash_taxes") + "-" + r("capex") + "-" + r("delta_nwc"));
  set("cash_flow_after_interest", r("cash_flow_available_for_debt_service") + "-" + r("interest"));
  set("cash_before_debt", r("opening_cash") + "+" + r("cash_flow_after_interest"));
  set("scheduled_principal_due", "MIN(" + r("opening_term_debt") + "," + T("initial_term_debt") + "*" + T("term_amortization_rate") + ")");
  set("maturity_principal_due_before_exit", "IF(AND(" + (i+1) + ">=" + T("term_maturity_year") + ",NOT(AND(" + (i+1) + "=5," + T("term_maturity_year") + "=5))),MAX(0," + r("opening_term_debt") + "-" + r("scheduled_principal_due") + "),0)");
  set("mandatory_principal_due", r("scheduled_principal_due") + "+" + r("maturity_principal_due_before_exit"));
  set("maturity_balloon_due_at_exit", "IF(AND(" + (i+1) + "=5," + T("term_maturity_year") + "=5)," + r("closing_term_debt") + ",0)");
  set("revolver_capacity", "MAX(0," + T("revolver_limit") + "-" + r("opening_revolver") + ")");
  set("requested_draw", "MAX(0," + T("minimum_cash") + "+" + r("mandatory_principal_due") + "-" + r("cash_before_debt") + ")");
  set("revolver_draw", "MIN(" + r("revolver_capacity") + "," + r("requested_draw") + ")");
  set("cash_with_draw", r("cash_before_debt") + "+" + r("revolver_draw"));
  set("mandatory_principal_paid", "MIN(" + r("mandatory_principal_due") + ",MAX(0," + r("cash_with_draw") + "-" + T("minimum_cash") + "))");
  set("mandatory_principal_shortfall", "MAX(0," + r("mandatory_principal_due") + "-" + r("mandatory_principal_paid") + ")");
  set("cash_after_mandatory", r("cash_with_draw") + "-" + r("mandatory_principal_paid"));
  set("revolver_before_paydown", r("opening_revolver") + "+" + r("revolver_draw"));
  set("revolver_repayment", "MIN(" + r("revolver_before_paydown") + ",MAX(0," + r("cash_after_mandatory") + "-" + T("minimum_cash") + "))");
  set("cash_after_revolver", r("cash_after_mandatory") + "-" + r("revolver_repayment"));
  set("term_after_mandatory", "MAX(0," + r("opening_term_debt") + "-" + r("mandatory_principal_paid") + ")");
  set("term_cash_sweep", "MIN(" + r("term_after_mandatory") + ",MAX(0," + r("cash_after_revolver") + "-" + T("minimum_cash") + ")*" + T("cash_sweep_rate") + ")");
  set("closing_term_debt", "MAX(0," + r("term_after_mandatory") + "-" + r("term_cash_sweep") + ")");
  set("closing_revolver", "MAX(0," + r("revolver_before_paydown") + "-" + r("revolver_repayment") + ")");
  set("closing_cash", r("cash_after_revolver") + "-" + r("term_cash_sweep"));
  set("liquidity_shortfall", "MAX(0," + T("minimum_cash") + "-" + r("closing_cash") + ")");
  set("net_debt", r("closing_term_debt") + "+" + r("closing_revolver") + "-" + r("closing_cash"));
  set("net_leverage", "IF(" + r("ebitda") + ">0," + r("net_debt") + "/" + r("ebitda") + ",\"n.a.\")");
  set("interest_coverage", "IF(" + r("interest") + ">0," + r("ebitda") + "/" + r("interest") + ",\"n.a.\")");
  set("contractual_debt_service", r("interest") + "+" + r("mandatory_principal_due"));
  set("debt_service_coverage", "IF(" + r("contractual_debt_service") + ">0," + r("cash_flow_available_for_debt_service") + "/" + r("contractual_debt_service") + ",\"n.a.\")");
  set("cash_tolerance", "MAX(ABS(" + r("opening_cash") + "),ABS(" + r("cash_flow_after_interest") + "),ABS(" + r("mandatory_principal_due") + "),ABS(" + r("revolver_draw") + "),ABS(" + r("closing_cash") + ")," + T("minimum_cash") + ")*1E-12");
  set("leverage_failure", "IF(" + r("ebitda") + "<=0,1,IF(" + r("net_leverage") + ">" + T("max_net_leverage") + "*(1+1E-12),1,0))");
  set("interest_failure", "IF(" + r("interest") + ">0,IF(" + r("interest_coverage") + "<" + T("min_interest_coverage") + "*(1-1E-12),1,0),0)");
  set("annual_failures", "IF(" + r("liquidity_shortfall") + ">" + r("cash_tolerance") + ",1,0)+IF(" + r("mandatory_principal_shortfall") + ">" + r("cash_tolerance") + ",1,0)+" + r("leverage_failure") + "+" + r("interest_failure"));
  set("cash_rollforward_difference", r("closing_cash") + "-(" + r("opening_cash") + "+" + r("cash_flow_after_interest") + "+" + r("revolver_draw") + "-" + r("mandatory_principal_paid") + "-" + r("revolver_repayment") + "-" + r("term_cash_sweep") + ")");
  set("term_rollforward_difference", r("closing_term_debt") + "-(" + r("opening_term_debt") + "-" + r("mandatory_principal_paid") + "-" + r("term_cash_sweep") + ")");
  set("revolver_rollforward_difference", r("closing_revolver") + "-(" + r("opening_revolver") + "+" + r("revolver_draw") + "-" + r("revolver_repayment") + ")");
});
cell("Acquisition", "F35:J113").formulas = qm;
for (const [_, r] of Object.entries(qr)) cols.forEach((c, i) => { cell("Acquisition", c + r).format.font.color = qm[r - 35][i].includes("!") ? colors.link : "#000000"; });
section("Acquisition", 86, "Exit and sponsor returns");
const exitFormulas = {
  88: ["Exit EBITDA", "J35"], 89: ["Exit EBITDA multiple", T("exit_ebitda_multiple")],
  90: ["Exit enterprise value", "IF(F88>0,F88*F89,NA())"],
  91: ["Exit fees", "F90*" + T("exit_fee_rate")], 92: ["Cash at exit", "J71"], 93: ["Term debt payoff", "J69"], 94: ["Revolver payoff", "J70"],
  95: ["Equity before limited-liability floor", "F90-F91+F92-F93-F94"], 96: ["Indicative sponsor proceeds", "MAX(0,F95)"],
  97: ["Exit debt-repayment shortfall", "MAX(0,-F95)"],
  98: ["Model financing conditions met (1 / 0)", "IF(AND(COUNT(F81:J81)=5,SUM(F81:J81)=0,F88>0,F97<=MAX(F90,F91,F92,F93,F94)*1E-12,F23>0,F13>=0),1,0)"],
  100: ["Sponsor MOIC", 'IF(F98=1,F96/F23,"n.a.")'],
  101: ["Annual sponsor IRR", 'IF(F98=1,(F96/F23)^(1/5)-1,"n.a.")'],
  102: ["Maturity settled in term payoff (memo)", "IF(" + T("term_maturity_year") + "=5,F93,0)"],
};
for (const [r, [label, f]] of Object.entries(exitFormulas)) {
  const n = Number(r); const nf = [89,100].includes(n) ? fmt.ratio : n === 101 ? fmt.percent : n === 98 ? fmt.count : fmt.money;
  rowLabel("Acquisition", n, label, nf, [90,96,100,101].includes(n)); formula("Acquisition", "F" + r, "=" + f, nf);
}
errorConditional("Acquisition", "F62:J62", "F62>F78");
errorConditional("Acquisition", "F72:J72", "F72>F78");
errorConditional("Acquisition", "F81:J81", "F81>0");
note("Acquisition", 104, "IRR is an equal-annual-period return: one initial investment and one year-five receipt.");
note("Acquisition", 105, "Returns are unavailable after funding, maturity, covenant or exit-debt repayment failure.");
note("Acquisition", 106, "Annual balances do not establish seasonal liquidity. Interest uses opening debt.");
note("Acquisition", 107, "Other claims are assumed settled at face amount at closing. No purchase accounting is modeled.");
section("Acquisition", 109, "Maturity timing: sale-date balloon settles once at exit");
periodHeaders("Acquisition", 110);
note("Acquisition", 115, "A maturity before exit is a mandatory annual payment; a year-five balloon uses sale proceeds.");

// Two transparent operating-line comparables. Inputs below are source facts;
// operating EBIT, financing debt and other claims are constructed visibly.
setup("Comps", "Selected comparable companies", 95);
note("Comps", 6, "USD millions except share prices and multiples. Selected FY2025 earnings, not latest LTM.");
value("Comps", "F8", "RPM"); value("Comps", "G8", "Clorox");
cell("Comps", "F8:G8").format = { fill: colors.blue, font: { color: "#FFFFFF", bold: true }, horizontalAlignment: "center" };
const compInputs = {
  10: ["Reference share price", p => p.quote.close, fmt.dollars],
  11: ["Reference price date", p => new Date(p.quote.date + "T00:00:00Z"), fmt.date],
  12: ["Common shares (millions)", p => p.shares.value / 1e6, fmt.shares],
  13: ["Share-count date", p => new Date(p.shares.as_of + "T00:00:00Z"), fmt.date],
  14: ["Financial period end", p => new Date(p.fiscal_period_end + "T00:00:00Z"), fmt.date],
  17: ["Revenue", p => p.income_statement.revenue / 1000],
  18: ["Cost of sales", p => (p.income_statement.cost_of_sales ?? p.income_statement.cost_of_products_sold) / 1000],
  19: ["Selling and administrative expense", p => (p.income_statement.selling_general_administrative ?? p.income_statement.selling_administrative) / 1000],
  20: ["Advertising separately deducted", p => (p.income_statement.advertising ?? 0) / 1000],
  21: ["R&D separately deducted", p => (p.income_statement.research_development ?? 0) / 1000],
  22: ["Restructuring expense", p => (p.income_statement.restructuring_expense ?? 0) / 1000],
  23: ["Goodwill impairment", p => (p.income_statement.goodwill_impairment ?? 0) / 1000],
  24: ["Loss on divestiture", p => (p.income_statement.loss_on_divestiture ?? 0) / 1000],
  25: ["Amortization in other expense", p => (p.income_statement.other_income_expense_components?.intangible_amortization_expense ?? 0) / 1000],
  31: ["Current borrowings", p => (p.balance_sheet.current_debt ?? p.balance_sheet.notes_loans_payable) / 1000],
  32: ["Noncurrent borrowings", p => (p.balance_sheet.long_term_debt ?? p.balance_sheet.long_term_debt_book) / 1000],
  33: ["Finance leases outside borrowings", p => p.entity.ticker === "CLX" ? p.balance_sheet.total_finance_lease_liabilities / 1000 : 0],
  35: ["Cash to deduct", p => p.balance_sheet.cash / 1000],
  36: ["Noncontrolling interests", p => p.balance_sheet.noncontrolling_interests_book / 1000],
  37: ["Preferred stock", p => p.balance_sheet.preferred_stock / 1000],
  38: ["Contingent acquisition consideration", p => (p.balance_sheet.contingent_acquisition_consideration_liability ?? 0) / 1000],
  39: ["Glad terminal obligation", p => (p.balance_sheet.glad_venture_terminal_obligation_carrying ?? 0) / 1000],
  40: ["Current recognized pension deficits", p => (p.balance_sheet.pension_liabilities_current ?? 0) / 1000],
  41: ["Noncurrent recognized pension deficits", p => (p.balance_sheet.pension_liabilities_noncurrent ?? 0) / 1000],
  42: ["Net retirement income deficit", p => (p.balance_sheet.pension_net_funded_deficit ?? 0) / 1000],
  43: ["Net retirement healthcare deficit", p => (p.balance_sheet.retirement_healthcare_net_funded_deficit ?? 0) / 1000],
  45: ["Other nonoperating assets deducted", p => p.suggested_enterprise_value_bridge.nonoperating_assets_to_deduct / 1000],
};
for (const [r, [label, get, nf]] of Object.entries(compInputs)) {
  rowLabel("Comps", Number(r), label, nf || fmt.money);
  facts.comparables.forEach((p,i) => {
    value("Comps", cols[i] + r, get(p), nf || fmt.money);
    cell("Comps", cols[i] + r).format.font.color = colors.input;
  });
}
section("Comps", 16, "Operating EBIT from disclosed line items");
section("Comps", 29, "Enterprise-value bridge");
for (const c of ["F","G"]) {
  formula("Comps", c + "26", "=IF(COUNT(" + c + "17:" + c + "25)=9," + c + "17-SUM(" + c + "18:" + c + "25),NA())", fmt.money);
  formula("Comps", c + "30", "=IF(AND(COUNT(" + c + "10," + c + "12)=2," + c + "10>0," + c + "12>0)," + c + "10*" + c + "12,NA())", fmt.money);
  formula("Comps", c + "34", "=IF(COUNT(" + c + "31:" + c + "33)=3,SUM(" + c + "31:" + c + "33),NA())", fmt.money);
  formula("Comps", c + "44", "=IF(COUNT(" + c + "38:" + c + "43)=6,SUM(" + c + "38:" + c + "43),NA())", fmt.money);
  formula("Comps", c + "47", "=IF(COUNT(" + c + "35:" + c + "37," + c + "45)=4," + c + "30+" + c + "34-" + c + "35+" + c + "36+" + c + "37+" + c + "44-" + c + "45,NA())", fmt.money);
  formula("Comps", c + "48", "=IF(" + c + "26>0," + c + "47/" + c + "26,NA())", fmt.ratio);
}
[[26,"Constructed operating EBIT"],[30,"Common equity market value"],[34,"Financing debt incl. finance leases"],[44,"Total identified other claims"],[47,"Enterprise value"],[48,"EV / operating EBIT"]].forEach(([r,l]) => rowLabel("Comps",r,l,r === 48 ? fmt.ratio : fmt.money,true));
section("Comps", 51, "WD-40 implied value using the selected range");
value("Comps", "F53", "Low"); value("Comps", "G53", "Median"); value("Comps", "H53", "High");
rowLabel("Comps", 54, "EV / operating EBIT", fmt.ratio);
formula("Comps","F54","=MIN(F48:G48)",fmt.ratio);formula("Comps","G54","=MEDIAN(F48:G48)",fmt.ratio);formula("Comps","H54","=MAX(F48:G48)",fmt.ratio);
for (const c of ["F","G","H"]) {
  formula("Comps",c+"55","="+guardedNumber(q("Actuals","H"+ar["income_statement.operating_income"]),0,1e9,true),fmt.money);
  formula("Comps",c+"56","="+c+"54*"+c+"55",fmt.money);
  formula("Comps",c+"57","="+O("cash"),fmt.money); formula("Comps",c+"58","="+O("debt"),fmt.money);
  formula("Comps",c+"59","="+V("other_claims"),fmt.money);
  formula("Comps",c+"60","="+c+"56+"+c+"57-"+c+"58-"+c+"59",fmt.money);
  formula("Comps",c+"61","="+O("shares"),fmt.shares);
  formula("Comps",c+"62","="+c+"60/"+c+"61",fmt.dollars);
}
[[55,"WD-40 reported operating EBIT"],[56,"Implied enterprise value"],[57,"Reported cash"],[58,"Financing debt"],[59,"Other claims"],[60,"Implied equity value"],[61,"Current common shares (millions)"],[62,"Implied value per share"]].forEach(([r,l]) => rowLabel("Comps",r,l,r===61?fmt.shares:r===62?fmt.dollars:fmt.money,[56,60,62].includes(r)));
note("Comps",65,"Two imperfect peers. Earnings retain restructuring, impairment and divestiture effects.");
note("Comps",66,"Clorox includes $21m intangible amortization reported in other expense.");
note("Comps",67,"RPM finance leases are already in borrowings. Clorox adds $36m once.");
note("Comps",68,"Pension and Glad obligations are disclosed analyst classifications. Book claims proxy fair value.");
note("Comps",69,"Separate share-count and financial dates remain visible; they are not October 31 closing balances.");
value("Comps","C72","Source locators");
value("Comps","C73","RPM: FY2025 annual report, embedded 10-K pp.34–35; notes G, E and N.");
value("Comps","C74","Clorox: FY2025 financial exhibit pp.25,27; notes 8,14,18,20; proxy share count.");
value("Comps","C75","Quotes: ChartExchange historical tables, dated October 31, 2025. URLs in Actuals source register.");

// Checks are terminal readers. Business calculations and output statuses do
// not depend on this worksheet.
setup("Review","Financial reconciliations",75);
note("Review",6,"Differences in USD millions. Numerical display tolerance $0.01; no accounting-materiality claim.");
periodHeaders("Review");
const reviewRows = [
  [10,"Assets less liabilities and equity", c => s("total_assets",c)+"-"+s("total_liabilities_and_equity",c)],
  [11,"Cash rollforward",c=>s("cash",c)+"-"+s("opening_cash",c)+"-"+s("cash_from_operations",c)+"-"+s("cash_from_investing",c)+"-"+s("cash_from_financing",c)],
  [12,"Operating cash conversion",c=>s("cash_from_operations",c)+"-"+s("ebitda",c)+"-"+s("stock_compensation",c)+"+"+s("interest_expense",c)+"+"+s("tax_expense",c)+"+"+s("delta_nwc",c)],
  [13,"PPE rollforward",c=>s("net_ppe",c)+"-"+s("opening_ppe",c)+"-"+s("ppe_capex",c)+"+"+s("depreciation",c)],
  [14,"Intangible rollforward",c=>s("net_intangibles",c)+"-"+s("opening_intangibles",c)+"-"+s("intangible_capex",c)+"+"+s("amortization",c)],
  [15,"Debt rollforward",c=>s("debt",c)+"-"+s("opening_debt",c)+"-"+s("debt_issued",c)+"+"+s("debt_repaid",c)],
  [16,"Equity rollforward",c=>s("equity",c)+"-"+s("opening_equity",c)+"-"+s("net_income",c)+"+"+s("dividends",c)+"-"+s("stock_compensation",c)+"-"+s("equity_issued",c)+"+"+s("repurchases",c)],
  [17,"Share rollforward (million shares)",c=>s("shares",c)+"-"+s("opening_shares",c)+"-"+s("stock_compensation_shares",c)+"-"+s("cash_issue_shares",c)+"+"+s("shares_repurchased",c)],
  [18,"NOL rollforward",c=>s("tax_loss_carryforward",c)+"-"+s("opening_nol",c)+"-"+s("nol_generated",c)+"+"+s("nol_used",c)],
  [19,"DCF FCFF to operating schedule",c=>q("Valuation",c+"16")+"-"+s("fcff",c)],
  [21,"Acquisition cash rollforward",c=>q("Acquisition",c+"82")],
  [22,"Acquisition term debt rollforward",c=>q("Acquisition",c+"83")],
  [23,"Acquisition revolver rollforward",c=>q("Acquisition",c+"84")],
];
for(const [row,label,make] of reviewRows){rowLabel("Review",row,label,fmt.check);cols.forEach(c=>formula("Review",c+row,"="+make(c),fmt.check));errorConditional("Review","F"+row+":J"+row,"ABS(F"+row+")>1E-8");cell("Review","F"+row+":J"+row).format.font.color=colors.ink;}
rowLabel("Review",25,"Closing sources less uses",fmt.check);formula("Review","F25","="+q("Acquisition","F25"),fmt.check);cell("Review","F25").format.font.color=colors.ink;
section("Review",28,"Reported historical source controls");
["2023","2024","2025"].forEach((y,i)=>value("Review",cols[i]+"30",y));
const hr = [
  [31,"Income to reported net income",(c)=>ax("income_statement","pretax_income",c)+"-"+ax("income_statement","income_tax_expense",c)+"-"+ax("income_statement","net_income",c)],
  [32,"Reported balance sheet",(c)=>ax("balance_sheet","total_assets",c)+"-"+ax("balance_sheet","total_liabilities",c)+"-"+ax("balance_sheet","total_equity",c)],
  [33,"Cash-flow sections incl. FX",(c)=>["operating_cash_flow","investing_cash_flow","financing_cash_flow","fx_cash_effect"].map(k=>ax("cash_flow",k,c)).join("+")+"-"+ax("cash_flow","net_cash_change",c)],
  [34,"Reported cash rollforward",(c)=>ax("cash_flow","beginning_cash",c)+"+"+ax("cash_flow","net_cash_change",c)+"-"+ax("cash_flow","ending_cash",c)],
  [35,"Cash flow to balance sheet",(c)=>ax("cash_flow","ending_cash",c)+"-"+ax("balance_sheet","cash",c)],
  [36,"Reported equity rollforward",(c)=>["beginning_equity","net_income","dividends","stock_based_compensation","award_tax_withholding","treasury_stock_purchases","other_comprehensive_income"].map(k=>ax("equity_rollforward",k,c)).join("+")+"-"+ax("equity_rollforward","ending_equity",c)],
];
for(const [row,label,make]of hr){rowLabel("Review",row,label,fmt.check);["F","G","H"].forEach(c=>formula("Review",c+row,"="+make(c).replace(/[FGH]\d+/g,m=>q("Actuals",m)),fmt.check));errorConditional("Review","F"+row+":H"+row,"ABS(F"+row+")>1E-8");cell("Review","F"+row+":H"+row).format.font.color=colors.ink;}
section("Review",39,"Items requiring qualified review");
[
"Actual closing balances and interim cash, dividends and dispositions.",
"Sustainable terminal economics and WACC market assumptions.",
"Current share count, existing awards, cash availability and complete claims.",
"Lease, deferred-tax, international-tax and purchase-accounting treatment.",
"Peer selection, normalization, claim classification and valuation dates.",
"Independent qualified human validation and employer acceptance.",
"Independent native Excel recalculation remains outstanding.",
].forEach((t,i)=>value("Review","C"+(41+i),t));

setup("Summary","WD-40 corporate and acquisition case",55);
sheets.Summary.tabColor=colors.navy;
sheets.Summary.freezePanes.unfreeze();
note("Summary",6,"Historical analysis cutoff: October 31, 2025. USD millions except per-share values.");
const summary = [
[8,"DCF value per share",q("Valuation","F43"),fmt.dollars],
[9,"Historical closing price",q("Actuals","F"+quoteRow),fmt.dollars],
[10,"DCF difference to reference","E8/E9-1",fmt.percent],
[12,"Selected peer range low",q("Comps","F62"),fmt.dollars],
[13,"Selected peer range high",q("Comps","H62"),fmt.dollars],
[15,"Sponsor equity invested",q("Acquisition","F23"),fmt.money],
[16,"Sponsor MOIC",q("Acquisition","F100"),fmt.ratio],
[17,"Annual sponsor IRR",q("Acquisition","F101"),fmt.percent],
[18,"Model financing conditions",'IF('+q("Acquisition","F98")+'=1,"Met","Not met")',undefined],
[20,"Reported balance date",q("Actuals","F"+sourceBalanceDateRow),fmt.date],
[21,"Hypothetical model opening",q("Actuals","F"+modelDateRow),fmt.date],
];
for(const[r,label,f,nf]of summary){value("Summary","C"+r,label);formula("Summary","E"+r,"="+f,nf);cell("Summary","E"+r).format.font.color=colors.ink;}
cell("Summary","E8:E9").format.font.bold=true;cell("Summary","E16:E17").format.font.bold=true;
value("Summary","C23","Closing-balance and independent review");value("Summary","E23","Outstanding");
cell("Summary","E23").format.font.color=colors.error;
cell("Summary","E1:E55").format.columnWidth=17;
cell("Summary","G1:N55").format.columnWidth=12;
cell("Summary","G26:I26").values=[["Model year","FCFF","Acquisition debt"]];
cell("Summary","G26:I26").format={fill:colors.blue,font:{name:"Arial",size:10,color:"#FFFFFF",bold:true},horizontalAlignment:"center"};
cols.forEach((c,i)=>{value("Summary","G"+(27+i),"Year "+(i+1));formula("Summary","H"+(27+i),"="+q("Valuation",c+"16"),fmt.money);formula("Summary","I"+(27+i),"="+q("Acquisition",c+"69")+"+"+q("Acquisition",c+"70"),fmt.money);});
const chart=sheets.Summary.charts.add("line",cell("Summary","G26:I31"));
chart.title="FCFF and acquisition debt (USD millions)";
chart.titleTextStyle.typeface="Arial";chart.titleTextStyle.fontSize=12;
chart.legend={position:"top",textStyle:{typeface:"Arial",fontSize:10}};
chart.xAxis={axisType:"textAxis",textStyle:{typeface:"Arial",fontSize:10}};
chart.yAxis={numberFormatCode:'#,##0',numberFormatSourceLinked:false,textStyle:{typeface:"Arial",fontSize:10}};
chart.series.items[0].line={fill:colors.blue,style:"solid",width:2};
chart.series.items[1].line={fill:colors.gold,style:"solid",width:2};
chart.setPosition("G8","N23");
[
"Change the single case selector on Assumptions. The same model recalculates.",
"Opening balances are a proxy carried from August 31. No interim rollforward is asserted.",
"Forecast periods are full model years ending October 31, not WD-40 fiscal years.",
"Reported 2025 earnings include an unusual tax benefit; the forecast uses a separate tax assumption.",
"The acquisition price, financing terms and exit multiple are hypothetical.",
"A calculated return is conditional on the stated assumptions and model financing checks.",
"Source inputs and reviewer items remain visible. Institutional acceptance is outstanding.",
].forEach((t,i)=>value("Summary","C"+(35+i),t));

// Verify independent spreadsheet formulas against the Python implementation.
// Authoring-only comparisons are saved outside the delivered workbook.
await fs.mkdir(outputDir,{recursive:true});
const python=process.env.CODEX_PRIMARY_RUNTIME_PYTHON || "python";
const expected=JSON.parse(execFileSync(python,["-c",
  "import json,sys; from copy import deepcopy; from pilot.corporate_case import evaluate_case; b=json.load(open(sys.argv[1])); out={};\nfor name in ('Base','Downside','Upside'):\n c=deepcopy(b['case']); c['selected_case']=name; out[name]=evaluate_case(c,b['facts'])\nprint(json.dumps(out,allow_nan=False))",input],{cwd:repo,encoding:"utf8",maxBuffer:20*1024*1024}));
const verification={case_results:[],changes:[],limitations:[
  "Formulas recalculated with Artifact Tool; native desktop Excel was not available for a separate application-engine check.",
  "Spreadsheet cash-boundary tolerance uses 1e-12 of local amounts, while Python reports its local floating-point allowance. This is numerical resolution, not accounting materiality.",
]};
verification.numeric_comparisons = 0;
verification.maximum_relative_comparison_error = 0;
function read(s,a){return cell(s,a).values[0][0];}
function close(actual,expected,label,scale=1){
  if(typeof actual!=="number"||!Number.isFinite(actual))throw Error(label+" is not numeric: "+actual);
  const expectedScaled=expected/scale;
  const tolerance=Math.max(Math.abs(expectedScaled)*2e-10,2e-9);
  if(Math.abs(actual-expectedScaled)>tolerance)throw Error(label+" differs: "+actual+" versus "+expectedScaled);
  verification.numeric_comparisons++;
  verification.maximum_relative_comparison_error = Math.max(verification.maximum_relative_comparison_error, Math.abs(actual-expectedScaled)/Math.max(1,Math.abs(expectedScaled)));
}
for(let k=0;k<names.length;k++){
  value("Assumptions","E4",k+1); wb.recalculate();
  const name=names[k], report=expected[name];
  for(let i=0;i<5;i++){
    const c=cols[i];
    for(const key of ["revenue","cogs","ebitda","ebit","net_income","cash","total_assets","total_liabilities","equity","cash_from_operations","cash_from_financing","net_ppe","net_intangibles","debt","delta_nwc","tax_loss_carryforward","retained_earnings","other_equity","shares","fcff"]){
      close(read("Statements",c+sr[key]),report.projection.forecast[i][key],name+" statements "+key+" year"+(i+1),1e6);
    }
    for(const key of ["interest","cash_taxes","closing_nol","scheduled_principal_due","maturity_principal_due_before_exit","maturity_balloon_due_at_exit","mandatory_principal_due","mandatory_principal_paid","mandatory_principal_shortfall","revolver_draw","revolver_repayment","term_cash_sweep","closing_term_debt","closing_revolver","closing_cash","liquidity_shortfall"]){
      close(read("Acquisition",c+qr[key]),report.acquisition.schedule[i][key],name+" financing "+key+" year"+(i+1),1e6);
    }
  }
  close(read("Valuation","F27"),report.valuation.wacc,name+" WACC");
  close(read("Valuation","F37"),report.valuation.enterprise_value,name+" DCF EV",1e6);
  close(read("Valuation","F43"),report.valuation.value_per_share,name+" DCF per share");
  close(read("Acquisition","F23"),report.acquisition.sources_uses.sponsor_equity,name+" sponsor investment",1e6);
  if(report.acquisition.returns.annual_irr===null){
    if(read("Acquisition","F100")!=="n.a."||read("Acquisition","F101")!=="n.a.")throw Error("Failed financing must withhold returns");
  }else{
    close(read("Acquisition","F100"),report.acquisition.returns.moic,name+" MOIC");
    close(read("Acquisition","F101"),report.acquisition.returns.annual_irr,name+" IRR");
  }
  ["low","median","high"].forEach((key,i)=>close(read("Comps",cols[i]+"62"),report.comparables.implied_values[key].value_per_share,name+" comps "+key));
  verification.case_results.push({case:name,dcf_per_share:read("Valuation","F43"),moic:read("Acquisition","F100"),annual_irr:read("Acquisition","F101"),financing_conditions_met:read("Acquisition","F98")});
}
value("Assumptions","E4",1);wb.recalculate();
const sourceRevenue=read("Actuals","H"+ar["income_statement.revenue"]);
const baselineDCF=read("Valuation","F43"), baseCash=read("Statements","J68");
const growthCell="J"+(dr.revenue_growth+1), originalGrowth=read("Assumptions",growthCell);
value("Assumptions",growthCell,originalGrowth+.01);wb.recalculate();
if(!(read("Valuation","F43")>baselineDCF)||read("Statements","J68")===baseCash)throw Error("Later-period growth edit did not propagate");
if(read("Actuals","H"+ar["income_statement.revenue"])!==sourceRevenue)throw Error("Forecast edit changed actuals");
verification.changes.push({change:"Base year-five revenue growth +1pp",dcf_per_share:read("Valuation","F43"),source_actual_unchanged:true});
value("Assumptions",growthCell,originalGrowth);
const taxCell="H"+(dr.tax_rate+1), originalTax=read("Assumptions",taxCell);
value("Assumptions",taxCell,originalTax+.01);wb.recalculate();
if(!(read("Valuation","F43")<baselineDCF))throw Error("Tax edit did not affect value");
verification.changes.push({change:"Base year-three tax +1pp",dcf_per_share:read("Valuation","F43")});
value("Assumptions",taxCell,originalTax);
const rateCell="F"+tr.term_interest_rate, originalRate=read("Assumptions",rateCell);
value("Assumptions",rateCell,originalRate+.01);wb.recalculate();
if(!(read("Acquisition","F43")>expected.Base.acquisition.schedule[0].term_interest/1e6))throw Error("Interest edit did not affect debt schedule");
verification.changes.push({change:"Term interest +1pp",first_year_interest:read("Acquisition","F43")});
value("Assumptions",rateCell,originalRate);
// Missing inactive driver must not affect the active case; selecting it must expose the gap.
const missingCell="F"+(dr.revenue_growth+2), preserved=read("Assumptions",missingCell);
value("Assumptions",missingCell,null);wb.recalculate();close(read("Valuation","F43"),expected.Base.valuation.value_per_share,"Inactive blank preserved base");
value("Assumptions","E4",2);wb.recalculate();
if(typeof read("Valuation","F43")==="number")throw Error("Missing active driver became a plausible valuation");
verification.changes.push({change:"Missing inactive / active case input",inactive_preserved:true,active_unavailable:true});
value("Assumptions",missingCell,preserved);value("Assumptions","E4",1);wb.recalculate();
for (const [sheet, address, resultSheet, resultAddress, label] of [
  ["Assumptions", "F" + vr.pretax_cost_of_debt, "Valuation", "F43", "Missing WACC input"],
  ["Assumptions", "F" + tr.term_interest_rate, "Acquisition", "F101", "Missing required financing input"],
  ["Assumptions", "F" + (dr.issuance_share_price + 1), "Valuation", "F43", "Missing required active price when issuance is zero"],
  ["Comps", "F18", "Comps", "F62", "Missing peer expense line"],
  ["Actuals", "H" + ar["balance_sheet.cash"], "Valuation", "F43", "Missing source opening cash"],
]) {
  const saved = read(sheet, address); value(sheet, address, null); wb.recalculate();
  if (typeof read(resultSheet, resultAddress) === "number") throw Error(label + " produced a plausible output");
  verification.changes.push({change: label, result_unavailable: true});
  value(sheet, address, saved); wb.recalculate();
}
const marginCell="F"+(dr.ebitda_margin+1), savedMargin=read("Assumptions",marginCell);
value("Assumptions",marginCell,.99); wb.recalculate();
if(typeof read("Valuation","F43")==="number")throw Error("EBITDA above gross profit was not rejected");
verification.changes.push({change:"EBITDA margin exceeds gross margin",result_unavailable:true});
value("Assumptions",marginCell,savedMargin);
const maturityCell="F"+tr.term_maturity_year, savedMaturity=read("Assumptions",maturityCell);
value("Assumptions",maturityCell,1);wb.recalculate();
if(read("Acquisition","F101")!=="n.a."||read("Acquisition","F62")<=0)throw Error("Earlier unfunded maturity did not withhold returns");
verification.changes.push({change:"Year-one maturity with insufficient funding",annual_irr:read("Acquisition","F101"),principal_shortfall_millions:read("Acquisition","F62")});
value("Assumptions",maturityCell,savedMaturity);value("Assumptions","E4",2);
const exitMultipleCell="F"+tr.exit_ebitda_multiple, savedExitMultiple=read("Assumptions",exitMultipleCell);
value("Assumptions",exitMultipleCell,.01);wb.recalculate();
if(read("Acquisition","F101")!=="n.a."||read("Acquisition","F97")<=0)throw Error("Insufficient exit proceeds did not withhold returns");
verification.changes.push({change:"Insufficient sale proceeds for final-year balloon",annual_irr:read("Acquisition","F101"),exit_shortfall_millions:read("Acquisition","F97")});
value("Assumptions",exitMultipleCell,savedExitMultiple);value("Assumptions","E4",1);wb.recalculate();
close(read("Valuation","F43"),expected.Base.valuation.value_per_share,"Restored base");
const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:300},summary:"Final formula error scan"});
verification.error_scan=errors.ndjson;
if(!errors.ndjson.includes("Cell search matched 0 entries."))throw Error("Final workbook contains formula errors: "+errors.ndjson);
const finalInspect=await wb.inspect({kind:"table",range:"Summary!C8:E23",include:"values,formulas",tableMaxRows:16,tableMaxCols:3,maxChars:5000});
await fs.writeFile(path.join(outputDir,"workbook_validation.json"),JSON.stringify(verification,null,2));
await fs.writeFile(path.join(outputDir,"workbook_inspection.ndjson"),finalInspect.ndjson+"\n"+errors.ndjson);
const views=[
["Summary","C2:N42","summary"],["Assumptions","C2:J34","assumptions"],["Statements","C2:J70","statements"],
["Valuation","C2:J49","valuation"],["Acquisition","C2:J29","acquisition_close"],["Acquisition","C60:J115","acquisition_exit"],
["Comps","C2:J75","comps"],["Actuals","C2:J40","actuals"],["Actuals","C"+(sourceRegistryStart)+":L"+(sourceRegistryStart+17),"sources"],["Review","C2:J48","review"],
["Statements","C73:J139","statement_schedules"],["Acquisition","C31:J60","acquisition_waterfall"],
["Assumptions","C34:J77","assumptions_working_capital"],["Assumptions","C78:J"+(driverRow+4),"assumptions_financing"],
["Actuals","C41:J87","actuals_balance_cash_flow"],["Actuals","C88:J128","actuals_equity_disclosures"],
["Actuals","C129:J158","opening_mapping"],["Actuals","C"+(sourceRegistryStart+18)+":L"+actualRow,"note_locators"],
];
for(const[name,range,filename]of views){
  const preview=await wb.render({sheetName:name,range,scale:1.5,format:"png"});
  await fs.writeFile(path.join(outputDir,filename+".png"),new Uint8Array(await preview.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(outputDir,"wdfc_corporate_acquisition.xlsx"));
console.log(JSON.stringify({output:path.join(outputDir,"wdfc_corporate_acquisition.xlsx"),case_results:verification.case_results,changes:verification.changes,error_scan:verification.error_scan}));
