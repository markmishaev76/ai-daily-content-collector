const DISPATCH_URL =
  "https://api.github.com/repos/markmishaev76/ai-daily-content-collector/actions/workflows/site.yml/dispatches";

export async function dispatch(token, fetchImpl = fetch) {
  if (!token) throw new Error("GITHUB_TOKEN secret is not set");
  const response = await fetchImpl(DISPATCH_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "thedailybrief-cron",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (response.status !== 204) {
    throw new Error(`GitHub dispatch failed: HTTP ${response.status} ${await response.text()}`);
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(dispatch(env.GITHUB_TOKEN));
  },
};
