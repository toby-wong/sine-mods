import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { SyncEngine } from "../sync-engine.mjs";
import {
  canonical, declaredPrefs, parseRepository, portablePref, rawURL,
  safePath, validateManifest, relayPayload,
} from "../sync-core.mjs";

const text = value => new TextEncoder().encode(value);
const hash = (value, algorithm = "sha256") => crypto.createHash(algorithm).update(value).digest("hex");
const commit = "a".repeat(40);
const settings = [
  { type: "dropdown", property: "uc.example.size" },
  { type: "checkbox", property: "uc.keyword-tab-search.enabled" },
  { type: "string", property: "extensions.example.api_key" },
  { type: "string", property: "extensions.example.ollama_base_url" },
  { type: "string", property: "uc.profile-switcher.external-profile" },
  { type: "string", property: "uc.example.file" },
];
const publicFiles = {
  "chrome.css": text(":root { --test-colour: red; }\n"),
  "preferences.json": text(JSON.stringify(settings)),
  "helper.sys.mjs": text("export const enabled = true;\n"),
};
const meta = {
  id: "example-mod", name: "Example", version: "1.0.0",
  homepage: "https://github.com/example/mod",
  preferences: "preferences.json", style: { chrome: "chrome.css", content: "" },
};

class Host {
  constructor(root, payloads) {
    this.root = root;
    this.modsDir = path.join(root, "chrome", "sine-mods");
    this.registryPath = path.join(this.modsDir, "mods.json");
    this.dataDir = path.join(root, "sine-sync");
    this.deviceId = crypto.randomUUID();
    this.processId = crypto.randomUUID();
    this.payloads = payloads;
    this.prefs = new Map();
    this.defaults = new Map();
    this.overrides = {};
    this.mode = "send";
    this.channel = "work";
    this.cancelled = false;
    this.fetchCount = 0;
    this.refreshes = 0;
    this.payloadWrites = 0;
  }
  join(...parts) { return path.join(...parts); }
  now() { return new Date().toISOString(); }
  nonce() { return crypto.randomUUID(); }
  hash(value, algorithm) { return hash(value, algorithm); }
  getPref(key) { return this.prefs.has(key) ? this.prefs.get(key) : (this.defaults.get(key) ?? null); }
  getUserPref(key) { return { set: this.prefs.has(key), value: this.getPref(key) }; }
  setPref(key, value) {
    if (this.failPref === key) { this.failPref = null; throw new Error("Simulated pref write failure"); }
    if (value === null) this.prefs.delete(key); else this.prefs.set(key, value);
  }
  clearPref(key) { this.prefs.delete(key); }
  prefLocked(key) { return this.lockedPref === key; }
  getPayload(channel) { return this.payloads.get(channel) || ""; }
  setPayload(channel, value) { this.payloadWrites++; this.payloads.set(channel, value); }
  status(value) { this.lastStatus = value; }
  watchPrefs(names) { this.watched = names; }
  assertCurrent(context) {
    if (this.cancelled || context.mode !== this.mode || context.channel !== this.channel) throw new Error("Settings changed");
  }
  async exists(file) { try { await fs.stat(file); return true; } catch (e) { if (e.code === "ENOENT") return false; throw e; } }
  async mkdir(directory) { await fs.mkdir(directory, { recursive: true }); }
  readFile(file) { return fs.readFile(file); }
  readText(file) { return fs.readFile(file, "utf8"); }
  async readJSON(file) { return JSON.parse(await this.readText(file)); }
  async writeFile(file, value) { await this.mkdir(path.dirname(file)); await fs.writeFile(file, value); }
  async writeJSON(file, value) { await this.writeFile(file, JSON.stringify(value)); }
  async move(from, to) {
    if (this.failMove === from) { this.failMove = null; throw new Error("Simulated move failure"); }
    await this.mkdir(path.dirname(to)); await fs.rename(from, to);
  }
  remove(file) { return fs.rm(file, { recursive: true, force: true }); }
  async listFiles(root) {
    const files = [];
    const walk = async (directory, prefix = "") => {
      for (const item of await fs.readdir(directory, { withFileTypes: true })) {
        if (item.isDirectory()) await walk(path.join(directory, item.name), prefix + item.name + "/");
        else {
          const info = await fs.stat(path.join(directory, item.name));
          files.push({ path: prefix + item.name, size: info.size, modified: info.mtimeMs });
        }
      }
    };
    await walk(root);
    return files;
  }
  async fetchJSON(url) {
    this.fetchCount++;
    if (url.includes("/commits/")) return { sha: commit };
    return {
      tree: Object.entries(publicFiles).map(([name, content]) => ({
        type: "blob", path: name,
        sha: hash(Buffer.concat([Buffer.from(`blob ${content.length}\0`), content]), "sha1"),
      })),
    };
  }
  async fetchBytes(url) {
    this.fetchCount++;
    if (this.beforeFetch) { const callback = this.beforeFetch; this.beforeFetch = null; await callback(); }
    if (this.badDownload) return text("damaged");
    return publicFiles[decodeURIComponent(url.split("/").at(-1))];
  }
  async refreshStyles() { this.refreshes++; }
  context() {
    return { mode: this.mode, channel: this.channel, settings: true, enabledStates: true };
  }
}

