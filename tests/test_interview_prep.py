"""Interview prep: quotas, ownership, persistence, and the honesty constraint.

The prompt assertions are the ones worth reading twice. Interview prep is an
advice product, and the single way it can genuinely hurt someone is by coaching
them to overstate their experience and getting them caught out in the room. That
rule lives in a module constant and is asserted here on the prompt text, so a
later edit that reworded the prompt could not quietly drop it.

The model itself is never called. A live model is not a dependable oracle for
"did it follow the rule", so what is tested is the rule being present in the
prompt and the validator refusing output that contradicts the stored score.
"""
import os, sys, json, pathlib

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/telos_test")
os.environ["OWNER_EMAILS"] = "patrickbarnsley@gmail.com"
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-not-used")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import database as db
from core import plans
from core import ai_engine
from core.models import Job, Profile

FAIL = []
def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        FAIL.append(name)

db.init_db()

A, B = "prep-a@example.com", "prep-b@example.com"
for _u in (A, B):
    try:
        db.purge_user_data(_u)
    except Exception:
        pass

# ---------- schema ----------
conn = db.get_connection(); cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = {r[0] for r in cur.fetchall()}
cur.close(); conn.close()
check("init_db creates interview_preps", "interview_preps" in tables, str(sorted(tables)))
check("interview_preps is erased on account deletion", "interview_preps" in db.USER_TABLES,
      str(db.USER_TABLES))

# ---------- fixtures ----------
db.save_profile(Profile(resume_text="Four years using Jira daily across three programmes at Cobalt. "
                                    "Built the sprint boards and the reporting views.",
                        target_role="Delivery Manager"), A)
job_a = db.create_job(Job(company="Acme", role="Delivery Manager", status="applied"), A)
db.save_match_result(
    62, "Strong delivery history, no administration experience.",
    ["Delivery management experience", "Stakeholder reporting"],
    ["Jira administration and workflow configuration"],
    [], ["Name the boards you configured"],
    "Jira administration and workflow configuration required. Five years delivery.",
    A, job_id=job_a, company="Acme", role="Delivery Manager",
    resume_snapshot="Four years using Jira daily across three programmes at Cobalt.",
)
match_a = db.get_match_results(job_a, A)[0]["id"]

job_b = db.create_job(Job(company="Globex", role="PM", status="applied"), B)
db.save_match_result(70, "s", ["m"], ["x"], [], [], "jd", B, job_id=job_b,
                     company="Globex", role="PM", resume_snapshot="B resume")
match_b = db.get_match_results(job_b, B)[0]["id"]

STORED = db.get_match_result(match_a, A)

# ---------- the prompt carries the rules that cannot be dropped ----------
print("\n[1] the prompt says the things it must say")
prompt = ai_engine._interview_prep_prompt(STORED, STORED["resume_snapshot"], "Delivery Manager")

check("prompt contains the honesty constraint verbatim",
      ai_engine.INTERVIEW_PREP_HONESTY in prompt)
check("honesty constraint forbids overstating in plain words",
      "overstate" in ai_engine.INTERVIEW_PREP_HONESTY.lower()
      and "never" in ai_engine.INTERVIEW_PREP_HONESTY.lower(),
      ai_engine.INTERVIEW_PREP_HONESTY[:120])
check("prompt requires every question to cite the posting",
      ai_engine.INTERVIEW_PREP_TRACEABILITY in prompt)
check("traceability rule names the quoted field",
      "from_requirement" in ai_engine.INTERVIEW_PREP_TRACEABILITY)
check("prompt requires strength to come from the stored match result",
      ai_engine.INTERVIEW_PREP_STRENGTH_RULE in prompt)
check("strength rule forbids contradicting the stored lists",
      "missing" in ai_engine.INTERVIEW_PREP_STRENGTH_RULE.lower()
      and "matched" in ai_engine.INTERVIEW_PREP_STRENGTH_RULE.lower())

check("prompt carries the stored score rather than re-deriving it", "62" in prompt)
check("prompt carries the stored matched requirements",
      "Stakeholder reporting" in prompt)
