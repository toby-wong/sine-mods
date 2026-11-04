import test from "node:test";
import assert from "node:assert/strict";
import { createCommandRouter } from "../ExternalProfileRouting.sys.mjs";

function fixture(overrides = {}) {
  const calls = { native: [], launch: [], replay: [], errors: [] };
  const target = { path: "/test/Work profile 工作", name: "Work" };
  const env = {
    currentPath: "/test/personal",
    remoteExplicit: 2,
    getTarget: () => target.path,
    original: command => { calls.native.push(command); return "native-result"; },
    readProfiles: async () => [{ name: "Work", path: "/another/profile" }, target],
    isWebURL: value => {
      try { return ["http:", "https:"].includes(new URL(value).protocol); }
      catch { return false; }
    },
    launch: (profile, urls) => calls.launch.push({ profile, urls }),
    replay: args => calls.replay.push(args),
    report: error => calls.errors.push(String(error)),
    ...overrides,
  };
  return { calls, env, target, router: createCommandRouter(env) };
}

function command(args = ["-url", "https://example.invalid/?q=hello%20world"], state = 2) {
  const remaining = [...args];
  return {
    state, preventDefault: false,
    get length() { return remaining.length; },
    getArgument: index => remaining[index],
    removeArguments: (start, end) => remaining.splice(start, end - start + 1),
    remaining,
  };
}

test("routes only the explicit URL to the exact registered profile path", async () => {
  const { router, calls, target } = fixture();
  const request = command();
  router.handle(request);
  assert.equal(request.preventDefault, true);
  assert.deepEqual(request.remaining, []);
  await router.idle();
  assert.deepEqual(calls.launch, [{ profile: target, urls: ["https://example.invalid/?q=hello%20world"] }]);
  assert.equal(calls.native.length, 0);
  assert.equal(calls.replay.length, 0);
});

test("forwards a batch once, preserving URL order and query encoding", async () => {
  const { router, calls } = fixture();
  const urls = ["http://example.invalid/a", "https://example.invalid/b?x=%2F&y=1"];
  router.handle(command(urls.flatMap(url => ["-url", url])));
  await router.idle();
  assert.equal(calls.launch.length, 1);
  assert.deepEqual(calls.launch[0].urls, urls);
});

test("normal routing and the destination profile never forward back to themselves", () => {
  for (const destination of ["", "/test/personal"]) {
    const { router, calls } = fixture({ getTarget: () => destination });
    const request = command();
    assert.equal(router.handle(request), "native-result");
    assert.equal(request.preventDefault, false);
    assert.equal(calls.native.length, 1);
    assert.equal(calls.launch.length, 0);
  }
});

test("startup, automatic remoting, activation, private windows and other commands stay native", () => {
  const requests = [
    command(undefined, 0), command(undefined, 1), command(["--profiles-activate"]),
    command(["-private-window", "https://example.invalid/"]),
    command(["-new-tab", "https://example.invalid/"]),
    command(["https://example.invalid/"]), command([]),
    command(["-url"]), command(["-url", "https://example.invalid/", "-foreground"]),
  ];
  for (const request of requests) {
    const { router, calls } = fixture();
    const original = [...request.remaining];
    assert.equal(router.handle(request), "native-result");
    assert.deepEqual(request.remaining, original);
    assert.equal(request.preventDefault, false);
    assert.equal(calls.launch.length, 0);
  }
});

test("non-web schemes and mixed batches are left to native security checks", () => {
  for (const url of ["file:///tmp/document", "about:config", "javascript:alert(1)", "data:text/html,test", "not a URL"]) {
    for (const args of [["-url", url], ["-url", "https://example.invalid/", "-url", url]]) {
      const { router, calls } = fixture();
      const request = command(args);
      assert.equal(router.handle(request), "native-result");
      assert.deepEqual(request.remaining, args);
      assert.equal(calls.launch.length, 0);
    }
  }
});

test("a removed destination falls back locally instead of selecting a profile with the same name", async () => {
  const { router, calls } = fixture({ readProfiles: async () => [{ name: "Work", path: "/replacement" }] });
  const args = ["-url", "https://example.invalid/"];
  router.handle(command(args));
  await router.idle();
  assert.equal(calls.launch.length, 0);
  assert.deepEqual(calls.replay, [args]);
  assert.match(calls.errors[0], /no longer registered/);
});

test("registry and native launch failures replay the original request once", async () => {
  for (const overrides of [
    { readProfiles: async () => { throw new Error("Cannot read registry"); } },
    { launch: () => { throw new Error("Cannot launch"); } },
  ]) {
    const { router, calls } = fixture(overrides);
    const request = command(), original = [...request.remaining];
    router.handle(request);
    await router.idle();
    assert.deepEqual(calls.replay, [original]);
    assert.equal(calls.errors.length, 1);
  }
});

test("unloading during profile discovery preserves the URL through the native fallback", async () => {
  let complete;
  const { router, calls, target } = fixture({
    readProfiles: () => new Promise(resolve => { complete = resolve; }),
  });
  const request = command(), original = [...request.remaining];
  router.handle(request);
  router.destroy();
  complete([target]);
  await router.idle();
  assert.deepEqual(calls.replay, [original]);
  assert.equal(calls.launch.length, 0);
  assert.equal(router.handle(command()), "native-result");
});

test("changing the destination during discovery does not launch a stale selection", async () => {
  let complete, selected = "/test/Work profile 工作";
  const { router, calls, target } = fixture({
    getTarget: () => selected,
    readProfiles: () => new Promise(resolve => { complete = resolve; }),
  });
  router.handle(command());
  selected = "";
  complete([target]);
  await router.idle();
  assert.equal(calls.launch.length, 0);
  assert.equal(calls.replay.length, 1);
});

test("a failing native fallback is reported without a duplicate replay", async () => {
  let replays = 0;
  const { router, calls } = fixture({
    readProfiles: async () => [],
    replay: () => { replays++; throw new Error("Native fallback failed"); },
  });
  router.handle(command());
  await router.idle().catch(() => {});
  assert.equal(replays, 1);
  assert.equal(calls.launch.length, 0);
  assert.equal(calls.errors.length, 2);
});
