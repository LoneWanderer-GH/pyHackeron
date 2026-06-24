/**
 * homebridge-corelec — Plugin Homebridge pour le régulateur piscine Corelec/Akeron
 *
 * Expose dans HomeKit :
 *   • ContactSensor  "Connexion"     — daemon BLE connecté / déconnecté
 *   • TemperatureSensor "pH"         — valeur pH affichée en °C (ex : 7.12°C = pH 7.12)
 *   • TemperatureSensor "Température"— température de l'eau
 *   • Fan            "Électrolyse"   — % production (rotation speed 0-100 %)
 *   • Switch         "Boost"         — activer/désactiver le boost chlore
 *
 * Toutes les lectures sont faites en interrogeant GET /api/state du web_server.py.
 * Les commandes (boost start/stop) utilisent POST /api/cmd.
 *
 * Aucune dépendance npm : utilise uniquement le module http/https natif Node.js.
 */

"use strict";

const http  = require("http");
const https = require("https");

const PLUGIN_NAME   = "homebridge-corelec";
const ACCESSORY_NAME = "CoreLecPool";

/** @param {import('homebridge').API} api */
module.exports = (api) => {
  api.registerAccessory(PLUGIN_NAME, ACCESSORY_NAME, CoreLecPoolAccessory);
};

// ── Helpers réseau ────────────────────────────────────────────────────────────

function fetchJson(rawUrl) {
  return new Promise((resolve, reject) => {
    const mod = rawUrl.startsWith("https") ? https : http;
    const req = mod.get(rawUrl, (res) => {
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      let buf = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { buf += c; });
      res.on("end",  () => {
        try { resolve(JSON.parse(buf)); }
        catch (e) { reject(e); }
      });
    });
    req.on("error", reject);
    req.setTimeout(8000, () => { req.destroy(new Error("timeout")); });
  });
}

function postJson(rawUrl, body) {
  return new Promise((resolve, reject) => {
    const mod  = rawUrl.startsWith("https") ? https : http;
    const data = JSON.stringify(body);
    const u    = new URL(rawUrl);
    const opts = {
      hostname: u.hostname,
      port:     u.port || (u.protocol === "https:" ? 443 : 80),
      path:     u.pathname + u.search,
      method:   "POST",
      headers:  { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) },
    };
    const req = mod.request(opts, (res) => {
      let buf = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { buf += c; });
      res.on("end",  () => {
        try { resolve(JSON.parse(buf)); }
        catch (e) { resolve({}); }
      });
    });
    req.on("error", reject);
    req.setTimeout(8000, () => { req.destroy(new Error("timeout")); });
    req.write(data);
    req.end();
  });
}

// ── Accessoire principal ──────────────────────────────────────────────────────

class CoreLecPoolAccessory {
  /**
   * @param {import('homebridge').Logging}           log
   * @param {object}                                 config
   * @param {import('homebridge').API}               api
   */
  constructor(log, config, api) {
    this.log  = log;
    this.api  = api;
    this.name = config.name || "Piscine";

    /** URL de base du web_server.py, ex : "http://192.168.0.20:8080" */
    this.baseUrl      = (config.webServerUrl || "http://localhost:8080").replace(/\/$/, "");
    this.pollInterval = (config.pollInterval  || 30) * 1000;
    /** Durée de boost par défaut en minutes quand on active le Switch */
    this.boostMinutes = config.boostMinutes   || 120;

    const { Service, Characteristic } = api.hap;
    this.Service        = Service;
    this.Characteristic = Characteristic;

    // ── Snapshot local ────────────────────────────────────────────────────
    this._state = {
      connected:          false,
      ph:                 7.0,
      temp:               20.0,
      electrolyse_pct:    0,
      boost_active:       false,
      boost_remaining_min: 0,
    };

    // ── Services ──────────────────────────────────────────────────────────
    this._buildServices();

    // ── Polling ───────────────────────────────────────────────────────────
    this._poll();
    this._timer = setInterval(() => this._poll(), this.pollInterval);

    log.info(`[Corelec] Plugin initialisé — ${this.baseUrl} (poll ${config.pollInterval || 30}s)`);
  }

  // ── Construction des services HomeKit ─────────────────────────────────

