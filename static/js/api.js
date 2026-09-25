// api.js — thin fetch wrapper over the REST API.
//
// Session cookies are sent automatically for same-origin requests
// (the cookie is HttpOnly + SameSite=Lax, so JS never sees it).

function withQuery(path, params) {
  if (!params) return path;
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      qs.set(key, value);
    }
  }
  const s = qs.toString();
  return s ? `${path}?${s}` : path;
}

async function request(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    // No JSON body (e.g. empty 2xx).
  }
  if (!res.ok) {
    let detail = data && (data.detail || data.message);
    if (typeof detail !== "string") {
      // FastAPI validation errors come back as a list of {msg, ...}.
      if (Array.isArray(detail)) {
        detail = detail.map((d) => d.msg).join("; ");
      } else {
        detail = `Request failed (${res.status})`;
      }
    }
    const err = new Error(detail);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const API = {
  // --- auth ---
  authStatus: () => request("GET", "/api/auth/status"),
  setup: (username, password) =>
    request("POST", "/api/auth/setup", { username, password }),
  login: (username, password) =>
    request("POST", "/api/auth/login", { username, password }),
  logout: () => request("POST", "/api/auth/logout"),
  me: () => request("GET", "/api/auth/me"),

  // --- accounts ---
  listAccounts: (params) => request("GET", withQuery("/api/accounts", params)),
  createAccount: (body) => request("POST", "/api/accounts", body),
  getAccount: (id) => request("GET", `/api/accounts/${id}`),
  updateAccount: (id, body) => request("PATCH", `/api/accounts/${id}`, body),
  deactivateAccount: (id) =>
    request("POST", `/api/accounts/${id}/deactivate`),

  // --- journal ---
  listJournal: (params) => request("GET", withQuery("/api/journal", params)),
  getJournal: (id) => request("GET", `/api/journal/${id}`),
  createJournal: (body) => request("POST", "/api/journal", body),
  voidJournal: (id) => request("POST", `/api/journal/${id}/void`),

  // --- ledger ---
  generalLedger: (accountId, params) =>
    request(
      "GET",
      withQuery(`/api/ledger/accounts/${accountId}/transactions`, params),
    ),
  trialBalance: (params) =>
    request("GET", withQuery("/api/ledger/trial-balance", params)),

  // --- reports ---
  incomeStatement: (params) =>
    request("GET", withQuery("/api/reports/income-statement", params)),
  balanceSheet: (params) =>
    request("GET", withQuery("/api/reports/balance-sheet", params)),

  // --- parties ---
  listCustomers: () => request("GET", "/api/customers"),
  createCustomer: (body) => request("POST", "/api/customers", body),
  listVendors: () => request("GET", "/api/vendors"),
  createVendor: (body) => request("POST", "/api/vendors", body),

  // --- items ---
  listItems: (params) => request("GET", withQuery("/api/items", params)),
  createItem: (body) => request("POST", "/api/items", body),
  updateItem: (id, body) => request("PATCH", `/api/items/${id}`, body),
  deactivateItem: (id) => request("POST", `/api/items/${id}/deactivate`),

  // --- invoices (AR) ---
  listInvoices: (params) => request("GET", withQuery("/api/invoices", params)),
  getInvoice: (id) => request("GET", `/api/invoices/${id}`),
  createInvoice: (body) => request("POST", "/api/invoices", body),
  payInvoice: (id, body) => request("POST", `/api/invoices/${id}/pay`, body),
  voidInvoice: (id) => request("POST", `/api/invoices/${id}/void`),

  // --- estimates ---
  listEstimates: (params) =>
    request("GET", withQuery("/api/estimates", params)),
  getEstimate: (id) => request("GET", `/api/estimates/${id}`),
  createEstimate: (body) => request("POST", "/api/estimates", body),
  convertEstimate: (id) => request("POST", `/api/estimates/${id}/convert`),

  // --- bills (AP) ---
  listBills: (params) => request("GET", withQuery("/api/bills", params)),
  getBill: (id) => request("GET", `/api/bills/${id}`),
  createBill: (body) => request("POST", "/api/bills", body),
  payBill: (id, body) => request("POST", `/api/bills/${id}/pay`, body),
  voidBill: (id) => request("POST", `/api/bills/${id}/void`),

  // --- budgets ---
  listBudgets: (params) => request("GET", withQuery("/api/budgets", params)),
  getBudget: (id) => request("GET", `/api/budgets/${id}`),
  createBudget: (body) => request("POST", "/api/budgets", body),
  updateBudget: (id, body) => request("PATCH", `/api/budgets/${id}`, body),
  deleteBudget: (id) => request("DELETE", `/api/budgets/${id}`),
  budgetReport: (params) =>
    request("GET", withQuery("/api/budgets/report", params)),

  // --- reconciliation ---
  bankAccounts: () => request("GET", "/api/reconciliation/accounts"),
  listReconciliations: (params) =>
    request("GET", withQuery("/api/reconciliation", params)),
  getReconciliation: (id) => request("GET", `/api/reconciliation/${id}`),
  createReconciliation: (body) =>
    request("POST", "/api/reconciliation", body),
  deleteReconciliation: (id) =>
    request("DELETE", `/api/reconciliation/${id}`),
};
