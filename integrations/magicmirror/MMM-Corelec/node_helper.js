/* node_helper.js — MMM-Corelec
 * Backend Node.js : poll HTTP /api/state depuis le web_server Corelec.
 * Utilise uniquement les modules Node.js built-in (http/https) — aucune
 * dépendance npm requise.
 */

const NodeHelper = require("node_helper");
const http  = require("http");
const https = require("https");
const url   = require("url");

module.exports = NodeHelper.create({

  start() {
    this._timer = null;
    console.log("[MMM-Corelec] node_helper démarré.");
  },

  stop() {
    if (this._timer) clearInterval(this._timer);
  },

  socketNotificationReceived(notification, payload) {
    if (notification === "START_POLLING") {
      if (this._timer) clearInterval(this._timer);
      this._apiUrl  = payload.url;
      this._interval = payload.interval;
      // Premier appel immédiat
      this._fetchState();
      // Puis périodique
      this._timer = setInterval(() => this._fetchState(), this._interval);
    }
  },

  _fetchState() {
    const parsed   = url.parse(this._apiUrl);
    const protocol = parsed.protocol === "https:" ? https : http;

    const req = protocol.get(this._apiUrl, res => {
      if (res.statusCode !== 200) {
        console.warn(`[MMM-Corelec] HTTP ${res.statusCode} pour ${this._apiUrl}`);
        res.resume();
        return;
      }
      let raw = "";
      res.setEncoding("utf8");
      res.on("data",  chunk => { raw += chunk; });
      res.on("end", () => {
        try {
          const data = JSON.parse(raw);
          this.sendSocketNotification("STATE_UPDATE", data);
        } catch (err) {
          console.error("[MMM-Corelec] Parse JSON:", err.message);
        }
      });
    });

    req.on("error", err => {
      console.error("[MMM-Corelec] Fetch error:", err.message);
    });
    req.setTimeout(8000, () => {
      console.warn("[MMM-Corelec] Timeout.");
      req.destroy();
    });
  },
});
