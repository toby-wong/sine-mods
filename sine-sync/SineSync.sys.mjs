import { setTimeout, clearTimeout, setInterval, clearInterval } from "resource://gre/modules/Timer.sys.mjs";
import { CHANNELS, DATA_PREFS, PREFIX, VERSION, MAX_FILE_BYTES, canonical, safePath, relayPayload } from "./sync-core.mjs";
import { SyncEngine } from "./sync-engine.mjs";

Cu.importGlobalProperties(["fetch", "AbortController", "TextEncoder", "TextDecoder"]);

const MODULE_URI = "chrome://sine/content/sine-sync/SineSync.sys.mjs";
const STATUS = `${PREFIX}status`;
const CONFIG_PREFS = ["mode", "channel", "settings", "enabled-states", "interval", "local-relay"].map(key => PREFIX + key);
const SYNC_TOPICS = ["weave:service:sync:finish", "weave:service:sync:error"];
const utf8 = new TextEncoder();
const makeId = () => Services.uuid.generateUUID().toString().slice(1, -1);

function getPref(name) {
  switch (Services.prefs.getPrefType(name)) {
    case Ci.nsIPrefBranch.PREF_BOOL: return Services.prefs.getBoolPref(name);
    case Ci.nsIPrefBranch.PREF_INT: return Services.prefs.getIntPref(name);
    case Ci.nsIPrefBranch.PREF_STRING: return Services.prefs.getStringPref(name);
    default: return null;
  }
}

function setPref(name, value) {
  if (value === null) Services.prefs.clearUserPref(name);
  else if (typeof value === "boolean") Services.prefs.setBoolPref(name, value);
  else if (typeof value === "number") Services.prefs.setIntPref(name, value);
  else Services.prefs.setStringPref(name, value);
}

function hash(content, algorithm = "sha256") {
  const digest = Cc["@mozilla.org/security/hash;1"].createInstance(Ci.nsICryptoHash);
  digest.initWithString(algorithm);
  digest.update(content, content.length);
  return [...digest.finish(false)].map(char => char.charCodeAt(0).toString(16).padStart(2, "0")).join("");
}

class BrowserHost {
  constructor(owner, manager, overrides) {
    this.owner = owner;
    this.manager = manager;
    this.overrides = overrides;
    this.profile = Services.dirsvc.get("ProfD", Ci.nsIFile).path;
    this.modsDir = PathUtils.join(this.profile, "chrome", "sine-mods");
    this.registryPath = PathUtils.join(this.modsDir, "mods.json");
    this.dataDir = PathUtils.join(this.profile, "sine-sync");
    this.relayDir = PathUtils.join(Services.dirsvc.get("UAppData", Ci.nsIFile).path, "sine-sync-relay");
    this.processId = `${Services.appinfo.processID}-${Date.now()}`;
    const idPref = PREFIX + "device-id";
    this.deviceId = Services.prefs.getStringPref(idPref, "");
    if (!this.deviceId) {
      this.deviceId = makeId();
      Services.prefs.setStringPref(idPref, this.deviceId);
    }
  }

