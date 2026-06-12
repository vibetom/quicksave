/* QUICKSAVE live desk — client-side status board.
   Derives the desk's current posture from the publish schedule embedded at
   build time (window.QS_DESK). No network calls; the strip and the board
   always show what the desk is doing — or standing by to do — right now. */
(function () {
  "use strict";
  var D = window.QS_DESK;
  if (!D) return;

  var AGENTS = ["scout", "angle", "writer", "editor", "publisher"];

  // [agent, activity] pools per phase of the publish cycle.
  var POOLS = {
    idle: [
      ["scout", "sweeping the wires for fresh stories"],
      ["scout", "scanning release calendars, patch notes and review feeds"],
      ["scout", "watching for stories with momentum (last 72 hours)"],
      ["scout", "cross-checking rumor mills against official channels"],
      ["editor", "recalibrating the originality gate (7-gram scan)"],
      ["editor", "auditing source links on recent stories"],
      ["angle", "war-gaming takes nobody else is writing"],
      ["scout", "deduplicating topics against the last 14 days"],
      ["editor", "re-reading the standards checklist, as one does"],
      ["scout", "monitoring industry, hardware, indie and esports beats"],
      ["publisher", "verifying the static build is healthy"],
      ["publisher", "standing by — next publish window queued"]
    ],
    prep: [
      ["scout", "shortlisting story candidates for this slot"],
      ["scout", "collecting facts with sources: confirmed vs reported vs rumor"],
      ["angle", "developing the thesis for the next story"],
      ["angle", "drafting an honest-but-clicky headline"]
    ],
    publish: [
      ["writer", "drafting original prose — 450 to 700 words"],
      ["writer", "attributing every reported fact to the outlet that broke it"],
      ["editor", "running the plagiarism gate against every source"],
      ["editor", "standards review: rumor labels, headline payoff, tone"],
      ["publisher", "rebuilding the site and shipping the article"]
    ]
  };

  var STANDBY = {
    scout: "monitoring the wire",
    angle: "waiting for the next pitch",
    writer: "keyboard warm, awaiting an approved angle",
    editor: "gates armed: originality + standards",
    publisher: D.articles + " stories live and serving"
  };

  function nowUTC() {
    var d = new Date();
    return d.getUTCHours() + d.getUTCMinutes() / 60;
  }

  // prep = 15 min before a slot, publish = 15 min after; otherwise idle.
  function phase() {
    var h = nowUTC();
    for (var i = 0; i < D.slots.length; i++) {
      var s = D.slots[i];
      if (h >= s - 0.25 && h < s) return "prep";
      if (h >= s && h < s + 0.25) return "publish";
    }
    return "idle";
  }

  // The soonest upcoming publish slot as a real Date (handles the day
  // rollover), so we can render it in any timezone the viewer prefers.
  function nextSlotDate() {
    var now = new Date(), best = null;
    for (var i = 0; i < D.slots.length; i++) {
      var s = D.slots[i];
      var d = new Date(now);
      d.setUTCHours(Math.floor(s), Math.round((s % 1) * 60), 0, 0);
      if (d <= now) d.setUTCDate(d.getUTCDate() + 1); // already passed today
      if (best === null || d < best) best = d;
    }
    return best;
  }

  function fmtDelta(ms) {
    var m = Math.max(1, Math.round(ms / 60000));
    var hh = Math.floor(m / 60), mm = m % 60;
    return hh > 0 ? hh + "h " + mm + "m" : mm + "m";
  }

  // Timezone mode: "local" (auto-detected) or "utc". Persisted across visits.
  var tzMode = "local";
  try { tzMode = localStorage.getItem("qs_tz") || "local"; } catch (e) {}

  function fmtClock(date) {
    if (tzMode === "utc") {
      return ("0" + date.getUTCHours()).slice(-2) + ":" +
             ("0" + date.getUTCMinutes()).slice(-2) + " UTC";
    }
    try {
      return date.toLocaleTimeString([], {
        hour: "numeric", minute: "2-digit", timeZoneName: "short" });
    } catch (e) {
      return date.toLocaleTimeString();
    }
  }

  var TICK_MS = 7000;
  function tickIndex() { return Math.floor(Date.now() / TICK_MS); }

  function setAll(attr, text) {
    var els = document.querySelectorAll("[" + attr + "]");
    for (var i = 0; i < els.length; i++) els[i].textContent = text;
  }

  var lastLogged = -1;
  function appendLog(agent, text) {
    var feed = document.getElementById("desk-log");
    if (!feed) return;
    var t = tickIndex();
    if (t === lastLogged) return;
    lastLogged = t;

    var d = new Date();
    var stamp = ("0" + d.getUTCHours()).slice(-2) + ":" +
                ("0" + d.getUTCMinutes()).slice(-2) + ":" +
                ("0" + d.getUTCSeconds()).slice(-2);

    var line = document.createElement("div");
    line.className = "log-line";
    var time = document.createElement("span");
    time.className = "log-time";
    time.textContent = stamp + " UTC";
    var who = document.createElement("span");
    who.className = "log-agent log-" + agent;
    who.textContent = agent.toUpperCase();
    var what = document.createElement("span");
    what.textContent = " " + text;
    line.appendChild(time);
    line.appendChild(who);
    line.appendChild(what);
    feed.prepend(line);
    while (feed.children.length > 14) feed.removeChild(feed.lastChild);
  }

  function update() {
    var ph = phase();
    var pool = POOLS[ph];
    var entry = pool[tickIndex() % pool.length];
    var agent = entry[0], text = entry[1];

    setAll("data-desk-now", agent.toUpperCase() + " // " + text);
    if (ph === "publish") {
      setAll("data-desk-next", "publish window open now");
    } else {
      var next = nextSlotDate();
      setAll("data-desk-next", "next publish · " + fmtClock(next) +
        " · in " + fmtDelta(next - new Date()));
    }

    // Live Desk page extras: highlight the active agent + roll the log.
    if (document.getElementById("desk-board")) {
      for (var i = 0; i < AGENTS.length; i++) {
        var a = AGENTS[i];
        var card = document.getElementById("agent-" + a);
        if (card) card.classList.toggle("agent-active", a === agent);
        var line = document.getElementById("agent-" + a + "-status");
        if (line) line.textContent = (a === agent) ? text : STANDBY[a];
      }
      appendLog(agent, text);
    }
  }

  // Timezone toggle (Live Desk page). Flips local <-> UTC and remembers it.
  function syncToggle() {
    var btn = document.querySelector("[data-desk-tz-toggle]");
    if (btn) btn.textContent = tzMode === "utc" ? "Show in my time" : "Show in UTC";
  }
  var toggle = document.querySelector("[data-desk-tz-toggle]");
  if (toggle) {
    toggle.addEventListener("click", function () {
      tzMode = tzMode === "utc" ? "local" : "utc";
      try { localStorage.setItem("qs_tz", tzMode); } catch (e) {}
      syncToggle();
      update();
    });
    syncToggle();
  }

  update();
  var reduced = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  setInterval(update, reduced ? 20000 : TICK_MS);
})();
