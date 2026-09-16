const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = async (url, data) => {
  const opts = data === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) };
  const res = await fetch(url, opts);
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || "Actie mislukt");
  return json;
};
const money = cents => new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(cents / 100);
const app = $("#app");
let state = { lang: localStorage.getItem("itb_lang") || "nl", data: {}, adminTab: "overview", galleryFilter: "all", account: null };

const t = {
  nl: {
    nav: { home: "Home", prices: "Prijzen", gallery: "Galerij", subs: "Abonnementen", contact: "Contact", book: "Afspraak maken" },
    bookIntro: "Vul hieronder je gewenste afspraak in. Ik bekijk je aanvraag en bevestig de afspraak zo snel mogelijk.",
    login: "Login", account: "Account", admin: "Admin", logout: "Uitloggen"
  },
  en: {
    nav: { home: "Home", prices: "Prices", gallery: "Gallery", subs: "Memberships", contact: "Contact", book: "Book appointment" },
    bookIntro: "Enter your preferred appointment below. I will review your request and confirm it as soon as possible.",
    login: "Login", account: "Account", admin: "Admin", logout: "Log out"
  }
};
const tr = key => key.split(".").reduce((o, k) => o?.[k], t[state.lang]) || key;
const local = (obj, key) => obj[`${key}_${state.lang}`] || obj[`${key}_nl`] || "";

async function boot() {
  state.data = await api("/api/bootstrap");
  renderNav();
  route();
}

function renderNav() {
  $$("[data-i18n]").forEach(el => el.textContent = tr(el.dataset.i18n));
  $("#langBtn").textContent = state.lang.toUpperCase() + " / " + (state.lang === "nl" ? "EN" : "NL");
  const user = state.data.user;
  $("#loginLink").textContent = user ? (user.role === "admin" ? tr("admin") : tr("account")) : tr("login");
  $("#loginLink").href = user ? (user.role === "admin" ? "/admin" : "/account") : "/login";
  document.documentElement.lang = state.lang;
}

function go(path) {
  history.pushState(null, "", path);
  route();
  $("#nav").classList.remove("open");
}

function setMeta(title, desc) {
  document.title = `${title} | ITBCUTZ`;
  $('meta[name="description"]').setAttribute("content", desc);
}

function route() {
  const path = location.pathname;
  renderNav();
  if (path === "/prijzen") return prices();
  if (path === "/galerij") return gallery();
  if (path === "/abonnementen") return subscriptions();
  if (path === "/contact") return contact();
  if (path === "/afspraak-maken") return booking();
  if (path === "/login") return login();
  if (path === "/account") return account();
  if (path === "/admin") return admin();
  return home();
}

function home() {
  const d = state.data;
  setMeta("Barber Amsterdam-West", "ITBCUTZ voor fades, tapers, overgangen, lijnen en baarden in Amsterdam-West.");
  app.innerHTML = `
    <section class="hero">
      <div>
        <h1>ITBCUTZ</h1>
        <p>${d.settings[`slogan_${state.lang}`]}</p>
        <div class="btn-row"><a class="btn" href="/afspraak-maken" data-link>${tr("nav.book")}</a></div>
      </div>
      <div class="hero-media"><img src="/static/images/1720.jpg" alt="ITBCUTZ fade haircut Amsterdam-West"></div>
    </section>
    <section class="section light"><div class="wrap"><div class="eyebrow">Amsterdam-West</div><h2 class="title">ITBCUTZ</h2><p class="copy">${d.settings[`about_${state.lang}`]}</p></div></section>
    <section class="section dark"><div class="wrap"><div class="eyebrow">${state.lang === "nl" ? "Waarom ITBCUTZ?" : "Why ITBCUTZ?"}</div><div class="grid three">
      ${["Goede kwaliteit|High quality", "Scherpe prijzen|Sharp prices", "Persoonlijke service|Personal service"].map(x => {
        const parts = x.split("|"); return `<article class="card"><h3>${state.lang === "nl" ? parts[0] : parts[1]}</h3><p class="muted">${state.lang === "nl" ? "Strak, precies en rustig afgewerkt." : "Clean, precise and calmly finished."}</p></article>`;
      }).join("")}
    </div></div></section>
    <section class="section light"><div class="wrap"><div class="eyebrow">${state.lang === "nl" ? "Mijn werk" : "My work"}</div><h2 class="title">${state.lang === "nl" ? "Fades, lijnen en baarden." : "Fades, line-ups and beards."}</h2><div class="gallery">${d.gallery.slice(0,6).map(photo).join("")}</div><div class="btn-row"><a class="btn secondary" href="/galerij" data-link>${state.lang === "nl" ? "Bekijk alle foto's" : "View all photos"}</a></div></div></section>
    <section class="section dark"><div class="wrap"><h2 class="title">${state.lang === "nl" ? "Contact" : "Contact"}</h2>${contactBits()}</div></section>`;
  bindLinks();
}

