---
name: sast-websocket
description: "WebSocket security — missing origin validation, unauthenticated upgrade, no per-message authz, missing size limits, message injection. Load when socket.io, ws, WebSocket, faye-websocket, or uWebSockets detected."
---

# WebSocket Security

Loaded when: `socket.io`, `ws`, `websocket`, `faye-websocket`, `uWebSockets`, or native `WebSocket` detected.

## WS1 — Missing Origin Validation

```javascript
// ❌ NEVER: accepts connections from any origin
const wss = new WebSocket.Server({ port: 8080 })

// ❌ NEVER: verifyClient always true
const wss = new WebSocket.Server({
  verifyClient: () => true
})

// ✅ ALWAYS: validate Origin header on upgrade
const wss = new WebSocket.Server({
  verifyClient: (info) => {
    const allowed = ['https://app.example.com']
    return allowed.includes(info.origin)
  }
})
```

**Why:** Without origin validation any website can open a WebSocket using the victim's session cookies — reading real-time data or sending commands on their behalf.

## WS2 — Unauthenticated Upgrade

```javascript
// ❌ NEVER: no auth check at connection time
wss.on('connection', (ws, req) => {
  ws.on('message', (msg) => processCommand(msg))  // who is this?
})

// ✅ ALWAYS: authenticate at upgrade; close on failure
wss.on('connection', (ws, req) => {
  const token = new URL(req.url, 'http://x').searchParams.get('token')
  const user = verifyJWT(token)
  if (!user) { ws.close(4001, 'Unauthorized'); return }
  ws.user = user
})
```

**Why:** HTTP auth middleware (Express/Koa guards) does NOT apply to WebSocket connections — they bypass all route-level auth unless explicitly re-checked at the upgrade handler.

## WS3 — No Per-Message Authorization

```javascript
// ❌ NEVER: auth at connect time only, no per-action check
ws.on('message', (data) => {
  const { action, resourceId } = JSON.parse(data)
  db.update(resourceId, action)  // does ws.user own resourceId?
})

// ✅ ALWAYS: authorize each action
ws.on('message', async (data) => {
  const { action, resourceId } = JSON.parse(data)
  const resource = await db.findById(resourceId)
  if (resource.ownerId !== ws.user.id) { ws.send('{"error":"forbidden"}'); return }
  db.update(resourceId, action)
})
```

## WS4 — Missing Message Size Limit

```javascript
// ❌ NEVER: no size cap (memory exhaustion DoS)
const wss = new WebSocket.Server({ port: 8080 })

// ✅ ALWAYS:
const wss = new WebSocket.Server({
  maxPayload: 64 * 1024   // 64 KB — tune to use case
})
```

## WS5 — Message Injection / Blind JSON Execution

```javascript
// ❌ NEVER: parse and execute without validation
ws.on('message', (data) => {
  const cmd = JSON.parse(data)
  eval(cmd.script)                              // RCE
  db.query(`SELECT * FROM ${cmd.table}`)       // SQLi
})

// ✅ ALWAYS: validate structure and allowlist actions
ws.on('message', (data) => {
  let cmd
  try { cmd = JSON.parse(data) } catch { ws.close(1003); return }
  if (!ALLOWED_ACTIONS.has(cmd.action)) return
  // use cmd values as data only
})
```

## WS6 — socket.io Room / Namespace Authorization

```javascript
// ❌ NEVER: user can join any room
io.on('connection', (socket) => {
  socket.on('join', (room) => socket.join(room))
})

// ✅ ALWAYS: check membership before join
socket.on('join', async (room) => {
  const ok = await canUserAccessRoom(socket.user.id, room)
  if (!ok) { socket.emit('error', 'forbidden'); return }
  socket.join(room)
})
```