async function setup(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "sine-sync-test-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const payloads = new Map();
  const source = new Host(path.join(root, "source"), payloads);
  const target = new Host(path.join(root, "target"), payloads);
  target.mode = "receive";
  await source.writeJSON(source.registryPath, { [meta.id]: { ...meta, enabled: true } });
  for (const [name, content] of Object.entries(publicFiles)) {
    await source.writeFile(source.join(source.modsDir, meta.id, name), content);
  }
  await target.writeJSON(target.registryPath, {
    unrelated: { id: "unrelated", enabled: false, version: "local", "no-updates": false },
  });
  source.prefs.set("uc.example.size", "10px");
  source.prefs.set("uc.keyword-tab-search.enabled", true);
  source.prefs.set("extensions.example.api_key", "MUST-NOT-LEAVE-SOURCE");
  source.prefs.set("extensions.example.ollama_base_url", "http://localhost:11434");
  source.prefs.set("uc.profile-switcher.external-profile", "/Users/test/Work");
  const sender = new SyncEngine(source), receiver = new SyncEngine(target);
  await sender.publish(source.context());
  return { source, target, sender, receiver, payloads, root };
}

test("portable settings preserve keywords but exclude secrets, paths and endpoints", () => {
  assert.deepEqual(declaredPrefs(settings), ["uc.example.size", "uc.keyword-tab-search.enabled"]);
  for (const name of ["services.sync.test", "identity.foo", "security.test", "uc.sine-sync.mode"]) {
    assert.equal(portablePref(name, "x"), false);
  }
  assert.equal(portablePref("uc.example.test", "C:\\Users\\test"), false);
  assert.equal(portablePref("uc.example.test", "url(file:///tmp/test)"), false);
  assert.equal(portablePref("uc.example.test", "rgba(10,20,30,.5)"), true);
});

test("portable paths reject Windows device names, traversal and alternate streams", () => {
  for (const value of ["../escape", "/absolute", "a\\b", "a/../../b", "NUL.css", "a/COM1", "C:/file", "a:b", "a.", "a%2fb"]) {
    assert.equal(safePath(value), false, value);
  }
  assert.equal(safePath("modules/folder/helper.sys.mjs"), true);
  assert.throws(() => parseRepository("https://example.com/repo"));
});

test("sender uses pinned verified files; receiver never publishes or touches unrelated mods", async t => {
  const { source, target, receiver } = await setup(t);
  const result = await receiver.receive(target.context());
  assert.equal(result.restartRequired, true);
  assert.equal(target.payloadWrites, 0);
  const registry = await target.readJSON(target.registryPath);
  assert.equal(registry.unrelated.version, "local");
  assert.equal(registry.unrelated.enabled, false);
  assert.equal(registry[meta.id]["no-updates"], true);
  assert.equal(target.getPref("uc.example.size"), "10px");
  assert.equal(target.getPref("extensions.example.api_key"), null);
  assert.equal(source.getPayload("work").includes("MUST-NOT-LEAVE"), false);
  assert.equal(source.getPayload("work").includes("/Users/"), false);
  assert.match(rawURL(JSON.parse(source.getPayload("work")).mods[0].source, "chrome.css"), new RegExp(commit));
});

test("unchanged source reuses public file verification and revision", async t => {
  const { source, sender } = await setup(t);
  const before = source.fetchCount, first = source.getPayload("work");
  await sender.publish(source.context());
  assert.equal(source.fetchCount, before);
  assert.equal(source.getPayload("work"), first);
  source.prefs.set("uc.example.size", "8px");
  const update = await sender.publish(source.context());
  assert.equal(update.revision, 2);
  assert.equal(source.fetchCount, before);
});

test("unpublished source file changes do not replace the last good payload", async t => {
  const { source, sender } = await setup(t);
  const before = source.getPayload("work");
  await source.writeFile(source.join(source.modsDir, meta.id, "chrome.css"), text("local unpublished edit"));
  await assert.rejects(sender.publish(source.context()), /does not match GitHub/);
  assert.equal(source.getPayload("work"), before);
});

