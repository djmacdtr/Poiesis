/**
 * 运行控制页：启动写作任务并实时轮询进度
 */
import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Play, Square } from 'lucide-react'
import { toast } from 'sonner'
import { startRun, fetchTaskStatus } from '@/services/run'
import { LoadingSpinner, ErrorMessage } from '@/components/Feedback'
import type { TaskDetail } from '@/types'

/** 任务状态中文映射 */
const statusLabel: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

/** 任务状态颜色 */
const statusColor: Record<string, string> = {
  pending: 'text-yellow-600 bg-yellow-50',
  running: 'text-blue-600 bg-blue-50',
  completed: 'text-green-600 bg-green-50',
  failed: 'text-red-600 bg-red-50',
}

export default function Run() {
  const [chapterCount, setChapterCount] = useState(1)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [isStarting, setIsStarting] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // 轮询任务状态
  const {
    data: task,
    error: taskError,
  } = useQuery<TaskDetail>({
    queryKey: ['task', taskId],
    queryFn: () => fetchTaskStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'completed' || status === 'failed') return false
      return 2000
    },
  })

  // 任务状态变化通知
  useEffect(() => {
    if (task?.status === 'completed') {
      toast.success('写作任务已完成！')
    } else if (task?.status === 'failed') {
      toast.error(`任务失败：${task.error ?? '未知错误'}`)
    }
  }, [task?.status])

  // 自动滚动日志到底部
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [task?.logs])

  const handleStart = async () => {
    setIsStarting(true)
    try {
      const res = await startRun(chapterCount)
      setTaskId(res.task_id)
      toast.success(`任务已启动，ID：${res.task_id}`)
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setIsStarting(false)
    }
  }

  const handleReset = () => {
    setTaskId(null)
  }

  const isRunning = task?.status === 'running' || task?.status === 'pending'

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-lg font-semibold text-gray-800">运行控制</h2>

      {/* 启动表单 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">启动写作任务</h3>

        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600 shrink-0" htmlFor="chapter-count">
            生成章节数
          </label>
          <input
            id="chapter-count"
            type="number"
            min={1}
            max={50}
            value={chapterCount}
            onChange={(e) => setChapterCount(Number(e.target.value))}
            disabled={isStarting || isRunning}
            className="w-24 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleStart}
            disabled={isStarting || isRunning}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {isStarting ? (
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {isStarting ? '启动中…' : '开始运行'}
          </button>

          {taskId && !isRunning && (
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 transition-colors"
            >
              <Square className="w-4 h-4" />
              重置
            </button>
          )}
        </div>
      </div>

      {/* 任务状态 */}
      {taskId && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700">任务状态</h3>
            {task?.status && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor[task.status] ?? ''}`}>
                {statusLabel[task.status] ?? task.status}
              </span>
            )}
          </div>

          {taskError && <ErrorMessage message={(taskError as Error).message} />}

          {task && (
            <div className="space-y-2 text-sm text-gray-600">
              <p>任务 ID：<span className="font-mono text-xs text-gray-400">{task.task_id}</span></p>
              {task.current_chapter != null && task.total_chapters != null && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>进度：{task.current_chapter} / {task.total_chapters} 章</span>
                    <span>{Math.round((task.current_chapter / task.total_chapters) * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-indigo-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${(task.current_chapter / task.total_chapters) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 日志输出 */}
          {task?.logs && task.logs.length > 0 && (
            <div className="bg-gray-900 rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-xs text-green-400 space-y-0.5">
              {task.logs.map((log, i) => (
                <div key={i}>{log}</div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}

          {!task && !taskError && <LoadingSpinner text="获取任务状态…" />}
        </div>
      )}
    </div>
  )
}
