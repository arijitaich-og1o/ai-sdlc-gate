---
name: sast-injection
description: "SAST category 1: injection sink analysis — SQL injection, command injection, XSS, SSTI, LDAP, XPath, NoSQL injection, and CRLF/header injection. Trace user input to dangerous sinks without sanitization."
---

# Category 1 — Injection Sinks

Trace: does user input (`req.body`, `req.query`, `req.params`, form data, URL) reach any sink below without parameterization/encoding?

## 1.1 SQL Injection

| Language | Dangerous sinks | Safe alternative |
|---|---|---|
| JS/TS | String concat/template in `db.query()` `knex.raw()` `sequelize.query()` `pool.query()` | Parameterized `$1`/`?` placeholders |
| Python | f-string in `cursor.execute()` `engine.execute()` Django `extra()`/`raw()` SQLAlchemy `text()` | `%s` with params tuple |
| Java | String concat in `Statement.execute()` `createQuery()` `JdbcTemplate.query()` | `PreparedStatement` named params |
| PHP | Interpolation in `mysqli_query()` `PDO::query()` `DB::select()` `whereRaw()` | `PDO::prepare()` Eloquent builder |
| C# | String concat in `SqlCommand` `FromSqlRaw()` `ExecuteSqlRaw()` | `SqlParameter` `FromSqlInterpolated()` LINQ |
| Go | `fmt.Sprintf` in `db.Query()` `db.Exec()` GORM `Raw()` | `db.Query(sql, args...)` |
| Ruby | Interpolation in `connection.execute()` `find_by_sql` `where("name = '#{}'")` | `where(name: value)` `where("name = ?", val)` |

## 1.2 Command Injection

| Language | Dangerous |
|---|---|
| JS/TS | `exec()` `execSync()` `spawn(shell:true)` backtick in exec |
| Python | `os.system()` `os.popen()` `subprocess.call(shell=True)` `eval()` `exec()` |
| Java | `Runtime.exec()` `ProcessBuilder` with user input `ScriptEngine.eval()` |
| PHP | `exec()` `system()` `passthru()` `shell_exec()` `popen()` backtick |
| C# | `Process.Start()` with user input in arguments |
| Go | `exec.Command()` with user input |
| Ruby | `system()` backtick `%x{}` `Kernel.exec()` `IO.popen()` |

## 1.3 XSS (Output Sinks)

| Context | Dangerous |
|---|---|
| React | `dangerouslySetInnerHTML` `innerHTML` `document.write()` |
| Express/Node | `res.send(userInput)` unescaped template output (`<%- %>` `{{{ }}}` `!{var}`) |
| Django | `mark_safe()` `|safe` `{% autoescape off %}` on user data |
| Flask/Jinja2 | `Markup()` `|safe` `{% autoescape false %}` on user data |
| Java JSP | `<%= var %>` `th:utext` `out.println()` |
| PHP | `echo $var` without `htmlspecialchars()` `{!! $var !!}` `|raw` |
| C# Razor | `@Html.Raw()` |
| Go | `template.HTML()` cast or `text/template` instead of `html/template` |
| Ruby ERB | `raw()` `html_safe` on user input `<%== %>` |

**DOM XSS — Non-Obvious Sources** (client-side only; trace these to sinks like `innerHTML`, `eval`, `document.write`):
- `location.hash` — attacker controls `#payload` in URL
- `document.referrer` — attacker controls origin page URL
- `window.name` — persists across navigations, set by opener window
- `URLSearchParams` — `new URLSearchParams(location.search).get('q')`
- `postMessage` event data — `event.data` without origin validation
- `localStorage` / `sessionStorage` — if attacker can write via earlier XSS
- `document.cookie` — parsed values from cookies set on parent domains

## 1.4 SSTI (Template Injection)

User input passed directly to template rendering:
- Flask: `render_template_string(user_input)`
- Jinja2: `Template(user_input).render()`
- Ruby: `ERB.new(user_input).result`
- JS: `new Function(user_input)`
- Java: Freemarker/Velocity/Thymeleaf with user-controlled template string

## 1.5 LDAP Injection
User input in LDAP filter strings: `(&(uid=USER_INPUT)...)` without `ldap_escape_filter()`.

