import assert from "node:assert/strict";
import { test } from "node:test";

import { dispatch } from "../src/index.js";

test("posts workflow_dispatch for main with the token", async () => {
  let call;
  await dispatch("tok", async (url, init) => {
    call = { url, init };
    return new Response(null, { status: 204 });
  });

  assert.match(call.url, /markmishaev76\/ai-daily-content-collector\/actions\/workflows\/site\.yml\/dispatches$/);
  assert.equal(call.init.method, "POST");
  assert.equal(call.init.headers.Authorization, "Bearer tok");
  assert.deepEqual(JSON.parse(call.init.body), { ref: "main" });
});

test("throws with status and body when GitHub rejects", async () => {
  await assert.rejects(
    dispatch("tok", async () => new Response("Bad credentials", { status: 401 })),
    /HTTP 401 Bad credentials/,
  );
});

test("throws when the token is missing", async () => {
  await assert.rejects(dispatch(undefined, async () => assert.fail("must not call")), /GITHUB_TOKEN/);
});
