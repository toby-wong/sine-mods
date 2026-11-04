import {
  canonical, cleanMeta, declaredPrefs, entrypoints, MAX_FILE_BYTES,
  nextRegistry, parseRepository, portablePref, rawURL, runtimeFile,
  safeId, validateManifest,
} from "./sync-core.mjs";

const same = (a, b) => canonical(a) === canonical(b);
const bytes = text => new TextEncoder().encode(text);

// All I/O is behind the host. The same transaction runs in the browser and tests.
export class SyncEngine {
  constructor(host) {
    this.h = host;
    this.state = { schema: 1, snapshots: {}, outgoing: {}, received: {} };
    this.trees = new Map();
    this.freshRefs = new Set();
    this.ready = false;
  }

  async init() {
    if (this.ready) return;
    await this.h.mkdir(this.h.dataDir);
    const path = this.h.join(this.h.dataDir, "state.json");
    if (await this.h.exists(path)) {
      const state = await this.h.readJSON(path);
      if (state.schema !== 1) throw new Error("Unsupported local sync state.");
      this.state = state;
    }
    this.ready = true;
  }

  async save() {
    await this.h.writeJSON(this.h.join(this.h.dataDir, "state.json"), this.state);
  }

  async tree(repository, requestedRef) {
    const key = `${repository.owner}/${repository.repo}/${requestedRef}`;
    if (this.trees.has(key)) {
      const cached = this.trees.get(key);
      return { ...cached, source: { ...cached.source, folder: repository.folder } };
    }
    const root = `https://api.github.com/repos/${repository.owner}/${repository.repo}`;
    let commit = requestedRef;
    if (!/^[a-f0-9]{40}$/.test(commit)) {
      const info = await this.h.fetchJSON(`${root}/commits/${encodeURIComponent(commit)}`);
      commit = info.sha;
    }
    if (!/^[a-f0-9]{40}$/.test(commit)) throw new Error("GitHub did not return a pinned revision.");
    const tree = await this.h.fetchJSON(`${root}/git/trees/${commit}?recursive=1`);
    if (tree.truncated || !Array.isArray(tree.tree)) throw new Error("The source tree is incomplete.");
    const result = {
      source: { owner: repository.owner, repo: repository.repo, folder: repository.folder, commit },
      blobs: new Map(tree.tree.filter(item => item.type === "blob").map(item => [item.path, item.sha])),
    };
    this.trees.set(key, result);
    return result;
  }

  async describeMod(mod) {
    const h = this.h;
    const override = h.overrides[mod.id] || {};
    const homepage = override.homepage || mod.homepage;
    const repository = parseRepository(homepage);
    const meta = cleanMeta({ ...mod, homepage });
    const folder = h.join(h.modsDir, mod.id);
    const listed = (await h.listFiles(folder)).filter(file =>
      runtimeFile(file.path) && (!override.files || override.files.includes(file.path)))
      .sort((a, b) => a.path.localeCompare(b.path));
    const fingerprint = h.hash(bytes(canonical({ meta, files: listed, commit: mod.commit || "" })));
    const previous = this.state.snapshots[mod.id];
    let bundle, names;
    if (previous?.fingerprint === fingerprint) {
      bundle = previous.bundle;
      names = previous.names;
    } else {
      h.status(`Checking published files for ${mod.name || mod.id}…`);
      const ref = override.revisions?.[mod.version] || mod.commit || repository.ref;
      // A changed local file must recheck moving branches, rather than a stale tree.
      const refKey = `${repository.owner}/${repository.repo}/${ref}`;
      if (!/^[a-f0-9]{40}$/.test(ref) && !this.freshRefs.has(refKey)) {
        this.trees.delete(refKey);
        this.freshRefs.add(refKey);
      }
      const { source, blobs } = await this.tree(repository, ref);
      const files = [];
      names = [];
      for (const item of listed) {
        if (item.size > MAX_FILE_BYTES) throw new Error(`${mod.id}: a file exceeds the sync size limit.`);
        let content = await h.readFile(h.join(folder, item.path));
        const header = bytes(`blob ${content.length}\0`);
        const gitBytes = new Uint8Array(header.length + content.length);
        gitBytes.set(header);
        gitBytes.set(content, header.length);
        const repoPath = [repository.folder, item.path].filter(Boolean).join("/");
        if (blobs.get(repoPath) !== h.hash(gitBytes, "sha1")) {
          // Sine can reformat a preferences file. Accept only semantic identity,
          // and still send the hash of the actual pinned public bytes.
          let equivalent = false;
          if (item.path === meta.preferences && blobs.has(repoPath)) {
            const remote = await h.fetchBytes(rawURL(source, item.path), MAX_FILE_BYTES);
            try {
              equivalent = same(
                JSON.parse(new TextDecoder().decode(content)),
                JSON.parse(new TextDecoder().decode(remote))
              );
            } catch {}
            if (equivalent) content = remote;
          }
          if (!equivalent) {
            throw new Error(`${mod.id}/${item.path} does not match GitHub. Publish the local changes before syncing.`);
          }
        }
        files.push({ path: item.path, size: content.length, sha256: h.hash(content) });
        if (item.path === meta.preferences) {
          names = declaredPrefs(JSON.parse(new TextDecoder().decode(content)));
        }
      }
      bundle = { id: mod.id, meta, source, files };
      const paths = new Set(files.map(file => file.path));
      if (!files.length || entrypoints(meta).some(path => !paths.has(path))) {
        throw new Error(`${mod.id}: missing or unsupported runtime files.`);
      }
      this.state.snapshots[mod.id] = { fingerprint, bundle, names };
    }
    const prefs = {};
    for (const name of names) {
      const value = h.getPref(name);
      if (portablePref(name, value)) prefs[name] = value;
    }
    return { ...structuredClone(bundle), enabled: mod.enabled !== false, prefs };
  }

