import type { ReactNode } from "react"

import type { Permission } from "@/client"
import { Skeleton } from "@/components/ui/skeleton"
import usePermissions from "@/hooks/usePermissions"
import AccessDenied from "./AccessDenied"

interface RequirePermissionProps {
  permission: Permission
  children: ReactNode
}

/** Renders children only if the current user has `permission`. */
const RequirePermission = ({
  permission,
  children,
}: RequirePermissionProps) => {
  const { can, isLoading } = usePermissions()

  if (isLoading) {
    return <Skeleton className="h-32 w-full" data-testid="permission-loading" />
  }
  if (!can(permission)) {
    return <AccessDenied />
  }
  return children
}

export default RequirePermission