  join(...parts) {
    // Relative paths in a manifest always use slash separators, including on Windows.
    return PathUtils.join(parts[0], ...parts.slice(1).flatMap(part => part.split("/")));
  }
  now() { return new Date().toISOString(); }
  nonce() { return makeId(); }
  hash(content, algorithm) { return hash(content, algorithm); }
  getPref(name) { return getPref(name); }
  getUserPref(name) { return { set: Services.prefs.prefHasUserValue(name), value: getPref(name) }; }
  setPref(name, value) { setPref(name, value); }
  clearPref(name) { Services.prefs.clearUserPref(name); }
  prefLocked(name) { return Services.prefs.prefIsLocked(name); }
  getPayload(channel) { return Services.prefs.getStringPref(PREFIX + "data." + channel, ""); }
  setPayload(channel, text) {
    Services.prefs.setStringPref(PREFIX + "data." + channel, text);
    Services.prefs.savePrefFile(null);
  }
  status(text) { this.owner.setStatus(text); }
  watchPrefs(names) { this.owner.watchPrefs(names); }
  assertCurrent(context) {
    if (!this.owner.started || context.epoch !== this.owner.epoch ||
        canonical(this.owner.config()) !== context.configKey) {
      throw new Error("Sync stopped because its settings changed.");
    }
  }
  exists(path) { return IOUtils.exists(path); }
  async mkdir(path) { await IOUtils.makeDirectory(path, { createAncestors: true, permissions: 0o700 }); }
  async readFile(path) {
    const stat = await IOUtils.stat(path, { followSymlinks: false });
    if (stat.type !== "regular" || stat.size > MAX_FILE_BYTES) throw new Error("Unsupported or oversized sync file.");
    return IOUtils.read(path);
  }
  async readText(path) { return new TextDecoder().decode(await this.readFile(path)); }
  async readJSON(path) { return JSON.parse(await this.readText(path)); }
  async writeFile(path, content) {
    await this.mkdir(PathUtils.parent(path));
    await IOUtils.write(path, content, { tmpPath: path + ".sine-sync-tmp", permissions: 0o600 });
  }
  async writeJSON(path, value) { await this.writeFile(path, utf8.encode(JSON.stringify(value, null, 2) + "\n")); }
  async move(from, to) {
    await this.mkdir(PathUtils.parent(to));
    await IOUtils.move(from, to, { noOverwrite: true });
  }
  async remove(path) { await IOUtils.remove(path, { recursive: true, ignoreAbsent: true }); }
  async listFiles(root) {
    const files = [];
    const walk = async (directory, prefix = "") => {
      const own = await IOUtils.stat(directory, { followSymlinks: false });
      if (own.type !== "directory") throw new Error("Symlinked mod directories are not supported.");
      for (const child of await IOUtils.getChildren(directory)) {
        const name = PathUtils.filename(child);
        if (name.startsWith(".") || /^(?:node_modules|tests?|scripts|reports|backups|hammerspoon)$/i.test(name)) continue;
        const relative = prefix + name;
        if (!safePath(relative)) throw new Error("A mod filename is not portable to Windows.");
        const info = await IOUtils.stat(child, { followSymlinks: false });
        if (info.type === "directory") await walk(child, relative + "/");
        else if (info.type === "regular") files.push({ path: relative, size: info.size, modified: info.lastModified });
        else throw new Error("Symlinked mod files are not supported.");
      }
    };
    await walk(root);
    return files;
  }
  async request(url, limit) {
    if (!/^https:\/\/(?:api\.github\.com|raw\.githubusercontent\.com)\//.test(url)) {
      throw new Error("Unsupported sync download host.");
    }
    const abort = new AbortController();
    this.owner.downloads.add(abort);
    const timeout = setTimeout(() => abort.abort(), 30000);
    try {
      const response = await fetch(url, {
        credentials: "omit", referrerPolicy: "no-referrer", signal: abort.signal,
        headers: { Accept: "application/vnd.github+json" },
      });
      if (!response.ok) throw new Error(`GitHub returned HTTP ${response.status}. Retry later.`);
      const reader = response.body.getReader();
      const chunks = [];
      let size = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > limit) {
          await reader.cancel();
          throw new Error("A sync download exceeds its expected size.");
        }
        chunks.push(value);
      }
      const result = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
      return result;
    } finally {
      clearTimeout(timeout);
      this.owner.downloads.delete(abort);
    }
  }
  async fetchJSON(url) { return JSON.parse(new TextDecoder().decode(await this.request(url, MAX_FILE_BYTES))); }
  fetchBytes(url, size) { return this.request(url, size); }
  async refreshStyles() { await this.manager.rebuildMods(false); }
  async writeRelay(manifest, context, claim) {
    this.assertCurrent(context);
    const path = this.join(this.relayDir, manifest.channel + ".json");
    if (await this.exists(path)) {
      const previous = await this.readJSON(path);
      if (previous.owner !== this.deviceId && previous.expires > Date.now() && !claim) {
        throw new Error("Another local profile is sending this channel.");
      }
    }
    this.assertCurrent(context);
    const requested = Number(context.interval);
    const seconds = [60, 300, 900].includes(requested) ? requested : 300;
    const ttl = (2 * seconds + 120) * 1000;
    await this.writeJSON(path, {
      schema: 1, owner: this.deviceId, expires: Date.now() + Math.min(ttl, 3600000),
      claim: !!claim, manifest,
    });
    this.relayTouched = true;
  }
  async clearOwnRelay() {
    if (!this.relayTouched && !this.owner.config().localRelay) return;
    for (const channel of CHANNELS) {
      const path = this.join(this.relayDir, channel + ".json");
      if (await this.exists(path)) {
        const packet = await this.readJSON(path);
        if (packet.owner === this.deviceId) await this.remove(path);
      }
    }
    this.relayTouched = false;
  }
}

