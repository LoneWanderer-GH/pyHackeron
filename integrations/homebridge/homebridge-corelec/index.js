/**
 * homebridge-corelec — Homebridge plugin for Corelec/Akeron pool controller
 *
 * Exposes in HomeKit:
 *   • ContactSensor      "Connexion BLE" — BLE daemon connected / disconnected
 *   • TemperatureSensor  "pH"            — pH value displayed as °C (7.12 °C = pH 7.12)
 *   • TemperatureSensor  "Température"   — water temperature  (if exposeTemp: true)
 *   • TemperatureSensor  "Redox"         — Redox/ORP in mV    (if exposeRedox: true)
 *   • Fanv2              "Électrolyse"   — electrolysis % (rotation speed 0-100 %)
 *   • Switch             "Boost"         — start/stop chlorine boost
 *
 * All reads poll GET /api/state from web_server.py.
 * Commands (boost) use POST /api/cmd.
 * No npm dependencies — only built-in http/https modules.
 *
 * Config options (config.schema.json):
 *   webServerUrl      URL of web_server.py  (default: http://localhost:8080)
 *   pollInterval      Polling interval in s  (default: 30)
 *   boostMinutes      Duration when boost switch toggled on (default: 120)
 *   clearOnDisconnect When true (default) accessories report "Not Responding"
 *                     when BLE is lost; false keeps last known value.
 *   exposeTemp        Expose water temperature sensor (default: true)
 *   exposeRedox       Expose Redox/ORP sensor         (default: false)
 */

"use strict";

const http  = require("http");
const https = require("https");

const PLUGIN_NAME    = "homebridge-corelec";
const ACCESSORY_NAME = "CoreLecPool";

/** @param {import('homebridge').API} api */
module.exports = (api) => {
  api.registerAccessory(PLUGIN_NAME, ACCESSORY_NAME, CoreLecPoolAccessory);
};

// ── Helpers réseau ────────────────────────────────────────────────────────────

function fetchJson(rawUrl, timeoutMs = 8000) {
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
    req.setTimeout(timeoutMs, () => { req.destroy(new Error("timeout")); });
  });
}

function postJson(rawUrl, body, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const mod  = rawUrl.startsWith("https") ? https : http;
    const data = JSON.stringify(body);
    const u    = new URL(rawUrl);
    const opts = {
      hostname: u.hostname,
      port:     Number(u.port) || (u.protocol === "https:" ? 443 : 80),
      path:     u.pathname + u.search,
      method:   "POST",
      headers:  {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(data),
      },
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
    req.setTimeout(timeoutMs, () => { req.destroy(new Error("timeout")); });
    req.write(data);
    req.end();
  });
}

// ── Accessoire principal ──────────────────────────────────────────────────────

class CoreLecPoolAccessory {
  /**
   * @param {import('homebridge').Logging}  log
   * @param {object}                        config
   * @param {import('homebridge').API}      api
   */
  constructor(log, config, api) {
    this.log  = log;
    this.api  = api;
    this.name = config.name || "Piscine";

    this.baseUrl           = (config.webServerUrl || "http://localhost:8080").replace(/\/$/, "");
    this.pollInterval      = (config.pollInterval  ?? 30) * 1000;
    this.boostMinutes      = config.boostMinutes   ?? 120;
    /** When true: throw HAP error on onGet while BLE is disconnected → shows "—" */
    this.clearOnDisconnect = config.clearOnDisconnect ?? true;
    this.exposeTemp        = config.exposeTemp  ?? true;
    this.exposeRedox       = config.exposeRedox ?? false;
    this.pinCode           = config.pinCode    ?? '';

    const { Service, Characteristic, HAPStatus } = api.hap;
    this.Service        = Service;
    this.Characteristic = Characteristic;
    this.HAPStatus      = HAPStatus;

    // ── Local snapshot ─────────────────────────────────────────────────
    this._state = {
      connected:           false,
      ph:                  7.0,
      temp:                20.0,
      redox:               650,
      electrolyse_pct:     0,
      boost_active:        false,
      boost_remaining_min: 0,
    };
    /** true when the last poll failed or BLE is disconnected */
    this._stale = true;

    // ── Build services ─────────────────────────────────────────────────
    this._services = this._buildServices();

    // ── Start polling ──────────────────────────────────────────────────
    api.on("didFinishLaunching", () => {
      this._poll();
      this._timer = setInterval(() => this._poll(), this.pollInterval);
    });

    log.info(`[Corelec] Initialized — ${this.baseUrl} | poll ${config.pollInterval ?? 30}s | clearOnDisconnect=${this.clearOnDisconnect}`);
  }

