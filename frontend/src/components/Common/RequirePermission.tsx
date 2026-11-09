import type { ReactNode } from "react"

import type { Permission } from "@/client"
import { Skeleton } from "@/components/ui/skeleton"
import usePermissions from "@/hooks/usePermissions"
import AccessDenied from "./AccessDenied"

interface RequirePermissionProps {
  permission: Permission
  children: ReactNode
}

const RequirePermission = ({
  permission,
  children,
}: RequirePermissionProps) => {
  const { can, isLoading, failedToLoad } = usePermissions()

  if (isLoading) {
    return <Skeleton className="h-32 w-full" data-testid="permission-loading" />
  }
  if (failedToLoad) {
    return (
      <p className="py-12 text-center text-muted-foreground" role="alert">
        Could not load your permissions. Please reload the page.
      </p>
    )
  }
  if (!can(permission)) {
    return <AccessDenied />
  }
  return children
}

export default RequirePermission
