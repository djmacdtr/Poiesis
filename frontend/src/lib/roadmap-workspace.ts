/**
 * 章节路线工作台辅助：负责前端本地的阶段聚合、轻量校验与锁定提示。
 * 这些规则只是即时反馈，最终锁定和覆盖仍以后端正式校验结果为准。
 */
import type { ChapterRoadmapItem, RoadmapValidationIssue, StoryArcPlan } from '@/types'

function dedupe(values: string[]): string[] {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)))
}

function sortArcs(arcs: StoryArcPlan[]): StoryArcPlan[] {
  return [...arcs].sort((left, right) => left.arc_number - right.arc_number)
}

export function deriveStoryArcsFromRoadmapDraft(
  roadmap: ChapterRoadmapItem[],
  baseStoryArcs: StoryArcPlan[] = [],
  expandedArcNumbers: number[] = [],
): StoryArcPlan[] {
  if (baseStoryArcs.length > 0) {
    const grouped = new Map<string, ChapterRoadmapItem[]>()
    roadmap.forEach((item) => {
      const rows = grouped.get(item.story_stage.trim()) ?? []
      rows.push(item)
      grouped.set(item.story_stage.trim(), rows)
    })
    return sortArcs(
      baseStoryArcs.map((arc) => {
        const rows = grouped.get(arc.title.trim()) ?? []
        const ordered = [...rows].sort((left, right) => left.chapter_number - right.chapter_number)
        return {
          ...arc,
          main_progress: ordered.length > 0 ? dedupe(ordered.map((item) => item.story_progress)) : arc.main_progress,
          relationship_progress:
            ordered.length > 0 ? dedupe(ordered.flatMap((item) => item.relationship_progress)) : arc.relationship_progress,
          loop_progress:
            ordered.length > 0
              ? dedupe(
                  ordered.flatMap((item) =>
                    item.planned_loops
                      .map((loop) => String(loop.title ?? loop.summary ?? loop.loop_id ?? ''))
                      .filter(Boolean),
                  ),
                )
              : arc.loop_progress,
          timeline_milestones:
            ordered.length > 0 ? dedupe(ordered.map((item) => item.timeline_anchor)) : arc.timeline_milestones,
          arc_climax:
            ordered.length > 0
              ? ordered
                  .slice()
                  .reverse()
                  .find((item) => ['反转', '揭示', '收束', '决战前夜'].includes(item.chapter_function) && item.turning_point)
                  ?.turning_point ??
                ordered.at(-1)?.turning_point ??
                arc.arc_climax
              : arc.arc_climax,
          status:
            arc.status === 'confirmed'
              ? 'confirmed'
              : expandedArcNumbers.includes(arc.arc_number) || ordered.length > 0
                ? 'expanded'
                : 'draft',
          has_chapters: expandedArcNumbers.includes(arc.arc_number) || ordered.length > 0,
        }
      }),
    )
  }
  if (roadmap.length === 0) {
    return []
  }
  const grouped = new Map<string, ChapterRoadmapItem[]>()
  roadmap.forEach((item) => {
    const key = item.story_stage.trim() || '未分阶段'
    const rows = grouped.get(key) ?? []
    rows.push(item)
    grouped.set(key, rows)
  })

  return Array.from(grouped.entries()).map(([title, rows], index) => {
    const ordered = [...rows].sort((left, right) => left.chapter_number - right.chapter_number)
    return {
      arc_number: index + 1,
      title,
      purpose: ordered[0]?.goal ?? '',
      start_chapter: ordered[0]?.chapter_number ?? index + 1,
      end_chapter: ordered.at(-1)?.chapter_number ?? index + 1,
      main_progress: dedupe(ordered.map((item) => item.story_progress)),
      relationship_progress: dedupe(ordered.flatMap((item) => item.relationship_progress)),
      loop_progress: dedupe(
        ordered.flatMap((item) =>
          item.planned_loops.map((loop) => String(loop.title ?? loop.summary ?? loop.loop_id ?? '')).filter(Boolean),
        ),
      ),
      timeline_milestones: dedupe(ordered.map((item) => item.timeline_anchor)),
      arc_climax:
        ordered
          .slice()
          .reverse()
          .find((item) => ['反转', '揭示', '收束', '决战前夜'].includes(item.chapter_function) && item.turning_point)
          ?.turning_point ??
        ordered.at(-1)?.turning_point ??
        '',
      status: 'expanded',
      has_chapters: true,
      expansion_issue_count: 0,
    }
  })
}