check("prompt carries the stored missing requirements",
      "Jira administration and workflow configuration" in prompt)
check("prompt fences the job posting as untrusted third-party text",
      "BEGIN JOB POSTING" in prompt and "END JOB POSTING" in prompt, prompt[:200])
check("prompt fences the resume", "BEGIN CANDIDATE RESUME" in prompt)
check("the real instruction comes after the untrusted posting",
      prompt.index("YOUR INSTRUCTIONS") > prompt.index("END JOB POSTING"))
check("prompt asks for 8 to 12 questions and forbids padding",
      "8 to 12" in prompt and "pad" in prompt.lower())

# ---------- the validator refuses output that contradicts the score ----------
print("\n[2] the validator will not let a prep disagree with the score")
MATCHED = ["Delivery management experience", "Stakeholder reporting"]
MISSING = ["Jira administration and workflow configuration"]

def entry(q="Walk me through administering Jira.",
          src="Jira administration and workflow configuration",
          strength="weak", ans="Your resume shows use, not administration."):
    return {"question": q, "from_requirement": src, "strength": strength,
            "how_your_resume_answers": ans}

good = ai_engine.validate_interview_prep({"questions": [entry()]}, MATCHED, MISSING)
check("a coherent prep passes", good["questions"][0]["strength"] == "weak")

def rejects(name, payload, matched=MATCHED, missing=MISSING):
    try:
        ai_engine.validate_interview_prep(payload, matched, missing)
        check(name, False, "accepted")
    except ValueError as e:
        check(name, True)
        check(name + " reads like a sentence",
              "Traceback" not in str(e) and len(str(e).split()) > 3, str(e))

rejects("a missing requirement rated strong is rejected",
        {"questions": [entry(strength="strong")]})
rejects("a matched requirement rated weak is rejected",
        {"questions": [entry(src="Stakeholder reporting", strength="weak")]})
rejects("an unrecognised strength is rejected",
        {"questions": [entry(strength="excellent")]})
rejects("a question with no posting source is rejected",
        {"questions": [entry(src="  ")]})
rejects("a question with no answer text is rejected",
        {"questions": [entry(ans="")]})
rejects("an empty question list is rejected", {"questions": []})
rejects("a non-list of questions is rejected", {"questions": "ten questions"})
rejects("a non-object response is rejected", ["not", "a", "prep"])

# Ordering is done in code, not left to the model, because the ordering is the
# whole point of the artifact.
mixed = ai_engine.validate_interview_prep({"questions": [
    entry(q="strong one", src="Stakeholder reporting", strength="strong"),
    entry(q="weak one", strength="weak"),
    entry(q="partial one", src="Jira administration and workflow configuration", strength="partial"),
]}, MATCHED, MISSING)
check("questions are ordered weakest first",
      [q["strength"] for q in mixed["questions"]] == ["weak", "partial", "strong"],
      str([q["strength"] for q in mixed["questions"]]))
check("validator always returns note and injection_attempt keys",
      "note" in mixed and "injection_attempt" in mixed)

# ---------- ownership ----------
print("\n[3] a prep can only be built from your own score")
check("another account's match result is not readable",
      db.get_match_result(match_b, A) is None)
check("your own match result is readable", db.get_match_result(match_a, A) is not None)

db.save_interview_prep(A, match_a, {"questions": [entry()], "note": "", "injection_attempt": ""},
                       job_id=job_a, company="Acme", role="Delivery Manager")
check("owner reads their stored prep", db.get_interview_prep(match_a, A) is not None)
check("another account cannot read that prep", db.get_interview_prep(match_a, B) is None)
db.delete_interview_prep(match_a, B)
check("another account cannot delete that prep", db.get_interview_prep(match_a, A) is not None)

# ---------- reopening is free ----------
print("\n[4] reopening a saved prep does not spend quota")
before = plans.used_this_month(A, plans.INTERVIEW_PREP)
reopened = db.get_interview_prep(match_a, A)
db.get_match_page_data(A)
after = plans.used_this_month(A, plans.INTERVIEW_PREP)
check("reopening returns the stored prep", reopened and reopened["prep"]["questions"])
check("reopening consumes no quota", before == after, f"{before} -> {after}")
check("the page bundle carries stored preps in one query",
      match_a in db.get_match_page_data(A)["interview_preps"])