function prices() {
  setMeta("Prijzen", "Bekijk ITBCUTZ prijzen voor fade, taper, baard, knippen en design lijnen.");
  app.innerHTML = `<section class="section light"><div class="wrap"><div class="eyebrow">ITBCUTZ</div><h1 class="title">${tr("nav.prices")}</h1><div class="price-list">${state.data.services.map(s => `<div class="price-row"><span>${local(s, "name")}</span><strong>${money(s.price_cents)}</strong></div>`).join("")}</div></div></section>`;
}

function photo(g) {
  return `<figure><img src="${g.image_url}" alt="${local(g, "alt") || g.title}" loading="lazy"></figure>`;
}

function gallery() {
  setMeta("Galerij", "ITBCUTZ galerij met taper fade, burst fade, overloop, baard en andere cuts.");
  const cats = ["all", "Taper Fade", "Burst Fade", "Overloop", "Baard", "Andere cuts"];
  const items = state.galleryFilter === "all" ? state.data.gallery : state.data.gallery.filter(g => g.category === state.galleryFilter);
  app.innerHTML = `<section class="section light"><div class="wrap"><div class="eyebrow">ITBCUTZ</div><h1 class="title">${tr("nav.gallery")}</h1><div class="filters">${cats.map(c => `<button class="chip ${state.galleryFilter === c ? "active" : ""}" data-filter="${c}">${c === "all" ? "Alle" : c}</button>`).join("")}</div><div class="gallery">${items.map(photo).join("")}</div></div></section>`;
  $$("[data-filter]").forEach(b => b.onclick = () => { state.galleryFilter = b.dataset.filter; gallery(); });
}

function subscriptions() {
  setMeta("Abonnementen", "ITBCUTZ abonnementen: onbeperkt behandelingen voor 1, 2 of 3 maanden, contant betalen.");
  app.innerHTML = `<section class="section dark"><div class="wrap"><div class="eyebrow">ITBCUTZ</div><h1 class="title">${tr("nav.subs")}</h1><p class="copy">${state.lang === "nl" ? "Geen online betaling. Je vraagt een abonnement aan en betaalt contant. Na acceptatie wordt het abonnement actief." : "No online payment. Request a membership and pay cash. After acceptance it becomes active."}</p><div class="grid three">${state.data.plans.map(p => `<article class="card plan">${p.featured ? `<span class="badge">${state.lang === "nl" ? "Meest gekozen" : "Most chosen"}</span>` : ""}<h3>${local(p, "name")}</h3><div class="price">${money(p.price_cents)}</div><p class="muted">${state.lang === "nl" ? "Onbeperkt behandelingen gedurende" : "Unlimited treatments for"} ${p.months} ${state.lang === "nl" ? "maand(en)" : "month(s)"}.</p><button class="btn subReq" data-id="${p.id}">${state.lang === "nl" ? "Aanvragen" : "Request"}</button></article>`).join("")}</div></div></section>`;
  $$(".subReq").forEach(btn => btn.onclick = async () => {
    if (!state.data.user) return go("/login");
    await act(() => api("/api/subscriptions", { plan_id: Number(btn.dataset.id) }), state.lang === "nl" ? "Abonnement aangevraagd." : "Membership requested.");
  });
}

