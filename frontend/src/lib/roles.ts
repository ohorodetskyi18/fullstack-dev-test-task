import type { Role } from "@/client"

// Display labels only. Record<Role, ...> makes the build fail when the
// backend adds a role (after client regeneration) until a label exists here.
// Permissions are never derived from roles in the frontend.
const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  manager: "Manager",
  member: "Member",
}

export const ROLE_OPTIONS = Object.keys(ROLE_LABELS) as Role[]

export const roleLabel = (role: Role) => ROLE_LABELS[role]
