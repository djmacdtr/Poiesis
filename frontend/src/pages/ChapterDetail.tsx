/**
 * 章节详情页：展示章节正文、写作计划及 AI 生成摘要
 */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { fetchChapter } from '@/services/chapters'
import { LoadingSpinner, ErrorMessage } from '@/components/Feedback'
import { formatDate, formatWordCount, chapterStatusLabel } from '@/lib/utils'

export default function ChapterDetail() {
  const { id } = useParams<{ id: string }>()
  const chapterId = Number(id)

  const { data, isLoading, error } = useQuery({
    queryKey: ['chapter', chapterId],
    queryFn: () => fetchChapter(chapterId),
    enabled: !isNaN(chapterId),
  })

  if (isLoading) return <LoadingSpinner text="加载章节详情…" />
  if (error) return <ErrorMessage message={(error as Error).message} />
  if (!data) return <ErrorMessage message="章节不存在" />

  return (
    <div className="space-y-5 max-w-3xl">
      {/* 返回按钮 */}
      <Link
        to="/chapters"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        返回章节列表
      </Link>

      {/* 头部信息 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs text-indigo-500 font-medium">第 {data.chapter_number} 章</p>
            <h2 className="text-xl font-bold text-gray-900 mt-1">{data.title || `第 ${data.chapter_number} 章`}</h2>
          </div>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full shrink-0">
            {chapterStatusLabel[data.status] ?? data.status}
          </span>
        </div>

        <div className="flex gap-4 text-xs text-gray-400">
          <span>字数：{formatWordCount(data.word_count)}</span>
          <span>创建：{formatDate(data.created_at)}</span>
          <span>更新：{formatDate(data.updated_at)}</span>
        </div>
      </div>

      {/* 写作计划 */}
      {data.plan && (
        <div className="bg-amber-50 rounded-xl border border-amber-100 p-5">
          <h3 className="text-sm font-semibold text-amber-800 mb-3">写作计划</h3>
          {data.plan.outline && (
            <p className="text-sm text-amber-700 mb-2">{data.plan.outline}</p>
          )}
          {data.plan.key_events && data.plan.key_events.length > 0 && (
            <div>
              <p className="text-xs font-medium text-amber-700 mb-1">关键事件：</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-amber-600">
                {data.plan.key_events.map((event, i) => (
                  <li key={i}>{event}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 正文内容 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">正文</h3>
        {data.content ? (
          <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed whitespace-pre-wrap text-sm">
            {data.content}
          </div>
        ) : (
          <p className="text-sm text-gray-400 italic">正文尚未生成</p>
        )}
      </div>
    </div>
  )
}
