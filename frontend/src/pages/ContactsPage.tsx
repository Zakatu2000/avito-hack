import { useContacts } from '../api/hooks'
import { Card } from '../components/ui/Card'
import { SkeletonCard } from '../components/ui/Skeleton'
import { ErrorState } from '../components/ui/States'
import type { Contact } from '../api/schemas'

const TONE_BACKGROUND: Record<Contact['tone'], string> = {
  green: 'var(--card-green)',
  blue: 'var(--card-blue)',
  purple: 'var(--card-purple)',
  red: 'var(--card-red)',
  gray: 'var(--card-gray)',
}

export function ContactsPage() {
  const contacts = useContacts()

  if (contacts.isLoading) {
    return (
      <div className="page">
        <SkeletonCard lines={3} />
        <SkeletonCard lines={3} />
      </div>
    )
  }
  if (contacts.isError || !contacts.data) {
    return <ErrorState onRetry={() => void contacts.refetch()} retryLoading={contacts.isRefetching} />
  }

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="heading-l">К кому обратиться</h1>
          <p className="body-secondary" style={{ marginTop: 4 }}>
            Не всё решает бот — живые люди отвечают быстрее, чем кажется
          </p>
        </div>
      </div>

      <div className="grid-2">
        {contacts.data.map((contact) => (
          <Card key={contact.id} tone={contact.tone === 'red' ? 'red' : contact.tone === 'blue' ? 'blue' : contact.tone === 'green' ? 'green' : contact.tone === 'purple' ? 'purple' : 'gray'}
            style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <span
                aria-hidden="true"
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  background: TONE_BACKGROUND[contact.tone],
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 800,
                }}
              >
                {contact.name.split(' ').map((w) => w[0]).join('')}
              </span>
              <div>
                <h2 className="heading-s">{contact.name}</h2>
                <p className="caption">{contact.role}</p>
              </div>
            </div>
            <ul style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {contact.helpsWith.map((topic) => (
                <li key={topic} className="body-secondary">
                  · {topic}
                </li>
              ))}
            </ul>
            <p className="caption" style={{ marginTop: 'auto' }}>
              {contact.channel} · {contact.responseTime}
            </p>
          </Card>
        ))}
      </div>

      <p className="caption">Тестовые контакты: синтетические имена, не реальные сотрудники.</p>
    </div>
  )
}
