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

  function nextSlotDelta() {
    var h = nowUTC(), best = null;
    for (var i = 0; i < D.slots.length; i++) {
      var d = D.slots[i] - h;
      if (d > 0 && (best === null || d < best)) best = d;
    }
    if (best === null) best = D.slots[0] + 24 - h; // tomorrow's first slot
    return best;
  }

  function fmtDelta(hours) {
    var m = Math.max(1, Math.round(hours * 60));
    var hh = Math.floor(m / 60), mm = m % 60;
    return hh > 0 ? hh + "h " + mm + "m" : mm + "m";
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
    setAll("data-desk-next", ph === "publish"
      ? "publish window open now"
      : "next publish window in " + fmtDelta(nextSlotDelta()));

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

  update();
  var reduced = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  setInterval(update, reduced ? 20000 : TICK_MS);
})();
