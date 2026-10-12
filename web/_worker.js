/**
 * Project page plus Jev relay for n8n on Hugging Face Spaces.
 *
 * Context: Hugging Face Spaces cannot complete TLS handshakes with api.cloudflare.com, while
 *          sites on customer domains stay reachable. This Pages worker serves the project page
 *          and passes Workers AI calls from n8n through to Cloudflare unchanged.
 * Input:   POST /client/v4/accounts/<account id>/ai/run with the caller's own
 *          "Authorization: Bearer <Cloudflare API token>" header and a JSON body;
 *          any other request is a page request.
 * Output:  Cloudflare's response with status and body unchanged, or the static page.
 *
 * Nothing secret is stored here: the token travels with each request exactly as it would to
 * api.cloudflare.com, so a request without a valid token is rejected by Cloudflare itself.
 */

const UPSTREAM = "https://api.cloudflare.com";
const RELAY_PATH = /^\/client\/v4\/accounts\/[0-9a-f]{32}\/ai\/run$/;
const MAX_BODY_BYTES = 64 * 1024;

/**
 * Forward one Workers AI request.
 *
 * Context: Called for requests on the relay path.
 * Input:   The incoming request and its path.
 * Output:  The upstream response, or 405/413 for requests outside the allowed shape.
 */
async function relay(request, pathname) {
  if (request.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }
  const body = await request.arrayBuffer();
  if (body.byteLength > MAX_BODY_BYTES) {
    return new Response("Payload too large", { status: 413 });
  }
  return fetch(UPSTREAM + pathname, {
    method: "POST",
    headers: {
      Authorization: request.headers.get("Authorization") ?? "",
      "Content-Type": "application/json",
    },
    body,
  });
}

export default {
  /**
   * Route a request to the relay or to the static page.
   *
   * Context: Entry point called by Cloudflare Pages.
   * Input:   The incoming request and the Pages environment with its ASSETS binding.
   * Output:  The relay response or the static asset.
   */
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (RELAY_PATH.test(pathname)) {
      return relay(request, pathname);
    }
    return env.ASSETS.fetch(request);
  },
};
