import type { Permission } from "@/client"
import useCurrentUser from "./useCurrentUser"

/**
 * What the current user may do, as computed by the backend (GET /users/me).
 *
 * The frontend never maps roles to permissions: it only consumes this list.
 * Hiding UI with `can()` is UX only; the API enforces every check.
 */
const usePermissions = () => {
  const { data: user, isLoading, isError } = useCurrentUser()
  const permissions = user?.permissions ?? []

  const can = (permission: Permission) => permissions.includes(permission)

  // A failed load is not a "no": callers must not show "Access denied" for it.
  return { can, permissions, isLoading, failedToLoad: isError && !user }
}

export default usePermissions