test("preferences formatting can differ, but changed definitions are rejected", async t => {
  const { source, sender } = await setup(t);
  const file = source.join(source.modsDir, meta.id, "preferences.json");
  await source.writeFile(file, text(JSON.stringify(settings, null, 4)));
  await sender.publish(source.context());
  const data = JSON.parse(source.getPayload("work"));
  assert.equal(data.mods[0].files.find(item => item.path === "preferences.json").sha256,
    hash(publicFiles["preferences.json"]));
  await source.writeFile(file, text(JSON.stringify([...settings, { type: "string", property: "new.setting" }])));
  await assert.rejects(sender.publish(source.context()), /does not match GitHub/);
});

test("settings changes apply without reloading code after restart", async t => {
  const { source, target, sender, receiver } = await setup(t);
  await receiver.receive(target.context());
  target.processId = "new-process";
  await receiver.clearRestartAfterStartup();
  const fetches = target.fetchCount;
  source.prefs.set("uc.example.size", "7px");
  await sender.publish(source.context());
  const result = await receiver.receive(target.context());
  assert.equal(result.restartRequired, false);
  assert.deepEqual(result.changedFiles, []);
  assert.equal(target.fetchCount, fetches);
  assert.equal(target.refreshes, 1);
  assert.equal(target.getPref("uc.example.size"), "7px");
});

test("bad file hash leaves existing files, preferences and registry intact", async t => {
  const { target, receiver } = await setup(t);
  const before = await target.readText(target.registryPath);
  target.badDownload = true;
  await assert.rejects(receiver.receive(target.context()), /verification/);
  assert.equal(await target.readText(target.registryPath), before);
  assert.equal(await target.exists(target.join(target.modsDir, meta.id)), false);
});

test("mid-transaction preference failure rolls files and registry back", async t => {
  const { target, receiver } = await setup(t);
  const registry = await target.readJSON(target.registryPath);
  registry[meta.id] = { ...meta, enabled: false, version: "old" };
  await target.writeJSON(target.registryPath, registry);
  await target.writeFile(target.join(target.modsDir, meta.id, "chrome.css"), text("original local code"));
  target.prefs.set("uc.example.size", "old-size");
  target.failPref = "uc.example.size";
  await assert.rejects(receiver.receive(target.context()), /Simulated pref write/);
  assert.deepEqual(await target.readJSON(target.registryPath), registry);
  assert.equal(await target.readText(target.join(target.modsDir, meta.id, "chrome.css")), "original local code");
  assert.equal(target.getPref("uc.example.size"), "old-size");
  assert.equal(await target.exists(target.join(target.modsDir, meta.id, "preferences.json")), false);
});

test("unrelated concurrent registry edits are preserved", async t => {
  const { target, receiver } = await setup(t);
  target.beforeFetch = async () => {
    const registry = await target.readJSON(target.registryPath);
    registry.another = { id: "another", enabled: true };
    await target.writeJSON(target.registryPath, registry);
  };
  await receiver.receive(target.context());
  assert.equal((await target.readJSON(target.registryPath)).another.enabled, true);
});

test("concurrent changes to a managed mod abort installation", async t => {
  const { target, receiver } = await setup(t);
  target.beforeFetch = async () => {
    const registry = await target.readJSON(target.registryPath);
    registry[meta.id] = { ...meta, enabled: false };
    await target.writeJSON(target.registryPath, registry);
  };
  await assert.rejects(receiver.receive(target.context()), /changed during download/);
  assert.equal((await target.readJSON(target.registryPath))[meta.id].enabled, false);
  assert.equal(await target.exists(target.join(target.modsDir, meta.id)), false);
});

test("changing role during download cancels without applying source settings", async t => {
  const { target, receiver } = await setup(t);
  target.beforeFetch = async () => { target.mode = "off"; };
  await assert.rejects(receiver.receive(target.context()), /Settings changed/);
  assert.equal((await target.readJSON(target.registryPath))[meta.id], undefined);
  assert.equal(target.getPref("uc.example.size"), null);
});

test("new incoming revision cancels an in-flight old installation", async t => {
  const { target, receiver, source, sender } = await setup(t);
  target.beforeFetch = async () => {
    source.prefs.set("uc.example.size", "updated");
    await sender.publish(source.context());
  };
  await assert.rejects(receiver.receive(target.context()), /newer sync arrived/);
  await receiver.receive(target.context());
  assert.equal(target.getPref("uc.example.size"), "updated");
});