function contact() {
  const c = state.data.contact;
  setMeta("Contact", "Neem contact op met ITBCUTZ in Amsterdam-West via WhatsApp, Snapchat, telefoon of e-mail.");
  app.innerHTML = `<section class="section light"><div class="wrap"><div class="eyebrow">Amsterdam-West</div><h1 class="title">${tr("nav.contact")}</h1><p class="copy">${local(c, "text")}</p>${contactBits()}<div class="btn-row"><a class="btn" href="/afspraak-maken" data-link>${tr("nav.book")}</a></div></div></section>`;
  bindLinks();
}

function contactBits() {
  const c = state.data.contact;
  return `<div class="contact-list">
    <a href="https://wa.me/${(c.whatsapp || "").replace(/\D/g, "")}">WhatsApp: ${c.whatsapp}</a>
    <span>Snapchat: ${c.snapchat}</span><a href="tel:${c.phone}">Telefoon: ${c.phone}</a><a href="mailto:${c.email}">E-mail: ${c.email}</a><span>${c.location}</span>
  </div>`;
}

function booking() {
  setMeta("Afspraak maken", "Vraag een afspraak aan bij ITBCUTZ. Je afspraak wordt officieel na bevestiging.");
  if (!state.data.user) return login("book");
  app.innerHTML = `<section class="section light"><div class="wrap"><h1 class="title">${tr("nav.book")}</h1><p class="copy">${tr("bookIntro")}</p><form class="form" id="bookForm">
    <label>Voornaam<input name="first_name" value="${state.data.user.first_name}" readonly></label>
    <label>Telefoonnummer<input name="phone" required value="${state.data.user.phone}"></label>
    <label>Service<select name="service_id">${state.data.services.map(s => `<option value="${s.id}">${local(s, "name")} - ${money(s.price_cents)}</option>`).join("")}</select></label>
    <label>Gewenste datum<input type="date" name="date" required></label>
    <label>Gewenste tijd<input type="time" name="time" required></label>
    <label class="hidden" id="subPay"><input type="checkbox" name="pay_with_subscription"> Betalen met abonnement</label>
    <label>Optionele notitie<textarea name="note"></textarea></label>
    <button class="btn">Aanvraag versturen</button><p id="msg"></p></form></div></section>`;
  api("/api/account").then(acc => {
    if (acc.subscriptions.some(s => s.status === "Actief")) $("#subPay").classList.remove("hidden");
  });
  $("#bookForm").onsubmit = async e => {
    e.preventDefault();
    const f = new FormData(e.target);
    const data = Object.fromEntries(f.entries());
    data.pay_with_subscription = f.get("pay_with_subscription") === "on";
    await act(() => api("/api/appointments", data), "Afspraak aangevraagd.");
  };
}

function login(mode = "") {
  setMeta("Login", "Log in of registreer voor je ITBCUTZ klantaccount.");
  app.innerHTML = `<section class="section light"><div class="wrap"><h1 class="title">Login / Registreren</h1><div class="grid two">
    <form class="form card" id="loginForm"><h3>Login</h3><label>E-mail<input type="email" name="email" required></label><label>Wachtwoord<input type="password" name="password" required></label><button class="btn">${tr("login")}</button></form>
    <form class="form card" id="regForm"><h3>Registreren</h3><label>Voornaam<input name="first_name" required></label><label>Achternaam<input name="last_name"></label><label>Telefoonnummer<input name="phone" required></label><label>E-mail<input type="email" name="email" required></label><label>Wachtwoord<input type="password" name="password" minlength="8" required></label><button class="btn">Registreren</button></form>
  </div><p id="msg"></p></div></section>`;
  $("#loginForm").onsubmit = async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    await act(async () => { const r = await api("/api/login", data); await boot(); go(r.role === "admin" ? "/admin" : mode === "book" ? "/afspraak-maken" : "/account"); }, "Ingelogd.");
  };
  $("#regForm").onsubmit = async e => {
    e.preventDefault();
    await act(async () => { await api("/api/register", Object.fromEntries(new FormData(e.target).entries())); await boot(); go(mode === "book" ? "/afspraak-maken" : "/account"); }, "Account gemaakt.");
  };
}