  // ── Build HomeKit services ─────────────────────────────────────────

  _buildServices() {
    const { Service, Characteristic } = this;

    // ── AccessoryInformation ──────────────────────────────────────────
    const infoService = new Service.AccessoryInformation()
      .setCharacteristic(Characteristic.Manufacturer,     "Corelec / Akeron")
      .setCharacteristic(Characteristic.Model,            "Pool Controller")
      .setCharacteristic(Characteristic.SerialNumber,     "corelec-001")
      .setCharacteristic(Characteristic.FirmwareRevision, "1.1.0");

    // ── 1. ContactSensor: BLE Connection ─────────────────────────────
    //    CONTACT_DETECTED(0) = connected / CONTACT_NOT_DETECTED(1) = disconnected
    const connectionService = new Service.ContactSensor("Connexion BLE", "connexion");
    connectionService.getCharacteristic(Characteristic.ContactSensorState)
      .onGet(() => this._state.connected ? 0 : 1);
    this._connectionService = connectionService;

    // ── 2. TemperatureSensor: pH ──────────────────────────────────────
    //    CurrentTemperature (-100…140 °C) is used to carry the pH value.
    const phService = new Service.TemperatureSensor("pH", "ph");
    phService.getCharacteristic(Characteristic.CurrentTemperature)
      .setProps({ minValue: 0, maxValue: 14, minStep: 0.01 })
      .onGet(() => {
        this._assertFresh();
        return this._clamp(this._state.ph, 0, 14);
      });
    this._phService = phService;

    const services = [infoService, connectionService, phService];

    // ── 3. TemperatureSensor: Water temperature ───────────────────────
    if (this.exposeTemp) {
      const tempService = new Service.TemperatureSensor("Température eau", "temp");
      tempService.getCharacteristic(Characteristic.CurrentTemperature)
        .setProps({ minValue: 0, maxValue: 50, minStep: 0.1 })
        .onGet(() => {
          this._assertFresh();
          return this._clamp(this._state.temp, 0, 50);
        });
      this._tempService = tempService;
      services.push(tempService);
    }

    // ── 4. TemperatureSensor: Redox/ORP ──────────────────────────────
    //    ORP in mV mapped to CurrentTemperature (range 0-1100).
    if (this.exposeRedox) {
      const redoxService = new Service.TemperatureSensor("Redox", "redox");
      redoxService.getCharacteristic(Characteristic.CurrentTemperature)
        .setProps({ minValue: 0, maxValue: 1100, minStep: 1 })
        .onGet(() => {
          this._assertFresh();
          return this._clamp(this._state.redox, 0, 1100);
        });
      this._redoxService = redoxService;
      services.push(redoxService);
    }

    // ── 5. Fanv2: Electrolysis % ──────────────────────────────────────
    //    Active = (elx > 0), RotationSpeed = 0–100.
    const elxService = new Service.Fanv2("Électrolyse", "elx");
    elxService.getCharacteristic(Characteristic.Active)
      .onGet(() => {
        if (this._stale && this.clearOnDisconnect) return 0;
        return this._state.electrolyse_pct > 0 ? 1 : 0;
      });
    elxService.getCharacteristic(Characteristic.RotationSpeed)
      .setProps({ minValue: 0, maxValue: 100, minStep: 1 })
      .onGet(() => {
        if (this._stale && this.clearOnDisconnect) return 0;
        return Math.round(this._state.electrolyse_pct);
      });
    this._elxService = elxService;
    services.push(elxService);

    // ── 6. Switch: Boost ──────────────────────────────────────────────
    const boostService = new Service.Switch("Boost", "boost");
    boostService.getCharacteristic(Characteristic.On)
      .onGet(() => {
        if (this._stale && this.clearOnDisconnect) return false;
        return !!this._state.boost_active;
      })
      .onSet(async (value) => {
        if (value) {
          await this._sendCmd({ type: "boost_start", minutes: this.boostMinutes });
        } else {
          await this._sendCmd({ type: "boost_stop" });
        }
      });
    this._boostService = boostService;
    services.push(boostService);

    return services;
  }

