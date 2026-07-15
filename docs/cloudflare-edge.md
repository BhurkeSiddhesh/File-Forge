# Cloudflare edge configuration (forgefiles.org)

File Forge runs as a FastAPI app (on Render or any Docker/ASGI host) — it is **not**
a Cloudflare Pages / Next.js static export. If you put Cloudflare in front of the
origin (the normal setup for `forgefiles.org`: Cloudflare proxies the orange-cloud
DNS record to your Render origin as a CDN + WAF), the app's own `robots.txt`
allow-list and hard-404 handling are not enough — Cloudflare can block or rewrite
requests **before** they ever reach the app. Configure the edge to match.

## 1. Stop the WAF / Bot Fight Mode from 403-ing AI crawlers

Cloudflare's Bot Fight Mode and Managed WAF rules treat non-browser user-agents as
threats and return `403 Forbidden`. That makes File Forge invisible to the AI
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

## 4. Verify after deploy

```bash
# AI crawler is allowed through the edge (expect 200, not 403)
curl -sI -A "GPTBot" https://forgefiles.org/merge-pdf | head -1

# Unknown path is a hard 404 at the edge, not a soft 404 (expect HTTP/.. 404)
curl -sI https://forgefiles.org/this-page-does-not-exist | head -1

# robots.txt is 200 and points at the sitemap
curl -sI https://forgefiles.org/robots.txt | head -1
curl -s  https://forgefiles.org/robots.txt | grep -i sitemap
```
