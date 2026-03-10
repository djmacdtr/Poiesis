/**
 * 章节状态卡：负责展示发布状态、阻塞项与发布动作。
 */
import type { PublishBlockers } from '@/types'
import { chapterStatusLabel, cn } from '@/lib/utils'
import { describePublishState } from '@/lib/scene-detail'
import { StatusPill } from './StatusPill'

interface ChapterStatusCardProps {
  publish: PublishBlockers
  isPublishing: boolean
  onPublish: () => void
}

export function ChapterStatusCard({ publish, isPublishing, onPublish }: ChapterStatusCardProps) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-stone-700">章节发布状态</h3>
            <StatusPill
              label={chapterStatusLabel[publish.chapter_status] ?? publish.chapter_status}
              tone={publish.can_publish ? 'success' : publish.chapter_status === 'published' ? 'info' : 'warning'}
            />
          </div>
          <p className="text-sm leading-6 text-stone-600">{describePublishState(publish)}</p>
        </div>
        <button
          onClick={onPublish}
          disabled={!publish.can_publish || isPublishing}
          className={cn(
            'rounded-lg px-3 py-1.5 text-xs font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50',
            publish.chapter_status === 'published' ? 'bg-sky-600 hover:bg-sky-600' : 'bg-stone-900 hover:bg-stone-800',
          )}
        >
          {publish.chapter_status === 'published' ? '已发布' : isPublishing ? '发布中…' : '立即发布'}
        </button>
      </div>

      {publish.blockers.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-medium text-amber-700">当前阻塞项</p>
          <ul className="mt-2 space-y-1 text-xs text-amber-700">
            {publish.blockers.map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
