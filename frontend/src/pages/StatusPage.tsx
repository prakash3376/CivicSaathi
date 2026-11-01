import { HealthStatus } from '@/features/health/HealthStatus'

/** For whoever runs the service: can the browser reach the API, and what does it report. */
export function StatusPage() {
  return (
    <div className="space-y-6">
      <title>System status · CivicSaathi</title>
      <HealthStatus />
    </div>
  )
}
