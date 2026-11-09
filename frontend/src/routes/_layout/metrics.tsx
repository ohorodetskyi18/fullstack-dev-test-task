import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { MetricsService } from "@/client"
import RequirePermission from "@/components/Common/RequirePermission"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ROLE_OPTIONS, roleLabel } from "@/lib/roles"

export const Route = createFileRoute("/_layout/metrics")({
  component: MetricsPage,
  head: () => ({
    meta: [
      {
        title: "Metrics - FastAPI Template",
      },
    ],
  }),
})

function MetricsPage() {
  return (
    <RequirePermission permission="metrics:view">
      <Metrics />
    </RequirePermission>
  )
}

function MetricCard({ label, value }: { label: string; value?: number }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl">
          {value === undefined ? <Skeleton className="h-9 w-16" /> : value}
        </CardTitle>
      </CardHeader>
    </Card>
  )
}

function Metrics() {
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: async () => (await MetricsService.readMetrics()).data,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Metrics</h1>
        <p className="text-muted-foreground">Usage at a glance</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Total users" value={metrics?.total_users} />
        <MetricCard label="Total items" value={metrics?.total_items} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ROLE_OPTIONS.map((role) => (
          <MetricCard
            key={role}
            label={`${roleLabel(role)}s`}
            value={metrics && (metrics.users_by_role[role] ?? 0)}
          />
        ))}
      </div>
    </div>
  )
}
