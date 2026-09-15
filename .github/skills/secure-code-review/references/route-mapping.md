---
name: route-mapping
description: "Phase 3 route mapping — extract HTTP routes and map to handler functions for Thorough depth scans and DAST correlation. Framework-specific grep patterns for Express/Fastify/NestJS, Django/Flask/FastAPI, Spring Boot, Laravel, ASP.NET, Gin/Fiber/Gorilla, Rails."
---

# Phase 3 — Route Mapping

Load this reference when: `--thorough` is passed, or `/engage-sast` needs DAST correlation targets.

If `--graph` was passed: route handlers are already identified as entry-point nodes during Phase G2 community detection in `graph-traversal.md` — use those entry_point values as the route map. Skip per-framework grep below.

## Extraction Patterns

### Express / Fastify / NestJS (JS/TS)
```
grep: app.get app.post app.put app.delete app.patch app.all app.use
      router.get router.post @Get() @Post() @Controller()
      fastify.get fastify.post
```

### Django / Flask / FastAPI (Python)
```
grep: path() re_path() url() @app.route @app.get @app.post
      @router.get @router.post urlpatterns
```

### Spring Boot (Java)
```
grep: @RequestMapping @GetMapping @PostMapping @PutMapping @DeleteMapping
      @RestController @Controller
```

### Laravel (PHP)
```
grep: Route::get Route::post Route::put Route::delete Route::resource
      Route::apiResource Route::group Route::middleware
```

### ASP.NET (C#)
```
grep: [HttpGet] [HttpPost] [HttpPut] [HttpDelete] [Route()]
      MapGet MapPost app.Map [ApiController]
```

### Gin / Fiber / Gorilla (Go)
```
grep: r.GET r.POST r.PUT r.DELETE router.HandleFunc
      app.Get app.Post (Fiber)
```

### Rails (Ruby)
```
grep: get post put patch delete resources resource match root
      (in config/routes.rb)
```

## Route Map Output

```json
{
  "POST /api/users": {
    "handler": "userController.create",
    "file": "src/controllers/userController.js",
    "line": 12,
    "middleware": ["authMiddleware", "rateLimiter"],
    "parameters": ["body.username", "body.email", "body.password"]
  }
}
```

## Uses

1. Link SAST findings to testable HTTP endpoints
2. Identify routes WITHOUT auth middleware (category 3 check)
3. Feed DAST correlation when invoked via `/engage-sast`
4. Generate `dast_target: true` flag on findings with confirmed sinks at reachable routes
