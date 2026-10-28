// pages/ai.js — AI command center: ask about the books; the local LLM
// answers by acting through the typed MCP tools, with a visible tool
// trail and human-approved write proposals.
//
// The chat streams over SSE (POST /api/ai/chat). We parse the stream by
// hand (fetch + ReadableStream) rather than through api.js, which is for
// JSON responses. The conversation is held in a page-level `messages`
// array (OpenAI format) and refreshed from each `done` event; a page
// reload starts a fresh chat (no server-side sessions).
import { esc, toast } from "../ui.js";
import { t } from "../i18n.js";

// Map a tool name to the SPA page that shows its records. Page-level links
// only (the SPA has no record-level deep links). Tools with no page (period
// locking, demo seed) return null and render a non-linking chip.
function toolPage(tool) {
  if (tool === "export_report") return "export";
  if (tool === "search_transactions") return "journal";
  if (/income_statement|balance_sheet/.test(tool)) return "statements";
  if (/ledger|trial_balance/.test(tool)) return "ledger";
  if (/journal|entry/.test(tool)) return "journal";
  if (/invoice/.test(tool)) return "invoices";
  if (/estimate|quote/.test(tool)) return "estimates";
  if (/bill/.test(tool)) return "bills";
  if (/budget/.test(tool)) return "budgets";
  if (/bank|reconcil/.test(tool)) return "reconciliation";
  if (/customer|item/.test(tool)) return "invoices";
  if (/vendor/.test(tool)) return "bills";
  if (/account/.test(tool)) return "accounts";
  return null;
}

// Human-readable key/value rows for a proposal's arguments (nested values
// collapse to JSON).
function formatArgs(args) {
  const entries = Object.entries(args || {});
  if (!entries.length) return "";
  return entries
    .map(([key, value]) => {
      const shown =
        value !== null && typeof value === "object"
          ? JSON.stringify(value)
          : String(value);
      return `<div class="proposal-arg"><span class="mono">${esc(key)}</span> = ${esc(shown)}</div>`;
    })
    .join("");
}