# ---------- quotas ----------
print("\n[5] quotas are 1 on free and 20 on Pro")
plans.set_plan(A, "free")
check("free plan allows one prep", plans.limit_for(A, plans.INTERVIEW_PREP) == 1,
      plans.limit_for(A, plans.INTERVIEW_PREP))
allowed, used, limit = plans.check_quota(A, plans.INTERVIEW_PREP)
check("free plan starts allowed", allowed and used == 0 and limit == 1, f"{allowed} {used} {limit}")
plans.record_usage(A, plans.INTERVIEW_PREP)
check("free plan blocks at one", plans.check_quota(A, plans.INTERVIEW_PREP)[0] is False)

plans.set_plan(A, "pro")
check("pro plan allows twenty", plans.limit_for(A, plans.INTERVIEW_PREP) == 20,
      plans.limit_for(A, plans.INTERVIEW_PREP))
check("pro plan is allowed after the free cap", plans.check_quota(A, plans.INTERVIEW_PREP)[0] is True)
for _ in range(19):
    plans.record_usage(A, plans.INTERVIEW_PREP)
allowed, used, limit = plans.check_quota(A, plans.INTERVIEW_PREP)
check("pro plan blocks at twenty", (not allowed) and used == 20, f"used={used}")
check("interview prep quota is separate from match quota",
      plans.check_quota(A, plans.MATCH)[0] is True)

# ---------- demo ----------
print("\n[6] the demo account cannot generate one")
check("demo has a zero prep quota",
      plans.limit_for(plans.DEMO_TESTER, plans.INTERVIEW_PREP) == 0)
check("demo is refused by check_quota",
      plans.check_quota(plans.DEMO_TESTER, plans.INTERVIEW_PREP)[0] is False)
db.save_interview_prep(plans.DEMO_TESTER, 1, {"questions": [entry()]})
check("demo writes are a no-op even if the gate is bypassed",
      db.get_interview_prep(1, plans.DEMO_TESTER) is None)

# ---------- deletion ----------
print("\n[7] account deletion erases stored preps")
plans.set_plan(A, "pro")
db.save_interview_prep(A, match_a, {"questions": [entry()], "note": "", "injection_attempt": ""})
check("prep exists before deletion", db.get_interview_prep(match_a, A) is not None)
removed = db.purge_user_data(A)
check("purge reports the prep rows it removed", removed.get("interview_preps", 0) >= 1, str(removed))
check("prep is gone after deletion", db.get_interview_prep(match_a, A) is None)
check("purge did not touch the other account", db.get_match_result(match_b, B) is not None)

# Deleting the score deletes the prep built from it, so nobody can reopen advice
# about a result they removed.
db.save_interview_prep(B, match_b, {"questions": [entry()], "note": "", "injection_attempt": ""})
check("prep saved against the other account's score", db.get_interview_prep(match_b, B) is not None)
db.delete_match_result(match_b, B)
check("deleting a match result deletes its prep", db.get_interview_prep(match_b, B) is None)

# ---------- routing and cost ----------
print("\n[8] prep runs on the reasoning tier and is priced")
from core import spend
check("interview_prep routes to sonnet",
      ai_engine.model_for("interview_prep") == "claude-sonnet-4-5",
      ai_engine.model_for("interview_prep"))
check("the prep model is priced in the ledger",
      spend._price_for(ai_engine.model_for("interview_prep")) is not spend.DEFAULT_PRICE)
check("interview_prep goes through the billing choke point",
      "action=\"interview_prep\"" in (ROOT / "core" / "ai_engine.py").read_text(encoding="utf-8"))

db.purge_user_data(B)

print()
print("=" * 46)
print("ALL INTERVIEW PREP TESTS PASSED" if not FAIL else "FAILURES: " + ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
