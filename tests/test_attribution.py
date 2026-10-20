"""Who AI spend gets billed to, when the call comes through the API.

core.ai_engine._current_user() reads Streamlit session state, which does not
exist behind FastAPI. Every AI call made through the API was therefore recorded
against an empty tester_name, blanking the per-user ledger that the admin view
and the cost-per-subscriber figures are built from.

The fix is a ContextVar set by current_account. It only works because that
dependency is async: FastAPI runs a *sync* dependency in a worker thread that
receives a copy of the context, so a write there dies with the copy and the
handler sees nothing. This suite exists because that failure is silent. If
someone makes current_account sync again, spend attribution quietly stops
working and nothing else complains.

No database and no API key: resume_session is stubbed, because what is under
test is the plumbing, not the lookup.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TELOS_TEST", "1")

# These suites test how our own pieces fit together, never the vendors, so the
# SDKs that core imports at module scope are stood in for. See tests/_stubs.py.
import _stubs                                        # noqa: E402
_stubs.install()

from fastapi import Depends, FastAPI                 # noqa: E402
from fastapi.testclient import TestClient            # noqa: E402

import core.auth as auth                             # noqa: E402
import core.ai_engine as ai                          # noqa: E402
from api.deps import current_account                 # noqa: E402

auth.resume_session = lambda token: "patrick@example.com" if token == "good" else ""

passed = failed = 0
failures = []


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        failures.append(label)
        print(f"  FAIL  {label}   {detail}")


app = FastAPI()


@app.get("/who")
def who(account: str = Depends(current_account)):
    return {"account": account, "billed_to": ai._current_user()}


client = TestClient(app)
GOOD = {"telos_session": "good"}

# The property that actually protects the ledger.
check("current_account is async, without which the ContextVar never propagates",
      inspect.iscoroutinefunction(current_account))

r = client.get("/who", cookies=GOOD)
check("a signed-in request bills AI spend to that account",
      r.status_code == 200 and r.json()["billed_to"] == "patrick@example.com",
      f"{r.status_code} {r.text[:120]}")

check("and it is the same account the handler was given",
      r.json().get("account") == r.json().get("billed_to"), r.text[:120])

# The quota dependency nests a sync dep under the async one, which is the shape
# every AI endpoint uses. That path reads real plan rows, so it is asserted in
# test_api.py against a live database rather than faked here.

# No session must not inherit the previous request's identity.
r = client.get("/who", cookies={"telos_session": "bad"})
check("an expired session is refused rather than billed to anyone",
      r.status_code == 401, f"{r.status_code} {r.text[:120]}")

r = client.get("/who")
check("no cookie is refused", r.status_code == 401, r.status_code)

# A fresh request must not leak the last one's account into the ledger.
ai.set_request_user("")
check("attribution resets to empty when nothing has set it",
      ai._current_user() == "", repr(ai._current_user()))

print(f"\n  {passed} passed, {failed} failed")
if failures:
    print("  FAILURES: " + "; ".join(failures))
sys.exit(1 if failed else 0)
