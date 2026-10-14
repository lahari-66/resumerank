// Shared helpers for every ResumeRank page. Values from the API are only ever inserted with
// textContent (see el()), never innerHTML, so a candidate's name cannot inject markup.
const RR = (() => {
  const API = ((window.RESUMERANK_CONFIG || {}).apiBaseUrl || "").replace(/\/+$/, "");
  const KEY_STORE = "resumerank.recruiterKey";
  const THEME_STORE = "resumerank.theme";

  // dark mode: <html data-theme="dark|light">, remembered per browser in localStorage
  function savedTheme() {
    try { return localStorage.getItem(THEME_STORE); } catch (e) { return null; }
  }
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(THEME_STORE, theme); } catch (e) { /* storage blocked */ }
    document.dispatchEvent(new CustomEvent("rr-theme", { detail: theme }));
  }
  document.documentElement.setAttribute("data-theme", savedTheme() ||
    (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  function theme() { return document.documentElement.getAttribute("data-theme"); }

  function recruiterKey() {
    try { return sessionStorage.getItem(KEY_STORE) || ""; } catch (e) { return ""; }
  }
  function setRecruiterKey(value) {
    try {
      if (value) sessionStorage.setItem(KEY_STORE, value);
      else sessionStorage.removeItem(KEY_STORE);
    } catch (e) { /* storage blocked: key lasts for this page only */ }
  }

  async function api(path, { method = "GET", body, recruiter = false } = {}) {
    if (!API) throw new Error("config.js is missing the API URL");
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (recruiter && recruiterKey()) headers["x-recruiter-key"] = recruiterKey();
    const res = await fetch(API + path, {
      method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) {
      const msg = res.status === 429 ? "too many requests – the API is throttling, try again in a moment"
        : (data.error || data.message || `request failed with status ${res.status}`);
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  // Request a pre-signed URL and PUT the file straight to S3.
  async function uploadResume(jobId, file, name, email) {
    const body = { jobId, name, contentType: "application/pdf", fileSize: file.size };
    if (email) body.email = email;
    const signed = await api("/upload-url", { method: "POST", body });
    const put = await fetch(signed.uploadUrl, { method: "PUT", headers: signed.headers, body: file });
    if (!put.ok) throw new Error(`upload to storage failed with status ${put.status}`);
    return signed;
  }

  function el(tag, opts = {}, children = []) {
    const node = document.createElement(tag);
    if (opts.text !== undefined && opts.text !== null) node.textContent = String(opts.text);
    if (opts.cls) node.className = opts.cls;
    if (opts.attrs) Object.entries(opts.attrs).forEach(([k, v]) => node.setAttribute(k, v));
    if (opts.on) Object.entries(opts.on).forEach(([k, v]) => node.addEventListener(k, v));
    children.forEach((c) => c && node.appendChild(c));
    return node;
  }

  function chips(list, kind, empty = "–") {
    const wrap = el("span");
    if (!list || !list.length) { wrap.appendChild(el("span", { text: empty, cls: "meta" })); return wrap; }
    list.forEach((s) => wrap.appendChild(el("span", { text: s, cls: "chip " + kind })));
    return wrap;
  }

  function band(score) {
    if (score >= 75) return "high";
    if (score >= 50) return "mid";
    return "low";
  }

  function scoreBadge(c) {
    const scored = c.status === "SCORED";
    return el("span", { text: scored ? c.score : "–", cls: "score " + (scored ? band(c.score) : "none") });
  }

  function when(iso) {
    if (!iso) return "–";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString();
  }

  function show(box, text, kind) {
    box.textContent = text;
    box.className = "message show " + kind;
  }
  function hide(box) { box.className = "message"; }

  function param(name) { return new URLSearchParams(location.search).get(name) || ""; }

  function nav(active) {
    const links = [
      ["index.html", "Home"], ["recruiter.html", "Recruiter dashboard"],
      ["upload.html", "Apply"], ["status.html", "Track application"],
    ];
    const bar = el("header", { cls: "topbar" }, [
      el("a", { cls: "brand", attrs: { href: "index.html" } }, [
        el("span", { cls: "brand-mark", text: "RR" }), el("span", { text: "ResumeRank" }),
      ]),
      el("nav", { cls: "nav-links" }, links.map(([href, label]) =>
        el("a", { text: label, cls: href === active ? "active" : "", attrs: { href } }))),
      el("span", { cls: "nav-tag", text: "Serverless on AWS" }),
      el("button", {
        cls: "theme-toggle", text: theme() === "dark" ? "☀ Light" : "☾ Dark",
        attrs: { type: "button", "aria-label": "Toggle dark mode" },
        on: { click: (e) => {
          applyTheme(theme() === "dark" ? "light" : "dark");
          e.currentTarget.textContent = theme() === "dark" ? "☀ Light" : "☾ Dark";
        } },
      }),
    ]);
    document.body.prepend(bar);
  }

  return { API, api, uploadResume, el, chips, band, scoreBadge, when, show, hide, param, nav,
           recruiterKey, setRecruiterKey, theme };
})();
