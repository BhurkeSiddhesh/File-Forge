# Cloudflare edge configuration (forgefiles.org)

Forge Files runs as a FastAPI app (on Render or any Docker/ASGI host) — it is **not**
a Cloudflare Pages / Next.js static export. If you put Cloudflare in front of the
origin (the normal setup for `forgefiles.org`: Cloudflare proxies the orange-cloud
DNS record to your Render origin as a CDN + WAF), the app's own `robots.txt`
allow-list and hard-404 handling are not enough — Cloudflare can block or rewrite
requests **before** they ever reach the app. Configure the edge to match.

## 1. Stop the WAF / Bot Fight Mode from 403-ing AI crawlers

Cloudflare's Bot Fight Mode and Managed WAF rules treat non-browser user-agents as
threats and return `403 Forbidden`. That makes Forge Files invisible to the AI
retrieval crawlers we explicitly welcome in `robots.txt`, so they can never cite
the tools in an answer.

Create a **WAF custom rule** that *skips* security for those bots:

1. Cloudflare Dashboard → **Security → WAF → Custom rules → Create rule**.
2. Name: `Allow AI Search Crawlers`.
3. Expression (keep this in sync with `AI_CRAWLERS` in `main.py`):

   ```
   (http.user_agent contains "GPTBot") or (http.user_agent contains "OAI-SearchBot") or (http.user_agent contains "ChatGPT-User") or (http.user_agent contains "ClaudeBot") or (http.user_agent contains "Claude-Web") or (http.user_agent contains "anthropic-ai") or (http.user_agent contains "PerplexityBot") or (http.user_agent contains "Perplexity-User") or (http.user_agent contains "Google-Extended") or (http.user_agent contains "Applebot-Extended") or (http.user_agent contains "Amazonbot") or (http.user_agent contains "Bytespider") or (http.user_agent contains "Meta-ExternalAgent") or (http.user_agent contains "CCBot")
   ```

4. Action: **Skip** → under *WAF components to skip*, check **Bot Fight Mode** /
   **Super Bot Fight Mode** and **All managed rules**.
5. **Deploy.**

> Keep this expression in sync with `AI_CRAWLERS` in `main.py`. Regenerate it with:
>
> ```bash
> python3 -c "import re;s=open('main.py').read();b=re.findall(r'\"([^\"]+)\"',re.search(r'AI_CRAWLERS = \[(.*?)\]',s,re.S).group(1));print(' or '.join('(http.user_agent contains \"%s\")'%x for x in b))"
> ```

If you enable Cloudflare's own **AI crawler controls** (Security → Bots), make sure
they are set to *allow* — not block/challenge — the same user-agents.

## 2. Keep 404s hard (no edge soft-404s)

The app already returns a real **HTTP 404** for unknown routes with a branded HTML
body (see `http_exception_handler` in `main.py` and `render_404_page` in
`scripts/seo_content.py`). Search engines penalise *soft 404s* — a custom
"not found" page served with a `200 OK` status — so do **not** undo this at the edge:

- Do **not** add a Cloudflare **Bulk Redirect** / **Redirect Rule** that catches
  unmatched paths and 302s them to `/` or `/index.html`. That turns every missing
  URL into a soft 404.
- Do **not** put a `_redirects` / `_headers` SPA-fallback (`/* /index.html 200`) in
  front of the origin — that is a Cloudflare **Pages** concept and would mask the
  origin's genuine 404 status. Let Cloudflare pass unmatched paths straight to the
  origin so the app can answer `404`.
- In **Caching → Configuration**, leave error responses uncached (or use a short
  TTL) so a transient 404 isn't pinned at the edge.

## 3. Performance / Core Web Vitals at the edge

- Enable **Brotli** compression and **HTTP/3**.
- Cache the static assets under `/static/*` aggressively (they are versioned with a
  `?v=` query string, so a long edge TTL is safe).