test("removed source mods are disabled, retained and unrelated mods survive", async t => {
  const { source, sender, target, receiver } = await setup(t);
  await receiver.receive(target.context());
  await source.writeJSON(source.registryPath, {});
  await sender.publish(source.context());
  await receiver.receive(target.context());
  const registry = await target.readJSON(target.registryPath);
  assert.equal(registry[meta.id].enabled, false);
  assert.equal(registry.unrelated.version, "local");
  assert.equal(await target.exists(target.join(target.modsDir, meta.id, "chrome.css")), true);
});

test("portable-settings toggle preserves destination choices", async t => {
  const { target, receiver } = await setup(t);
  target.prefs.set("uc.example.size", "local");
  await receiver.receive({ ...target.context(), settings: false });
  assert.equal(target.getPref("uc.example.size"), "local");
});

test("on/off-state toggle preserves existing destination enable choice", async t => {
  const { target, receiver } = await setup(t);
  const registry = await target.readJSON(target.registryPath);
  registry[meta.id] = { ...meta, enabled: false };
  await target.writeJSON(target.registryPath, registry);
  await receiver.receive({ ...target.context(), enabledStates: false });
  assert.equal((await target.readJSON(target.registryPath))[meta.id].enabled, false);
});

test("work and personal channels remain separate", async t => {
  const { source, sender, target, receiver, payloads } = await setup(t);
  const work = payloads.get("work");
  source.channel = "personal";
  source.prefs.set("uc.example.size", "personal");
  await sender.publish(source.context());
  assert.equal(payloads.get("work"), work);
  await receiver.receive(target.context());
  assert.equal(target.getPref("uc.example.size"), "10px");
  target.channel = "personal";
  await receiver.receive(target.context());
  assert.equal(target.getPref("uc.example.size"), "personal");
});

test("a second sender requires explicit takeover rather than repeated overwrites", async t => {
  const { source, sender, payloads } = await setup(t);
  const data = JSON.parse(payloads.get("work"));
  data.source = crypto.randomUUID();
  payloads.set("work", canonical(data));
  await assert.rejects(sender.publish(source.context()), /another sender/);
  await sender.publish(source.context(), { claim: true });
  assert.equal(JSON.parse(payloads.get("work")).source, source.deviceId);
});

test("malformed paths, wrong channels and undeclared preferences cannot be applied", async t => {
  const { source, target, receiver, payloads } = await setup(t);
  const original = JSON.parse(source.getPayload("work"));
  assert.throws(() => validateManifest(original, "personal"), /mismatched/);
  const badPath = structuredClone(original);
  badPath.mods[0].files[0].path = "../prefs.js";
  assert.throws(() => validateManifest(badPath, "work"), /Invalid synced file/);
  const duplicate = structuredClone(original);
  duplicate.mods.push(duplicate.mods[0]);
  assert.throws(() => validateManifest(duplicate, "work"), /duplicate/);
  original.mods[0].prefs["uc.something.undeclared"] = "must-not-apply";
  payloads.set("work", canonical(original));
  await assert.rejects(receiver.receive(target.context()), /not declared/);
  assert.equal(target.getPref("uc.something.undeclared"), null);
});

test("locked preferences are detected before any installed files change", async t => {
  const { target, receiver } = await setup(t);
  target.lockedPref = "uc.example.size";
  await assert.rejects(receiver.receive(target.context()), /locked locally/);
  assert.equal(await target.exists(target.join(target.modsDir, meta.id)), false);
});

test("a missing channel waits without clearing destination state", async t => {
  const { target, receiver } = await setup(t);
  target.channel = "personal";
  assert.equal((await receiver.receive(target.context())).action, "waiting");
  assert.equal((await target.readJSON(target.registryPath)).unrelated.version, "local");
});

test("local relay accepts only fresh, valid, matching-channel manifests", async t => {
  const { source } = await setup(t);
  const manifest = JSON.parse(source.getPayload("work"));
  const now = Date.now();
  const packet = { schema: 1, owner: manifest.source, expires: now + 60000, manifest };
  assert.equal(relayPayload(packet, "work", "", now), canonical(manifest));
  assert.equal(relayPayload(packet, "work", canonical(manifest), now), null);
  assert.equal(relayPayload({ ...packet, expires: now - 1 }, "work", "", now), null);
  assert.throws(() => relayPayload(packet, "personal", "", now), /mismatched/);
  assert.throws(() => relayPayload({ ...packet, owner: "other" }, "work", "", now), /owner/);
  const other = { ...manifest, source: crypto.randomUUID() };
  assert.throws(() => relayPayload(packet, "work", canonical(other), now), /another sender/);
  assert.equal(relayPayload({ ...packet, claim: true }, "work", canonical(other), now), canonical(manifest));
  assert.equal(relayPayload(packet, "work", canonical({ ...manifest, revision: 99 }), now), null);
});
