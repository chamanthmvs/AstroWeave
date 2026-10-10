/* AstroWeave single-page frontend.
 * Talks to the FastAPI backend on the same origin (no CORS needed).
 * State (token / user / current conversation) lives in localStorage so a
 * refresh keeps you signed in. */
(function () {
  "use strict";

  var API = window.location.origin; // served by FastAPI from the same origin
  var LS = {
    token: "astroweave:token",
    user: "astroweave:user",
    convo: "astroweave:conversation_id",
    session: "astroweave:session_id",
    theme: "astroweave:theme",
  };

  // --- tiny helpers --------------------------------------------------------
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  function store(key, val) {
    try {
      if (val === null) localStorage.removeItem(key);
      else localStorage.setItem(key, typeof val === "string" ? val : JSON.stringify(val));
    } catch (e) {}
  }
  function load(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function loadJSON(key) {
    var raw = load(key);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return null; }
  }

  var state = {
    token: load(LS.token),
    user: loadJSON(LS.user),
    conversationId: load(LS.convo),
    sessionId: load(LS.session),
  };

  // --- API ----------------------------------------------------------------
  function api(path, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (state.token) headers["Authorization"] = "Bearer " + state.token;
    return fetch(API + path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    }).then(function (res) {
      return res.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
        if (!res.ok) {
          var err = new Error("HTTP " + res.status);
          err.status = res.status;
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  function errorMessage(err) {
    if (err && err.data) {
      var d = err.data.detail !== undefined ? err.data.detail : err.data;
      if (typeof d === "string") return d;
      if (d && d.message) return d.message;
      if (Array.isArray(d) && d.length && d[0].msg) return d.map(function (x) { return x.msg; }).join("; ");
      try { return JSON.stringify(d); } catch (e) {}
    }
    if (err && err.message) return err.message;
    return "Something went wrong.";
  }

  // --- Theme ---------------------------------------------------------------
  function currentTheme() {
    var t = load(LS.theme);
    if (t === "light" || t === "dark") return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    $$("[data-theme-toggle]").forEach(function (b) { b.textContent = t === "dark" ? "☀️" : "🌙"; });
  }
  function initTheme() {
    applyTheme(currentTheme());
    $$("[data-theme-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var next = currentTheme() === "dark" ? "light" : "dark";
        store(LS.theme, next);
        applyTheme(next);
      });
    });
  }

  // --- View switching ------------------------------------------------------
  function showView(name) {
    $("#auth-view").classList.toggle("hidden", name !== "auth");
    $("#app-view").classList.toggle("hidden", name !== "app");
  }

  function initials(name) {
    if (!name) return "··";
    var parts = name.trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "··";
    var first = parts[0][0] || "";
    var last = parts.length > 1 ? (parts[parts.length - 1][0] || "") : "";
    return (first + last).toUpperCase() || "··";
  }

  function setUser(user, token) {
    state.user = user;
    state.token = token;
    store(LS.user, user);
    store(LS.token, token);
  }

  function signOut() {
    state.user = null; state.token = null;
    state.conversationId = null; state.sessionId = null;
    store(LS.user, null); store(LS.token, null);
    store(LS.convo, null); store(LS.session, null);
    showView("auth");
  }

  // ========================================================================
  // Auth view
  // ========================================================================
  function initAuth() {
    $$("[data-auth-tab]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        var which = tab.getAttribute("data-auth-tab");
        $$("[data-auth-tab]").forEach(function (t) { t.classList.toggle("active", t === tab); });
        $("#signin-form").classList.toggle("hidden", which !== "signin");
        $("#register-form").classList.toggle("hidden", which !== "register");
      });
    });

    // Sign in
    $("#signin-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var f = e.target, errEl = $("[data-error]", f);
      errEl.textContent = "";
      var btn = $("button[type=submit]", f);
      btn.disabled = true; btn.textContent = "Signing in…";
      api("/auth/sign-in", { method: "POST", body: {
        email: f.email.value.trim(), password: f.password.value,
      } }).then(function (data) {
        setUser(data.user, data.token);
        enterApp();
      }).catch(function (err) {
        errEl.textContent = err.status === 401 ? "Invalid email or password." : errorMessage(err);
      }).finally(function () {
        btn.disabled = false; btn.textContent = "Continue";
      });
    });

    // Register — geocode
    var geocoded = null;
    var regForm = $("#register-form");
    var regSubmit = $("button[type=submit]", regForm);
    var geoResult = $("[data-geo-result]", regForm);

    function resetGeo() {
      geocoded = null;
      regSubmit.disabled = true;
      geoResult.textContent = "";
      geoResult.classList.remove("ok-text");
    }
    regForm.place.addEventListener("input", resetGeo);

    $("[data-geocode]", regForm).addEventListener("click", function () {
      var place = regForm.place.value.trim();
      if (!place) { geoResult.textContent = "Enter a place name first."; return; }
      geoResult.classList.remove("ok-text");
      geoResult.textContent = "Looking up…";
      api("/geocode?place=" + encodeURIComponent(place)).then(function (data) {
        geocoded = data;
        regSubmit.disabled = false;
        geoResult.classList.add("ok-text");
        geoResult.textContent = "✓ " + (data.display_name || place) +
          " · " + data.latitude.toFixed(3) + ", " + data.longitude.toFixed(3);
      }).catch(function (err) {
        resetGeo();
        geoResult.textContent = errorMessage(err);
      });
    });

    regForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = $("[data-error]", regForm);
      errEl.textContent = "";
      if (!geocoded) { errEl.textContent = "Find your birth place coordinates first."; return; }
      if (regForm.password.value.length < 8) { errEl.textContent = "Password must be at least 8 characters."; return; }
      regSubmit.disabled = true; regSubmit.textContent = "Creating…";
      api("/auth/register", { method: "POST", body: {
        name: regForm.name.value.trim(),
        email: regForm.email.value.trim(),
        password: regForm.password.value,
        birth_details: {
          date: regForm.date.value,
          time: regForm.time.value.length === 5 ? regForm.time.value + ":00" : regForm.time.value,
          latitude: geocoded.latitude,
          longitude: geocoded.longitude,
          utc_offset_hours: geocoded.utc_offset_hours,
          place_name: geocoded.display_name || regForm.place.value.trim(),
          date_known: true,
        },
      } }).then(function (data) {
        setUser(data.user, data.token);
        enterApp();
      }).catch(function (err) {
        errEl.textContent = errorMessage(err);
      }).finally(function () {
        regSubmit.disabled = false; regSubmit.textContent = "Create account";
      });
    });
  }

  // ========================================================================
  // App view
  // ========================================================================
  var busy = false;

  function enterApp() {
    showView("app");
    var name = (state.user && (state.user.name || state.user.email)) || "Account";
    $("[data-user-name]").textContent = name;
    $("[data-user-email]").textContent = (state.user && state.user.email) || "";
    $("[data-avatar]").textContent = initials(state.user && state.user.name);
    refreshConversations();
    if (state.conversationId) loadMessages(state.conversationId);
    else renderThread([]);
  }

  function refreshConversations() {
    api("/conversations?limit=50").then(function (data) {
      renderConversations(data.conversations || []);
    }).catch(function () { /* keep whatever is shown */ });
  }

  function renderConversations(list) {
    var wrap = $("[data-convo-list]");
    wrap.innerHTML = "";
    if (!list.length) {
      wrap.innerHTML = '<p class="note" style="padding:0.4rem 0.6rem">No conversations yet.</p>';
      return;
    }
    list.forEach(function (c) {
      var row = document.createElement("div");
      row.className = "convo" + (c.conversation_id === state.conversationId ? " active" : "");
      var title = document.createElement("span");
      title.className = "convo-title";
      title.textContent = c.title || "Untitled reading";
      var del = document.createElement("button");
      del.className = "icon-btn convo-del";
      del.title = "Delete conversation";
      del.textContent = "🗑";
      row.appendChild(title);
      row.appendChild(del);
      title.addEventListener("click", function () { selectConversation(c.conversation_id); });
      del.addEventListener("click", function (e) {
        e.stopPropagation();
        deleteConversation(c.conversation_id);
      });
      wrap.appendChild(row);
    });
  }

  function selectConversation(id) {
    state.conversationId = id;
    state.sessionId = null; // the backend issues a fresh session for this client
    store(LS.convo, id); store(LS.session, null);
    refreshConversations();
    loadMessages(id);
    closeNav();
  }

  function newConversation() {
    state.conversationId = null;
    state.sessionId = null;
    store(LS.convo, null); store(LS.session, null);
    refreshConversations();
    renderThread([]);
    closeNav();
    $("[data-run-form] textarea").focus();
  }

  function deleteConversation(id) {
    api("/conversations/" + encodeURIComponent(id), { method: "DELETE" }).then(function () {
      if (id === state.conversationId) newConversation();
      else refreshConversations();
    }).catch(function (err) { showBanner(errorMessage(err)); });
  }

  function loadMessages(id) {
    api("/conversations/" + encodeURIComponent(id) + "/messages?limit=50").then(function (data) {
      renderThread(data.messages || []);
    }).catch(function () { renderThread([]); });
  }

  // --- Rendering messages --------------------------------------------------
  function renderMarkdown(text) {
    try {
      var html = window.marked ? window.marked.parse(text) : text;
      return window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
    } catch (e) {
      return document.createTextNode(text).textContent;
    }
  }

  function messageEl(role, content, isMarkdown) {
    var msg = document.createElement("div");
    msg.className = "msg " + (role === "user" ? "user" : "ai");
    var icon = document.createElement("div");
    icon.className = "msg-role";
    icon.textContent = role === "user" ? "🙂" : "✦";
    var body = document.createElement("div");
    body.className = "msg-body";
    if (role === "user" || !isMarkdown) body.textContent = content;
    else body.innerHTML = renderMarkdown(content);
    msg.appendChild(icon);
    msg.appendChild(body);
    return msg;
  }

  function traceSummary(trace) {
    if (!Array.isArray(trace)) return "";
    var names = trace
      .filter(function (t) { return t.step === "specialist" && t.specialist; })
      .map(function (t) { return t.specialist.charAt(0).toUpperCase() + t.specialist.slice(1); });
    if (!names.length) return "";
    return "Consulted: " + names.join(" · ");
  }

  function renderThread(messages) {
    var thread = $("[data-thread]");
    thread.innerHTML = "";
    if (!messages.length) {
      var empty = document.createElement("div");
      empty.className = "empty";
      empty.innerHTML = '<div class="big">What\'s on your mind?</div>' +
        '<div>Ask about your career, relationships, finances, or the next chapter — the specialists will weigh in.</div>';
      thread.appendChild(empty);
      return;
    }
    messages.forEach(function (m) {
      thread.appendChild(messageEl(m.role, m.content, m.role !== "user"));
    });
    scrollThread();
  }

  function scrollThread() {
    var thread = $("[data-thread]");
    thread.scrollTop = thread.scrollHeight;
  }

  function appendTyping() {
    var thread = $("[data-thread]");
    var msg = document.createElement("div");
    msg.className = "msg ai";
    msg.setAttribute("data-typing", "");
    msg.innerHTML = '<div class="msg-role">✦</div>' +
      '<div class="msg-body"><span class="typing"><span></span><span></span><span></span></span></div>';
    thread.appendChild(msg);
    scrollThread();
    return msg;
  }

  function uuid() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0, v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  // --- Submitting a reading ------------------------------------------------
  function sendQuery(query, methodology) {
    if (busy) return;
    busy = true;
    showBanner(null);
    var sendBtn = $("[data-send]");
    sendBtn.disabled = true;

    // Drop the empty-state if present, then show the question + typing bubble.
    if ($("[data-empty]", $("[data-thread]")) || !$(".msg", $("[data-thread]"))) {
      $("[data-thread]").innerHTML = "";
    }
    $("[data-thread]").appendChild(messageEl("user", query, false));
    var typingEl = appendTyping();

    var messageId = uuid();

    function attempt(retriesLeft) {
      api("/run", { method: "POST", body: {
        query: query,
        methodology: methodology,
        message_id: messageId,
        conversation_id: state.conversationId,
        session_id: state.sessionId,
      } }).then(function (data) {
        state.conversationId = data.conversation_id;
        state.sessionId = data.session_id;
        store(LS.convo, data.conversation_id);
        store(LS.session, data.session_id);
        typingEl.remove();
        var aiMsg = messageEl("assistant", data.answer || "_(no answer returned)_", true);
        var summary = traceSummary(data.execution_trace);
        if (summary) {
          var trace = document.createElement("div");
          trace.className = "msg-trace";
          trace.textContent = summary;
          $(".msg-body", aiMsg).appendChild(trace);
        }
        $("[data-thread]").appendChild(aiMsg);
        scrollThread();
        refreshConversations();
        done();
      }).catch(function (err) {
        var code = err.data && err.data.detail && err.data.detail.code;
        if (err.status === 409 && code === "request_in_progress" && retriesLeft > 0) {
          setTimeout(function () { attempt(retriesLeft - 1); }, 2500);
          return;
        }
        typingEl.remove();
        if (err.status === 401) { showBanner("Your session expired — please sign in again."); setTimeout(signOut, 1500); }
        else showBanner("Reading failed: " + errorMessage(err));
        done();
      });
    }

    function done() {
      busy = false;
      sendBtn.disabled = false;
    }

    attempt(24); // ~60s of polling if the backend reports in-progress
  }

  function showBanner(text) {
    var b = $("[data-banner]");
    if (!text) { b.classList.add("hidden"); b.textContent = ""; return; }
    b.textContent = text;
    b.classList.remove("hidden");
  }

  // --- Mobile nav ----------------------------------------------------------
  function openNav() { $("#app-view").classList.add("nav-open"); $("[data-scrim]").classList.remove("hidden"); }
  function closeNav() { $("#app-view").classList.remove("nav-open"); $("[data-scrim]").classList.add("hidden"); }

  function initApp() {
    $("[data-new-convo]").addEventListener("click", newConversation);
    $("[data-signout]").addEventListener("click", signOut);
    $("[data-menu]").addEventListener("click", openNav);
    $("[data-scrim]").addEventListener("click", closeNav);

    var form = $("[data-run-form]");
    var textarea = form.query;

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = textarea.value.trim();
      if (!q) return;
      sendQuery(q, form.methodology.value);
      textarea.value = "";
      autoGrow();
    });

    // Enter to send, Shift+Enter for newline.
    textarea.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
    function autoGrow() {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 220) + "px";
    }
    textarea.addEventListener("input", autoGrow);
  }

  // ========================================================================
  // Boot
  // ========================================================================
  initTheme();
  initAuth();
  initApp();

  if (state.token && state.user) {
    // Verify the saved token is still valid before trusting it.
    api("/auth/me").then(function () { enterApp(); }).catch(function () { signOut(); });
  } else {
    showView("auth");
  }
})();