export function buildLocalRoadmapIssues(
  storyArcs: StoryArcPlan[],
  roadmap: ChapterRoadmapItem[],
  expandedArcNumbers: number[] = [],
): RoadmapValidationIssue[] {
  const issues: RoadmapValidationIssue[] = []
  const stageArcMap = new Map(storyArcs.map((arc) => [arc.title, arc.arc_number]))
  let previous: ChapterRoadmapItem | null = null
  let repeatedFunctionCount = 0
  let stagnantTimelineCount = 0
  let emptyRelationshipCount = 0
  let emptyLoopCount = 0

  roadmap.forEach((item) => {
    const arcNumber = stageArcMap.get(item.story_stage) ?? null
    if (arcNumber !== null && expandedArcNumbers.length > 0 && !expandedArcNumbers.includes(arcNumber)) {
      previous = item
      return
    }
    if (!item.story_progress.trim()) {
      issues.push({
        severity: 'fatal',
        type: 'missing_story_progress',
        message: `第 ${item.chapter_number} 章没有明确主线推进。`,
        chapter_number: item.chapter_number,
        story_stage: item.story_stage,
        arc_number: arcNumber,
        suggested_action: 'edit_chapter',
      })
    }
    if (previous) {
      if (item.chapter_function && item.chapter_function === previous.chapter_function) {
        repeatedFunctionCount += 1
      } else {
        repeatedFunctionCount = 0
      }
      if (repeatedFunctionCount >= 1) {
        issues.push({
          severity: 'fatal',
          type: 'repeated_chapter_function',
          message: `第 ${previous.chapter_number}-${item.chapter_number} 章连续使用“${item.chapter_function || '未填写'}”功能，缺少有效升级。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'regenerate_arc',
        })
      }
      if (item.timeline_anchor && item.timeline_anchor === previous.timeline_anchor) {
        stagnantTimelineCount += 1
      } else {
        stagnantTimelineCount = 0
      }
      if (stagnantTimelineCount >= 2) {
        issues.push({
          severity: 'warning',
          type: 'timeline_stagnation',
          message: `第 ${Math.max(1, item.chapter_number - 2)}-${item.chapter_number} 章时间线停滞，建议加入明确时间推进。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'review_arc',
        })
      }
    }
    if (item.relationship_progress.length === 0) {
      emptyRelationshipCount += 1
    } else {
      emptyRelationshipCount = 0
    }
    if (emptyRelationshipCount >= 4) {
      issues.push({
        severity: 'warning',
        type: 'relationship_stagnation',
        message: `第 ${Math.max(1, item.chapter_number - 3)}-${item.chapter_number} 章长期缺少关系推进。`,
        chapter_number: item.chapter_number,
        story_stage: item.story_stage,
        arc_number: arcNumber,
        suggested_action: 'review_arc',
      })
    }
    if (item.planned_loops.length === 0) {
      emptyLoopCount += 1
    } else {
      emptyLoopCount = 0
    }
    if (emptyLoopCount >= 3) {
      issues.push({
        severity: 'warning',
        type: 'loop_stagnation',
        message: `第 ${Math.max(1, item.chapter_number - 2)}-${item.chapter_number} 章连续缺少计划线索推进。`,
        chapter_number: item.chapter_number,
        story_stage: item.story_stage,
        arc_number: arcNumber,
        suggested_action: 'review_arc',
      })
    }
    previous = item
  })

  storyArcs.forEach((arc) => {
    const chapters = roadmap.filter(
      (item) => item.chapter_number >= arc.start_chapter && item.chapter_number <= arc.end_chapter,
    )
    const functionSet = new Set(chapters.map((item) => item.chapter_function).filter(Boolean))
    if (chapters.length >= 2 && functionSet.size < 2) {
      issues.push({
        severity: 'fatal',
        type: 'arc_function_monotony',
        message: `阶段“${arc.title}”内部章节功能过于单一，缺少递进。`,
        chapter_number: arc.end_chapter,
        story_stage: arc.title,
        arc_number: arc.arc_number,
        suggested_action: 'regenerate_arc',
      })
    }
    if (chapters.length >= 3 && !chapters.some((item) => ['反转', '揭示', '收束', '决战前夜'].includes(item.chapter_function))) {
      issues.push({
        severity: 'warning',
        type: 'arc_missing_climax',
        message: `阶段“${arc.title}”缺少明确转折或收束节点。`,
        chapter_number: arc.end_chapter,
        story_stage: arc.title,
        arc_number: arc.arc_number,
        suggested_action: 'review_arc',
      })
    }
  })

  const seen = new Set<string>()
  return issues.filter((issue) => {
    const key = `${issue.type}:${issue.chapter_number ?? 'none'}:${issue.story_stage}:${issue.arc_number ?? 'none'}`
    if (seen.has(key)) {
      return false
    }
    seen.add(key)
    return true
  })
}

export function summarizeRoadmapLockState(
  storyArcs: StoryArcPlan[],
  expandedArcNumbers: number[],
  roadmapIssues: RoadmapValidationIssue[],
  roadmap: ChapterRoadmapItem[],
): { canLock: boolean; reasons: string[] } {
  const fatalIssues = roadmapIssues.filter((item) => item.severity === 'fatal')
  const reasons = fatalIssues.map((item) => item.message)
  const missingArcs = storyArcs.filter((item) => !expandedArcNumbers.includes(item.arc_number))
  if (missingArcs.length > 0) {
    reasons.push(`仍有阶段未展开章节：第 ${missingArcs.map((item) => item.arc_number).join('、')} 幕。`)
  }
  const missingFunction = roadmap.find((item) => !item.chapter_function.trim())
  if (missingFunction) {
    reasons.push(`第 ${missingFunction.chapter_number} 章缺少章节功能。`)
  }
  const missingProgress = roadmap.find((item) => !item.story_progress.trim())
  if (missingProgress) {
    reasons.push(`第 ${missingProgress.chapter_number} 章缺少主线推进。`)
  }
  return {
    canLock: reasons.length === 0 && storyArcs.length > 0,
    reasons,
  }
}