  async publish(context, { claim = false } = {}) {
    await this.init();
    const h = this.h;
    h.assertCurrent(context);
    const registryText = await h.readText(h.registryPath);
    const registry = JSON.parse(registryText);
    this.freshRefs.clear();
    const mods = [];
    for (const mod of Object.values(registry)) {
      if (mod.id === "sine-sync" || mod.id?.startsWith("local-")) continue;
      if (!safeId(mod.id)) throw new Error("An installed mod has an unsupported ID.");
      const description = await this.describeMod(mod);
      if (!context.settings) description.prefs = {};
      mods.push(description);
      h.assertCurrent(context);
    }
    mods.sort((a, b) => a.id.localeCompare(b.id));
    if (registryText !== await h.readText(h.registryPath)) {
      throw new Error("The installed mod list changed. Sync will retry.");
    }
    const previous = this.state.outgoing[context.channel];
    const current = h.getPayload(context.channel);
    if (current && !claim) {
      const other = validateManifest(current, context.channel);
      if (other.source !== h.deviceId) {
        throw new Error("This channel has another sender. Stop that sender, then choose “Use this computer as sender”.");
      }
    }
    const manifest = same(previous?.mods, mods) && previous?.source === h.deviceId
      ? previous
      : {
        schema: 1, channel: context.channel, source: h.deviceId,
        revision: Math.max(previous?.revision || 0, 0) + 1,
        createdAt: h.now(), mods,
      };
    validateManifest(manifest, context.channel);
    h.assertCurrent(context);
    this.state.outgoing[context.channel] = manifest;
    await this.save();
    h.assertCurrent(context);
    const text = canonical(manifest);
    if (h.getPayload(context.channel) !== text) h.setPayload(context.channel, text);
    h.watchPrefs(mods.flatMap(mod => Object.keys(mod.prefs)));
    h.status(`Ready to send ${mods.length} mods (${context.channel}, revision ${manifest.revision}).`);
    return { action: "send", mods: mods.length, revision: manifest.revision, manifest };
  }

