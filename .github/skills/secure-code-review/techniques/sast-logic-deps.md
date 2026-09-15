---
name: sast-logic-deps
description: "SAST categories 8+9: business logic vulnerabilities (race conditions/TOCTOU, mass assignment, type coercion, integer overflow, missing rate limiting) and dependency analysis (known CVEs, deprecated APIs, unsafe native bindings)."
---

# Category 8 — Business Logic

## 8.1 Race Conditions (TOCTOU)

Non-atomic check-then-act is the core anti-pattern:

```javascript
// ❌ NEVER: two concurrent requests both read balance=100, both pass, both deduct
const user = await User.findById(userId)
if (user.balance >= amount) {
  await user.save({ balance: user.balance - amount })  // no lock — race window here
}

// ❌ NEVER: coupon double-redemption
const coupon = await Coupon.findOne({ code })
if (!coupon.used) {
  coupon.used = true; await coupon.save()  // race between check and save
}

// ✅ ALWAYS: atomic update or DB transaction
// MongoDB atomic:
await Coupon.findOneAndUpdate({ code, used: false }, { used: true })
// SQL: wrap in transaction with SELECT FOR UPDATE
await db.transaction(async (trx) => {
  const user = await User.query(trx).forUpdate().findById(userId)
  if (user.balance < amount) throw new Error('Insufficient funds')
  await user.$query(trx).patch({ balance: user.balance - amount })
})
```

**Flag pattern:** `findOne()` / `SELECT` followed by update in the same logical operation without a transaction or `SELECT FOR UPDATE` / `findOneAndUpdate()` with a condition. Especially on: balance, coupon/promo codes, inventory, gift cards, rate limit counters. Severity: HIGH (financial loss).

## 8.2 Mass Assignment

When a controller binds model fields directly from request parameters without an explicit allowlist, an attacker adds fields like `is_admin=true`, `role=admin`, `balance=99999`.

```ruby
# ❌ NEVER (Rails): permits ALL user-supplied fields
def update
  @user.update(params[:user])   # attacker sets role, is_admin, plan
end

# ✅ ALWAYS:
@user.update(params.require(:user).permit(:name, :email))
```

```python
# ❌ NEVER (Django DRF): exposes all model fields including is_staff, is_superuser
class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

# ✅ ALWAYS: explicit field list
fields = ['name', 'email']
```

```java
// ❌ NEVER (Spring): binds everything from request
@PostMapping("/profile")
public String update(@ModelAttribute User user) { ... }

// ✅ ALWAYS: @InitBinder restriction
@InitBinder
protected void initBinder(WebDataBinder binder) {
    binder.setAllowedFields("name", "email");
}
```

```php
// ❌ NEVER (Laravel): passes all request fields
User::create($request->all());

// ✅ ALWAYS:
User::create($request->only(['name', 'email']));
// OR use $fillable on the model
```

**Flag:** `params[:model]` without `.permit()`, `.permit!` (wildcard), `fields = '__all__'` on sensitive models, `@ModelAttribute` without `@InitBinder`, `$request->all()` to `fill()`/`create()`, `$guarded = []` with no `$fillable`. Severity: HIGH.

## 8.3 Unsafe Type Coercion

- `==` instead of `===` in security checks (JS): `"0" == false`, `null == undefined`
- PHP loose comparison: `$password == $hash` (use `hash_equals()`)
- Numeric string comparison in password reset tokens

## 8.4 Integer Overflow

- Arithmetic on user-supplied values without bounds checking
- Price/quantity calculations that could overflow or go negative
- `parseInt()` / `int()` on unbounded input used in array allocation or payment math

## 8.5 Missing Rate Limiting

- Login endpoints without rate limiting middleware
- Password reset without throttling
- OTP/2FA verification without attempt limiting
- API endpoints with no limit on expensive operations (LLM calls, file processing)

## 8.6 API Pagination / Unbounded Results

Missing pagination on collection endpoints allows attackers to dump entire datasets in one request — user lists, transaction history, file inventories.

```javascript
// ❌ NEVER: returns all records — leaks entire table, causes OOM under attack
app.get('/api/users', async (req, res) => {
  const users = await User.findAll()   // no WHERE limit, no LIMIT clause
  res.json(users)
})

// ✅ ALWAYS: enforce a max page size and require offset/cursor
app.get('/api/users', async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 20, 100)  // cap at 100
  const offset = parseInt(req.query.offset) || 0
  const users = await User.findAll({ limit, offset })
  res.json({ data: users, next: offset + limit })
})
```

**Flag:** ORM calls (`findAll()`, `find()`, `filter()`, `all()`, `list()`) on collection endpoints without a `limit`/`take`/`LIMIT` clause. Especially on endpoints returning user data, logs, orders, transactions, or files. Severity: MEDIUM (data exfiltration + DoS).

Also flag:
- `limit` accepted from user input without a **server-side cap** — `LIMIT req.query.limit` with no `Math.min()` → attacker sets limit=999999
- Cursor-based pagination without cursor integrity validation (unsigned cursors can skip auth boundaries)

---

# Category 9 — Dependency Analysis

## 9.1 Known Vulnerable Packages

Read dependency files and check versions:
- `package.json` / `package-lock.json`
- `requirements.txt` / `Pipfile.lock` / `poetry.lock`
- `pom.xml` / `build.gradle`
- `Gemfile.lock` / `composer.lock` / `go.sum` / `Cargo.lock`

Flag:
- Unpinned deps (`*` `latest` `>=`)
- Packages with CVEs in training data
- Deps not updated in 2+ years vs known EOL

Note: confidence:MEDIUM — training data may not include latest advisories. Recommend `npm audit` / `pip-audit` for authoritative results.

## 9.2 Deprecated API Usage

- Deprecated stdlib functions: Node `Buffer()` without `new`, Python `cgi` module (3.13+)
- Deprecated framework methods with security implications
- EOL runtime versions in `.node-version`, `.python-version`, `Dockerfile FROM`

## 9.3 Unsafe Native Bindings

- Native C/C++ addons without memory safety review → flag for manual audit
- Python `ctypes` / `cffi` without input validation on size/type params
- `unsafe` blocks in Rust → flag for manual review
- CGO calls in Go with user-controlled input
