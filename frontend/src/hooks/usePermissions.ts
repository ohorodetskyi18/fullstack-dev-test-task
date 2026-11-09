import type { Permission } from "@/client"
import useAuth from "./useAuth"

/**
 * What the current user may do, as computed by the backend (GET /users/me).
 *
 * The frontend never maps roles to permissions: it only consumes this list.
 * Hiding UI with `can()` is UX only; the API enforces every check.
 */
const usePermissions = () => {
  const { user, isLoading } = useAuth()
  const permissions = user?.permissions ?? []

  const can = (permission: Permission) => permissions.includes(permission)

  return { can, permissions, isLoading }
}

export default usePermissions
