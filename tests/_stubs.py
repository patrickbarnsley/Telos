"""Stand-ins for third-party SDKs, for suites that test plumbing not integration.

core.auth imports the Supabase SDK and core.ai_engine imports anthropic, both at
module scope, so importing either drags in the whole vendor tree. The suites
that use this file never call out to anything: they test how our own pieces fit
together. Stubbing keeps them runnable on a laptop with no Telos credentials and
no build toolchain, which is the difference between a suite that gets run and
one that does not.

Integration behaviour is covered elsewhere, against real services.
"""
import sys
import types


def install() -> None:
    if "supabase" not in sys.modules:
        m = types.ModuleType("supabase")
        m.create_client = lambda *a, **k: None
        m.Client = object
        sys.modules["supabase"] = m

    if "anthropic" not in sys.modules:
        m = types.ModuleType("anthropic")

        class _Anthropic:
            def __init__(self, *a, **k): pass

        m.Anthropic = _Anthropic
        m.APIError = type("APIError", (Exception,), {})
        m.APIStatusError = type("APIStatusError", (Exception,), {})
        m.RateLimitError = type("RateLimitError", (Exception,), {})
        m.APIConnectionError = type("APIConnectionError", (Exception,), {})
        sys.modules["anthropic"] = m

    if "stripe" not in sys.modules:
        m = types.ModuleType("stripe")
        m.api_key = None
        sys.modules["stripe"] = m
