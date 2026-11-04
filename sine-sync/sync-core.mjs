// Pure validation and planning shared by the browser controller and Node tests.
export const VERSION = "0.1.0";
export const CHANNELS = ["work", "personal"];
export const PREFIX = "uc.sine-sync.";
export const MAX_MANIFEST_BYTES = 64 * 1024;
export const MAX_FILE_BYTES = 5 * 1024 * 1024;
export const MAX_TOTAL_BYTES = 40 * 1024 * 1024;
export const MAX_FILES = 300;
export const MAX_MODS = 50;
export const DATA_PREFS = CHANNELS.map(channel => `${PREFIX}data.${channel}`);
const encoder = new TextEncoder();
const own = (object, key) => Object.hasOwn(object, key);
const record = value => !!value && typeof value === "object" && !Array.isArray(value);

export function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (record(value)) {
    return `{${Object.keys(value).sort().map(key =>
      `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function safePath(path) {
  if (typeof path !== "string" || !path || path.length > 240) return false;
  return path.split("/").every(part => part && part !== "." && part !== ".." &&
    !/[\\:%<>\"|?*\u0000-\u001f]/.test(part) && !/[. ]$/.test(part) &&
    !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part));
}

export function safeId(id) {
  return typeof id === "string" && /^[a-z0-9][a-z0-9._-]{0,99}$/i.test(id) &&
    safePath(id) && id !== "sine-sync" && !id.startsWith("local-");
}

export function portablePref(name, value) {
  if (typeof name !== "string" || name.length > 160 ||
      !/^[a-z0-9_.-]+$/i.test(name)) return false;
  // Only a mod's declared settings are considered, and these are never portable.
  if (/^(services|identity|security|signon|network|app|toolkit|sine)\./i.test(name) ||
      name.startsWith(PREFIX) || /external-profile/i.test(name) ||
      /(?:api[_-]?key|password|secret|credential|token|base[_-]?url|endpoint|directory)/i.test(name) ||
      /(?:^|[._-])(?:path|file|folder-path)(?:$|[._-])/i.test(name)) return false;
  if (value === null || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isInteger(value) &&
    value >= -2147483648 && value <= 2147483647;
  return typeof value === "string" && value.length <= 4096 &&
    !/^(?:\/|~\/|[a-z]:[\\/]|\\\\)/i.test(value) &&
    !/(?:file|moz-extension|blob|data|javascript):/i.test(value) &&
    !/https?:\/\/(?:localhost\b|127\.|0\.0\.0\.0|\[::1\]|10\.|192\.168\.)/i.test(value);
}

export function declaredPrefs(definition) {
  const result = new Set();
  function visit(value) {
    if (Array.isArray(value)) value.forEach(visit);
    else if (record(value)) {
      if (typeof value.property === "string" &&
          ["checkbox", "string", "dropdown"].includes(value.type) &&
          portablePref(value.property, null)) result.add(value.property);
      for (const [key, child] of Object.entries(value)) {
        if (key !== "conditions") visit(child);
      }
    }
  }
  visit(definition);
  return [...result].sort();
}

export function parseRepository(url) {
  if (typeof url !== "string") throw new Error("A GitHub source is required.");
  const match = /^(?:https:\/\/github\.com\/)?([\w.-]+)\/([\w.-]+)(?:\/(?:tree|commit)\/([\w.-]+)(?:\/(.+?))?)?\/?$/.exec(url);
  if (!match || [match[1], match[2]].some(v => v === "." || v === "..")) {
    throw new Error("Only public GitHub repository sources are supported.");
  }
  const folder = match[4] || "";
  if (folder && !safePath(folder)) throw new Error("Invalid repository folder.");
  return { owner: match[1], repo: match[2], ref: match[3] || "main", folder };
}

export function rawURL(source, path) {
  if (!safePath(path) || !/^[0-9a-f]{40}$/.test(source.commit) ||
      !/^[\w.-]+$/.test(source.owner) || !/^[\w.-]+$/.test(source.repo) ||
      (source.folder && !safePath(source.folder))) throw new Error("Invalid pinned source.");
  const relative = [source.folder, path].filter(Boolean).join("/");
  return `https://raw.githubusercontent.com/${source.owner}/${source.repo}/${source.commit}/` +
    relative.split("/").map(encodeURIComponent).join("/");
}

export function runtimeFile(path) {
  return safePath(path) && !path.split("/").some(part =>
    part.startsWith(".") || /^(?:node_modules|tests?|scripts|reports|backups|hammerspoon)$/i.test(part)) &&
    path !== "theme.json" &&
    (/\.(?:js|mjs|css|json|svg|png|jpe?g|gif|webp|woff2?|ttf|otf|wasm)$/i.test(path) ||
     /(?:^|\/)(?:LICENSE|COPYING)(?:[.-].*)?$/i.test(path));
}

const META_FIELDS = [
  "id", "name", "description", "version", "author", "homepage", "readme",
  "createdAt", "updatedAt", "fork", "tags", "ai", "scripts", "style",
  "preferences", "supportsUnload",
];

export function cleanMeta(input) {
  if (!record(input) || !safeId(input.id)) throw new Error("Invalid mod ID.");
  if (input.chromeManifest) throw new Error(`${input.id}: custom chrome manifests are not supported.`);
  const output = {};
  for (const key of META_FIELDS) if (own(input, key)) {
    output[key] = JSON.parse(JSON.stringify(input[key]));
  }
  return output;
}

export function entrypoints(meta) {
  const paths = new Set();
  if (meta.preferences) paths.add(meta.preferences);
  if (typeof meta.style === "string" && meta.style) paths.add(meta.style);
  else if (record(meta.style)) {
    for (const value of Object.values(meta.style)) if (value) paths.add(value);
  }
  function scripts(value, prefix = "") {
    if (!record(value)) throw new Error("Invalid script declaration.");
    for (const [key, spec] of Object.entries(value)) {
      const path = prefix ? `${prefix}/${key}` : key;
      if (/\.(?:uc\.js|uc\.mjs|sys\.mjs)$/.test(path)) {
        if (!record(spec)) throw new Error("Invalid script options.");
        paths.add(path);
      } else scripts(spec, path);
    }
  }
  if (meta.scripts) scripts(meta.scripts);
  return [...paths];
}

export function validateManifest(input, expectedChannel) {
  const text = typeof input === "string" ? input : JSON.stringify(input);
  if (encoder.encode(text).length > MAX_MANIFEST_BYTES) throw new Error("Sync manifest is too large.");
  const data = JSON.parse(text);
  if (!record(data) || data.schema !== 1 || !CHANNELS.includes(data.channel) ||
      data.channel !== expectedChannel || !/^[a-z0-9-]{10,64}$/i.test(data.source) ||
      !Number.isSafeInteger(data.revision) || data.revision < 1 ||
      !Array.isArray(data.mods) || data.mods.length > MAX_MODS) {
    throw new Error("Invalid or mismatched sync manifest.");
  }
  const ids = new Set();
  let count = 0, bytes = 0;
  for (const mod of data.mods) {
    if (!record(mod) || !safeId(mod.id) || ids.has(mod.id.toLowerCase()) ||
        typeof mod.enabled !== "boolean" || !record(mod.source) ||
        !Array.isArray(mod.files) || !mod.files.length || !record(mod.prefs)) {
      throw new Error("Invalid or duplicate synced mod.");
    }
    ids.add(mod.id.toLowerCase());
    const meta = cleanMeta(mod.meta);
    if (meta.id !== mod.id || canonical(meta) !== canonical(mod.meta)) throw new Error("Invalid mod metadata.");
    const files = new Set();
    for (const file of mod.files) {
      if (!record(file) || !runtimeFile(file.path) || files.has(file.path.toLowerCase()) ||
          !/^[a-f0-9]{64}$/.test(file.sha256) || !Number.isSafeInteger(file.size) ||
          file.size < 0 || file.size > MAX_FILE_BYTES) throw new Error("Invalid synced file.");
      rawURL(mod.source, file.path);
      files.add(file.path.toLowerCase());
      count++;
      bytes += file.size;
    }
    if (count > MAX_FILES || bytes > MAX_TOTAL_BYTES) throw new Error("Synced files exceed the size limit.");
    for (const path of entrypoints(meta)) {
      if (!safePath(path) || !files.has(path.toLowerCase())) {
        throw new Error(`${mod.id}: missing or unsafe entrypoint.`);
      }
    }
    for (const [key, value] of Object.entries(mod.prefs)) {
      if (!portablePref(key, value)) throw new Error("A non-portable setting was found.");
    }
  }
  return data;
}

export function nextRegistry(current, manifest, previouslyManaged, followEnabled = true) {
  const result = structuredClone(current);
  const incoming = new Set(manifest.mods.map(mod => mod.id));
  for (const mod of manifest.mods) {
    result[mod.id] = {
      ...mod.meta,
      commit: mod.source.commit,
      enabled: followEnabled ? mod.enabled : (current[mod.id]?.enabled ?? mod.enabled),
      // Only the sender chooses new code versions.
      "no-updates": true,
    };
  }
  if (followEnabled) for (const id of previouslyManaged) {
    if (!incoming.has(id) && result[id] && safeId(id)) result[id].enabled = false;
  }
  return result;
}

export function relayPayload(packet, channel, current, now) {
  if (!record(packet) || packet.schema !== 1 || !Number.isFinite(packet.expires) ||
      packet.expires <= now || packet.expires > now + 3600000) return null;
  const manifest = validateManifest(packet.manifest, channel);
  if (packet.owner !== manifest.source) throw new Error("Invalid local relay owner.");
  if (current) {
    const existing = validateManifest(current, channel);
    if (existing.source !== manifest.source && !packet.claim) {
      throw new Error(`The ${channel} channel has another sender; local relay will not replace it.`);
    }
    if (existing.source === manifest.source && existing.revision > manifest.revision) return null;
  }
  const text = canonical(manifest);
  return text === current ? null : text;
}
