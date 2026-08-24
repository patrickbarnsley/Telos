import os, sys
os.environ.setdefault("DATABASE_URL","postgresql://postgres:postgres@localhost:5432/telos_test")
os.environ.setdefault("ANTHROPIC_API_KEY","sk-test")
os.environ.setdefault("SUPABASE_URL","https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY","test-anon-key")
sys.path.insert(0,"/home/claude/Telos")
from streamlit.testing.v1 import AppTest

passed=failed=0
def check(name, cond, extra=""):
    global passed, failed
    if cond: passed+=1; print(f"  PASS  {name}")
    else: failed+=1; print(f"  FAIL  {name} {extra}")

print("\n[1] signed-out landing renders")
at = AppTest.from_file("/home/claude/Telos/app.py", default_timeout=60).run()
check("no exception", not at.exception, at.exception)
body = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
check("hero present", "Telos" in body)
check("demo button", any("demo" in b.label.lower() for b in at.button))
# AppTest does not expose tab labels, so assert on the widgets each tab holds:
# sign in (email+password+remember), create account (email+2 passwords+terms), forgot (email)
btns = [b.label for b in at.button]
check("sign-in form", "Sign in" in btns, btns)
check("create-account form", "Create account" in btns, btns)
check("forgot-password form", "Email me a reset link" in btns, btns)
check("remember-me checkbox", any("Keep me signed in" in c.label for c in at.checkbox), [c.label for c in at.checkbox])

print("\n[2] forgot-password tab is enumeration safe")
src = open("/home/claude/Telos/app.py").read()
check("no branch on account existence", "If that address has an account" in src)
check("send_password_reset called", "send_password_reset(fp_email)" in src)

print("\n[3] signup enforces password policy + terms")
check("uses MIN_PASSWORD caption", "MIN_PASSWORD} characters" in src)
check("terms checkbox required", "accept the terms" in src)
check("no legacy 6-char rule", "< 6" not in src)

print("\n[4] sign-out revokes the durable token")
check("forget_session on sign out", "forget_session(st.session_state.session_token)" in src)
check("query params cleared", src.count("st.query_params.clear()") >= 3)

print("\n[5] recovery deep link is wired")
check("recovery guard", 'params.get("type") == "recovery"' in src)
check("verify_recovery used", "verify_recovery(recovery_token)" in src)
check("set_password_with_client used", "set_password_with_client(st.session_state.recovery_client" in src)
check("stops before signed-out UI", src.index("if recovery_token") < src.index("if not st.session_state.user_email:\n    st.markdown"))

print("\n[6] demo deep link still works")
at2 = AppTest.from_file("/home/claude/Telos/app.py", default_timeout=60)
at2.query_params["demo"] = "1"
at2.run()
check("no exception in demo", not at2.exception, at2.exception)
check("demo identity kept", at2.session_state["tester_name"] == "__demo__", at2.session_state["tester_name"])
demo_body = " ".join(m.value for m in at2.markdown)
check("demo banner shown", "demo account" in demo_body.lower(), demo_body[:200])
check("sign-out button says Exit demo", any(b.label=="Exit demo" for b in at2.button), [b.label for b in at2.button])

print("\n[7] signed-in view for a real account")
at3 = AppTest.from_file("/home/claude/Telos/app.py", default_timeout=60)
at3.session_state["user_email"]="tester@example.com"
at3.session_state["tester_name"]="tester@example.com"
at3.run()
check("no exception", not at3.exception, at3.exception)
check("shows plan chip", any("plan" in m.value.lower() for m in at3.markdown))
check("page links present", len(at3.get("page_link")) >= 4, len(at3.get("page_link")))
check("Sign out not Exit demo", any(b.label=="Sign out" for b in at3.button), [b.label for b in at3.button])

print("\n[8] support + legal reachable from both states")
check("support email in signed-out footer", "SUPPORT_EMAIL" in src)
check("privacy link", "privacy.html" in src)
check("terms link", "terms.html" in src)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
