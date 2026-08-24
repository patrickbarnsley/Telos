import os, sys
os.environ.setdefault("DATABASE_URL","postgresql://postgres:postgres@localhost:5432/telos_test")
os.environ["OWNER_EMAILS"] = "patrickbarnsley@gmail.com"
os.environ["ANTHROPIC_API_KEY"] = "sk-test-not-used"
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
sys.path.insert(0, "/home/claude/Telos")
from streamlit.testing.v1 import AppTest

FAIL = []
def check(n, c, extra=""):
    print(("PASS  " if c else "FAIL  ") + n + (f"   [{extra}]" if extra and not c else ""))
    if not c: FAIL.append(n)

def run(path, session=None, timeout=60):
    at = AppTest.from_file("/home/claude/Telos/"+path, default_timeout=timeout)
    if session:
        for k, v in session.items():
            at.session_state[k] = v
    at.run()
    return at

# ---------- logged-out landing ----------
at = run("app.py")
check("app.py renders logged out", not at.exception, str(at.exception))
btn_labels = [b.label for b in at.button]
check("demo button present on login page",
      any("demo" in l.lower() for l in btn_labels), str(btn_labels))
check("login + signup forms present", len(at.tabs) >= 2)

# ---------- enter demo via the button ----------
demo_btn = [b for b in at.button if "demo" in b.label.lower()][0]
demo_btn.click().run()
check("clicking demo enters the demo account", not at.exception, str(at.exception))
def ss(at, k):
    try:
        return at.session_state[k]
    except Exception:
        return None
check("demo session identity set", ss(at, "tester_name") == "__demo__", str(ss(at, "tester_name")))
md = " ".join(str(m.value) for m in at.markdown)
check("demo banner shown on home", "demo account" in md.lower(), md[:200])

DEMO = {"user_email": "demo@usetelosapp.com", "tester_name": "__demo__", "chat_history": {}}
USER = {"user_email": "alice@example.com", "tester_name": "alice@example.com", "chat_history": {}}

# ---------- every page, in demo ----------
for page in ["pages/0_Profile.py", "pages/1_Track.py", "pages/2_Match.py", "pages/3_Guide.py"]:
    at = run(page, DEMO)
    check(f"{page} renders in demo", not at.exception, str(at.exception))
    txt = " ".join(str(m.value) for m in at.markdown)
    check(f"{page} shows demo banner", "demo account" in txt.lower(), txt[:160])

# ---------- every page, as a real free user ----------
for page in ["pages/0_Profile.py", "pages/1_Track.py", "pages/2_Match.py", "pages/3_Guide.py"]:
    at = run(page, USER)
    check(f"{page} renders for a real user", not at.exception, str(at.exception))

# ---------- logged-in home for a real user ----------
at = run("app.py", USER)
check("app.py renders logged in", not at.exception, str(at.exception))
metric_labels = [m.label for m in at.metric]
check("home shows usage meters", any("Match scores" in l for l in metric_labels), str(metric_labels))

# ---------- quota exhaustion surfaces in Match ----------
from core import plans, database as _db
from core.models import Profile as _P, Job as _J
_db.purge_user_data("capped@example.com")
plans.set_plan("capped@example.com", "free")
_db.save_profile(_P(resume_text="resume", target_role="PM"), "capped@example.com")
_db.save_resume_version("capped@example.com", "v1", "resume", "r.pdf", True)
_db.create_job(_J(company="Acme", role="PM", status="applied"), "capped@example.com")
for _ in range(10):
    plans.record_usage("capped@example.com", plans.MATCH)
at = run("pages/2_Match.py", {"user_email": "capped@example.com",
                              "tester_name": "capped@example.com", "chat_history": {}})
check("Match renders for a capped user", not at.exception, str(at.exception))
caps = " ".join(str(c.value) for c in at.caption)
check("capped user sees usage caption", "10 of 10" in caps or "used this month" in caps, caps[:200])

# ---------- waitlist deep link ----------
at = AppTest.from_file("/home/claude/Telos/app.py", default_timeout=60)
at.query_params["waitlist"] = "1"
at.run()
check("waitlist deep link renders", not at.exception, str(at.exception))
md = " ".join(str(m.value) for m in at.markdown)
check("waitlist form appears", "waitlist" in md.lower(), md[:200])



# ---------- duplicate labels do not collapse or crash ----------
# Two resume versions can share a label, and two applications can share a
# company and role. Both used to be keyed by their display string, which made
# the second one unreachable and, when the active version fell past the end of
# the collapsed list, crashed the page outright.
DUPE = "dupe@example.com"
_db.purge_user_data(DUPE)
_db.save_profile(_P(resume_text="resume", resume_filename="r.pdf", target_role="PM"), DUPE)
for _i in range(4):
    _db.save_resume_version(DUPE, "v1", "resume text", "r.pdf", set_active=(_i == 3))
_db.create_job(_J(company="Acme", role="PM", status="applied"), DUPE)
_db.create_job(_J(company="Acme", role="PM", status="applied"), DUPE)

at = run("pages/2_Match.py", {"user_email": DUPE, "tester_name": DUPE, "chat_history": {}})
check("Match survives duplicate resume labels", not at.exception, str(at.exception))
_sel = list(at.selectbox)
check("all four resume versions selectable",
      any(len(s.options) == 4 for s in _sel), str([(s.label, len(s.options)) for s in _sel]))
check("both identical jobs selectable",
      any(len(s.options) == 2 for s in _sel), str([(s.label, len(s.options)) for s in _sel]))
_db.purge_user_data(DUPE)

print()
print("=" * 46)
print("ALL PAGE TESTS PASSED" if not FAIL else "FAILURES: " + ", ".join(FAIL))
sys.exit(1 if FAIL else 0)

