import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.app.main import app

routes = []
for route in app.routes:
    if hasattr(route, "methods"):
        methods = ",".join(sorted(route.methods))
        path = route.path
        name = route.name
        routes.append((methods, path, name))

print(f"Total API routes registered: {len(routes)}")
for m, p, n in sorted(routes, key=lambda x: x[1]):
    print(f"  {m:15} | {p:55} | {n}")