async function account() {
  if (!state.data.user) return login();
  state.account = await api("/api/account");
  const a = state.account;
  setMeta("Klantaccount", "Bekijk je ITBCUTZ afspraken, historie, profiel en abonnement.");
  app.innerHTML = `<section class="section light"><div class="wrap"><h1 class="title">Klantaccount</h1><div class="btn-row"><button class="btn secondary" id="logout">Uitloggen</button></div>
    <div class="grid two">
      <article class="card"><h3>Mijn afspraken</h3>${a.appointments.filter(x => x.status !== "Voltooid").map(apptLine).join("") || "<p class='muted'>Geen open afspraken.</p>"}</article>
      <article class="card"><h3>Mijn abonnement</h3>${a.subscriptions.map(subLine).join("") || "<p class='muted'>Geen abonnement.</p>"}</article>
      <article class="card"><h3>Afsprakenhistorie</h3>${a.appointments.filter(x => x.status === "Voltooid").map(apptLine).join("") || "<p class='muted'>Nog geen historie.</p>"}</article>
      <form class="form card" id="profileForm"><h3>Mijn profiel</h3><label>Voornaam<input name="first_name" value="${a.user.first_name}" required></label><label>Achternaam<input name="last_name" value="${a.user.last_name || ""}"></label><label>Telefoon<input name="phone" value="${a.user.phone}" required></label><label>E-mail<input type="email" name="email" value="${a.user.email}" required></label><button class="btn">Opslaan</button></form>
    </div>
    <section class="card" style="margin-top:18px"><h3>Review plaatsen</h3>${reviewForm(a.reviewable)}</section><p id="msg"></p></div></section>`;
  $("#logout").onclick = async () => { await api("/api/logout", {}); state.data.user = null; go("/"); };
  $("#profileForm").onsubmit = e => { e.preventDefault(); act(() => api("/api/profile", Object.fromEntries(new FormData(e.target).entries())), "Profiel opgeslagen."); };
  const rf = $("#reviewForm");
  if (rf) rf.onsubmit = async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const file = e.target.photo.files[0];
    data.photo = file ? await fileToData(file) : "";
    await act(() => api("/api/reviews", data), "Review ingestuurd voor goedkeuring.");
    account();
  };
}

function apptLine(a) {
  return `<p><b>${a.date} ${a.time}</b><br>${a.service_name}<br><span class="status ${a.status === "Bevestigd" ? "ok" : a.status === "Afgewezen" ? "bad" : "wait"}">${a.status}</span>${a.subscription_id ? "<br>Betaald met abonnement" : ""}</p>`;
}
function subLine(s) {
  return `<p><b>${s.name_nl}</b><br><span class="status ${s.status === "Actief" ? "ok" : "wait"}">${s.status}</span><br>${s.start_date || "-"} t/m ${s.end_date || "-"}<br>Gebruikte afspraken: ${s.used_count}</p>`;
}
function reviewForm(items) {
  if (!items.length) return "<p class='muted'>Na een voltooide afspraak kun je hier een review plaatsen.</p>";
  return `<form class="form" id="reviewForm"><label>Afspraak<select name="appointment_id">${items.map(a => `<option value="${a.id}">${a.date} ${a.time} - ${a.service_name}</option>`)}</select></label><label>Sterren<select name="stars"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select></label><label>Tekst<textarea name="text" required></textarea></label><label>Optionele foto<input type="file" name="photo" accept="image/*"></label><button class="btn">Review versturen</button></form>`;
}

async function admin() {
  if (!state.data.user || state.data.user.role !== "admin") return login();
  const d = await api("/api/admin");
  state.admin = d;
  setMeta("Admin Dashboard", "Privé ITBCUTZ admin dashboard.");
  const tabs = ["overview", "appointments", "subscriptions", "customers", "reviews", "gallery", "services", "contact", "settings"];
  app.innerHTML = `<section class="section light"><div class="wrap"><h1 class="title">Admin Dashboard</h1><div class="admin-layout"><aside class="side">${tabs.map(tab => `<button data-tab="${tab}" class="${state.adminTab === tab ? "active" : ""}">${tabName(tab)}</button>`).join("")}<button id="logout">Uitloggen</button></aside><div id="adminPanel" class="panel"></div></div></div></section>`;
  $(".side").onclick = e => { if (e.target.dataset.tab) { state.adminTab = e.target.dataset.tab; adminPanel(); } };
  $("#logout").onclick = async () => { await api("/api/logout", {}); state.data.user = null; go("/"); };
  adminPanel();
}

