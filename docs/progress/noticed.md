# Noticed

Open items seen in passing, not fixed. Newest last.

- HK-66: FastAPI 0.142 keeps included routers lazy (`app.routes` holds `_IncludedRouter`, no `.path`). Any test walking `app.routes` for `.path` or `.dependant` silently sees nothing; use `fastapi.routing.iter_route_contexts`. The HK-66 guard does.
- HK-66: the request called this "item 21"; the LLD has 12 items and guards is item 12.
- HK-66: the statement-capture helpers of LLD item 12 are not built; no route or repository exists yet to capture. Build with the first integration test that needs them.
