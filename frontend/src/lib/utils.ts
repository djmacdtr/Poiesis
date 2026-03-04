// shadcn/ui 标准 cn 工具函数：合并 Tailwind 类名并去除冲突
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// 将 ISO 日期字符串格式化为本地可读日期
export function formatDate(dateStr: string): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

// 将字数格式化为带单位的字符串
export function formatWordCount(count: number): string {
  return `${count.toLocaleString('zh-CN')} 字`
}

// 章节状态中文标签
export const chapterStatusLabel: Record<string, string> = {
  draft: '草稿',
  completed: '已完成',
  published: '已发布',
}

// 伏笔状态中文标签
export const foreshadowingStatusLabel: Record<string, string> = {
  active: '活跃',
  resolved: '已解决',
  dropped: '已放弃',
}

// 候选变更状态中文标签
export const stagingStatusLabel: Record<string, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已拒绝',
}