function tabName(tab) {
  return ({ overview: "Overzicht", appointments: "Afspraken", subscriptions: "Abonnementen", customers: "Klanten", reviews: "Reviews", gallery: "Galerij", services: "Services & prijzen", contact: "Contact", settings: "Website-instellingen" })[tab];
}

function adminPanel() {
  const p = $("#adminPanel"), d = state.admin, tab = state.adminTab;
  if (tab === "overview") p.innerHTML = `<div class="kpis">${Object.entries(d.stats).map(([k,v]) => `<div class="kpi"><span>${k}</span><b>${v}</b></div>`).join("")}</div>`;
  if (tab === "appointments") p.innerHTML = table(["Klant","Service","Datum","Status","Acties"], d.appointments.map(a => [`${a.first_name} ${a.last_name || ""}<br>${a.email}<br>${a.phone}`, `${a.service_name}<br>${a.note || ""}`, `${a.date}<br>${a.time}`, a.status, statusBtns("appointment", a.id, ["Bevestigd","Afgewezen","Voltooid"])]));
  if (tab === "subscriptions") p.innerHTML = table(["Klant","Plan","Status","Data","Gebruikt","Acties"], d.subscriptions.map(s => [`${s.first_name} ${s.last_name || ""}<br>${s.email}`, s.name_nl, s.status, `${s.start_date || "-"}<br>${s.end_date || "-"}`, s.used_count, `<button class="mini" data-accept="${s.id}">Betaling ontvangen / Accepteren</button>${statusBtns("subscription", s.id, ["Betaling in afwachting","Actief","Verlopen"])}`]));
  if (tab === "customers") p.innerHTML = table(["Klant","Contact","Afspraken","Sinds"], d.customers.map(c => [`${c.first_name} ${c.last_name || ""}`, `${c.email}<br>${c.phone}`, c.appointment_count, c.created_at]));
  if (tab === "reviews") p.innerHTML = table(["Klant","Review","Status","Acties"], d.adminReviews.map(r => [`${r.first_name} ${r.last_name || ""}<br>${r.date}`, `${"★".repeat(r.stars)}<br><textarea data-rtext="${r.id}">${r.text}</textarea>`, r.status, `<button class="mini" data-review="${r.id}" data-status="Goedgekeurd" data-stars="${r.stars}">Goedkeuren</button><button class="mini light" data-review="${r.id}" data-status="Afgewezen" data-stars="${r.stars}">Afwijzen</button><button class="mini light" data-delreview="${r.id}">Verwijderen</button>`]));
  if (tab === "gallery") p.innerHTML = `${galleryAdminForm(d.gallery)}${table(["Foto","Categorie","Titel","Volgorde","Acties"], d.gallery.map(g => [`<img src="${g.image_url}" alt="" style="width:80px;height:90px;object-fit:cover">`, g.category, g.title, g.sort_order, `<button class="mini light" data-editgallery="${g.id}">Laden</button><button class="mini light" data-delgallery="${g.id}">Verwijderen</button>`]))}`;
  if (tab === "services") p.innerHTML = `${serviceForm()}${table(["Service","Prijs","Volgorde","Acties"], d.services.map(s => [`<input data-snl="${s.id}" value="${s.name_nl}"><input data-sen="${s.id}" value="${s.name_en}">`, `<input data-sprice="${s.id}" type="number" step="0.01" value="${(s.price_cents/100).toFixed(2)}">`, `<input data-sorder="${s.id}" type="number" value="${s.sort_order}">`, `<button class="mini" data-saveservice="${s.id}">Opslaan</button><button class="mini light" data-delservice="${s.id}">Verwijderen</button>`]))}`;
  if (tab === "contact") p.innerHTML = contactForm(d.contact);
  if (tab === "settings") p.innerHTML = settingsForm(d);
  bindAdminActions();
}