export default {
  async render(container) {
    let messages = []; // OpenAI-format conversation; refreshed from `done.messages`.
    let busy = false;

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("ai.title")}</h1>
          <p class="page-sub">${t("ai.subtitle")}</p>
        </div>
        <div id="ai-status" class="ai-status"></div>
      </div>
      <div class="card ai-card">
        <div id="ai-messages" class="ai-messages"></div>
        <div class="ai-input-row">
          <textarea id="ai-input" class="ai-input" rows="1"></textarea>
          <button id="ai-send" class="btn primary">${t("ai.send")}</button>
        </div>
      </div>
    `;

    const messagesEl = document.getElementById("ai-messages");
    const inputEl = document.getElementById("ai-input");
    const sendBtn = document.getElementById("ai-send");
    inputEl.placeholder = t("ai.placeholder");
    messagesEl.innerHTML = `<div class="empty">${t("ai.empty")}</div>`;

    function scrollBottom() {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function clearEmpty() {
      const empty = messagesEl.querySelector(".empty");
      if (empty) empty.remove();
    }

    // A user bubble.
    function addUserMessage(text) {
      clearEmpty();
      const msg = document.createElement("div");
      msg.className = "ai-msg user";
      const bubble = document.createElement("div");
      bubble.className = "ai-bubble";
      bubble.textContent = text;
      msg.appendChild(bubble);
      messagesEl.appendChild(msg);
      scrollBottom();
    }

    // An AI turn: text + tool trail + proposal cards, built up as events
    // stream in. Returns refs to the live sub-elements.
    function newAiTurn() {
      clearEmpty();
      const msg = document.createElement("div");
      msg.className = "ai-msg ai";
      const bubble = document.createElement("div");
      bubble.className = "ai-bubble";
      const thinking = document.createElement("div");
      thinking.className = "ai-thinking";
      const spinner = document.createElement("span");
      spinner.className = "ai-spinner";
      thinking.appendChild(spinner);
      thinking.appendChild(document.createTextNode(t("ai.thinking")));
      const text = document.createElement("div");
      text.className = "ai-text";
      const trail = document.createElement("div");
      trail.className = "ai-trail";
      trail.setAttribute("aria-label", t("ai.trail"));
      const proposals = document.createElement("div");
      proposals.className = "ai-proposals";
      bubble.append(thinking, text, trail, proposals);
      msg.appendChild(bubble);
      messagesEl.appendChild(msg);
      scrollBottom();
      return { bubble, text, trail, proposals, thinking };
    }

    function dropThinking(turn) {
      if (turn.thinking) {
        turn.thinking.remove();
        turn.thinking = null;
      }
    }

    // A trail chip: the tool that ran, with a ✓/✗ and a page link when one
    // exists. The summary goes in the tooltip.
    function addTrailChip(trailEl, toolEvent) {
      const page = toolPage(toolEvent.tool);
      const mark = toolEvent.ok ? "✓" : "✗";
      const tone = toolEvent.ok ? "ok" : "err";
      const chip = document.createElement(page ? "a" : "span");
      chip.className = "ai-chip" + (page ? " ai-chip-link" : "");
      chip.title = `${toolEvent.tool} — ${toolEvent.summary}`;
      if (page) chip.href = `#/${page}`;
      chip.innerHTML = `<span class="ai-chip-mark ${tone}">${mark}</span> ${esc(toolEvent.tool)}`;
      trailEl.appendChild(chip);
    }

    // A proposal card: the write tool + its arguments, with Approve/Reject.
    function addProposal(proposalsEl, proposal) {
      const card = document.createElement("div");
      card.className = "proposal";
      card.innerHTML = `
        <div class="proposal-head">
          <span class="proposal-title">${t("ai.proposal_title")}</span>
          <span class="mono proposal-tool">${esc(proposal.tool)}</span>
        </div>
        <div class="proposal-args">${formatArgs(proposal.args)}</div>
        <div class="proposal-actions">
          <button type="button" class="btn primary btn-approve">${t("ai.approve")}</button>
          <button type="button" class="btn btn-reject">${t("ai.reject")}</button>
        </div>
        <div class="proposal-note"></div>
      `;
      proposalsEl.appendChild(card);

      const approveBtn = card.querySelector(".btn-approve");
      const rejectBtn = card.querySelector(".btn-reject");
      const note = card.querySelector(".proposal-note");
      const disableButtons = () => {
        approveBtn.disabled = true;
        rejectBtn.disabled = true;
      };

      approveBtn.addEventListener("click", async () => {
        approveBtn.disabled = true;
        try {
          const res = await fetch("/api/ai/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool: proposal.tool, args: proposal.args }),
          });
          let data = null;
          try {
            data = await res.json();
          } catch {
            // non-JSON error body
          }
          if (res.ok) {
            note.className = "proposal-note ok";
            note.textContent = "✓ " + t("ai.approved");
            const page = toolPage(proposal.tool);
            if (page) {
              const link = document.createElement("a");
              link.href = `#/${page}`;
              link.textContent = " · " + t(`nav.${page}`);
              note.appendChild(link);
            }
            toast(t("ai.approved"), "success");
          } else {
            const detail = (data && data.detail) || String(res.status);
            note.className = "proposal-note err";
            note.textContent = detail;
            toast(detail, "error");
          }
        } catch (err) {
          note.className = "proposal-note err";
          note.textContent = String(err);
          toast(String(err), "error");
        } finally {
          disableButtons();
        }
      });

      rejectBtn.addEventListener("click", () => {
        note.className = "proposal-note rejected";
        note.textContent = "✗ " + t("ai.rejected");
        disableButtons();
      });
    }

    function showTurnError(turn, detail) {
      dropThinking(turn);
      const errEl = document.createElement("div");
      errEl.className = "ai-error";
      errEl.textContent = t("ai.error", { detail: String(detail) });
      turn.bubble.appendChild(errEl);
      scrollBottom();
    }

    function handleEvent(event, turn) {
      switch (event.type) {
        case "delta":
          dropThinking(turn);
          turn.text.textContent += event.text;
          scrollBottom();
          break;
        case "tool":
          dropThinking(turn);
          addTrailChip(turn.trail, event);
          scrollBottom();
          break;
        case "proposal":
          dropThinking(turn);
          addProposal(turn.proposals, event);
          scrollBottom();
          break;
        case "error":
          showTurnError(turn, event.detail);
          break;
        case "done":
          // Keep the accumulated delta text (done.answer is only the final
          // round); just refresh the conversation state for the next turn.
          dropThinking(turn);
          messages = event.messages;
          scrollBottom();
          break;
      }
    }

    // Parse the SSE body: frames are separated by a blank line, each event
    // is a `data: {json}` line.
    async function readStream(res, turn) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let sep;
        while ((sep = buf.indexOf("\n\n")) !== -1) {
          const frame = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          for (const line of frame.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            let event;
            try {
              event = JSON.parse(line.slice(6));
            } catch {
              continue;
            }
            handleEvent(event, turn);
          }
        }
      }
    }

    async function send() {
      if (busy) return;
      const content = inputEl.value.trim();
      if (!content) return;
      busy = true;
      sendBtn.disabled = true;
      inputEl.value = "";

      messages.push({ role: "user", content });
      addUserMessage(content);
      const turn = newAiTurn();

      try {
        const res = await fetch("/api/ai/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages }),
        });
        if (!res.ok || !res.body) {
          let detail = String(res.status);
          try {
            detail = (await res.json()).detail || detail;
          } catch {
            // non-JSON error body
          }
          showTurnError(turn, detail);
          return;
        }
        await readStream(res, turn);
      } catch (err) {
        showTurnError(turn, String(err));
      } finally {
        busy = false;
        sendBtn.disabled = false;
        inputEl.focus();
      }
    }

    sendBtn.addEventListener("click", send);
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });

    // Reachability check on load: a green dot + model name, or a down notice.
    async function loadStatus() {
      const statusEl = document.getElementById("ai-status");
      let html;
      try {
        const res = await fetch("/api/ai/status");
        const data = await res.json();
        if (data.reachable) {
          html = `<span class="ai-dot ok"></span>${esc(t("ai.status_ok", { model: data.model }))}`;
        } else {
          html = `<span class="ai-dot down"></span>${esc(t("ai.status_down"))}`;
        }
      } catch {
        html = `<span class="ai-dot down"></span>${esc(t("ai.status_down"))}`;
      }
      statusEl.innerHTML = html;
    }

    loadStatus();
  },
};
