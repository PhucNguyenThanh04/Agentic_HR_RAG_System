import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'

type ComingSoonPageProps = {
  backendNote: string
  title: string
}

export function ComingSoonPage({ backendNote, title }: ComingSoonPageProps) {
  return (
    <section className="page-stack">
      <PageHeader
        description="Frontend đã chuẩn bị route và layout cho module này."
        eyebrow="Module"
        title={title}
      />
      <EmptyState
        description={backendNote}
        title="Chưa có endpoint backend trong api_router"
      />
    </section>
  )
}
