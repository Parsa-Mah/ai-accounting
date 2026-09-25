// pages/export.js — export UI. The CSV/PDF endpoints land in Phase 10;
// this page is a placeholder until then.
import { esc } from "../ui.js";

export default {
  async render(container) {
    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">Export</h1>
          <p class="page-sub">Download your books as CSV or PDF.</p>
        </div>
      </div>
      <div class="card">
        <h2>Coming soon</h2>
        <p class="muted">
          Export endpoints (CSV and PDF via ReportLab) are built in Phase 10.
          Once available, you will be able to export the general ledger, trial
          balance, financial statements, and journal to CSV or PDF from here.
        </p>
        <div class="empty">No export endpoints are wired up yet.</div>
      </div>
    `;
  },
};
