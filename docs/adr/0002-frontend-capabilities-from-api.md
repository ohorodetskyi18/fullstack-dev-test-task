# ADR 0002 — Frontend learns capabilities from the API

- Status: accepted
- Date: 2026-11-09

## Context

The React frontend must hide links and buttons the user cannot use and show a clear "Access denied" page on direct navigation, instead of the template's silent redirect. It needs to know what the current user may do. The backend already owns the role → permission mapping (ADR 0001); the question is how the frontend gets that knowledge without the two drifting apart.

## Options

1. **Hardcoded role checks in the frontend** (`user.role === "admin"`). No API change, but it duplicates the mapping in TypeScript. When `ROLE_PERMISSIONS` changes, the UI silently disagrees with the API, and adding a role means finding every check.
2. **Permissions list in `GET /users/me`.** The backend computes `permissions` for the current user and returns them with the profile the frontend already loads on every page.
3. **Separate `GET /permissions` endpoint.** Same data as option 2, but an extra request, an extra cache entry to keep in sync with the user, and a second loading state.

## Decision

Option 2. `GET /users/me` returns `UserMePublic`, which adds `permissions: list[Permission]` derived from the role (a Pydantic computed field, so it cannot disagree with the role). The generated client types `Permission` as a string union. `usePermissions()` exposes `can(permission)`; the sidebar and settings tabs declare an optional `permission` and are filtered with it, and `<RequirePermission>` wraps protected pages, showing a loading state, then the page, `<AccessDenied>`, or a load error if `/users/me` fails (a failed load is not treated as "no permission"). The frontend contains no role → permission mapping; role names appear only in display code: labels (`Record<Role, string>`, so a new backend role breaks the build until it has a label), the role badge and the role select.

401 and 403 are handled differently: 401 logs the user out; 403 shows a toast, keeps the session and refetches `/users/me`, so the UI catches up if an admin changed the user's role.

## Consequences

- One source of truth: changing `ROLE_PERMISSIONS` changes the UI with no frontend edit.
- No extra request; permissions arrive with the user the app already fetches.
- Permissions in the UI can be stale until `/users/me` is refetched (on a 403, after profile changes or on reload). This only affects what is shown — the API enforces every action.
- The UI checks permissions, not roles, so it reacts correctly to roles it has never heard of.
