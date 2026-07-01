/* MMM-Corelec.js
 * MagicMirror² module — Corelec Pool Monitor
 *
 * Configuration example (config.js):
 *   {
 *     module: "MMM-Corelec",
 *     position: "top_right",
 *     header: "Piscine",
 *     config: {
 *       webServerUrl: "http://192.168.0.20:8080",
 *       pollInterval: 30,
 *       fields: ["ph", "temp", "electrolyse_pct", "boost"],
 *     }
 *   }
 *
 * Available field names:
 *   ph, ph_consigne, temp, redox, redox_consigne,
 *   electrolyse_pct, boost, connection
 */

Module.register("MMM-Corelec", {

  defaults: {
    webServerUrl: "http://localhost:8080",
    pollInterval: 30,           // seconds
    fields: ["ph", "temp", "electrolyse_pct", "boost"],
    showAlarms: true,
    animateBoost: true,
    pinCode: "",                // PIN code requis par le serveur (si --pin-code configuré)
  },

  // ── Field definitions ──────────────────────────────────────────────────
  FIELD_META: {
    ph:             { label: "pH",          unit: "",    fmt: v => v != null ? Number(v).toFixed(2) : "—" },
    ph_consigne:    { label: "pH consigne", unit: "",    fmt: v => v != null ? Number(v).toFixed(2) : "—" },
    temp:           { label: "Temp.",       unit: "°C",  fmt: v => v != null ? Number(v).toFixed(1) : "—" },
    redox:          { label: "Redox",       unit: "mV",  fmt: v => v != null ? Math.round(v) : "—" },
    redox_consigne: { label: "Redox cons.", unit: "mV",  fmt: v => v != null ? Math.round(v) : "—" },
    electrolyse_pct:{ label: "Électrolyse", unit: "%",   fmt: v => v != null ? Math.round(v) : "—" },
    boost:          {
      label: "Boost",
      unit: "",
      fmt: (v, pool) => {
        if (!pool) return "—";
        return pool.boost_active
          ? `ACTIF (${pool.boost_remaining_min} min)`
          : "OFF";
      },
    },
    connection: {
      label: "Connexion",
      unit: "",
      fmt: (v, pool, conn) => conn ? (conn.status_name || "—") : "—",
    },
  },

  // ── Lifecycle ──────────────────────────────────────────────────────────
  start() {
    this.state = null;
    this.lastUpdate = null;
    Log.info(`MMM-Corelec: start, polling ${this.config.webServerUrl} every ${this.config.pollInterval}s`);
    this.sendSocketNotification("START_POLLING", {
      url: this.config.webServerUrl + "/api/state",
      interval: this.config.pollInterval * 1000,
    });
  },

  socketNotificationReceived(notification, payload) {
    if (notification === "STATE_UPDATE") {
      this.state = payload;
      this.lastUpdate = new Date();
      this.updateDom(300);
    }
  },

  // ── DOM ────────────────────────────────────────────────────────────────
  getDom() {
    const wrapper = document.createElement("div");
    wrapper.className = "MMM-Corelec";

    if (!this.state) {
      wrapper.innerHTML = `<div class="corelec-loading">En attente de données…</div>`;
      return wrapper;
    }

    const pool = this.state.pool || {};
    const conn = this.state.connection || {};
    const hasAlarm = pool.alarme || pool.flow_alarm;

    // Alarm banner
    if (this.config.showAlarms && hasAlarm) {
      const alarm = document.createElement("div");
      alarm.className = "corelec-alarm";
      alarm.textContent = "⚠ Alarme piscine";
      wrapper.appendChild(alarm);
    }

    // Connection dot
    const statusRow = document.createElement("div");
    statusRow.className = "corelec-status";
    const dot = document.createElement("span");
    dot.className = `corelec-dot corelec-dot--${conn.status_name || "disconnected"}`;
    statusRow.appendChild(dot);
    if (this.lastUpdate) {
      const ts = document.createElement("span");
      ts.className = "corelec-ts";
      ts.textContent = this.lastUpdate.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
      statusRow.appendChild(ts);
    }
    wrapper.appendChild(statusRow);

    // Fields table
    const table = document.createElement("table");
    table.className = "corelec-table";

    for (const key of this.config.fields) {
      const meta = this.FIELD_META[key];
      if (!meta) continue;

      const raw = key === "boost" ? pool.boost_active : pool[key];
      const display = meta.fmt(raw, pool, conn);
      const unit    = meta.unit;

      const tr = document.createElement("tr");
      tr.className = "corelec-row";

      const tdLabel = document.createElement("td");
      tdLabel.className = "corelec-label";
      tdLabel.textContent = meta.label;

      const tdValue = document.createElement("td");
      tdValue.className = "corelec-value";

      // Color coding for pH
      if (key === "ph" && pool.ph != null) {
        const ph = pool.ph;
        const pc = pool.ph_consigne;
        const hi = pc != null ? pc + 0.3 : 7.6;
        const lo = pc != null ? pc - 0.4 : 6.8;
        if (ph < lo - 0.2 || ph > hi + 0.2) tdValue.classList.add("corelec-danger");
        else if (ph < lo || ph > hi)         tdValue.classList.add("corelec-warn");
        else                                  tdValue.classList.add("corelec-ok");
      }

      // Boost animation
      if (key === "boost" && pool.boost_active && this.config.animateBoost) {
        tdValue.classList.add("corelec-boost-active");
      }

      tdValue.textContent = display + (unit ? " " + unit : "");
      tr.appendChild(tdLabel);
      tr.appendChild(tdValue);
      table.appendChild(tr);
    }

    wrapper.appendChild(table);
    return wrapper;
  },

  getStyles() {
    return ["MMM-Corelec.css"];
  },
});
