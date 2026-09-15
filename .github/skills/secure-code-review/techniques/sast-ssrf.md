---
name: sast-ssrf
description: "SSRF (Server-Side Request Forgery) — user-controlled URLs in outbound HTTP, cloud metadata endpoint abuse, DNS rebinding, webhook callbacks, PDF/image generation with user URLs. Covers Node.js (axios/fetch/got), Python (requests/httpx/urllib), Java (HttpClient/RestTemplate), PHP (curl/file_get_contents), Go (http.Get), Ruby (Net::HTTP). Auto-loaded for Standard and Thorough scans."
---

# SSRF — Server-Side Request Forgery

`OWASP: A10:2021 SSRF` · `CWE-918`

Trace: does user-controlled input reach an outbound HTTP request without allowlist validation?

## HTTP Client Sinks

| Language | Dangerous when URL derives from user input |
|---|---|
| JS/TS | `axios.get(url)` `fetch(url)` `got(url)` `http.get(url)` `request(url)` |
| Python | `requests.get(url)` `httpx.get(url)` `urllib.request.urlopen(url)` `urllib2.urlopen(url)` |
| Java | `HttpClient.send(URI.create(url))` `RestTemplate.getForObject(url)` `WebClient.get().uri(url)` `new URL(url).openConnection()` |
| PHP | `curl_setopt($ch, CURLOPT_URL, $url)` `file_get_contents($url)` `readfile($url)` |
| Go | `http.Get(url)` `http.NewRequest(method, url, body)` |
| Ruby | `Net::HTTP.get(URI(url))` `HTTParty.get(url)` `open(url)` — Kernel#open is especially dangerous |

## Cloud Metadata Targets (always flag if URL is user-controlled)

- `169.254.169.254` — AWS / GCP / Azure instance metadata service
- `metadata.google.internal` — GCP metadata
- `100.64.0.0/10` — AWS internal ranges
- `169.254.169.254/latest/meta-data/iam/security-credentials/` — AWS IAM role credentials

## Less-Obvious SSRF Sinks

- **Webhooks**: `POST /webhooks` endpoint that pings back a user-supplied callback URL
- **XML/SVG processing**: external entity `<!ENTITY xxe SYSTEM "http://...">` — XXE → SSRF
- **Archive extraction**: zip symlinks pointing to internal paths
- **`import()` with URL**: Node.js dynamic import of user-controlled URL

## Rendering-Based SSRF

Headless browsers and document renderers fetch the URL server-side — the server makes the outbound request, not the user's browser. Any user-controlled URL passed to these tools is a full SSRF sink.

### wkhtmltopdf
```python
# ❌ NEVER:
url = request.args.get('url')
subprocess.run(['wkhtmltopdf', url, '/tmp/output.pdf'])
# attacker passes url=http://169.254.169.254/latest/meta-data/ → IAM creds in PDF
```
- Also flag `--allow` flag without a strict allowlist
- Bypass via `<iframe src="file:///etc/passwd">` in HTML input when HTML-to-PDF endpoint exists

### Puppeteer / Playwright
```javascript
// ❌ NEVER:
const url = req.body.url
await page.goto(url)   // headless Chrome fetches user-controlled URL
await page.pdf({ path: '/tmp/report.pdf' })

// ✅ ALWAYS: allowlist check before goto()
const allowed = new URL(url)
if (!['myapp.com', 'cdn.myapp.com'].includes(allowed.hostname)) {
  throw new Error('URL not in allowlist')
}
```

Flag: `page.goto(userInput)`, `browser.newPage()` followed by `.goto(req.*)`, `chromium.launch()` in handlers that accept URL params.

### pdfkit / WeasyPrint / imgproxy / wkhtmltopdf via library wrappers
```python
# ❌ NEVER:
from weasyprint import HTML
HTML(url=request.json['url']).write_pdf('/tmp/output.pdf')

# ❌ NEVER:
import pdfkit
pdfkit.from_url(request.args.get('url'), '/tmp/output.pdf')
```

Flag: `HTML(url=userInput)`, `pdfkit.from_url(userInput)`, `imgproxy` URL generation with unvalidated source URLs.

### SSRF via HTML injection → rendering
Even if the renderer receives a trusted URL, if user HTML is rendered without sanitization:
```html
<!-- attacker injects into template rendered by Puppeteer/wkhtmltopdf -->
<img src="http://169.254.169.254/latest/meta-data/iam/security-credentials/role-name">
```
Flag: user HTML concatenated into PDF template without DOMPurify or equivalent sanitization.

### Severity
All rendering-based SSRF: **HIGH** (internal network access, metadata credential theft). Escalate to **CRITICAL** if the service runs in cloud and IAM role has significant permissions.

## Validation — Flag These as Insufficient

| Pattern | Why it fails |
|---|---|
| Blocklist of IPs | Bypassed via DNS rebinding, IPv6 (`::1`), decimal encoding (`2130706433` = `127.0.0.1`), octal (`0177.0.0.1`) |
| Blocklist of hostnames | `localhost` → `localtest.me` resolves to `127.0.0.1` |
| Only checking scheme | `http://attacker.com@169.254.169.254/` — host is the IP |
| Following redirects after check | Allowed URL redirects to internal target after validation passes |

**Safe pattern**: Allowlist of specific permitted domains. Validate AFTER DNS resolution, not before.

## Finding Format

```json
{
  "id": "SF01", "category": "ssrf", "severity": "HIGH", "confidence": "HIGH",
  "file": "src/services/webhookService.js", "line": 34,
  "sink": "axios.get(callbackUrl)", "source": "req.body.callbackUrl",
  "owasp": "A10:2021 Server-Side Request Forgery",
  "cwe": "CWE-918",
  "remediation": "Validate callbackUrl against an allowlist of permitted domains before making outbound request"
}
```
