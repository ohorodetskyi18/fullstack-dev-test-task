import { Link } from "@tanstack/react-router"
import { ShieldX } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const AccessDenied = () => {
  return (
    <div
      className="flex justify-center py-12"
      data-testid="access-denied"
      role="alert"
    >
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <ShieldX className="mx-auto mb-2 size-10 text-muted-foreground" />
          <CardTitle className="text-xl">Access denied</CardTitle>
          <CardDescription>
            You don't have permission to view this page. Contact an
            administrator if you think this is a mistake.
          </CardDescription>
        </CardHeader>
        <CardFooter className="justify-center">
          <Button asChild>
            <Link to="/">Back to dashboard</Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}

export default AccessDenied
