"""
security_scan_score.py — Interactive security scan for src/score.py.

Runs Semgrep against score.py using the auto ruleset (covers OWASP Top 10,
injection, insecure deserialization, etc.) and prints a human-readable
score/summary.

Usage:
    python scripts/security_scan_score.py [--target src/score.py] [--min-score 80]

The script exits with:
    0  — score >= min_score (all good)
    1  — score < min_score  (security review required)

Intended to be run locally by a developer before pushing a change to score.py,
OR as part of the CI SAST step (non-interactive mode when --ci flag is passed).
"""

import argparse
import json
import subprocess
import sys


# ---------------------------------------------------------------------------
# Severity weights used to compute a security score out of 100
# ---------------------------------------------------------------------------
_SEVERITY_WEIGHT = {
    "ERROR": 20,   # Critical / high-severity findings
    "WARNING": 10,  # Medium-severity findings
    "INFO": 2,      # Low-severity / informational findings
}

_MAX_DEDUCTION = 100  # score starts at 100 and findings deduct points


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Semgrep security scan for score.py with scoring output."
    )
    p.add_argument(
        "--target",
        default="src/score.py",
        help="Path to the file to scan (default: src/score.py)",
    )
    p.add_argument(
        "--min-score",
        type=int,
        default=80,
        help="Minimum acceptable security score 0-100 (default: 80)",
    )
    p.add_argument(
        "--ci",
        action="store_true",
        help="Non-interactive mode — skip user prompts (used in GitHub Actions)",
    )
    return p.parse_args()


def run_semgrep(target: str) -> dict:
    """Run semgrep and return the parsed JSON output."""
    cmd = [
        "semgrep",
        "--config", "auto",
        "--json",
        target,
    ]
    print(f"\n[scan] Running: {' '.join(cmd)}\n")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("[error] semgrep not found. Install it with: pip install semgrep")
        sys.exit(1)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print("[error] Could not parse semgrep output:")
        print(result.stdout[:2000])
        sys.exit(1)


def compute_score(findings: list[dict]) -> tuple[int, dict]:
    """
    Compute a 0-100 security score based on finding severities.

    Returns
    -------
    score      : int   — final score (100 = no issues)
    breakdown  : dict  — count per severity level
    """
    breakdown: dict[str, int] = {"ERROR": 0, "WARNING": 0, "INFO": 0}

    deduction = 0
    for finding in findings:
        severity = finding.get("extra", {}).get("severity", "INFO").upper()
        breakdown[severity] = breakdown.get(severity, 0) + 1
        deduction += _SEVERITY_WEIGHT.get(severity, 2)

    score = max(0, _MAX_DEDUCTION - deduction)
    return score, breakdown


def print_findings(findings: list[dict]) -> None:
    if not findings:
        print("  ✅  No findings.")
        return

    for f in findings:
        loc = f.get("path", "?")
        line = f.get("start", {}).get("line", "?")
        severity = f.get("extra", {}).get("severity", "INFO")
        message = f.get("extra", {}).get("message", "No message")
        rule_id = f.get("check_id", "unknown-rule")

        severity_icon = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(severity, "⚪")
        print(f"  {severity_icon} [{severity}] {loc}:{line}")
        print(f"     Rule   : {rule_id}")
        print(f"     Message: {message}")
        print()


def print_report(target: str, score: int, breakdown: dict, findings: list[dict], min_score: int) -> None:
    print("=" * 60)
    print(f"  Semgrep Security Scan Report — {target}")
    print("=" * 60)
    print(f"\n  Security Score : {score} / 100")
    print(f"  Min Required   : {min_score} / 100")
    print(f"\n  Findings by severity:")
    print(f"    🔴 ERROR   (high)   : {breakdown.get('ERROR', 0)}")
    print(f"    🟡 WARNING (medium) : {breakdown.get('WARNING', 0)}")
    print(f"    🔵 INFO    (low)    : {breakdown.get('INFO', 0)}")
    print(f"    Total               : {len(findings)}\n")
    print("-" * 60)
    print("  Finding details:")
    print_findings(findings)
    print("=" * 60)

    if score >= min_score:
        print(f"\n  ✅  PASSED — score {score} >= {min_score}")
    else:
        print(f"\n  ❌  FAILED — score {score} < {min_score}  (review required)")

    print()


def interactive_review(findings: list[dict], ci: bool) -> None:
    """
    When not in CI mode, allow the user to inspect each finding interactively.
    """
    if ci or not findings:
        return

    print("\n[review] Interactive mode — press ENTER to step through each finding (or Ctrl+C to skip).\n")
    try:
        for idx, f in enumerate(findings, 1):
            loc = f.get("path", "?")
            line = f.get("start", {}).get("line", "?")
            severity = f.get("extra", {}).get("severity", "INFO")
            message = f.get("extra", {}).get("message", "No message")
            fix = f.get("extra", {}).get("fix", None)

            print(f"--- Finding {idx}/{len(findings)} ---")
            print(f"  Location : {loc}:{line}")
            print(f"  Severity : {severity}")
            print(f"  Message  : {message}")
            if fix:
                print(f"  Suggested fix: {fix}")
            input("  [Press ENTER to continue] ")
            print()
    except KeyboardInterrupt:
        print("\n[review] Skipped remaining findings.")


def main() -> None:
    args = parse_args()

    if not args.ci:
        print(f"\n🔍  Security scan starting for: {args.target}")
        print(f"    Minimum score required    : {args.min_score}/100")

    semgrep_output = run_semgrep(args.target)
    findings = semgrep_output.get("results", [])

    score, breakdown = compute_score(findings)
    print_report(args.target, score, breakdown, findings, args.min_score)
    interactive_review(findings, ci=args.ci)

    sys.exit(0 if score >= args.min_score else 1)


if __name__ == "__main__":
    main()