  async receive(context) {
    await this.init();
    const h = this.h;
    h.assertCurrent(context);
    const incoming = h.getPayload(context.channel);
    if (!incoming) {
      h.status(`Waiting for the ${context.channel} sender. Sign in and sync Settings on both computers.`);
      return { action: "waiting" };
    }
    const manifest = validateManifest(incoming, context.channel);
    const initialText = await h.readText(h.registryPath);
    const initial = JSON.parse(initialText);
    const previous = this.state.received[context.channel] || { managed: [] };
    const desired = nextRegistry(initial, manifest, previous.managed, context.enabledStates);
    const touchedIds = new Set([...manifest.mods.map(mod => mod.id), ...previous.managed]);
    const changedFiles = [];
    const prefs = {};
    const transaction = h.join(h.dataDir, "staging", h.nonce());
    await h.mkdir(transaction);
    try {
      for (const mod of manifest.mods) {
        h.assertCurrent(context);
        h.status(`Checking ${mod.meta.name || mod.id}…`);
        const localDir = h.join(h.modsDir, mod.id);
        let filesMatch = true;
        for (const file of mod.files) {
          const path = h.join(localDir, file.path);
          if (!await h.exists(path) || h.hash(await h.readFile(path)) !== file.sha256) {
            filesMatch = false;
            break;
          }
        }
        let prefBytes;
        if (!filesMatch) {
          const stage = h.join(transaction, mod.id);
          await h.mkdir(stage);
          // Download sequentially within a mod: bounded memory and no request storm.
          for (const file of mod.files) {
            h.assertCurrent(context);
            const content = await h.fetchBytes(rawURL(mod.source, file.path), file.size);
            if (content.length !== file.size || h.hash(content) !== file.sha256) {
              throw new Error(`${mod.id}/${file.path}: downloaded contents failed verification.`);
            }
            await h.writeFile(h.join(stage, file.path), content);
            if (file.path === mod.meta.preferences) prefBytes = content;
          }
          await h.writeJSON(h.join(stage, "theme.json"), mod.meta);
          changedFiles.push(mod.id);
        } else if (mod.meta.preferences) {
          prefBytes = await h.readFile(h.join(localDir, mod.meta.preferences));
        }
        if (context.settings && prefBytes) {
          const allowed = new Set(declaredPrefs(JSON.parse(new TextDecoder().decode(prefBytes))));
          for (const [name, value] of Object.entries(mod.prefs)) {
            if (!allowed.has(name)) throw new Error(`${mod.id}: a setting is not declared by the downloaded mod.`);
            if (Object.hasOwn(prefs, name) && !same(prefs[name], value)) {
              throw new Error("Two synced mods disagree about a shared preference.");
            }
            prefs[name] = value;
          }
        }
      }
      h.assertCurrent(context);
      if (h.getPayload(context.channel) !== incoming) {
        throw new Error("A newer sync arrived during download. Sync will retry.");
      }
      const changedPrefs = Object.keys(prefs).filter(name => !same(h.getPref(name), prefs[name]));
      for (const name of changedPrefs) {
        if (h.prefLocked(name)) throw new Error(`The setting ${name} is locked locally.`);
      }
      // Refresh before writing. Preserve unrelated edits made while downloads ran.
      const freshText = await h.readText(h.registryPath);
      const fresh = JSON.parse(freshText);
      for (const id of touchedIds) {
        if (!same(initial[id], fresh[id])) throw new Error("A synced mod changed during download. Sync will retry.");
      }
      const merged = { ...fresh };
      for (const id of touchedIds) if (desired[id]) merged[id] = desired[id];
      const registryChanged = !same(fresh, merged);
      const restart = changedFiles.length > 0 || [...touchedIds].some(id =>
        !same(fresh[id]?.scripts, merged[id]?.scripts) ||
        fresh[id]?.enabled !== merged[id]?.enabled);
      let backup = null;
      if (registryChanged || changedPrefs.length || changedFiles.length) {
        backup = h.join(h.dataDir, "backups", `${h.now().replace(/[:.]/g, "-")}-${h.nonce()}`);
        await h.mkdir(backup);
        const oldPrefs = Object.fromEntries(changedPrefs.map(name => [name, h.getUserPref(name)]));
        await h.writeJSON(h.join(backup, "registry-before.json"), fresh);
        await h.writeJSON(h.join(backup, "preferences-before.json"), oldPrefs);
        const receipt = {
          schema: 1, channel: context.channel, revision: manifest.revision,
          changedFiles, changedPrefs, status: "prepared", touchedIds: [...touchedIds],
        };
        await h.writeJSON(h.join(backup, "receipt.json"), receipt);
        h.assertCurrent(context);
        if (freshText !== await h.readText(h.registryPath)) {
          throw new Error("The mod registry changed immediately before installation. Sync will retry.");
        }
        const moved = [];
        let registryWritten = false;
        try {
          for (const id of changedFiles) {
            h.assertCurrent(context);
            const localDir = h.join(h.modsDir, id);
            const existed = await h.exists(localDir);
            if (existed) await h.move(localDir, h.join(backup, "mods", id));
            moved.push({ id, existed });
            await h.move(h.join(transaction, id), localDir);
          }
          h.assertCurrent(context);
          await h.writeJSON(h.registryPath, merged);
          registryWritten = true;
          for (const name of changedPrefs) h.setPref(name, prefs[name]);
          receipt.status = "installed";
          receipt.restartRequired = restart;
          await h.writeJSON(h.join(backup, "receipt.json"), receipt);
        } catch (error) {
          for (const { id, existed } of moved.reverse()) {
            await h.remove(h.join(h.modsDir, id));
            if (existed) await h.move(h.join(backup, "mods", id), h.join(h.modsDir, id));
          }
          if (registryWritten) {
            const rollback = await h.readJSON(h.registryPath);
            for (const id of touchedIds) {
              if (fresh[id]) rollback[id] = fresh[id];
              else delete rollback[id];
            }
            await h.writeJSON(h.registryPath, rollback);
          }
          for (const [name, saved] of Object.entries(oldPrefs)) {
            if (saved.set) h.setPref(name, saved.value);
            else h.clearPref(name);
          }
          receipt.status = "rolled-back";
          await h.writeJSON(h.join(backup, "receipt.json"), receipt);
          throw error;
        }
      }
      const restartRequired = restart || !!previous.restartRequired;
      this.state.received[context.channel] = {
        managed: manifest.mods.map(mod => mod.id), source: manifest.source,
        revision: manifest.revision, restartRequired, process: h.processId,
      };
      await this.save();
      h.assertCurrent(context);
      if (!restartRequired && changedPrefs.length) await h.refreshStyles();
      h.status(`Received ${manifest.mods.length} mods (${context.channel}, revision ${manifest.revision}).` +
        (restartRequired ? " Restart Zen to activate mod changes." : " Up to date."));
      return { action: "receive", mods: manifest.mods.length, changedFiles, changedPrefs, restartRequired, backup };
    } finally {
      await h.remove(transaction);
    }
  }

  async clearRestartAfterStartup() {
    await this.init();
    for (const entry of Object.values(this.state.received)) {
      if (entry.process !== this.h.processId) entry.restartRequired = false;
    }
    await this.save();
  }
}
