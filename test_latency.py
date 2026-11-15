import time
import httpx

def check(url, name):
    t0 = time.perf_counter()
    try:
        r = httpx.get(url, timeout=10.0)
        dt = (time.perf_counter() - t0) * 1000
        print(f"[{name}] {url} -> {r.status_code} in {dt:.1f}ms (size: {len(r.content)} bytes)")
    except Exception as e:
        print(f"[{name}] {url} -> FAILED ({e})")

check("http://localhost:8001/", "Backend Root")
check("http://localhost:8001/api/auth/me", "Backend Auth Me")
check("http://localhost:8001/api/curriculum/classes", "Backend Curriculum")
check("http://localhost:8080/", "Frontend Root")