Patterns:
- Java: string concatenation into `ctx.search(base, filter, controls)` — use `LdapEncoder.filterEncode()`
- Python: `conn.search_s(base, scope, f"(uid={username})")` — use `ldap.filter.filter_format("(uid=%s)", [username])`
- JS: `client.search(base, { filter: \`(uid=${req.body.username})\` })` — use `ldap-escape`

Severity: HIGH — `*)(uid=*)` in username field returns all users, bypassing auth.

## 1.6 XPath Injection
User input in XPath: `//user[name='USER_INPUT']` string construction, `XPathExpression.evaluate()` with concat.

## 1.7 NoSQL Injection

MongoDB query operator injection — attacker replaces a string value with a MongoDB operator object:

```javascript
// ❌ NEVER: direct req.body into query — attacker sends { password: { "$gt": "" } }
const user = await User.findOne({
  username: req.body.username,
  password: req.body.password   // { "$gt": "" } matches ANY document → auth bypass
})

// ❌ NEVER: $where with string interpolation → JS injection
User.find({ $where: `this.username === '${req.body.name}'` })

// ✅ ALWAYS: enforce type + use parameterized query
if (typeof req.body.password !== 'string') return res.status(400).send()
const user = await User.findOne({ username: String(req.body.username) }).select('+password')
```

```python
# ❌ NEVER: dict from request body directly into query
collection.find({"username": request.json["username"]})
# attacker sends: { "username": { "$regex": "^a" } } → data exfil

# ✅ ALWAYS: enforce type
username = str(request.json.get("username", ""))
```

Flag: `Model.find(req.body)` (entire body as query — complete operator injection). Also flag `$where` with any string interpolation (RCE in older MongoDB).

## 1.8 CRLF / Header Injection
User input in HTTP response headers without CRLF stripping:
- `res.setHeader('Location', userInput)` → `\r\n` splits into new headers
- `response.addHeader("X-Custom", userInput)`

## 1.9 Template Engine Unescaped Output

Beyond SSTI (section 1.4), flag unescaped output directives in template engines where user data flows through:

| Engine | Unsafe (renders HTML) | Safe (escapes HTML) |
|---|---|---|
| Handlebars | `{{{userVar}}}` | `{{userVar}}` |
| EJS | `<%- userVar %>` | `<%= userVar %>` |
| Pug | `!= userVar` | `= userVar` |
| Nunjucks | `userVar \| safe` | `userVar` (default escaped) |
| Mustache | `{{{userVar}}}` | `{{userVar}}` |
| Twig (PHP) | `userVar \| raw` | `{{ userVar }}` (escaped) |

Flag when the variable flowing through the unsafe directive originates from user input (req.body, req.query, req.params, DB-stored user content). Severity: HIGH (Stored XSS when content is user-supplied).

## 1.10 CSV / Formula Injection

When user-controlled data is written to CSV exports, fields beginning with `=`, `+`, `-`, or `@` are interpreted as formulas by Excel and Google Sheets:

```javascript
// ❌ NEVER: user-supplied field values written directly to CSV
const csv = users.map(u => `${u.name},${u.email}`).join('\n')
// attacker name: =HYPERLINK("http://attacker.com","Click me") → executes when admin opens CSV

// ✅ ALWAYS: sanitize fields starting with formula characters
function sanitizeCsvField(value) {
  const s = String(value)
  if (['+', '-', '=', '@', '\t', '\r'].some(c => s.startsWith(c))) {
    return `'${s}`   // prefix with single quote — neutralizes formula
  }
  return s
}
```

**What to flag:** CSV write operations (`csv-writer`, `papaparse`, `fast-csv`, Python `csv.writer`, Ruby `CSV.generate`) where field values derive from user-controlled data without prefix sanitization. Severity: MEDIUM.

## Finding Format

```json
{
  "id": "SF01", "category": "injection", "class": "sql_injection",
  "severity": "CRITICAL", "confidence": "HIGH",
  "file": "src/services/userService.js", "line": 47,
  "sink": "db.query(sql)", "source": "req.body.username",
  "data_flow": ["req.body.username → controller:14", "→ service:28", "→ db.query():47 (SINK)"],
  "route": "POST /api/users", "remediation": "Use parameterized query"
}
```