  _buildServices() {
    const { Service, Characteristic } = this;

    // AccessoryInformation
    this.infoService = new Service.AccessoryInformation()
      .setCharacteristic(Characteristic.Manufacturer,    "Corelec / Akeron")
      .setCharacteristic(Characteristic.Model,           "Pool Controller")
      .setCharacteristic(Characteristic.SerialNumber,    "corelec-001")
      .setCharacteristic(Characteristic.FirmwareRevision, "1.0");

    // ── 1. ContactSensor : Connexion BLE ──────────────────────────────────
    this.connectionService = new Service.ContactSensor("Connexion BLE", "connexion");
    this.connectionService.getCharacteristic(Characteristic.ContactSensorState)
      .onGet(() => {
        // 0 = contact détecté = CONNECTÉ  /  1 = contact ouvert = DÉCONNECTÉ
        return this._state.connected ? 0 : 1;
      });

    // ── 2. TemperatureSensor : pH ─────────────────────────────────────────
    //    Remarque : CurrentTemperature (-100…100 °C) sert à afficher le pH.
    //    L'accessoire s'appelle "pH" donc HomeKit affiche "7.12 pH" dans les apps tierces.
    this.phService = new Service.TemperatureSensor("pH", "ph");
    this.phService.getCharacteristic(Characteristic.CurrentTemperature)
      .setProps({ minValue: 0, maxValue: 14, minStep: 0.01 })
      .onGet(() => this._clamp(this._state.ph, 0, 14));

    // ── 3. TemperatureSensor : Température eau ─────────────────────────────
    this.tempService = new Service.TemperatureSensor("Température eau", "temp");
    this.tempService.getCharacteristic(Characteristic.CurrentTemperature)
      .setProps({ minValue: 0, maxValue: 50, minStep: 0.1 })
      .onGet(() => this._clamp(this._state.temp, 0, 50));

    // ── 4. Fan : Électrolyse % ────────────────────────────────────────────
    //    On = (elx > 0), RotationSpeed = valeur directe 0-100
    this.elxService = new Service.Fanv2("Électrolyse", "elx");
    this.elxService.getCharacteristic(Characteristic.Active)
      .onGet(() => this._state.electrolyse_pct > 0 ? 1 : 0);
    this.elxService.getCharacteristic(Characteristic.RotationSpeed)
      .setProps({ minValue: 0, maxValue: 100, minStep: 1 })
      .onGet(() => Math.round(this._state.electrolyse_pct));

    // ── 5. Switch : Boost ─────────────────────────────────────────────────
    this.boostService = new Service.Switch("Boost", "boost");
    this.boostService.getCharacteristic(Characteristic.On)
      .onGet(() => !!this._state.boost_active)
      .onSet(async (value) => {
        if (value) {
          await this._sendCmd({ type: "boost_start", minutes: this.boostMinutes });
        } else {
          await this._sendCmd({ type: "boost_stop" });
        }
      });
  }

  // ── Polling ────────────────────────────────────────────────────────────

  async _poll() {
    try {
      const data = await fetchJson(this.baseUrl + "/api/state");
      const conn = data.connection || {};
      const pool = data.pool       || {};

      this._state.connected           = conn.status_name === "connected";
      this._state.ph                  = pool.ph               ?? this._state.ph;
      this._state.temp                = pool.temp             ?? this._state.temp;
      this._state.electrolyse_pct     = pool.electrolyse_pct  ?? this._state.electrolyse_pct;
      this._state.boost_active        = !!pool.boost_active;
      this._state.boost_remaining_min = pool.boost_remaining_min ?? 0;

      this._pushUpdates();
    } catch (err) {
      this.log.warn(`[Corelec] Polling error: ${err.message}`);
      // Sur erreur réseau → marquer comme déconnecté
      this._state.connected = false;
      this._pushUpdates();
    }
  }

  _pushUpdates() {
    const { Characteristic } = this;

    // ContactSensor
    this.connectionService
      .getCharacteristic(Characteristic.ContactSensorState)
      .updateValue(this._state.connected ? 0 : 1);

    // pH
    this.phService
      .getCharacteristic(Characteristic.CurrentTemperature)
      .updateValue(this._clamp(this._state.ph, 0, 14));

    // Temp
    this.tempService
      .getCharacteristic(Characteristic.CurrentTemperature)
      .updateValue(this._clamp(this._state.temp, 0, 50));

    // Électrolyse
    this.elxService
      .getCharacteristic(Characteristic.Active)
      .updateValue(this._state.electrolyse_pct > 0 ? 1 : 0);
    this.elxService
      .getCharacteristic(Characteristic.RotationSpeed)
      .updateValue(Math.round(this._state.electrolyse_pct));

    // Boost
    this.boostService
      .getCharacteristic(Characteristic.On)
      .updateValue(!!this._state.boost_active);
  }

  // ── Commandes ──────────────────────────────────────────────────────────

  async _sendCmd(payload) {
    try {
      const resp = await postJson(this.baseUrl + "/api/cmd", payload);
      if (!resp.ok) {
        this.log.warn(`[Corelec] Commande refusée: ${JSON.stringify(resp)}`);
      }
    } catch (err) {
      this.log.error(`[Corelec] Erreur commande: ${err.message}`);
      throw err;
    }
  }

  // ── Utilitaires ────────────────────────────────────────────────────────

  _clamp(v, min, max) {
    if (v == null || isNaN(v)) return min;
    return Math.max(min, Math.min(max, Number(v)));
  }

  // ── API Homebridge ─────────────────────────────────────────────────────

  getServices() {
    return [
      this.infoService,
      this.connectionService,
      this.phService,
      this.tempService,
      this.elxService,
      this.boostService,
    ];
  }
}
