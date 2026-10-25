/* Sea Temperature card — bundled with the sea_temperature integration. */

const CARD_VERSION = "0.5.0";
const DOMAIN = "sea_temperature";
const REFRESH_MS = 30 * 60 * 1000;

const KEYS = [
  "sea_temperature", "swim_comfort", "sea_state", "temperature_change",
  "tide_state", "next_high_tide", "next_low_tide",
  "wave_height", "wave_period", "wave_direction",
];

const SWIM_COLOURS = {
  very_cold: "#2563eb", cold: "#0891b2", fresh: "#14b8a6",
  comfortable: "#22c55e", warm: "#f59e0b",
};
const SWIM_LABELS = {
  very_cold: "Very cold", cold: "Cold", fresh: "Fresh", comfortable: "Comfortable", warm: "Warm",
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class SeaTemperatureCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._history = null;      // [{t: ms, v: number}]
    this._historyFor = null;   // entity id the history belongs to
    this._historyAt = 0;
    this._loading = false;
    this._signature = "";
    this._hoverIndex = null;
    this._lastWidth = 0;
    this._resizer = new ResizeObserver(() => {
      const w = Math.round(this.getBoundingClientRect().width);
      if (Math.abs(w - this._lastWidth) > 8 && this._config && this._hass) {
        this._lastWidth = w;
        this._render();
      }
    });
  }

  connectedCallback() { this._resizer.observe(this); }
  disconnectedCallback() { this._resizer.disconnect(); }

  static getConfigElement() {
    return document.createElement("sea-temperature-card-editor");
  }

  static getStubConfig(hass) {
    const found = Object.values(hass?.entities || {}).find(
      (e) => e.platform === DOMAIN && e.translation_key === "sea_temperature"
    );
    return { entity: found ? found.entity_id : "" };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Choose a Sea Temperature sensor (any sensor from the beach).");
    }
    this._config = { days: 7, show_graph: true, ...config };
    this._history = null;
    this._historyFor = null;
    this._signature = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    const sig = this._signatureOf();
    if (sig !== this._signature) {
      this._signature = sig;
      this._render();
    }
    this._maybeLoadHistory();
  }

  getCardSize() {
    return this._config?.show_graph === false ? 4 : 7;
  }

  // ---- entity lookup ------------------------------------------------------

  _siblings() {
    const hass = this._hass;
    const base = this._config.entity;
    const ent = hass.entities?.[base];
    const out = {};
    if (ent?.device_id) {
      for (const e of Object.values(hass.entities)) {
        if (e.device_id === ent.device_id && e.platform === DOMAIN && e.translation_key) {
          out[e.translation_key] = e.entity_id;
        }
      }
    }
    if (!Object.keys(out).length) {
      // Fallback: guess from the entity id, e.g. sensor.praa_sands_sea_temperature
      const stem = base.replace(/^sensor\./, "").replace(/_(sea_temperature|swim_comfort|sea_state|temperature_change_24_h|tide|next_high_tide|next_low_tide|wave_height|wave_period|wave_direction)$/, "");
      const guess = {
        sea_temperature: "sea_temperature", swim_comfort: "swim_comfort", sea_state: "sea_state",
        temperature_change: "temperature_change_24_h", tide_state: "tide",
        next_high_tide: "next_high_tide", next_low_tide: "next_low_tide",
        wave_height: "wave_height", wave_period: "wave_period", wave_direction: "wave_direction",
      };
      for (const [k, suffix] of Object.entries(guess)) out[k] = `sensor.${stem}_${suffix}`;
    }
    return out;
  }

  _state(id) {
    const s = id ? this._hass.states[id] : undefined;
    return s && s.state !== "unavailable" && s.state !== "unknown" ? s : null;
  }

  _signatureOf() {
    const ids = this._siblings();
    return KEYS.map((k) => {
      const s = ids[k] ? this._hass.states[ids[k]] : null;
      return s ? `${s.state}|${s.attributes?.source ?? ""}` : "-";
    }).join(";") + `|${this._config.entity}`;
  }

  // ---- history -----------------------------------------------------------

  async _maybeLoadHistory() {
    if (!this._config.show_graph || this._loading || !this._hass) return;
    const tempId = this._siblings().sea_temperature;
    if (!tempId) return;
    const stale = Date.now() - this._historyAt > REFRESH_MS;
    if (this._historyFor === tempId && !stale) return;
    this._loading = true;
    try {
      const points = await this._fetchHistory(tempId);
      this._history = points;
      this._historyFor = tempId;
      this._historyAt = Date.now();
    } catch (err) {
      this._history = [];
      this._historyFor = tempId;
      this._historyAt = Date.now();
      console.warn("sea-temperature-card: could not load history", err);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _fetchHistory(entityId) {
    const days = Math.max(1, Math.min(Number(this._config.days) || 7, 30));
    const end = new Date();
    const start = new Date(end.getTime() - days * 86400000);

    // Hourly statistics are small and outlive the recorder's purge window.
    try {
      const stats = await this._hass.callWS({
        type: "recorder/statistics_during_period",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        statistic_ids: [entityId],
        period: "hour",
        types: ["mean"],
      });
      const rows = (stats?.[entityId] || []).filter((r) => r.mean != null);
      if (rows.length >= 2) {
        return rows.map((r) => ({ t: typeof r.start === "number" ? r.start : Date.parse(r.start), v: r.mean }));
      }
    } catch (_) { /* fall through to raw history */ }

    const hist = await this._hass.callWS({
      type: "history/history_during_period",
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      entity_ids: [entityId],
      minimal_response: true,
      no_attributes: true,
      significant_changes_only: false,
    });
    const raw = hist?.[entityId] || [];
    const pts = [];
    for (const p of raw) {
      const v = parseFloat(p.s ?? p.state);
      const ts = p.lu ?? p.lc ?? p.last_updated ?? p.last_changed;
      if (Number.isNaN(v) || ts == null) continue;
      pts.push({ t: typeof ts === "number" ? ts * 1000 : Date.parse(ts), v });
    }
    return pts;
  }

  // ---- rendering ---------------------------------------------------------

  _fmtState(entityId) {
    const s = this._state(entityId);
    if (!s) return "–";
    if (this._hass.formatEntityState) return this._hass.formatEntityState(s);
    return s.state;
  }

  _fmtTime(entityId) {
    const s = this._state(entityId);
    if (!s) return "–";
    const d = new Date(s.state);
    if (Number.isNaN(d.getTime())) return "–";
    const lang = this._hass.locale?.language;
    const time = d.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
    const sameDay = d.toDateString() === new Date().toDateString();
    return sameDay ? time : `${d.toLocaleDateString(lang, { weekday: "short" })} ${time}`;
  }

  _render() {
    if (!this._config) return;
    if (!this._hass) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="pad">Loading…</div></ha-card>`;
      return;
    }
    const ids = this._siblings();
    const temp = this._state(ids.sea_temperature);
    if (!temp) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="pad muted">Sea temperature is unavailable for ${esc(this._config.entity)}.</div></ha-card>`;
      return;
    }

    const deviceName = this._config.name
      || this._hass.devices?.[this._hass.entities?.[this._config.entity]?.device_id]?.name
      || temp.attributes.friendly_name?.replace(/\s*Sea temperature$/i, "")
      || "Sea";
    const unit = temp.attributes.unit_of_measurement || "°C";
    const value = Number(temp.state);
    const big = Number.isFinite(value) ? value.toFixed(1) : esc(temp.state);

    const swim = this._state(ids.swim_comfort);
    const swimKey = swim?.state;
    const swimLabel = swim ? this._fmtState(ids.swim_comfort) : "";
    const swimColour = SWIM_COLOURS[swimKey] || "var(--primary-color)";
    const rough = swim?.attributes?.rough_water === true;

    const changeS = this._state(ids.temperature_change);
    let change = "";
    if (changeS) {
      const c = Number(changeS.state);
      if (Number.isFinite(c)) {
        const arrow = c > 0.04 ? "▲" : c < -0.04 ? "▼" : "▬";
        change = `<span class="change" title="Change over the last 24 hours (model)">${arrow} ${Math.abs(c).toFixed(1)}${esc(unit)} / 24 h</span>`;
      }
    }

    const source = temp.attributes.source || "";
    const buoy = temp.attributes.buoy;
    const buoyDist = temp.attributes.buoy_distance_km;
    const sourceLine = buoy
      ? `Measured: ${esc(buoy)}${buoyDist != null ? ` (${esc(buoyDist)} km away)` : ""}`
      : esc(source).replace(/\s*\(model\)/i, " · model");

    const wh = this._state(ids.wave_height);
    const wp = this._state(ids.wave_period);
    const waves = wh
      ? `${this._fmtState(ids.wave_height)}${wp ? ` · ${this._fmtState(ids.wave_period)}` : ""}`
      : "–";

    const tideS = this._state(ids.tide_state);
    const tideArrow = tideS?.state === "rising" ? "▲" : tideS?.state === "falling" ? "▼" : "";
    const tideSource = this._state(ids.tide_state)?.attributes?.source || "";
    const tideApprox = /model/i.test(tideSource) ? "approx." : "";

    const graph = this._config.show_graph ? this._graphHtml(unit) : "";

    this.shadowRoot.innerHTML = `${this._styles()}
      <ha-card>
        <div class="pad">
          <div class="top">
            <div>
              <div class="name">${esc(deviceName)}</div>
              <div class="source">${sourceLine}</div>
            </div>
            ${swim ? `<div class="chips"><span class="chip" style="background:${swimColour}">${esc(swimLabel)}</span>${rough ? `<span class="chip warn">⚠ Rough water</span>` : ""}</div>` : ""}
          </div>
          <div class="hero"><span class="big">${big}</span><span class="unit">${esc(unit)}</span>${change}</div>
          <div class="grid">
            <div class="cell"><div class="label">Sea state</div><div class="val">${esc(this._fmtState(ids.sea_state))}</div></div>
            <div class="cell"><div class="label">Waves</div><div class="val">${esc(waves)}</div></div>
            <div class="cell"><div class="label">Tide ${tideApprox ? `<span class="approx" title="${esc(tideSource)}">(${tideApprox})</span>` : ""}</div><div class="val">${tideArrow} ${esc(tideS ? this._fmtState(ids.tide_state) : "–")}</div></div>
            <div class="cell"><div class="label">Next high</div><div class="val">${esc(this._fmtTime(ids.next_high_tide))}</div></div>
            <div class="cell"><div class="label">Next low</div><div class="val">${esc(this._fmtTime(ids.next_low_tide))}</div></div>
          </div>
          ${graph}
        </div>
      </ha-card>`;

    this._attachGraphEvents();
  }

  _graphHtml(unit) {
    const days = Number(this._config.days) || 7;
    const pts = this._history;
    if (pts === null) return `<div class="graph muted">Loading ${days}-day history…</div>`;
    if (pts.length < 2) {
      return `<div class="graph muted">Collecting history. The ${days}-day graph fills in as Home Assistant records the sensor.</div>`;
    }
    const W = Math.max(240, Math.round((this.getBoundingClientRect().width || 360) - 32)), H = 150, L = 34, R = 8, T = 10, B = 22;
    const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
    let lo = Math.min(...pts.map((p) => p.v)), hi = Math.max(...pts.map((p) => p.v));
    if (hi - lo < 1) { const mid = (hi + lo) / 2; lo = mid - 0.5; hi = mid + 0.5; }
    else { lo = Math.floor(lo * 2) / 2 - 0.25; hi = Math.ceil(hi * 2) / 2 + 0.25; }
    const x = (t) => L + ((t - t0) / (t1 - t0 || 1)) * (W - L - R);
    const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
    this._geom = { x, y, t0, t1, W, H, L, R, T, B };

    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    const area = `${line}L${x(t1).toFixed(1)},${H - B}L${x(t0).toFixed(1)},${H - B}Z`;

    const vmin = pts.reduce((a, b) => (b.v < a.v ? b : a));
    const vmax = pts.reduce((a, b) => (b.v > a.v ? b : a));

    // midnight ticks
    const lang = this._hass.locale?.language;
    let ticks = "";
    const d = new Date(t0); d.setHours(24, 0, 0, 0);
    const spanDays = (t1 - t0) / 86400000;
    const every = spanDays > 10 ? 2 : 1;
    let n = 0;
    for (let tt = d.getTime(); tt < t1; tt += 86400000, n++) {
      if (n % every) continue;
      const xx = x(tt).toFixed(1);
      ticks += `<line x1="${xx}" x2="${xx}" y1="${T}" y2="${H - B}" class="grid-line"/>`
        + `<text x="${xx}" y="${H - 6}" text-anchor="middle" class="axis">${esc(new Date(tt).toLocaleDateString(lang, { weekday: "short" }))}</text>`;
    }

    return `
      <div class="graph">
        <div class="graph-head"><span>Last ${days} days</span>
          <span class="muted">low ${vmin.v.toFixed(1)} · high ${vmax.v.toFixed(1)} ${esc(unit)}</span></div>
        <svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="svg" role="img" aria-label="Sea temperature over the last ${days} days">
          <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--primary-color)" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="var(--primary-color)" stop-opacity="0.02"/></linearGradient></defs>
          <text x="${L - 4}" y="${y(hi) + 8}" text-anchor="end" class="axis">${hi.toFixed(1)}</text>
          <text x="${L - 4}" y="${y(lo)}" text-anchor="end" class="axis">${lo.toFixed(1)}</text>
          <line x1="${L}" x2="${W - R}" y1="${y(hi)}" y2="${y(hi)}" class="grid-line"/>
          <line x1="${L}" x2="${W - R}" y1="${y(lo)}" y2="${y(lo)}" class="grid-line"/>
          ${ticks}
          <path d="${area}" fill="url(#g)"/>
          <path d="${line}" class="line" vector-effect="non-scaling-stroke"/>
          <circle cx="${x(vmax.t).toFixed(1)}" cy="${y(vmax.v).toFixed(1)}" r="3" class="dot"/>
          <circle cx="${x(vmin.t).toFixed(1)}" cy="${y(vmin.v).toFixed(1)}" r="3" class="dot"/>
          <g id="hover" style="display:none"><line id="hv" y1="${T}" y2="${H - B}" class="hover-line"/><circle id="hd" r="4" class="dot"/></g>
        </svg>
        <div id="tip" class="tip" style="display:none"></div>
      </div>`;
  }

  _attachGraphEvents() {
    const svg = this.shadowRoot.querySelector(".svg");
    if (!svg || !this._history || this._history.length < 2) return;
    const pts = this._history;
    const g = this._geom;
    const hover = this.shadowRoot.getElementById("hover");
    const hv = this.shadowRoot.getElementById("hv");
    const hd = this.shadowRoot.getElementById("hd");
    const tip = this.shadowRoot.getElementById("tip");
    const unit = this._state(this._siblings().sea_temperature)?.attributes?.unit_of_measurement || "°C";
    const lang = this._hass.locale?.language;

    const move = (ev) => {
      const rect = svg.getBoundingClientRect();
      const px = ((ev.clientX - rect.left) / rect.width) * g.W;
      const tt = g.t0 + ((px - g.L) / (g.W - g.L - g.R)) * (g.t1 - g.t0);
      let best = 0, bd = Infinity;
      for (let i = 0; i < pts.length; i++) {
        const dd = Math.abs(pts[i].t - tt);
        if (dd < bd) { bd = dd; best = i; }
      }
      const p = pts[best];
      const cx = g.x(p.t), cy = g.y(p.v);
      hover.style.display = "";
      hv.setAttribute("x1", cx); hv.setAttribute("x2", cx);
      hd.setAttribute("cx", cx); hd.setAttribute("cy", cy);
      tip.style.display = "";
      tip.textContent = `${p.v.toFixed(1)}${unit} · ${new Date(p.t).toLocaleString(lang, { weekday: "short", hour: "2-digit", minute: "2-digit" })}`;
      const frac = (cx / g.W);
      tip.style.left = `${Math.min(Math.max(frac * 100, 18), 82)}%`;
    };
    const leave = () => { hover.style.display = "none"; tip.style.display = "none"; };
    svg.addEventListener("pointermove", move);
    svg.addEventListener("pointerdown", move);
    svg.addEventListener("pointerleave", leave);
  }

  _styles() {
    return `<style>
      :host { display:block; }
      ha-card { overflow:hidden; }
      .pad { padding:16px; }
      .muted { color: var(--secondary-text-color); }
      .top { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
      .name { font-size:1.15rem; font-weight:500; color: var(--primary-text-color); }
      .source { font-size:0.8rem; color: var(--secondary-text-color); margin-top:2px; }
      .chips { display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }
      .chip { color:#fff; font-size:0.8rem; font-weight:500; padding:4px 10px; border-radius:999px; white-space:nowrap; }
      .chip.warn { background:#b45309; }
      .hero { display:flex; align-items:baseline; gap:4px; margin:10px 0 12px; flex-wrap:wrap; }
      .big { font-size:3rem; line-height:1; font-weight:300; color: var(--primary-text-color); }
      .unit { font-size:1.2rem; color: var(--secondary-text-color); }
      .change { margin-left:12px; font-size:0.85rem; color: var(--secondary-text-color); }
      .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(105px, 1fr)); gap:10px; }
      .cell { background: var(--secondary-background-color, rgba(127,127,127,.1)); border-radius:10px; padding:8px 10px; }
      .label { font-size:0.72rem; text-transform:uppercase; letter-spacing:.04em; color: var(--secondary-text-color); }
      .approx { text-transform:none; letter-spacing:0; }
      .val { font-size:0.98rem; margin-top:2px; color: var(--primary-text-color); }
      .graph { margin-top:14px; position:relative; }
      .graph-head { display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:4px; color: var(--primary-text-color); }
      .svg { width:100%; height:auto; display:block; touch-action:none; }
      .line { fill:none; stroke: var(--primary-color); stroke-width:2; stroke-linejoin:round; }
      .dot { fill: var(--primary-color); }
      .grid-line { stroke: var(--divider-color, rgba(127,127,127,.3)); stroke-width:1; vector-effect:non-scaling-stroke; }
      .hover-line { stroke: var(--secondary-text-color); stroke-width:1; stroke-dasharray:3 3; vector-effect:non-scaling-stroke; }
      .axis { fill: var(--secondary-text-color); font-size:10px; }
      .tip { position:absolute; top:22px; transform:translateX(-50%); background: var(--primary-text-color); color: var(--card-background-color, #000);
             font-size:0.78rem; padding:3px 8px; border-radius:6px; pointer-events:none; white-space:nowrap; }
    </style>`;
  }
}

class SeaTemperatureCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  set hass(hass) { this._hass = hass; if (this._form) this._form.hass = hass; }

  _render() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = { days: 7, show_graph: true, ...this._config };
    this._form.schema = [
      { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: DOMAIN } } },
      { name: "name", selector: { text: {} } },
      { name: "show_graph", selector: { boolean: {} } },
      { name: "days", selector: { number: { min: 1, max: 30, mode: "box" } } },
    ];
    this._form.computeLabel = (s) => ({
      entity: "Any sensor from the beach", name: "Name (optional)",
      show_graph: "Show history graph", days: "Days of history",
    }[s.name] || s.name);
  }
}

if (!customElements.get("sea-temperature-card")) {
  customElements.define("sea-temperature-card", SeaTemperatureCard);
  customElements.define("sea-temperature-card-editor", SeaTemperatureCardEditor);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "sea-temperature-card")) {
  window.customCards.push({
    type: "sea-temperature-card",
    name: "Sea Temperature",
    description: "Sea temperature, swim comfort, waves, tides and a history graph for one beach.",
    preview: false,
  });
}
console.info(`%c SEA-TEMPERATURE-CARD %c ${CARD_VERSION} `, "color:#fff;background:#0891b2;font-weight:700", "color:#0891b2;background:#fff");
