---
name: sast-grpc
description: "gRPC security — server reflection in production, missing deadline/timeout, missing auth interceptor, WithInsecure/plaintext connections, missing TLS, unvalidated proto fields. Load when grpc, @grpc/grpc-js, grpcio, io.grpc detected."
---

# gRPC Security

Loaded when: `grpc`, `@grpc/grpc-js`, `grpcio`, `io.grpc`, `google.golang.org/grpc` detected.

## G1 — Server Reflection Enabled in Production

```python
# ❌ NEVER in production: exposes full service schema unauthenticated
from grpc_reflection.v1alpha import reflection
reflection.enable_server_reflection(SERVICE_NAMES, server)

# ✅ ALWAYS: guard with env check
if os.getenv('ENV') == 'development':
    reflection.enable_server_reflection(SERVICE_NAMES, server)
```

```go
// ❌ NEVER:
reflection.Register(s)

// ✅ ALWAYS:
if os.Getenv("ENV") == "development" {
    reflection.Register(s)
}
```

**Why:** Reflection lets anyone enumerate all services, methods, and message schemas — a complete API blueprint for attackers, no auth required.

## G2 — Missing Deadline / Timeout

```python
# ❌ NEVER: hangs indefinitely
stub.GetUser(request)

# ✅ ALWAYS:
stub.GetUser(request, timeout=5.0)
```

```go
// ❌ NEVER:
client.GetUser(ctx, req)

// ✅ ALWAYS:
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
client.GetUser(ctx, req)
```

**Why:** Missing deadline → goroutine/thread accumulation under slow downstream; resource exhaustion DoS.

## G3 — Missing Auth Interceptor

```go
// ❌ NEVER: no auth interceptor on server
s := grpc.NewServer()
pb.RegisterUserServiceServer(s, &server{})

// ✅ ALWAYS: unary + stream interceptors
s := grpc.NewServer(
    grpc.UnaryInterceptor(authInterceptor),
    grpc.StreamInterceptor(streamAuthInterceptor),
)

func authInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    md, ok := metadata.FromIncomingContext(ctx)
    if !ok { return nil, status.Error(codes.Unauthenticated, "missing metadata") }
    if !validateToken(md.Get("authorization")) {
        return nil, status.Error(codes.Unauthenticated, "invalid token")
    }
    return handler(ctx, req)
}
```

## G4 — Plaintext / WithInsecure Connection

```go
// ❌ NEVER:
conn, _ := grpc.Dial(addr, grpc.WithInsecure())
conn, _ := grpc.Dial(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))

// ✅ ALWAYS:
creds, _ := credentials.NewClientTLSFromFile(certFile, "")
conn, _ := grpc.Dial(addr, grpc.WithTransportCredentials(creds))
```

```python
# ❌ NEVER:
channel = grpc.insecure_channel('localhost:50051')

# ✅ ALWAYS:
creds = grpc.ssl_channel_credentials(root_certificates=cert)
channel = grpc.secure_channel('host:50051', creds)
```

## G5 — Unvalidated Proto Field Values

Proto definitions enforce types, not business-logic constraints. Flag gRPC handlers that use proto field values in:
- Database queries without parameterization (same SQLi rules as HTTP)
- File paths without sanitization
- Shell commands
- HTML output without encoding

**Rule:** gRPC is a transport, not a trust boundary. Treat all incoming proto fields as untrusted user input.
