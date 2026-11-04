const test = require("node:test");
const assert = require("node:assert/strict");
const { catalogue, profileColour, activateProfile } = require("../profile-switcher.uc.js");

test("uses paths to distinguish profiles with duplicate names", () => {
  const entries = [
    { name: "Personal", path: "/profiles/one" },
    { name: "Personal", path: "/profiles/two" },
    { name: "Stale duplicate", path: "/profiles/one" },
  ];
  const profiles = catalogue(entries, "/profiles/two", "Fallback");
  assert.equal(profiles.length, 2);
  assert.equal(profiles[0].path, "/profiles/two");
  assert.equal(profiles[0].current, true);
  assert.equal(profiles[1].current, false);
});

test("keeps an unregistered current profile visible without treating other profiles as current", () => {
  const profiles = catalogue([{ name: "Other", path: "/other" }], "/unregistered", "Temporary");
  assert.deepEqual(profiles[0], { path: "/unregistered", name: "Temporary", current: true });
  assert.equal(profiles[1].current, false);
});

test("preserves Unicode names as text and rejects entries without paths", () => {
  const profiles = catalogue([
    { name: "工作 <b>Home</b>\u0000", path: "/one" },
    { name: "Missing" },
    { name: "   ", path: "/two" },
  ], "/one", "Fallback");
  assert.equal(profiles[0].name, "工作 <b>Home</b>");
  assert.equal(profiles[1].name, "Unnamed profile");
  assert.equal(profiles.length, 2);
});

test("automatic colour stays stable across renames and validates configured colours", () => {
  const before = profileColour("/profiles/stable");
  assert.match(before, /^#[0-9a-f]{6}$/);
  assert.equal(profileColour("/profiles/stable"), before);
  assert.equal(profileColour("/profiles/stable", "blue"), "#377cde");
  assert.equal(profileColour("/profiles/stable", "toString"), before);
  assert.equal(profileColour("/profiles/stable", "url(https://invalid.test)"), before);
});

test("activates the exact registered path with spaces and Unicode", async () => {
  const target = { name: "Same name", path: "C:\\Users\\Example\\Profiles\\个人 two" };
  const launches = [];
  await activateProfile(target.path, {
    currentPath: "/current",
    readProfiles: async () => [{ name: "Same name", path: "/different" }, target],
    focus: () => assert.fail("Must not focus the current profile"),
    launch: profile => launches.push(profile),
  });
  assert.deepEqual(launches, [target]);
});

test("revalidates a profile after the menu opens and does not launch a removed profile", async () => {
  let entries = [{ name: "Old", path: "/removed" }];
  const fromMenu = catalogue(entries, "/current", "Current")[1];
  entries = [{ name: "Old", path: "/replacement" }];
  await assert.rejects(activateProfile(fromMenu.path, {
    currentPath: "/current", readProfiles: async () => entries,
    focus: () => assert.fail("Unexpected focus"),
    launch: () => assert.fail("Unexpected launch"),
  }), /no longer registered/);
});

test("focuses the current window without launching another process", async () => {
  let focused = 0;
  await activateProfile("/current", {
    currentPath: "/current", readProfiles: async () => [{ name: "Current", path: "/current" }],
    focus: () => focused++, launch: () => assert.fail("Unexpected launch"),
  });
  assert.equal(focused, 1);
});

test("surfaces read and native launch failures without a fallback to a different profile", async () => {
  const env = {
    currentPath: "/current",
    readProfiles: async () => [{ name: "Target", path: "/target" }],
    launch: () => { throw new Error("Native launch failed"); },
  };
  await assert.rejects(activateProfile("/target", env), /Native launch failed/);
  env.readProfiles = async () => { throw new Error("Registry unavailable"); };
  env.launch = () => assert.fail("Unexpected launch");
  await assert.rejects(activateProfile("/target", env), /Registry unavailable/);
});
