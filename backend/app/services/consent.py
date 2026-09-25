"""Age check and recorded consent.

Bulgaria sets the digital age of consent at 14 (GDPR Art. 8), and most of
this product's users are 11-14. Signing in used to show a line of small print
— "if you are under 14, ask a parent" — and record nothing, so there was no
way to show that consent had ever been given (Art. 7(1)).

Now every account answers once: 14 or older (and accepts the documents), or
under 14 with a parent or guardian confirming. The answer, the time and the
documents' version are stored on the user row and appended to the event log
as an audit trail. Bumping CONSENT_VERSION after a material change to the
privacy policy or terms asks everyone again.

This records consent; it does not *verify* that the person ticking the parent
box is a parent. Stronger verification (e.g. a confirmation email to the
parent) is a separate decision.
"""
from __future__ import annotations

from app.models.user import User

# The date of the privacy policy and terms the consent refers to.
CONSENT_VERSION = "2026-09-25"

AGE_GROUPS = ("14_plus", "under_14")


def consent_required(user: User) -> bool:
    return user.consent_version != CONSENT_VERSION
