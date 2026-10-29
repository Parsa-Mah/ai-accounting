// pages/ai.js — AI command center: ask about the books; the local LLM
// answers by acting through the typed MCP tools, with a visible tool
// trail and human-approved write proposals.
//
// The chat streams over SSE (POST /api/ai/chat). We parse the stream by
// hand (fetch + ReadableStream) rather than through api.js, which is for
// JSON responses. The conversation is held in a page-level `messages`
// array (OpenAI format) and refreshed from each `done` event.
//
// Chat history: conversations are persisted server-side (one row each,
// holding the full message array + the last completed turn). On load we
// open the most recent conversation and re-render its bubbles; a turn's
// trail chips + proposals come from the stored `last_done`. A conversation
// is created lazily on the first send of a new chat, and every `done`
// event is saved back with a PUT. Proposals re-loaded from a persisted
// conversation are "stale": re-approving one could double-execute a write
// that may already have happened, so their Approve/Reject buttons are
// disabled and an "expired" note is shown instead.
import { API } from "../api.js";
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
    let currentConvId = null; // id of the open conversation, or null for a new chat.
    let lastDone = null; // last `done` state: {answer, trail, proposals}.

    container.innerHTML = `
      <div class="page-head">
        <div>
          <h1 class="page-title">${t("ai.title")}</h1>
          <p class="page-sub">${t("ai.subtitle")}</p>
        </div>
        <div id="ai-status" class="ai-status"></div>
      </div>
      <div class="card ai-card">
        <div class="ai-convs-bar">
          <label class="field"><span>${t("ai.conversations")}</span>
            <select id="ai-conv-select"></select>
          </label>
          <button id="ai-new-chat" class="btn" type="button">${t("ai.new_chat")}</button>
        </div>
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
    const convSelect = document.getElementById("ai-conv-select");
    const newChatBtn = document.getElementById("ai-new-chat");
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
    // When `opts.stale` is set (a proposal re-loaded from a persisted
    // conversation), both buttons are disabled and an "expired" note is
    // shown: re-approving could double-execute an already-applied write.
    function addProposal(proposalsEl, proposal, opts = {}) {
      const stale = !!opts.stale;
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

      if (stale) {
        disableButtons();
        note.className = "proposal-note expired";
        note.textContent = t("ai.expired");
        return;
      }

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
          // round); refresh the conversation state for the next turn and
          // persist the completed turn (fire-and-forget — a failure surfaces
          // as a toast but never blocks the stream).
          dropThinking(turn);
          messages = event.messages;
          lastDone = {
            answer: event.answer,
            trail: event.trail,
            proposals: event.proposals,
          };
          if (currentConvId !== null) {
            API.saveConversation(currentConvId, {
              messages,
              last_done: lastDone,
            }).catch((err) =>
              toast(t("ai.save_failed", { detail: err.message }), "error"),
            );
          }
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

    // Re-render a loaded conversation: user + assistant text bubbles from
    // `messages`, then the last turn's trail chips + (stale) proposals from
    // `lastDone`. system/tool messages are not rendered — the system prompt
    // is boilerplate and tool results surface through the trail chips.
    function renderHistory() {
      messagesEl.innerHTML = "";
      let lastAiTurn = null;
      for (const m of messages) {
        if (m.role === "user") {
          addUserMessage(typeof m.content === "string" ? m.content : "");
        } else if (m.role === "assistant") {
          const turn = newAiTurn();
          dropThinking(turn);
          if (typeof m.content === "string" && m.content) {
            turn.text.textContent = m.content;
          }
          lastAiTurn = turn;
        }
      }
      if (!lastAiTurn) {
        messagesEl.innerHTML = `<div class="empty">${t("ai.empty")}</div>`;
      }
      if (lastDone && lastAiTurn) {
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === "assistant") {
          for (const ev of lastDone.trail || []) {
            addTrailChip(lastAiTurn.trail, ev);
          }
          for (const p of lastDone.proposals || []) {
            addProposal(lastAiTurn.proposals, p, { stale: true });
          }
        }
      }
      scrollBottom();
    }

    // Open a persisted conversation by id and render it.
    async function openConversation(id) {
      try {
        const detail = await API.getConversation(id);
        currentConvId = id;
        messages = detail.messages;
        lastDone = detail.last_done;
        renderHistory();
        inputEl.focus();
      } catch (err) {
        toast(err.message, "error");
      }
    }

    // Start a fresh (not-yet-persisted) chat.
    function newChat() {
      currentConvId = null;
      messages = [];
      lastDone = null;
      convSelect.value = "";
      messagesEl.innerHTML = `<div class="empty">${t("ai.empty")}</div>`;
      inputEl.focus();
    }

    // Populate the picker from the server list and open the most recent
    // conversation (the list is newest-first).
    async function loadConversations() {
      try {
        const convs = await API.listConversations();
        convSelect.innerHTML = "";
        if (convs.length === 0) {
          messagesEl.innerHTML = `<div class="empty">${t("ai.no_conversations")}</div>`;
          return;
        }
        for (const c of convs) {
          const opt = document.createElement("option");
          opt.value = String(c.id);
          opt.textContent = c.title;
          convSelect.appendChild(opt);
        }
        convSelect.value = String(convs[0].id);
        await openConversation(convs[0].id);
      } catch (err) {
        toast(err.message, "error");
      }
    }

    // Add a freshly created conversation to the picker (newest first) and
    // select it.
    function refreshConvSelect(created) {
      if (
        ![...convSelect.options].some((o) => o.value === String(created.id))
      ) {
        const opt = document.createElement("option");
        opt.value = String(created.id);
        opt.textContent = created.title;
        convSelect.insertBefore(opt, convSelect.firstChild);
      }
      convSelect.value = String(created.id);
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
        // Lazily create the conversation on the first send of a new chat so
        // the turn can be saved; the title is derived server-side from this
        // message. If creation fails we can't persist the turn, so abort.
        if (currentConvId === null) {
          try {
            const created = await API.createConversation({ messages });
            currentConvId = created.id;
            refreshConvSelect(created);
          } catch (err) {
            showTurnError(turn, t("ai.save_failed", { detail: err.message }));
            return;
          }
        }
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
    convSelect.addEventListener("change", (e) => {
      const id = Number(e.target.value);
      if (id) openConversation(id);
    });
    newChatBtn.addEventListener("click", newChat);

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
    loadConversations();
  },
};
