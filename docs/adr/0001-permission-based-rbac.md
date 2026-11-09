# ADR 0001 — Permission-based RBAC with roles mapped in code

- Status: accepted
- Date: 2026-11-09

## Context

The template had a single `is_superuser` flag, checked inline in routes (`if current_user.is_superuser`) and in a `get_current_active_superuser` dependency. We need three roles (admin, manager, member) enforced consistently, no privilege escalation, and a model a teammate can understand in five minutes. Adding a role should not mean touching many files.

## Options

1. **More boolean flags** (`is_manager`, ...). Simple, but flags combine into ambiguous states, each new role is a migration, and checks stay scattered.
2. **Role checks in routes** (`if user.role in {"admin", "manager"}`). Readable at first, but the meaning of a role is spread across every endpoint; adding a role means editing all of them.
3. **Role → permission map in code.** Routes check permissions (`users:read`); one dictionary says which role grants which permissions.
4. **Policy engine** (Casbin, OPA). Powerful (ABAC, per-resource rules), but adds a dependency, a policy language and a runtime component — far more than three static roles need.

For storage: a **native Postgres enum** gives DB-level validation, but every new role needs an `ALTER TYPE` migration; a **VARCHAR** validated by a Python enum keeps adding a role code-only.

## Decision

Option 3. `app/core/permissions.py` holds `Role`, `Permission`, `ROLE_PERMISSIONS` and `has_permission()` — the only place roles map to permissions. Routes declare `Depends(require_permission(Permission.X))`; object-level rules call `ensure_permission()`. Both raise the same 403 and log to `app.authz`. `user.role` is a `VARCHAR(20)` mapped to `Role` with `sa.Enum(native_enum=False)`, so values are validated on input and on load. `is_superuser` is removed so there is one source of truth. The JWT carries only the user id; the role is read from the database on every request.

## Consequences

- Adding a role = two edits in one backend file, no migration. Outside the authorization logic it also needs a display label in the frontend, its expected permissions in the RBAC tests and a column in the README matrix.
- Every protected endpoint names its permission, which makes reviews and the README matrix easy to keep in sync; the table-driven test denies unknown roles by default.
- Role changes take effect immediately, at the cost of the user lookup the template already did per request.
- Permissions are coarse: there are no per-resource ACLs or attribute rules. If those become necessary, a policy engine can replace `has_permission()` without changing the route-level API.
- The downgrade migration cannot distinguish manager from member.
