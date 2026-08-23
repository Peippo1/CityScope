# CityScope dependency security triage

## Executive summary

The GitHub alert count of 25 represents 25 advisories attached to two npm dependency nodes, not 25 separate libraries. The actionable issue is the direct dependency `next@14.2.35`, which also brings `postcss@8.4.31`. npm reports two vulnerable package nodes, both with high-severity advisories in their dependency trees. No critical npm findings were reported and no credentials were found in tracked files.

Remediation applied in the follow-up change: Next.js was upgraded to patched `15.5.21`, with explicit patched `postcss@8.5.23` and `sharp@0.35.3` overrides. The lockfile was regenerated, npm reports zero vulnerabilities, the full Python test suite passes, and the Next production-start smoke returns HTTP 200. Do not revert to the old Next 14 line.

## Findings

### DEP-001 — vulnerable Next.js runtime — high — resolved

- Package: direct `next`, locked at `14.2.35` in `apps/web/package-lock.json`.
- GitHub alerts: 1–5, 7–22, plus related medium/low advisories.
- Main impact classes: server-side request forgery, React Server Component/server-action denial of service, request deserialization issues, cache confusion/poisoning, and internal endpoint disclosure.
- Reachability: the current app has no middleware, rewrites, server actions, or `next/image` usage, which reduces exposure for several advisories. It is still a self-hosted Next application using the App Router, so the Server Component/DoS class should be treated as relevant until patched.
- Fix applied: upgraded to `next@15.5.21`; the Next production build and production-start smoke pass with the existing React 18 application.
- Verification: `npm audit --audit-level=high` reports zero vulnerabilities.

### DEP-002 — vulnerable PostCSS transitive dependency — high — resolved with DEP-001

- Package: transitive `postcss`, locked at `8.4.31`, required by Next.js.
- GitHub alerts: 6, 23–25.
- Main impact classes: CSS-string XSS and attacker-controlled source-map path traversal/arbitrary `.map` file disclosure.
- Reachability: PostCSS is used in the build pipeline rather than as a direct application request handler, so exploitation depends on attacker-controlled CSS/build inputs. It remains vulnerable in the shipped dependency graph.
- Fix applied: the Next 15 lockfile is explicitly overridden to patched `postcss@8.5.23` and `sharp@0.35.3`; npm audit reports zero vulnerabilities.

### DEP-003 — Python dependency audit tooling — resolved

- `pip-audit>=2.7,<3` is now declared in the development dependencies.
- The environment uses patched `pip` and `pytest` versions (`pip 26.2.1`, `pytest 9.1.1`).
- `.venv/bin/pip-audit --skip-editable` reports no known vulnerabilities. The local editable `cityscope` distribution is skipped because it is not published on PyPI.
- A committed Python lockfile is still recommended before production deployment.

## Credential and repository checks

- `.env.local` is ignored and not tracked.
- Tracked example files contain empty credential placeholders only.
- No API-key-like or secret-token patterns were found in tracked/source files.
- Server credentials remain separate from `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`, which is intentionally browser-visible.

## Recommended remediation order

1. Run a manual production-start smoke check before deployment.
2. Confirm the Routes/Gemini/Maps server credentials are still read only by backend code.
3. Add a committed Python lockfile before public deployment.
4. Recheck GitHub Dependabot alerts after pushing the lockfile and Next upgrade.
