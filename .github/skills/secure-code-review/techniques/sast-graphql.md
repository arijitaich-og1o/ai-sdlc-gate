---
name: sast-graphql
description: "GraphQL security — resolver-level authorization (most common GraphQL vuln), introspection in production, depth/complexity limiting, batching/alias abuse for brute-force, subscription WebSocket auth. Auto-triggered when graphql, apollo-server, strawberry, graphene, hotchocolate, or hasura found in dependency files."
---

# GraphQL Security

`OWASP: A01:2021 Broken Access Control · A05:2021 Security Misconfiguration`

Auto-triggered when found in deps:
`graphql` `apollo-server` `@apollo/server` `@apollo/gateway` `strawberry-graphql` `graphene` `hotchocolate` `hasura` `graphql-yoga` `mercurius` `pothos-graphql`

## 1. Missing Resolver-Level Authorization

The #1 GraphQL vulnerability. Schema defines what's possible — resolvers must enforce who can do it. HTTP middleware auth does NOT protect resolvers.

**Dangerous:**
```javascript
const resolvers = {
  Query: {
    user: (_, { id }) => db.users.findById(id),        // no auth — anyone can query any user
    adminStats: () => db.getAdminStats(),               // no role check
  },
  Mutation: {
    deleteUser: (_, { id }) => db.users.delete(id),    // no ownership check
  }
}
```

**Check:** Every resolver that returns sensitive data or performs mutations must verify `context.user` or equivalent before proceeding. Compare resolver list against auth-checked resolvers.

**IDOR pattern:** `user(id: $id)` resolver without `WHERE user_id = context.currentUser.id` constraint.

Severity: HIGH · OWASP: A01:2021 · CWE-285

## 2. Introspection Enabled in Production

Exposes full schema — all types, queries, mutations, field names — to attackers.

Signal: `introspection: true` in production Apollo config, or no explicit `introspection: process.env.NODE_ENV !== 'production'`. Strawberry: `Schema(introspection=True)` without env guard.

Severity: MEDIUM · CWE-200

## 3. Missing Depth / Complexity Limiting

No query depth or cost analysis → trivially nested query DoS:
```graphql
{ user { friends { friends { friends { friends { posts { comments { author { friends { name } } } } } } } } } }
```

Signal: `new ApolloServer({schema})` without `validationRules: [depthLimit(N)]` or `plugins: [ApolloServerPluginQueryComplexity(...)]`. Strawberry: no `Extensions` with complexity limiting.

Severity: MEDIUM · CWE-400

## 4. Batching / Alias Abuse for Brute-Force

GraphQL aliases allow sending multiple operations in one HTTP request — bypasses per-request rate limiting:

```graphql
{
  a1: login(username: "admin", password: "pass1") { token }
  a2: login(username: "admin", password: "pass2") { token }
  a3: login(username: "admin", password: "pass3") { token }
}
```

Signal: `login` `verifyOTP` `resetPassword` `confirmCode` resolvers with no per-resolver rate limiting (HTTP-level rate limiting is insufficient).

Severity: HIGH · CWE-307

## 5. Subscription WebSocket Auth

WebSocket connections for subscriptions often skip auth because they're initialized outside the HTTP middleware chain:

```javascript
// HTTP routes protected, but subscriptions auth skipped
useServer({ schema }, wsServer)  // no onConnect handler
```

**Safe:**
```javascript
useServer({
  schema,
  onConnect: async (ctx) => {
    const token = ctx.connectionParams?.authToken
    if (!token || !verifyToken(token)) throw new Error('Unauthorized')
  }
}, wsServer)
```

Severity: HIGH · CWE-306

## Finding Format

```json
{
  "id": "SF01", "category": "authorization", "class": "graphql_missing_resolver_auth",
  "severity": "HIGH", "confidence": "HIGH",
  "file": "src/graphql/resolvers/userResolver.js", "line": 12,
  "owasp": "A01:2021 Broken Access Control",
  "cwe": "CWE-285 (Improper Authorization)",
  "remediation": "Check context.user in every resolver before returning data or performing mutations"
}
```