- Do **not** enable Cloudflare features that inject blocking JavaScript into the
  document `<head>` (e.g. Rocket Loader) — they can hurt LCP/INP and interfere with
  the app's own lazy AdSense `IntersectionObserver` loader.

## 4. Make the trusted client-IP header actually trustworthy

The rate limiter buckets on `CF-Connecting-IP` (see `client_identity()` in
`main.py`). Cloudflare sets that header from the real connection and strips any
client-supplied copy — but **only for requests that go through Cloudflare**.
Putting Cloudflare in front of the origin does not stop anyone from talking to
the origin directly: the origin IP answers on 443, and if it terminates its own
TLS the hostname is published in the Certificate Transparency logs. A request
sent straight there arrives with an attacker-chosen `CF-Connecting-IP`, and
rotating it mints a fresh rate-limit bucket per request on the endpoints that
run OCR, `pdf2docx` and LibreOffice.

So one of these is required, not optional:

**a. Close the direct path.** Restrict inbound 443 on the origin to
Cloudflare's [published ranges](https://www.cloudflare.com/ips/), or front it
with Cloudflare Tunnel / Authenticated Origin Pulls. Then the header is
genuinely unforgeable and no app configuration is needed.

**b. Prove the request came through the edge.** Set `RATE_LIMIT_EDGE_SECRET`
in the app's environment and have your reverse proxy inject it — and blank the
Cloudflare headers — only when the peer is a Cloudflare address:

```nginx
# /etc/nginx/conf.d/cloudflare-edge.conf, at http level.
geo $from_cloudflare {
    default 0;
    173.245.48.0/20 1;  103.21.244.0/22 1;  103.22.200.0/22 1;
    103.31.4.0/22   1;  141.101.64.0/18 1;  108.162.192.0/18 1;
    190.93.240.0/20 1;  188.114.96.0/20 1;  197.234.240.0/22 1;
    198.41.128.0/17 1;  162.158.0.0/15  1;  104.16.0.0/13    1;
    104.24.0.0/14   1;  172.64.0.0/13   1;  131.0.72.0/22    1;
}
map $from_cloudflare $cf_edge_auth { 1 "<RATE_LIMIT_EDGE_SECRET>"; default ""; }
map $from_cloudflare $cf_client_ip { 1 $http_cf_connecting_ip;     default ""; }
map $from_cloudflare $cf_country   { 1 $http_cf_ipcountry;         default ""; }
```

```nginx
# ...and in the proxying location block:
proxy_set_header X-FF-Edge-Auth   $cf_edge_auth;
proxy_set_header CF-Connecting-IP $cf_client_ip;
proxy_set_header CF-IPCountry     $cf_country;
```

Requests without the secret are bucketed on the socket peer instead, and their
`CF-IPCountry` is discarded rather than being written to the event log. Rename
the header with `RATE_LIMIT_EDGE_HEADER` if `X-FF-Edge-Auth` collides with
something. Refresh the range list with:

```bash
curl -s https://www.cloudflare.com/ips-v4 | sed 's/$/ 1;/'
```

Leaving `RATE_LIMIT_EDGE_SECRET` unset keeps the old behaviour and logs a
warning at boot. Independently of either option, `RATE_LIMIT_HEAVY_CONCURRENCY`
(default 4) caps how many heavy jobs run at once across *all* clients, so a
spoofed flood still cannot saturate the worker — it just gets `503`s.

## 5. Verify after deploy

```bash
# AI crawler is allowed through the edge (expect 200, not 403)
curl -sI -A "GPTBot" https://forgefiles.org/merge-pdf | head -1

# Unknown path is a hard 404 at the edge, not a soft 404 (expect HTTP/.. 404)
curl -sI https://forgefiles.org/this-page-does-not-exist | head -1

# robots.txt is 200 and points at the sitemap
curl -sI https://forgefiles.org/robots.txt | head -1
curl -s  https://forgefiles.org/robots.txt | grep -i sitemap
```