  // ── Stale guard ────────────────────────────────────────────────────

  /**
   * Throw a HAP communication failure error when clearOnDisconnect is enabled
   * and BLE is not connected.  HomeKit will display "—" for the characteristic.
   */
  _assertFresh() {
    if (this._stale && this.clearOnDisconnect) {
      throw new this.api.hap.HapStatusError(
        this.HAPStatus.SERVICE_COMMUNICATION_FAILURE,
      );
    }
  }

  // ── Polling ────────────────────────────────────────────────────────

  async _poll() {
    try {
      const data = await fetchJson(this.baseUrl + "/api/state");
      const conn = data.connection || {};
      const pool = data.pool       || {};

      const wasConnected = this._state.connected;
      this._state.connected           = conn.status_name === "connected";
      this._state.ph                  = pool.ph                ?? this._state.ph;
      this._state.temp                = pool.temp              ?? this._state.temp;
      this._state.redox               = pool.redox             ?? this._state.redox;
      this._state.electrolyse_pct     = pool.electrolyse_pct   ?? this._state.electrolyse_pct;
      this._state.boost_active        = !!pool.boost_active;
      this._state.boost_remaining_min = pool.boost_remaining_min ?? 0;

      const wasStale = this._stale;
      this._stale = !this._state.connected;

      if (wasStale && !this._stale) {
        this.log.info("[Corelec] BLE reconnected — resuming live values");
      } else if (!wasStale && this._stale) {
        this.log.warn("[Corelec] BLE disconnected — values " +
          (this.clearOnDisconnect ? "cleared" : "frozen at last known state"));
      }

      this._pushUpdates();
    } catch (err) {
      this.log.warn(`[Corelec] Poll error: ${err.message}`);
      this._stale = true;
      this._state.connected = false;
      this._pushUpdates();
    }
  }

  _pushUpdates() {
    const { Characteristic } = this;

    // ContactSensor — always reflects real connection state
    this._connectionService
      .getCharacteristic(Characteristic.ContactSensorState)
      .updateValue(this._state.connected ? 0 : 1);

    if (this._stale && this.clearOnDisconnect) {
      // Characteristics that support null / error will show "—" via onGet throwing.
      // updateValue with null is not valid in HAP; let onGet handle it.
      return;
    }

    // pH
    this._phService
      .getCharacteristic(Characteristic.CurrentTemperature)
      .updateValue(this._clamp(this._state.ph, 0, 14));

    // Temperature (optional)
    if (this._tempService) {
      this._tempService
        .getCharacteristic(Characteristic.CurrentTemperature)
        .updateValue(this._clamp(this._state.temp, 0, 50));
    }

    // Redox (optional)
    if (this._redoxService) {
      this._redoxService
        .getCharacteristic(Characteristic.CurrentTemperature)
        .updateValue(this._clamp(this._state.redox, 0, 1100));
    }

    // Electrolysis
    this._elxService
      .getCharacteristic(Characteristic.Active)
      .updateValue(this._state.electrolyse_pct > 0 ? 1 : 0);
    this._elxService
      .getCharacteristic(Characteristic.RotationSpeed)
      .updateValue(Math.round(this._state.electrolyse_pct));

    // Boost
    this._boostService
      .getCharacteristic(Characteristic.On)
      .updateValue(!!this._state.boost_active);
  }

  // ── Commands ───────────────────────────────────────────────────────

  async _sendCmd(payload) {
    try {
      const resp = await postJson(this.baseUrl + "/api/cmd", payload);
      if (!resp.ok) {
        this.log.warn(`[Corelec] Command rejected: ${JSON.stringify(resp)}`);
      }
    } catch (err) {
      this.log.error(`[Corelec] Command error: ${err.message}`);
      throw err;
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────

  _clamp(v, min, max) {
    if (v == null || Number.isNaN(Number(v))) return min;
    return Math.max(min, Math.min(max, Number(v)));
  }

  // ── Homebridge API ─────────────────────────────────────────────────

  getServices() {
    return this._services;
  }
}

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
      const body = this.pinCode ? { ...payload, pin: this.pinCode } : payload;
      const resp = await postJson(this.baseUrl + "/api/cmd", body);
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
