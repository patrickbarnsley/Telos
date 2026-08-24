"""One place that turns exceptions into sentences a person can act on.

Two rules drive this module.

First, a stack trace is not an error message. "KeyError: 'overall_score'" tells
the user nothing they can do and tells an attacker something about the inside
of the app. Every failure the user can reach should name what broke and what to
try next.

Second, failures are not all the same. A rate limit is worth retrying in a
minute. A malformed resume is worth re-uploading. A spend cap will not clear
until next month. Collapsing all of them into "Something went wrong" trains
people to give up.
"""

import json
import logging

log = logging.getLogger("telos")

_GENERIC = (
    "Something went wrong on our side. Nothing was saved, so it is safe to try again. "
    "If it keeps happening, email {support} and tell us what you were doing."
)


def friendly(exc: Exception, doing: str = "") -> str:
    """Translate an exception into a message worth showing a user."""
    from core.plans import SUPPORT_EMAIL
    name = type(exc).__name__
    text = str(exc)

    # The monthly AI ceiling. Its message is already written for a person.
    if name == "SpendCapReached":
        return text

    # Quota refusals raised by the page layer.
    if "limit reached" in text.lower():
        return text

    # Anthropic SDK failures, matched by class name so this module does not
    # need to import the SDK just to format a string.
    if name in ("RateLimitError", "APIStatusError") and "429" in text:
        return ("The AI service is busy right now. Wait about a minute and try again. "
                "Nothing was lost.")
    if name == "RateLimitError":
        return "The AI service is busy right now. Wait about a minute and try again."
    if name in ("APIConnectionError", "APITimeoutError", "ConnectionError", "Timeout"):
        return ("Could not reach the AI service. This is usually a network blip. "
                "Try again in a moment.")
    if name == "AuthenticationError":
        log.error("Anthropic authentication failed: %s", text)
        return (f"AI features are temporarily unavailable. This is on us, not you. "
                f"Email {SUPPORT_EMAIL} if it lasts more than a few minutes.")
    if name in ("BadRequestError", "APIStatusError"):
        return ("The AI service rejected that request. It is usually the input being too "
                "long. Try trimming the text and running it again.")
    if name == "OverloadedError":
        return "The AI service is at capacity. Give it a minute and try again."

    # A model reply that did not parse. Retrying genuinely helps here.
    if isinstance(exc, (json.JSONDecodeError, ValueError)) and doing:
        if isinstance(exc, json.JSONDecodeError) or "JSON" in text:
            return ("The AI returned a response we could not read. Run it again. "
                    "This usually clears on the second attempt.")
    if isinstance(exc, (KeyError, TypeError, IndexError)):
        return ("The AI returned an incomplete result. Run it again. If it happens twice "
                "in a row, the input is probably the problem.")

    # A ValueError we raised ourselves is already a written message.
    if isinstance(exc, ValueError) and text and not text.startswith("<"):
        return text

    # Database trouble.
    if name.startswith("Operational") or "psycopg2" in str(type(exc)):
        log.error("Database error during %s: %s", doing or "an operation", text)
        return (f"We could not reach the database. Your work was not saved. Try again in a "
                f"moment, and email {SUPPORT_EMAIL} if it persists.")

    log.exception("Unhandled error during %s", doing or "an operation")
    return _GENERIC.format(support=SUPPORT_EMAIL)


def show(exc: Exception, doing: str = ""):
    """Render a failure to the user in the way that failure deserves."""
    import streamlit as st
    message = friendly(exc, doing)
    if type(exc).__name__ == "SpendCapReached":
        st.warning(message)
    elif "busy" in message or "network blip" in message or "capacity" in message:
        st.warning(message)
    else:
        st.error(message)


class ai_action:
    """Context manager around one AI-backed action.

        with ai_action("scoring your match") as run:
            result = score_match(...)
        if run.ok:
            ...

    Swallows the exception, shows the right message, and records nothing on
    failure so a failed call never counts against the user's quota.
    """

    def __init__(self, doing: str):
        self.doing = doing
        self.ok = True
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            return False
        self.ok = False
        self.error = exc
        show(exc, self.doing)
        return True  # handled
