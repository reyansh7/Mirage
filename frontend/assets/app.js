(() => {
  const API = "";
  const state = {
    sessions: [],
    filter: "all",
    selectedId: null,
    replayTimer: null,
    replayFrames: [],
    replayIdx: 0,
  };

  const $ = (id) => document.getElementById(id);
  const sessionList = $("session-list");
  const liveFeed = $("live-feed");
  const wsStatus = $("ws-status");
  const statActive = $("stat-active");
  const statEvents = $("stat-events");

  function shortId(id) {
    return id ? String(id).slice(0, 8) : "—";
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function fmtDuration(sec) {
    if (sec == null) return "—";
    const s = Math.floor(sec);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}m ${r}s`;
  }

  function eventSummary(ev) {
    const p = ev.payload || {};
    switch (ev.event_type) {
      case "COMMAND":
        return `Executed ${p.command || ""}`.trim();
      case "HTTP_REQUEST":
        return `${p.method || "GET"} ${p.path || p.url || ""}`;
      case "SQL_QUERY":
        return (p.query || "").slice(0, 80);
      case "AUTH_SUCCESS":
      case "AUTH_FAILURE":
      case "LOGIN":
        return `${ev.event_type} · ${p.user || p.username || "?"}`;
      case "FILE_READ":
      case "FILE_WRITE":
      case "FILE_DELETE":
        return `${ev.event_type} · ${p.filename || p.path || ""}`;
      case "DIRECTORY_CHANGE":
        return `cd ${p.cwd || ""}`;
      default:
        return ev.event_type;
    }
  }

  async function api(path) {
    const res = await fetch(`${API}${path}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  function renderSessions() {
    const filtered = state.sessions.filter((s) => {
      if (state.filter === "all") return true;
      return s.status === state.filter;
    });
    sessionList.innerHTML = filtered
      .map((s) => {
        const active = s.id === state.selectedId ? "active" : "";
        return `<li class="session-item ${active}" data-id="${s.id}">
          <div class="row1">
            <span>#${shortId(s.id)} · ${s.username || "unknown"}</span>
            <span class="badge ${s.status}">${s.status}</span>
          </div>
          <div class="row2">
            <span class="badge ${s.service}">${s.service}</span>
            ${s.source_ip || "—"} · ${fmtTime(s.start_time)} · ${fmtDuration(s.duration_seconds)}
            · ${s.event_count ?? 0} ev
          </div>
        </li>`;
      })
      .join("");

    sessionList.querySelectorAll(".session-item").forEach((el) => {
      el.addEventListener("click", () => selectSession(el.dataset.id));
    });

    const activeCount = state.sessions.filter((s) => s.status === "active").length;
    statActive.textContent = `${activeCount} active`;
  }

  function prependLive(ev, session) {
    const li = document.createElement("li");
    li.className = "live-item flash";
    const sid = ev.session_id || (session && session.id);
    li.innerHTML = `<div class="row1"><span>${fmtTime(ev.timestamp)}</span><span class="badge ${ev.service}">${ev.service}</span></div>
      <div class="row2">Session #${shortId(sid)} · ${eventSummary(ev)}</div>`;
    li.addEventListener("click", () => {
      if (sid) selectSession(sid);
    });
    liveFeed.prepend(li);
    while (liveFeed.children.length > 120) liveFeed.removeChild(liveFeed.lastChild);
    const n = Number(statEvents.textContent) || 0;
    statEvents.textContent = `${n + 1} events`;
  }

  async function loadSessions() {
    const data = await api("/sessions?limit=100");
    state.sessions = data.items || [];
    statActive.textContent = `${data.active ?? 0} active`;
    renderSessions();
  }

  async function loadEventsBootstrap() {
    const data = await api("/events?limit=40");
    liveFeed.innerHTML = "";
    (data.items || [])
      .slice()
      .reverse()
      .forEach((ev) => prependLive(ev));
    statEvents.textContent = `${data.total ?? data.items.length} events`;
  }

  async function selectSession(id) {
    state.selectedId = id;
    renderSessions();
    $("btn-timeline").disabled = false;
    $("btn-replay").disabled = false;
    $("timeline-view").classList.add("hidden");
    $("replay-view").classList.add("hidden");
    stopReplay();

    const s = await api(`/sessions/${id}`);
    $("detail-title").textContent = `Session #${shortId(id)}`;
    $("session-meta").classList.remove("empty");
    $("session-meta").innerHTML = `
      <strong>${s.service.toUpperCase()}</strong> · ${s.status}<br/>
      IP <strong>${s.source_ip || "—"}</strong> · ${s.country || "—"} · user <strong>${s.username || "—"}</strong><br/>
      Started ${fmtTime(s.start_time)} · Duration ${fmtDuration(s.duration_seconds)}
      ${s.end_reason ? ` · Ended: ${s.end_reason}` : ""}
    `;

    const [cmds, files] = await Promise.all([
      api(`/sessions/${id}/commands`),
      api(`/sessions/${id}/files`),
    ]);
    $("command-list").innerHTML = (cmds || [])
      .map(
        (c) =>
          `<li class="data-item"><span class="cmd">$ ${escapeHtml(c.command)}</span><br/><span class="muted">${fmtTime(c.timestamp)} · exit ${c.exit_code ?? "—"} · ${escapeHtml(c.cwd || "")}</span></li>`
      )
      .join("") || `<li class="data-item muted">No commands yet</li>`;
    $("file-list").innerHTML = (files || [])
      .map(
        (f) =>
          `<li class="data-item">${escapeHtml(f.action)} <strong>${escapeHtml(f.filename)}</strong><br/><span class="muted">${fmtTime(f.time)}</span></li>`
      )
      .join("") || `<li class="data-item muted">No file access yet</li>`;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function showTimeline() {
    if (!state.selectedId) return;
    const data = await api(`/sessions/${state.selectedId}/timeline`);
    const view = $("timeline-view");
    view.classList.remove("hidden");
    $("replay-view").classList.add("hidden");
    view.innerHTML = (data.items || [])
      .map(
        (t) =>
          `<li class="timeline-item"><div class="t">${fmtTime(t.timestamp)} · ${t.event_type}</div><div class="s">${escapeHtml(t.summary)}</div></li>`
      )
      .join("") || `<li class="timeline-item muted">Empty timeline</li>`;
  }

  async function showReplay() {
    if (!state.selectedId) return;
    const data = await api(`/sessions/${state.selectedId}/replay`);
    state.replayFrames = data.frames || [];
    state.replayIdx = 0;
    $("replay-view").classList.remove("hidden");
    $("timeline-view").classList.add("hidden");
    $("replay-term").textContent = "";
    $("replay-progress").textContent = `0 / ${state.replayFrames.length}`;
  }

  function stopReplay() {
    if (state.replayTimer) {
      clearTimeout(state.replayTimer);
      state.replayTimer = null;
    }
  }

  function playReplay() {
    stopReplay();
    const term = $("replay-term");
    if (!state.replayFrames.length) {
      term.textContent = "(nothing to replay)";
      return;
    }
    if (state.replayIdx >= state.replayFrames.length) {
      state.replayIdx = 0;
      term.textContent = "";
    }

    const step = () => {
      if (state.replayIdx >= state.replayFrames.length) {
        $("replay-progress").textContent = `done · ${state.replayFrames.length} frames`;
        return;
      }
      const f = state.replayFrames[state.replayIdx++];
      const user = f.user || "attacker";
      let chunk = "";
      if (f.command != null) {
        const prompt = f.prompt || `${user}@build-server-01:${f.cwd || "~"}$ `;
        chunk += `<span class="prompt">${escapeHtml(prompt)}</span>${escapeHtml(f.command)}\n`;
      }
      if (f.output) {
        chunk += `<span class="out">${escapeHtml(f.output)}</span>\n`;
      }
      term.innerHTML += chunk;
      term.scrollTop = term.scrollHeight;
      $("replay-progress").textContent = `${state.replayIdx} / ${state.replayFrames.length}`;
      state.replayTimer = setTimeout(step, f.delay_ms || 400);
    };
    step();
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/events`);
    ws.onopen = () => {
      wsStatus.textContent = "Live";
      wsStatus.className = "pill pill-ok";
    };
    ws.onclose = () => {
      wsStatus.textContent = "Reconnecting…";
      wsStatus.className = "pill pill-warn";
      setTimeout(connectWs, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        if (data.type === "event" && data.event) {
          prependLive(data.event, data.session);
          if (data.session) upsertSession(data.session);
          if (state.selectedId && data.event.session_id === state.selectedId) {
            selectSession(state.selectedId);
          }
        } else if (data.type === "session" && data.session) {
          upsertSession(data.session);
        }
      } catch (_) {
        /* ignore */
      }
    };
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 25000);
  }

  function upsertSession(s) {
    const idx = state.sessions.findIndex((x) => x.id === s.id);
    if (idx >= 0) state.sessions[idx] = { ...state.sessions[idx], ...s };
    else state.sessions.unshift(s);
    state.sessions.sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
    renderSessions();
  }

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.filter = chip.dataset.filter;
      renderSessions();
    });
  });

  $("btn-timeline").addEventListener("click", showTimeline);
  $("btn-replay").addEventListener("click", showReplay);
  $("replay-play").addEventListener("click", playReplay);
  $("replay-stop").addEventListener("click", stopReplay);

  Promise.all([loadSessions(), loadEventsBootstrap()])
    .then(connectWs)
    .catch((err) => {
      wsStatus.textContent = "API error";
      console.error(err);
    });

  setInterval(loadSessions, 15000);
})();
