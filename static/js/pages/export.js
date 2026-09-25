// pages/export.js — download reports as CSV or PDF.
import { API } from "../api.js";
import { esc, toast } from "../ui.js";

// Each report lists which optional fields it exposes. "account" is a required
// account picker (general ledger); "account_opt"/"customer"/"vendor" are
// optional filters; "from"/"to"/"asof" are date fields; "voided" toggles
// whether voided documents/entries are included.
const REPORTS = {
  "general-ledger": { label: "General ledger", fields: ["account", "from", "to", "voided"] },
  "trial-balance": { label: "Trial balance", fields: ["asof"] },
  "income-statement": { label: "Income statement", fields: ["from", "to"] },
  "balance-sheet": { label: "Balance sheet", fields: ["asof"] },
  journal: { label: "Journal", fields: ["account_opt", "from", "to", "voided"] },
  invoices: { label: "Invoices", fields: ["customer", "voided"] },
  bills: { label: "Bills", fields: ["vendor", "voided"] },
};

export default {
  async render(container) {
    const [accounts, customers, vendors] = await Promise.all([
      API.listAccounts({ include_inactive: true }),
      API.listCustomers(),
      API.listVendors(),
    ]);
    const accountOptions = accounts
      .map((a) => `<option value="${a.id}">${esc(a.number)} — ${esc(a.name)}</option>`)
      .join("");
    const partyOptions = (list) =>
      list.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Export</h1>
          <p class="page-sub">Download your books as CSV or PDF.</p>
        </div>
      </div>
      <div class="card">
        <form id="export-form" class="toolbar" novalidate>
          <label class="field" style="min-width:220px"><span>Report</span>
            <select id="ex-report">
              ${Object.entries(REPORTS)
                .map(([key, r]) => `<option value="${key}">${esc(r.label)}</option>`)
                .join("")}
            </select>
          </label>
          <div id="ex-fields" class="toolbar" style="flex:1"></div>
          <label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px">
            <span style="font-weight:500">Format</span>
            <select id="ex-format">
              <option value="csv">CSV</option>
              <option value="pdf">PDF</option>
            </select>
          </label>
          <button class="btn primary" type="submit" style="align-self:flex-end">Download</button>
        </form>
        <p class="muted" id="ex-note" style="margin-top:10px">
          The file downloads directly; your session cookie is sent automatically.
        </p>
      </div>
    `;

    const fieldsEl = container.querySelector("#ex-fields");
    const reportSel = container.querySelector("#ex-report");
    const formatSel = container.querySelector("#ex-format");

    function fieldHtml(kind) {
      switch (kind) {
        case "account":
          return `<label class="field" style="min-width:240px"><span>Account</span><select id="ex-account">${accountOptions}</select></label>`;
        case "account_opt":
          return `<label class="field" style="min-width:240px"><span>Account (filter)</span><select id="ex-account"><option value="">All accounts</option>${accountOptions}</select></label>`;
        case "customer":
          return `<label class="field"><span>Customer (filter)</span><select id="ex-customer"><option value="">All customers</option>${partyOptions(customers)}</select></label>`;
        case "vendor":
          return `<label class="field"><span>Vendor (filter)</span><select id="ex-vendor"><option value="">All vendors</option>${partyOptions(vendors)}</select></label>`;
        case "from":
          return `<label class="field"><span>From</span><input type="date" id="ex-from" /></label>`;
        case "to":
          return `<label class="field"><span>To</span><input type="date" id="ex-to" /></label>`;
        case "asof":
          return `<label class="field"><span>As of</span><input type="date" id="ex-asof" /></label>`;
        case "voided":
          return `<label class="field" style="flex-direction:row;align-items:center;gap:8px;padding-bottom:9px"><input type="checkbox" id="ex-voided" style="width:auto" checked /><span style="font-weight:500">Include voided</span></label>`;
        default:
          return "";
      }
    }

    function renderFields() {
      fieldsEl.innerHTML = REPORTS[reportSel.value].fields.map(fieldHtml).join("");
    }

    function val(id) {
      const el = container.querySelector(id);
      return el ? el.value : "";
    }
    function checked(id) {
      const el = container.querySelector(id);
      return el ? el.checked : true;
    }

    function buildParams() {
      const report = reportSel.value;
      const params = { format: formatSel.value };
      if (report === "general-ledger") {
        params.account_id = val("#ex-account");
        if (val("#ex-from")) params.date_from = val("#ex-from");
        if (val("#ex-to")) params.date_to = val("#ex-to");
        params.include_voided = checked("#ex-voided");
      } else if (report === "trial-balance") {
        if (val("#ex-asof")) params.as_of = val("#ex-asof");
      } else if (report === "income-statement") {
        if (val("#ex-from")) params.date_from = val("#ex-from");
        if (val("#ex-to")) params.date_to = val("#ex-to");
      } else if (report === "balance-sheet") {
        if (val("#ex-asof")) params.as_of = val("#ex-asof");
      } else if (report === "journal") {
        if (val("#ex-account")) params.account_id = val("#ex-account");
        if (val("#ex-from")) params.date_from = val("#ex-from");
        if (val("#ex-to")) params.date_to = val("#ex-to");
        params.include_voided = checked("#ex-voided");
      } else if (report === "invoices") {
        if (val("#ex-customer")) params.customer_id = val("#ex-customer");
        params.include_voided = checked("#ex-voided");
      } else if (report === "bills") {
        if (val("#ex-vendor")) params.vendor_id = val("#ex-vendor");
        params.include_voided = checked("#ex-voided");
      }
      return params;
    }

    reportSel.addEventListener("change", renderFields);

    container.querySelector("#export-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const report = reportSel.value;
      if (report === "general-ledger" && !val("#ex-account")) {
        toast("Choose an account to export its general ledger.", "error");
        return;
      }
      const params = buildParams();
      window.location.href = API.exportUrl(report, params);
      toast(`Downloading ${REPORTS[report].label} (${params.format.toUpperCase()})…`, "info");
    });

    renderFields();
  },
};
