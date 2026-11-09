# Notes — Task 1 (RBAC)

## How this was built

The work was done with an AI coding agent (Claude Code): I wrote the requirements and made the design decisions (permission model, matrix, status codes, process), reviewed each phase and verified the results. The agent wrote most of the code, tests and docs. The session transcript is in [`ai-conversations/`](ai-conversations/). The repository was recreated at the root partway through the session (template moved from `task1-rbac/`, commits re-applied with `git am`), so commit hashes and `task1-rbac/` paths in the first part of the transcript differ from this repository.

## Time spent

About 2 hours of implementation with the agent, then about 1 hour of review with follow-up fixes, plus the planning beforehand. The official timebox is about one hour; the extra time went into tests, the e2e updates, documentation and the review fixes.

## What was cut and why

- **New Playwright tests per role** (manager read-only admin page, member Access Denied on `/metrics`). The authorization logic is covered by backend tests; the existing e2e tests that depended on `is_superuser` (in `admin.spec.ts` and `user-settings.spec.ts`) were updated and the full e2e suite passes locally (62/62; one flaky failure on the first run, then five green runs in a row).
- **Audit table for denied attempts.** Denials are logged (`app.authz` logger, `WARNING`, with user id, role, permission, method and path), not persisted.
- **Per-resource permissions / ACLs.** The model is role-wide by design (see ADR 0001).

## Known limitations

- **Coarse permissions.** No ACLs, no attribute-based rules (e.g. "manager of team X"). `items:manage_any` is all-or-nothing.
- **`settings:manage` is backend-only.** The template has no global settings page, so the permission guards only `POST /utils/test-email/` and has no UI.
- **Frontend permissions can be stale** until `/users/me` is refetched (on reload, on any 403, after profile updates). This affects only what the UI shows; the API enforces every request.
- **Unknown fields are ignored, not rejected.** `PATCH /users/me` or signup with `{"role": "admin"}` returns 200 and leaves the role unchanged (template behaviour of SQLModel schemas). Returning 422 with `extra="forbid"` would be more explicit.
- **Template behaviour kept as-is:** JWTs live 8 days and cannot be revoked; logging in as an inactive user returns 400 "Inactive user".
- **"At least one admin" is not race-proof.** Admins cannot demote or deactivate themselves (409), but two admins demoting each other at the same moment can both succeed. A full guarantee would need a locked count of remaining admins in the transaction. The rule is also strict: an admin cannot step down even when other admins exist (another admin has to do it).
- **Recovery-preview header:** `POST /password-recovery-html-content/{email}` sends the email subject as an HTTP header; a non-Latin-1 `PROJECT_NAME` would make it fail (template behaviour).
- **Migration downgrade is lossy:** managers and members both become regular users, because `is_superuser` cannot represent them.
- **Tests wipe the dev database's users** (template fixture behaviour). Re-run `uv run python -m app.seed_demo_users` afterwards.
- `scripts/test.sh` needs `uv run` (it calls `coverage` from the virtualenv).

## Template issues fixed along the way

- `POST /password-recovery-html-content/{email}` returned a `subject:` header (invalid name) and crashed for everyone; found by the new matrix test, fixed in a separate commit.
- `get_current_user` returned 403 for invalid tokens, 404 for a deleted user's token and 400 for an inactive user; all three are now 401 with `WWW-Authenticate: Bearer`, so the frontend logs such sessions out instead of showing a broken page.
- The frontend logged users out on any 403; now only on 401.
- The settings page computed `tabsConfig.slice(0, 3)` for superusers, which still showed the Danger zone tab; tabs are now filtered by `account:delete_own`.

## With more time

- Playwright tests per role (sidebar items, read-only admin table, Access Denied, 403 toast without logout).
- Persist authorization events in an audit table and show them to admins.
- `extra="forbid"` on self-service schemas (422 on unknown fields such as `role`).
- Route-level `beforeLoad` permission checks using the cached `/users/me`, to avoid rendering a loading state first.
- Token revocation / shorter token lifetime with refresh tokens.
- CI job running backend tests, lint and e2e on every push.