function table(head, rows) {
  return `<table class="table"><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table><p id="msg"></p>`;
}
function statusBtns(type, id, statuses) {
  return `<div class="actions">${statuses.map(s => `<button class="mini ${s.includes("Af") || s === "Verlopen" ? "light" : ""}" data-${type}="${id}" data-status="${s}">${s}</button>`).join("")}</div>`;
}
function galleryAdminForm(items) {
  return `<form class="form grid2 card" id="galleryForm"><h3>Foto uploaden / vervangen</h3><input type="hidden" name="id"><label>Bestaande foto<select name="existing"><option value="">Nieuwe foto</option>${items.map(g => `<option value="${g.id}">${g.title}</option>`)}</select></label><label>Categorie<select name="category">${["Taper Fade","Burst Fade","Overloop","Baard","Andere cuts"].map(c => `<option>${c}</option>`)}</select></label><label>Titel<input name="title" required></label><label>Alt NL<input name="alt_nl" required></label><label>Alt EN<input name="alt_en" required></label><label>Volgorde<input name="sort_order" type="number" value="10"></label><label>Foto<input name="imageFile" type="file" accept="image/*"></label><button class="btn">Opslaan</button></form>`;
}
function serviceForm() {
  return `<form class="form grid2 card" id="serviceForm"><h3>Service toevoegen</h3><label>Naam NL<input name="name_nl" required></label><label>Naam EN<input name="name_en" required></label><label>Prijs<input name="price" type="number" step="0.01" required></label><label>Volgorde<input name="sort_order" type="number" value="10"></label><button class="btn">Opslaan</button></form>`;
}
function contactForm(c) {
  return `<form class="form card" id="contactForm"><h3>Contactgegevens</h3>${["snapchat","whatsapp","phone","email","location"].map(k => `<label>${k}<input name="${k}" value="${c[k] || ""}"></label>`).join("")}<label>Tekst NL<textarea name="text_nl">${c.text_nl || ""}</textarea></label><label>Tekst EN<textarea name="text_en">${c.text_en || ""}</textarea></label><button class="btn">Opslaan</button><p id="msg"></p></form>`;
}
function settingsForm(d) {
  return `<form class="form card" id="settingsForm"><h3>Website-instellingen</h3><label>Slogan NL<input name="slogan_nl" value="${d.settings.slogan_nl || ""}"></label><label>Slogan EN<input name="slogan_en" value="${d.settings.slogan_en || ""}"></label><label>Tekst NL<textarea name="about_nl">${d.settings.about_nl || ""}</textarea></label><label>Tekst EN<textarea name="about_en">${d.settings.about_en || ""}</textarea></label><label>Meest gekozen abonnement<select name="featured_plan">${d.plans.map(p => `<option value="${p.id}" ${p.featured ? "selected" : ""}>${p.name_nl}</option>`).join("")}</select></label><button class="btn">Opslaan</button><p id="msg"></p></form>`;
}