class Controller {
  version = VERSION;
  started = false;
  starting = null;
  epoch = 0;
  timer = null;
  interval = null;
  relayTimer = null;
  running = null;
  queued = false;
  watched = new Set();
  downloads = new Set();
  engine = null;

  config() {
    return {
      mode: Services.prefs.getStringPref(PREFIX + "mode", "off"),
      channel: Services.prefs.getStringPref(PREFIX + "channel", "work"),
      settings: Services.prefs.getBoolPref(PREFIX + "settings", true),
      enabledStates: Services.prefs.getBoolPref(PREFIX + "enabled-states", true),
      interval: Services.prefs.getStringPref(PREFIX + "interval", "300"),
      localRelay: Services.prefs.getBoolPref(PREFIX + "local-relay", false),
    };
  }
  setStatus(text) {
    if (Services.prefs.getStringPref(STATUS, "") !== text) Services.prefs.setStringPref(STATUS, text);
  }
  async start() {
    if (this.starting) return this.starting;
    if (this.started) return;
    this.starting = this.initialize();
    try { await this.starting; } finally { this.starting = null; }
  }
  async initialize() {
    const manager = ChromeUtils.importESModule("chrome://userscripts/content/core/manager.sys.mjs").default;
    const profile = Services.dirsvc.get("ProfD", Ci.nsIFile).path;
    const overrides = await IOUtils.readJSON(PathUtils.join(profile, "chrome", "sine-mods", "sine-sync", "source-overrides.json"));
    this.started = true;
    this.epoch++;
    this.host ||= new BrowserHost(this, manager, overrides);
    this.engine ||= new SyncEngine(this.host);
    try {
      await this.engine.clearRestartAfterStartup();
      // Both channels must be understood on every participating profile because
      // Firefox keeps application preferences together in one encrypted record.
      for (const pref of DATA_PREFS) {
        Services.prefs.setBoolPref("services.sync.prefs.sync." + pref, true);
        Services.prefs.addObserver(pref, this);
      }
      // These controls are always local, including when changing direction.
      for (const pref of [...CONFIG_PREFS, PREFIX + "device-id", STATUS]) {
        Services.prefs.setBoolPref("services.sync.prefs.sync." + pref, false);
      }
      for (const pref of CONFIG_PREFS) Services.prefs.addObserver(pref, this);
      for (const topic of SYNC_TOPICS) Services.obs.addObserver(this, topic);
      manager.addUnloadListener(MODULE_URI, null, () => this.stop());
      this.resetInterval();
      this.schedule(1500);
    } catch (error) {
      await this.stop();
      throw error;
    }
  }
  watchPrefs(names) {
    for (const name of this.watched) if (!names.includes(name)) Services.prefs.removeObserver(name, this);
    for (const name of names) if (!this.watched.has(name)) Services.prefs.addObserver(name, this);
    this.watched = new Set(names);
  }
  resetInterval() {
    if (this.interval !== null) clearInterval(this.interval);
    if (this.relayTimer !== null) clearInterval(this.relayTimer);
    const seconds = Number(this.config().interval);
    this.interval = setInterval(() => this.schedule(0), ([60, 300, 900].includes(seconds) ? seconds : 300) * 1000);
    this.relayTimer = this.config().localRelay ? setInterval(() => {
      this.relayLocal().catch(error => this.setStatus(error.message));
    }, 30000) : null;
  }
  async relayLocal() {
    const config = this.config();
    if (!this.started || !config.localRelay || config.mode === "off" ||
        !Services.prefs.getStringPref("services.sync.username", "")) return;
    for (const channel of CHANNELS) {
      const path = this.host.join(this.host.relayDir, channel + ".json");
      if (!await this.host.exists(path)) continue;
      const packet = await this.host.readJSON(path);
      const text = relayPayload(packet, channel, this.host.getPayload(channel), Date.now());
      if (text && this.started && this.config().localRelay && this.config().mode !== "off") {
        this.host.setPayload(channel, text);
      }
    }
  }
  observe(subject, topic, name) {
    if (!this.started) return;
    if (topic === "nsPref:changed") {
      if (CONFIG_PREFS.includes(name)) {
        this.epoch++;
        for (const download of this.downloads) download.abort();
        this.resetInterval();
      }
      // Publishing writes the payload itself; only rerun if native Sync replaced it.
      if (DATA_PREFS.includes(name) && this.config().mode === "send") {
        const channel = this.config().channel;
        const outgoing = this.engine?.state.outgoing[channel];
        if (outgoing && this.host.getPayload(channel) === canonical(outgoing)) return;
      }
      this.schedule(1000);
    } else if (topic === "weave:service:sync:finish") {
      this.schedule(1000);
    } else if (topic === "weave:service:sync:error") {
      this.setStatus("Mozilla Sync could not connect. The local setup is preserved; retry when connected.");
    }
  }
  schedule(delay = 1000) {
    if (!this.started) return;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.timer = null;
      this.run().catch(error => this.setStatus(error.message));
    }, delay);
  }
  async run(options = {}) {
    if (!this.started) return;
    if (this.running) {
      this.queued = true;
      await this.running;
      if (options.claim) return this.run(options);
      return;
    }
    const config = this.config();
    if (config.mode === "off") {
      this.watchPrefs([]);
      await this.host.clearOwnRelay();
      this.setStatus("Off. Installed mods remain unchanged.");
      return { action: "off" };
    }
    if (!CHANNELS.includes(config.channel) || !["send", "receive"].includes(config.mode)) {
      throw new Error("Choose a valid sync role and channel.");
    }
    const context = { ...config, configKey: canonical(config), epoch: this.epoch };
    this.running = (async () => {
      const result = config.mode === "send"
        ? await this.engine.publish(context, options)
        : await this.engine.receive(context);
      if (config.localRelay && config.mode === "send") {
        await this.host.writeRelay(result.manifest, context, options.claim);
      } else {
        await this.host.clearOwnRelay();
      }
      await this.relayLocal();
      return result;
    })();
    try { return await this.running; }
    finally {
      this.running = null;
      if (this.queued) { this.queued = false; this.schedule(1000); }
    }
  }
  async syncNow({ claim = false } = {}) {
    await this.start();
    if (this.timer !== null) { clearTimeout(this.timer); this.timer = null; }
    if (this.config().mode === "off") return this.run();
    if (this.config().mode === "send") await this.run({ claim });
    // An unsigned-in source can hand its manifest to another opted-in local
    // profile. Do not turn on browser sync or import accounts on its behalf.
    if (!Services.prefs.getStringPref("services.sync.username", "")) {
      this.setStatus(this.config().localRelay
        ? "Queued locally. A signed-in profile with Local relay enabled will upload this channel."
        : "Sign in to the same Mozilla account on both computers, then choose Sync now.");
      return { action: this.config().localRelay ? "queued-for-local-relay" : "sign-in-required" };
    }
    await this.relayLocal();
    const { Weave } = ChromeUtils.importESModule("resource://services-sync/main.sys.mjs");
    await Weave.Service.promiseInitialized;
    const prefsEngine = Weave.Service.engineManager.get("prefs");
    if (!prefsEngine?.enabled) {
      this.setStatus("Turn on Settings in your Mozilla account’s Sync options, then choose Sync now.");
      return { action: "settings-sync-disabled" };
    }
    await Weave.Service.sync({ engines: ["prefs"], why: "user" });
    if (this.config().mode === "send") {
      // Native prefs sync can first accept an older server record. Reassert the
      // configured sender after that pull, then upload once more if necessary.
      const afterPull = canonical(CHANNELS.map(channel => this.host.getPayload(channel)));
      await this.run({ claim });
      if (canonical(CHANNELS.map(channel => this.host.getPayload(channel))) !== afterPull) {
        await Weave.Service.sync({ engines: ["prefs"], why: "user" });
      }
    }
    if (this.config().mode === "receive") return this.run();
    return { action: "sync-requested" };
  }
  async stop() {
    if (!this.started) return;
    this.started = false;
    this.epoch++;
    if (this.timer !== null) clearTimeout(this.timer);
    if (this.interval !== null) clearInterval(this.interval);
    if (this.relayTimer !== null) clearInterval(this.relayTimer);
    this.timer = this.interval = this.relayTimer = null;
    for (const download of this.downloads) download.abort();
    for (const pref of [...CONFIG_PREFS, ...DATA_PREFS]) {
      try { Services.prefs.removeObserver(pref, this); } catch {}
    }
    for (const topic of SYNC_TOPICS) {
      try { Services.obs.removeObserver(this, topic); } catch {}
    }
    this.watchPrefs([]);
    if (this.running) await this.running.catch(() => {});
    await this.host?.clearOwnRelay();
    this.setStatus("Off. Installed mods remain unchanged.");
  }
}

export const controller = new Controller();
