import os, sys, json
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/telos_test")
os.environ["OWNER_EMAILS"] = "patrickbarnsley@gmail.com"
sys.path.insert(0, "/home/claude/Telos")

from core import database as db
from core import plans
from core import demo
from core.models import Job, Profile

FAIL = []
def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{extra}]" if extra and not cond else ""))
    if not cond: FAIL.append(name)

# ---------- schema ----------
db.init_db()

# Start from a clean slate. These tests assert on exact counts and quota
# positions, so rows left behind by a previous run make them fail for the wrong
# reason. Purging up front is the difference between a real regression signal
# and noise.
for _u in ("alice@example.com", "bob@example.com", "patrickbarnsley@gmail.com"):
    try:
        db.purge_user_data(_u)
    except Exception:
        pass
db.init_db()  # idempotent
conn = db.get_connection(); cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = {r[0] for r in cur.fetchall()}
cur.close(); conn.close()
check("init_db creates all tables",
      {"jobs","profile","resume_versions","career_paths","match_results","guide_progress",
       "critical_path","user_plans","usage_events","waitlist"} <= tables, str(sorted(tables)))

# ---------- demo seeding ----------
demo.ensure_seeded()
jobs = db.get_jobs(demo.DEMO_TESTER)
matches = db.get_all_match_results(demo.DEMO_TESTER)
paths = db.get_career_paths(demo.DEMO_TESTER)
cp = db.get_critical_path(demo.DEMO_TESTER, paths[0]["id"]) if paths else None
prof = db.get_profile(demo.DEMO_TESTER)
check("demo seeds jobs", len(jobs) == 12, f"{len(jobs)}")
check("demo seeds match results", len(matches) == 3, f"{len(matches)}")
check("demo seeds critical path", cp is not None and len(cp["path"]["milestones"]) == 5)
check("demo seeds profile", prof is not None and prof["target_role"] == "Technical Project Manager")
check("demo match JSON round-trips", isinstance(json.loads(matches[0]["matched_reqs"]), list))

before = len(jobs)
demo.ensure_seeded()   # must not double-seed
check("demo seeding is idempotent", len(db.get_jobs(demo.DEMO_TESTER)) == before)

# ---------- demo write lock ----------
db.create_job(Job(company="Hacker Co", role="x", status="applied"), demo.DEMO_TESTER)
check("demo blocks create_job", len(db.get_jobs(demo.DEMO_TESTER)) == before)
victim = jobs[0]["id"]
db.delete_job(victim, demo.DEMO_TESTER)
check("demo blocks delete_job", db.get_job(victim, demo.DEMO_TESTER) is not None)
db.update_job(victim, {"company": "WRECKED"}, demo.DEMO_TESTER)
check("demo blocks update_job", db.get_job(victim, demo.DEMO_TESTER)["company"] != "WRECKED")
db.save_profile(Profile(resume_text="x", target_role="x"), demo.DEMO_TESTER)
check("demo blocks save_profile", db.get_profile(demo.DEMO_TESTER)["target_role"] == "Technical Project Manager")

# ---------- real users still write ----------
A, B = "alice@example.com", "bob@example.com"
a_job = db.create_job(Job(company="Acme", role="PM", status="applied"), A)
b_job = db.create_job(Job(company="Globex", role="PM", status="applied"), B)
check("real user create_job works", isinstance(a_job, int) and a_job > 0)

# ---------- IDOR ----------
check("get_job is owner-scoped", db.get_job(a_job, B) is None)
check("get_job works for owner", db.get_job(a_job, A) is not None)
db.delete_job(a_job, B)
check("delete_job is owner-scoped", db.get_job(a_job, A) is not None)
db.update_job(a_job, {"company": "PWNED"}, B)
check("update_job is owner-scoped", db.get_job(a_job, A)["company"] == "Acme")
db.save_match_result(80,"s",["m"],["x"],[],[],"jd",A,job_id=a_job,company="Acme",role="PM")
mres = db.get_match_results(a_job, A)
check("get_match_results owner sees it", len(mres) == 1)
check("get_match_results is owner-scoped", len(db.get_match_results(a_job, B)) == 0)
db.delete_match_result(mres[0]["id"], B)
check("delete_match_result is owner-scoped", len(db.get_match_results(a_job, A)) == 1)
rv = db.save_resume_version(A, "v1", "resume text", "a.pdf", True)
db.delete_resume_version(rv, B)
check("delete_resume_version is owner-scoped", len(db.get_resume_versions(A)) == 1)
cpid = db.create_career_path(A, "Path", "PM")
db.delete_career_path(cpid, B)
check("delete_career_path is owner-scoped", len(db.get_career_paths(A)) == 1)

# ---------- plans & quota ----------
check("new user defaults to free", plans.get_plan(A) == "free")
check("owner email resolves to owner plan", plans.get_plan("patrickbarnsley@gmail.com") == "owner")
check("demo resolves to demo plan", plans.get_plan(demo.DEMO_TESTER) == "demo")
check("owner is unlimited", plans.check_quota("patrickbarnsley@gmail.com", plans.MATCH)[0] is True
      and plans.limit_for("patrickbarnsley@gmail.com", plans.MATCH) == plans.UNLIMITED)
check("demo has zero match quota", plans.check_quota(demo.DEMO_TESTER, plans.MATCH)[0] is False)

allowed, used, limit = plans.check_quota(A, plans.MATCH)
check("free plan starts at 0/10", allowed and used == 0 and limit == 10)
for _ in range(10):
    plans.record_usage(A, plans.MATCH)
allowed, used, limit = plans.check_quota(A, plans.MATCH)
check("free plan blocks at the cap", (not allowed) and used == 10, f"used={used} allowed={allowed}")
check("quota is per-action", plans.check_quota(A, plans.ROADMAP)[0] is True)
check("quota is per-user", plans.check_quota(B, plans.MATCH)[0] is True)

plans.set_plan(A, "pro")
check("set_plan upgrades", plans.get_plan(A) == "pro")
check("pro raises the cap", plans.check_quota(A, plans.MATCH)[0] is True)
plans.set_plan(A, "pro")  # upsert must not error
check("set_plan is idempotent", plans.get_plan(A) == "pro")

plans.join_waitlist("someone@example.com", "wants unlimited")
plans.join_waitlist("someone@example.com", "duplicate")  # must not raise
conn = db.get_connection(); cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM waitlist"); n = cur.fetchone()[0]; cur.close(); conn.close()
check("waitlist dedupes on email", n == 1, f"{n}")

print()
print("=" * 46)
print(f"{'ALL TESTS PASSED' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
sys.exit(1 if FAIL else 0)
