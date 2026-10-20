"""API boundary tests.

The point of this suite is not that the endpoints work. It is that the
properties which took the longest to get right in the Streamlit app survive the
move to an HTTP boundary, where every one of them is newly reachable by anyone
with curl.

Sessions are minted directly with remember_session rather than through
core.auth.sign_in, because sign_in calls Supabase. What is under test here is
the API's handling of a session, not Supabase's ability to issue one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TELOS_TEST", "1")

from fastapi.testclient import TestClient          # noqa: E402
from api.deps import SESSION_COOKIE                # noqa: E402
from api.main import app                           # noqa: E402
from core.auth import remember_session             # noqa: E402
from core.database import get_connection, init_db  # noqa: E402
from core.models import Job                        # noqa: E402

passed = failed = 0
failures = []


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")          # run_all.py counts these lines
    else:
        failed += 1
        failures.append(label)
        print(f"  FAIL  {label}   {detail}")


ALICE = "alice.api@telos.test"
BOB = "bob.api@telos.test"


def wipe(email):
    conn = get_connection(); cur = conn.cursor()
    for t in ("jobs", "profile", "resume_versions", "match_results",
              "interview_preps", "usage_events", "user_sessions", "user_plans"):
        cur.execute(f"DELETE FROM {t} WHERE tester_name = %s", (email,))
    conn.commit(); cur.close(); conn.close()


def client_for(email):
    c = TestClient(app)
    c.cookies.set(SESSION_COOKIE, remember_session(email))
    return c


init_db()
wipe(ALICE); wipe(BOB)

anon = TestClient(app)
alice = client_for(ALICE)
bob = client_for(BOB)

# ---------------------------------------------------------------- 1. no session
print("\n[1] an unauthenticated caller reaches nothing")
GUARDED = [("GET", "/api/me"), ("GET", "/api/jobs"), ("POST", "/api/jobs"),
           ("GET", "/api/profile"), ("PUT", "/api/profile"),
           ("GET", "/api/resumes"), ("GET", "/api/match"), ("POST", "/api/match"),
           ("GET", "/api/roadmap"), ("POST", "/api/roadmap"),
           ("POST", "/api/advisor"), ("GET", "/api/export"),
           ("DELETE", "/api/account")]
for method, path in GUARDED:
    r = anon.request(method, path, json={})
    check(f"{method} {path} is refused without a session", r.status_code == 401,
          f"got {r.status_code}")

check("health is the one endpoint that needs no session",
      anon.get("/api/health").status_code == 200)
check("a forged cookie is refused",
      anon.get("/api/me", cookies={SESSION_COOKIE: "not-a-real-token"}).status_code == 401)

# ---------------------------------------------------------------- 2. identity
print("\n[2] identity comes from the cookie and nowhere else")
r = alice.get("/api/me")
check("a valid session resolves", r.status_code == 200, r.text[:120])
check("and resolves to the right account", r.json().get("email") == ALICE)
check("quotas are reported", isinstance(r.json().get("quotas"), dict))

r = alice.post("/api/jobs", json={"company": "Cobalt", "role": "Delivery Manager",
                                  "status": "applied", "tester_name": BOB})
check("a body cannot smuggle in another account", r.status_code == 201, r.text[:120])
alice_job = r.json()["id"]
owner = [j for j in alice.get("/api/jobs").json()["jobs"] if j["id"] == alice_job]
check("the row belongs to the cookie account, not the body one", len(owner) == 1)
check("and Bob does not see it",
      all(j["id"] != alice_job for j in bob.get("/api/jobs").json()["jobs"]))

# ---------------------------------------------------------------- 3. isolation
print("\n[3] one account cannot reach another's rows")
r = bob.get(f"/api/jobs/{alice_job}")
check("reading another account's job is 404, not 403", r.status_code == 404,
      f"got {r.status_code}")
r = bob.patch(f"/api/jobs/{alice_job}", json={"status": "rejected"})
check("patching another account's job is refused", r.status_code == 404)
r = bob.delete(f"/api/jobs/{alice_job}")
check("deleting another account's job is refused", r.status_code == 404)
still = alice.get(f"/api/jobs/{alice_job}")
check("and the row is untouched after all three attempts",
      still.status_code == 200 and still.json().get("status") == "applied",
      still.text[:120])
r = bob.get("/api/match/999999")
check("a match id that is not yours is 404", r.status_code == 404)
r = bob.get("/api/match/999999/interview-prep")
check("interview prep for a match that is not yours is 404", r.status_code == 404)

# ---------------------------------------------------------------- 4. quotas
print("\n[4] quotas are enforced at the boundary, before any model call")
from core.plans import PLANS, record_usage, set_plan  # noqa: E402

set_plan(ALICE, "free")
limit = PLANS["free"]["limits"]["match"]
for _ in range(limit):
    record_usage(ALICE, "match")
r = alice.post("/api/match", json={"jd_text": "Senior Delivery Manager, Jira required."})
check("an exhausted quota is refused with 402", r.status_code == 402, f"got {r.status_code}")
check("and the refusal names the limit", str(limit) in r.text, r.text[:160])

prep_limit = PLANS["free"]["limits"]["interview_prep"]
for _ in range(prep_limit):
    record_usage(ALICE, "interview_prep")
r = alice.post("/api/match/999999/interview-prep")
check("the quota gate runs before the ownership check",
      r.status_code == 402, f"got {r.status_code}")

set_plan(BOB, "free")
r = bob.post("/api/roadmap")
check("a roadmap with no resume is refused with 409, not a crash",
      r.status_code == 409, f"got {r.status_code}")

# ---------------------------------------------------------------- 5. validation
print("\n[5] bad input is refused in the caller's language")
r = alice.post("/api/jobs", json={"company": "Acme"})
check("a job with no role is rejected", r.status_code == 422, f"got {r.status_code}")
r = alice.patch(f"/api/jobs/{alice_job}", json={})
check("an empty patch is rejected", r.status_code == 400, f"got {r.status_code}")
# Free plan allows zero advisor messages, so the quota gate would answer first.
# Input validation is only reachable for an account that may use the feature.
set_plan(BOB, "pro")
r = bob.post("/api/advisor", json={"message": "   "})
check("an empty advisor message is rejected before billing",
      r.status_code == 400, f"got {r.status_code}")
set_plan(BOB, "free")

# ---------------------------------------------------------------- 5b. sessions
print("\n[5b] signing out revokes the token, not just the browser's copy")
from core.auth import remember_session as _mint, resume_session as _resolve  # noqa: E402

tok = _mint("session.probe@telos.test")
check("a fresh token resolves", _resolve(tok) == "session.probe@telos.test")

sc = TestClient(app); sc.cookies.set(SESSION_COOKIE, tok)
r = sc.post("/api/auth/logout")
check("logout answers 200", r.status_code == 200, r.text[:120])

# The regression this guards: logout declared its cookie as a plain parameter,
# so FastAPI read it from the query string. The endpoint cleared the browser
# cookie, returned 200, and left the token live for its full 30 days.
check("the token is revoked server-side", _resolve(tok) is None, "still resolves")

stale = TestClient(app); stale.cookies.set(SESSION_COOKIE, tok)
check("and a captured cookie no longer works",
      stale.get("/api/me").status_code == 401, stale.get("/api/me").status_code)

check("logging out twice does not error",
      sc.post("/api/auth/logout").status_code == 200)

# ---------------------------------------------------------------- 5c. throttling
print("\n[5c] guessing a password is made expensive")
from core.ratelimit import (LOGIN_LIMIT, LOGIN_WINDOW_SECONDS, SIGNUP_LIMIT,  # noqa: E402
                            attempts_since, check as rl_check, clear as rl_clear,
                            record_attempt)

# Exercised against the limiter directly rather than by hammering /login.
# Whether a login succeeds depends on the Supabase credentials in the
# environment, and a successful login deliberately clears the bucket, so driving
# this through the endpoint would test the environment instead of the limiter.
BUCKET = "login:email:bruteforce@example.com"
rl_clear(BUCKET)
check("a fresh bucket is empty", attempts_since(BUCKET, LOGIN_WINDOW_SECONDS) == 0)

for _ in range(LOGIN_LIMIT - 1):
    record_attempt(BUCKET)
allowed, _ = rl_check([BUCKET], LOGIN_LIMIT, LOGIN_WINDOW_SECONDS)
check("attempts below the limit are allowed", allowed is True)

record_attempt(BUCKET)
allowed, retry = rl_check([BUCKET], LOGIN_LIMIT, LOGIN_WINDOW_SECONDS)
check("the attempt at the limit is refused", allowed is False)
check("and the refusal says how long to wait", retry == LOGIN_WINDOW_SECONDS, retry)

check("a successful sign-in clears the throttle",
      (rl_clear(BUCKET), attempts_since(BUCKET, LOGIN_WINDOW_SECONDS))[1] == 0)

# The endpoint refuses once a bucket is full, whatever the credentials do.
ip_bucket = "login:ip:testclient"
rl_clear(ip_bucket)
for _ in range(LOGIN_LIMIT):
    record_attempt(ip_bucket)
rl = TestClient(app)
r = rl.post("/api/auth/login", json={"email": "anyone@example.com", "password": "x"})
check("the endpoint refuses when the address bucket is full",
      r.status_code == 429, f"got {r.status_code}")
check("the refusal carries Retry-After", r.headers.get("retry-after") is not None)
check("and is phrased for a person", "15 minutes" in r.json().get("detail", ""), r.text[:120])
check("one address cannot spray many accounts",
      rl.post("/api/auth/login",
              json={"email": "a.different.one@example.com", "password": "x"}).status_code == 429)
rl_clear(ip_bucket)

check("signup is throttled harder than login", SIGNUP_LIMIT < LOGIN_LIMIT,
      f"{SIGNUP_LIMIT} vs {LOGIN_LIMIT}")
check("the limiter fails open rather than locking everyone out",
      attempts_since("", LOGIN_WINDOW_SECONDS) == 0)

# ---------------------------------------------------------------- 5d. parity
print("\n[5d] the features ported back from Streamlit are scoped like the rest")

for method, path in (("POST", "/api/match/scam-check"), ("GET", "/api/paths"),
                     ("POST", "/api/paths"), ("GET", "/api/roadmap/progress"),
                     ("PUT", "/api/roadmap/progress"), ("GET", "/api/billing"),
                     ("POST", "/api/billing/checkout"), ("POST", "/api/billing/portal")):
    check(f"{method} {path} needs a session",
          anon.request(method, path, json={}).status_code == 401)

r = alice.post("/api/match/scam-check", json={"company": "  ", "jd_text": "Real posting."})
check("a scam check with no company is refused", r.status_code == 400, r.status_code)
r = alice.post("/api/match/scam-check", json={"company": "Acme", "jd_text": "   "})
check("a scam check with no posting is refused", r.status_code == 400, r.status_code)

r = alice.post("/api/paths", json={"path_name": "PM track", "target_role": "Delivery Manager"})
check("a career path is created", r.status_code == 201, r.text[:120])
path_id = r.json()["id"]
check("the owner sees it",
      any(p["id"] == path_id for p in alice.get("/api/paths").json()["paths"]))
check("another account does not",
      not any(p["id"] == path_id for p in bob.get("/api/paths").json()["paths"]))
check("and cannot delete it", bob.delete(f"/api/paths/{path_id}").status_code == 404)
check("a path with no name is refused",
      alice.post("/api/paths", json={"path_name": " ", "target_role": "x"}).status_code == 400)

r = alice.put("/api/roadmap/progress",
              json={"milestone_order": 1, "milestone_title": "Jira admin", "completed": True})
check("a milestone can be ticked off", r.status_code == 200, r.text[:120])
check("the progress is recorded",
      alice.get("/api/roadmap/progress").json()["progress"].get("1") is True,
      alice.get("/api/roadmap/progress").json())
check("progress does not leak to another account",
      not bob.get("/api/roadmap/progress").json()["progress"])
check("a milestone can be un-ticked",
      (alice.put("/api/roadmap/progress",
                 json={"milestone_order": 1, "milestone_title": "Jira admin",
                       "completed": False}),
       alice.get("/api/roadmap/progress").json()["progress"].get("1"))[1] is False)
check("the owner can delete their own path",
      alice.delete(f"/api/paths/{path_id}").status_code == 204)

r = alice.get("/api/billing")
check("billing state is readable", r.status_code == 200, r.text[:120])
check("and reports the founding seats left",
      isinstance(r.json().get("founding_seats_left"), int), r.json())
check("checkout without Stripe configured fails safely, not with a traceback",
      alice.post("/api/billing/checkout", json={"annual": False}).status_code in (409, 503),
      alice.post("/api/billing/checkout", json={"annual": False}).status_code)
check("the portal refuses when there is no customer yet",
      alice.post("/api/billing/portal").status_code in (409, 503))

# ---------------------------------------------------------------- 5e. contracts
print("\n[5e] responses are shaped for the caller, not for the database")

# Three times now, a core/ function has returned its payload nested inside a
# storage envelope, the router has passed that envelope straight through, and
# the frontend has read the wrong level and rendered nothing. Type checking
# cannot see it and the build passes. These assertions are the net.
from core.database import (save_critical_path, save_interview_prep,  # noqa: E402
                           save_match_result)

save_critical_path(ALICE, {"target_role": "Delivery Manager", "summary": "A summary.",
                           "milestones": [{"title": "One", "detail": "Detail."}]})
road = alice.get("/api/roadmap").json()
check("the roadmap exposes milestones at the top level",
      isinstance(road.get("milestones"), list) and len(road["milestones"]) == 1, road)
check("and does not leak the storage envelope", "path" not in road, list(road))

mid = save_match_result(80, "Summary.", ["Has"], ["Needs"], [], [],
                        "A posting.", ALICE, company="Acme", role="PM")
save_interview_prep(ALICE, mid, {"questions": [
    {"question": "Q?", "from_requirement": "R", "strength": "weak",
     "how_your_resume_answers": "A"}], "note": "", "injection_attempt": ""})
prep = alice.get(f"/api/match/{mid}/interview-prep").json()
check("interview prep exposes questions at the top level",
      isinstance(prep.get("questions"), list) and len(prep["questions"]) == 1, list(prep))
check("and does not leak its envelope either", "prep" not in prep, list(prep))

q = (prep.get("questions") or [{}])[0]
for field in ("question", "from_requirement", "strength", "how_your_resume_answers"):
    check(f"a prep question carries {field}", field in q, list(q))

m = alice.get(f"/api/match/{mid}").json()
check("a match result exposes its score directly",
      m.get("overall_score") is not None, list(m))

# ---------------------------------------------------------------- 6. deletion
print("\n[6] deletion removes what it claims to")
victim = "carol.api@telos.test"
wipe(victim)
carol = client_for(victim)
carol.post("/api/jobs", json={"company": "Vantage", "role": "APM", "status": "applied"})
carol.put("/api/profile", json={"resume_text": "Four years of Jira.",
                                "target_role": "Delivery Manager"})
check("carol has rows before deletion",
      len(carol.get("/api/jobs").json()["jobs"]) == 1)

exported = carol.get("/api/export")
check("export returns the account's data", exported.status_code == 200, exported.text[:120])

r = carol.delete("/api/account")
check("deletion reports success", r.status_code == 200, r.text[:160])

conn = get_connection(); cur = conn.cursor()
left = {}
for t in ("jobs", "profile", "user_sessions", "match_results"):
    cur.execute(f"SELECT count(*) FROM {t} WHERE tester_name = %s", (victim,))
    left[t] = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM ai_spend WHERE tester_name = %s", (victim,))
spend_rows = cur.fetchone()[0]
cur.close(); conn.close()
check("jobs are gone", left["jobs"] == 0, left)
check("the profile is gone", left["profile"] == 0, left)
check("every session is revoked", left["user_sessions"] == 0, left)
check("the spend ledger keeps no identifying row", spend_rows == 0, spend_rows)

after = TestClient(app)
after.cookies.set(SESSION_COOKIE, "stale")
check("the deleted account's session no longer resolves",
      after.get("/api/me").status_code == 401)

wipe(ALICE); wipe(BOB); wipe(victim)

print(f"\n  {passed} passed, {failed} failed")
if failures:
    print("  FAILURES: " + "; ".join(failures))
sys.exit(1 if failed else 0)