function bindAdminActions() {
  $$("[data-appointment]").forEach(b => b.onclick = () => adm("/api/admin/appointment-status", { id: Number(b.dataset.appointment), status: b.dataset.status }));
  $$("[data-subscription]").forEach(b => b.onclick = () => adm("/api/admin/subscription-status", { id: Number(b.dataset.subscription), status: b.dataset.status }));
  $$("[data-accept]").forEach(b => b.onclick = () => adm("/api/admin/subscription-accept", { id: Number(b.dataset.accept) }));
  $$("[data-review]").forEach(b => b.onclick = () => adm("/api/admin/review", { id: Number(b.dataset.review), status: b.dataset.status, stars: Number(b.dataset.stars), text: $(`[data-rtext="${b.dataset.review}"]`).value }));
  $$("[data-delreview]").forEach(b => b.onclick = () => adm("/api/admin/review-delete", { id: Number(b.dataset.delreview) }));
  $$("[data-delgallery]").forEach(b => b.onclick = () => adm("/api/admin/gallery-delete", { id: Number(b.dataset.delgallery) }));
  $$("[data-editgallery]").forEach(b => b.onclick = () => {
    const g = state.admin.gallery.find(x => x.id === Number(b.dataset.editgallery));
    const f = $("#galleryForm");
    f.elements.id.value = g.id; f.existing.value = g.id; f.category.value = g.category; f.title.value = g.title; f.alt_nl.value = g.alt_nl; f.alt_en.value = g.alt_en; f.sort_order.value = g.sort_order;
  });
  const existing = $('#galleryForm [name="existing"]');
  if (existing) existing.onchange = () => {
    if (!existing.value) return;
    const g = state.admin.gallery.find(x => x.id === Number(existing.value));
    const f = $("#galleryForm");
    f.elements.id.value = g.id; f.category.value = g.category; f.title.value = g.title; f.alt_nl.value = g.alt_nl; f.alt_en.value = g.alt_en; f.sort_order.value = g.sort_order;
  };
  $$("[data-saveservice]").forEach(b => b.onclick = () => {
    const id = b.dataset.saveservice;
    adm("/api/admin/service-save", { id: Number(id), name_nl: $(`[data-snl="${id}"]`).value, name_en: $(`[data-sen="${id}"]`).value, price: $(`[data-sprice="${id}"]`).value, sort_order: $(`[data-sorder="${id}"]`).value, active: 1 });
  });
  $$("[data-delservice]").forEach(b => b.onclick = () => adm("/api/admin/service-delete", { id: Number(b.dataset.delservice) }));
  const gf = $("#galleryForm");
  if (gf) gf.onsubmit = async e => { e.preventDefault(); const f = new FormData(e.target); const file = f.get("imageFile"); if (!f.get("id") && (!file || !file.size)) { $("#msg").textContent = "Kies een foto voor nieuwe uploads."; return; } await adm("/api/admin/gallery-save", { id:f.get("id") ? Number(f.get("id")) : null, category:f.get("category"), title:f.get("title"), alt_nl:f.get("alt_nl"), alt_en:f.get("alt_en"), sort_order:f.get("sort_order"), image: await fileToData(file) }); };
  const sf = $("#serviceForm");
  if (sf) sf.onsubmit = e => { e.preventDefault(); adm("/api/admin/service-save", Object.fromEntries(new FormData(e.target).entries())); };
  const cf = $("#contactForm");
  if (cf) cf.onsubmit = e => { e.preventDefault(); adm("/api/admin/contact", Object.fromEntries(new FormData(e.target).entries())); };
  const setf = $("#settingsForm");
  if (setf) setf.onsubmit = async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const plan = data.featured_plan; delete data.featured_plan;
    await api("/api/admin/settings", data);
    await api("/api/admin/featured-plan", { id: Number(plan) });
    await refreshAdmin("Opgeslagen.");
  };
}
async function adm(url, data) { await act(() => api(url, data), "Opgeslagen."); await refreshAdmin(); }
async function refreshAdmin(msg = "") { state.data = await api("/api/bootstrap"); state.admin = await api("/api/admin"); adminPanel(); if (msg && $("#msg")) $("#msg").textContent = msg; }

async function act(fn, ok) {
  try { await fn(); const m = $("#msg"); if (m) m.textContent = ok; }
  catch (e) { const m = $("#msg"); if (m) m.textContent = e.message; else alert(e.message); }
}
function fileToData(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.size) return resolve("");
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}
function bindLinks() {
  $$("a[data-link]").forEach(a => a.onclick = e => { e.preventDefault(); go(a.getAttribute("href")); });
}
document.addEventListener("click", e => {
  const a = e.target.closest("a[data-link]");
  if (a) { e.preventDefault(); go(a.getAttribute("href")); }
});
$("#menuBtn").onclick = () => $("#nav").classList.toggle("open");
$("#langBtn").onclick = () => { state.lang = state.lang === "nl" ? "en" : "nl"; localStorage.setItem("itb_lang", state.lang); route(); };
window.onpopstate = route;
boot();
