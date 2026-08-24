import os, sys, json
os.environ.setdefault("DATABASE_URL","postgresql://postgres:postgres@localhost:5432/telos_test")
os.environ.setdefault("ANTHROPIC_API_KEY","sk-test")
os.environ.setdefault("SUPABASE_URL","https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY","test-anon-key")
sys.path.insert(0,"/home/claude/Telos")
from streamlit.testing.v1 import AppTest
from core.database import init_db, create_job, export_user_data, purge_user_data, get_jobs
from core.models import Job
init_db()

passed=failed=0
def check(n,c,e=""):
    global passed,failed
    if c: passed+=1; print(f"  PASS  {n}")
    else: failed+=1; print(f"  FAIL  {n} {e}")

USER="acct-test@example.com"
OTHER="bystander@example.com"

print("\n[1] Profile page renders for a signed-in user")
at = AppTest.from_file("/home/claude/Telos/pages/0_Profile.py", default_timeout=60)
at.session_state["user_email"]=USER; at.session_state["tester_name"]=USER
at.run()
check("no exception", not at.exception, at.exception)
btns=[b.label for b in at.button]
check("export button", "Prepare my data export" in btns, btns)
check("sign out everywhere", "Sign out of all devices" in btns, btns)
check("delete button", "Permanently delete my account" in btns, btns)

print("\n[2] demo visitor cannot use any of it")
at2 = AppTest.from_file("/home/claude/Telos/pages/0_Profile.py", default_timeout=60)
at2.session_state["user_email"]="demo@usetelosapp.com"; at2.session_state["tester_name"]="__demo__"
at2.run()
check("no exception", not at2.exception, at2.exception)
disabled = {b.label: b.disabled for b in at2.button if b.label in
            ("Prepare my data export","Sign out of all devices","Permanently delete my account")}
check("all three disabled in demo", all(disabled.values()) and len(disabled)==3, disabled)

print("\n[3] delete requires typing DELETE")
at3 = AppTest.from_file("/home/claude/Telos/pages/0_Profile.py", default_timeout=60)
at3.session_state["user_email"]=USER; at3.session_state["tester_name"]=USER
at3.run()
create_job(Job(company="Acme", role="PM", status="applied", notes="keep me"), USER)
create_job(Job(company="Other Co", role="PM", status="applied", notes="other user"), OTHER)
[b for b in at3.button if b.label=="Permanently delete my account"][0].click().run()
errs=" ".join(e.value for e in at3.error)
check("blocked without confirmation", "Type DELETE" in errs, errs)
check("data survived", len(get_jobs(USER))>=1, len(get_jobs(USER)))

print("\n[4] export returns this user's rows only")
bundle = export_user_data(USER)
blob = json.dumps(bundle, default=str)
check("own data present", "keep me" in blob)
check("other user absent", "other user" not in blob)
check("no session tokens exported", "user_sessions" not in bundle, list(bundle))

print("\n[5] purge removes only this user")
res = purge_user_data(USER)
check("purge reports rows", sum(res.values())>0, res)
check("user emptied", len(get_jobs(USER))==0, len(get_jobs(USER)))
check("bystander untouched", len(get_jobs(OTHER))==1, len(get_jobs(OTHER)))
purge_user_data(OTHER)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
