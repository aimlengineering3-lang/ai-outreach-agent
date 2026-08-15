"""
Validates email addresses using two FREE, non-paid checks:
1. Syntax validation (regex)
2. MX record lookup (does the domain even accept mail?)

This is NOT a delivery guarantee — it filters obvious garbage
(typos, fake domains) before we waste a send attempt or damage
sender reputation on a hard bounce.
"""

import re
from dataclasses import dataclass

import dns.resolver


EMAIL_SYNTAX_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


@dataclass
class EmailValidationResult:
    email: str
    status: str  # "valid" / "invalid" / "unknown"
    reason: str


def _has_valid_syntax(email: str) -> bool:
    return bool(EMAIL_SYNTAX_PATTERN.match(email))


def _domain_has_mx_record(domain: str, timeout: float = 5.0) -> bool:
    """
    Checks whether the domain has any MX (Mail Exchange) DNS record —
    i.e. whether mail servers exist to receive email for this domain at all.
    An absent MX record means the domain almost certainly cannot receive
    email, regardless of how correct the syntax looks.
    """
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        return len(answers) > 0
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.resolver.LifetimeTimeout,
    ):
        return False


def validate_email(email: str) -> EmailValidationResult:
    email = email.strip()

    if not _has_valid_syntax(email):
        return EmailValidationResult(email=email, status="invalid", reason="bad_syntax")

    domain = email.split("@")[1]

    try:
        mx_exists = _domain_has_mx_record(domain)
    except Exception:
        # Any unexpected DNS-layer failure — don't claim invalid, we
        # genuinely don't know.
        return EmailValidationResult(email=email, status="unknown", reason="dns_check_failed")

    if mx_exists:
        return EmailValidationResult(email=email, status="valid", reason="syntax_ok_mx_found")
    else:
        return EmailValidationResult(email=email, status="invalid", reason="no_mx_record")


if __name__ == "__main__":
    print(validate_email("test@gmail.com"))          # Expect: valid
    print(validate_email("not-an-email"))              # Expect: invalid, bad_syntax
    print(validate_email("test@this-domain-does-not-exist-xyz123.com"))  # Expect: invalid, no_mx_record