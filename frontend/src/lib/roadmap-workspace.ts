/**
 * 章节路线工作台辅助：负责前端本地的阶段聚合、轻量校验与连续性摘要。
 *
 * 这里的规则必须尽量贴近后端用例层，否则就会出现“前端可点、后端拒绝”的体验裂缝。
 * 因此前端不再自行发明阶段门禁，而是显式维护“当前最早未完成阶段才可生成下一章”的同一套规则。
 */
import type {
  BlueprintContinuityLoop,
  BlueprintContinuityEvent,
  BlueprintContinuityState,
  BlueprintRelationshipState,
  ChapterRoadmapItem,
  PlannedLoopItem,
  PlannedRelationshipBeat,
  PlannedTaskItem,
  RoadmapValidationIssue,
  StoryArcPlan,
} from '@/types'

function dedupe(values: string[]): string[] {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)))
}

function sortArcs(arcs: StoryArcPlan[]): StoryArcPlan[] {
  return [...arcs].sort((left, right) => left.arc_number - right.arc_number)
}

function isArcCompleted(arc: StoryArcPlan): boolean {
  return arc.next_chapter_number === null || arc.status === 'completed' || arc.status === 'confirmed'
}

/**
 * 在前端草稿态下重建“是否允许生成下一章”的门禁信息。
 * 规则故意保持非常保守：
 * - 最早未完成阶段才可继续生成；
 * - 已完成阶段直接禁用；
 * - 被阻塞阶段要带上 blocking_arc_number，供按钮文案显示“需先完成第 N 幕”。
 */
function decorateArcGenerationGate(arcs: StoryArcPlan[]): StoryArcPlan[] {
  const earliestIncompleteArc = sortArcs(arcs).find((arc) => !isArcCompleted(arc))?.arc_number ?? null
  return sortArcs(
    arcs.map((arc) => {
      if (isArcCompleted(arc)) {
        return {
          ...arc,
          can_generate_next_chapter: false,
          blocking_arc_number: null,
        }
      }
      return {
        ...arc,
        can_generate_next_chapter: earliestIncompleteArc === arc.arc_number,
        blocking_arc_number: earliestIncompleteArc === arc.arc_number ? null : earliestIncompleteArc,
      }
    }),
  )
}

function normalizeTask(task: PlannedTaskItem, chapterNumber: number, index: number): PlannedTaskItem {
  return {
    task_id: task.task_id || `chapter-${chapterNumber}-task-${index + 1}`,
    summary: task.summary.trim(),
    status: task.status,
    related_characters: task.related_characters ?? [],
    due_end_chapter: task.due_end_chapter ?? null,
  }
}

function formatLoopDisplay(loop: PlannedLoopItem): string {
  if (loop.title.trim()) {
    return loop.title.trim()
  }
  if (loop.summary.trim()) {
    return loop.summary.trim()
  }
  return loop.loop_id.trim() || '未命名伏笔'
}

/**
 * 根据路线草稿全量重建连续性工作态。
 * 这份状态只服务于蓝图工作台，不等于正式 canon：
 * - task / loop / relationship 使用后写覆盖前写，表示“最新计划态”；
 * - recent_events / worldUpdates 保留近邻摘要，用于右侧摘要栏和下一章生成前检查；
 * - roadmap 是唯一真源，因此这里不做增量 patch，而是每次重新扫描整份草稿。
 */
export function buildLocalContinuityState(roadmap: ChapterRoadmapItem[]): BlueprintContinuityState {
  const ordered = [...roadmap].sort((left, right) => left.chapter_number - right.chapter_number)
  const tasks = new Map<string, PlannedTaskItem>()
  const loops = new Map<string, BlueprintContinuityLoop>()
  const relationshipStates = new Map<string, BlueprintRelationshipState>()
  const recentEvents: BlueprintContinuityEvent[] = []
  const worldUpdates: string[] = []

  ordered.forEach((chapter) => {
    if (chapter.story_progress.trim()) {
      recentEvents.push({
        chapter_number: chapter.chapter_number,
        story_stage: chapter.story_stage,
        timeline_anchor: chapter.timeline_anchor,
        kind: 'main_progress',
        summary: chapter.story_progress,
      })
    }
    chapter.key_events.forEach((event) => {
      const summary = event.trim()
      if (!summary) {
        return
      }
      recentEvents.push({
        chapter_number: chapter.chapter_number,
        story_stage: chapter.story_stage,
        timeline_anchor: chapter.timeline_anchor,
        kind: 'key_event',
        summary,
      })
    })
    chapter.new_reveals.forEach((event) => {
      const summary = event.trim()
      if (!summary) {
        return
      }
      recentEvents.push({
        chapter_number: chapter.chapter_number,
        story_stage: chapter.story_stage,
        timeline_anchor: chapter.timeline_anchor,
        kind: 'reveal',
        summary,
      })
    })
    chapter.world_updates.forEach((event) => {
      const summary = event.trim()
      if (!summary) {
        return
      }
      recentEvents.push({
        chapter_number: chapter.chapter_number,
        story_stage: chapter.story_stage,
        timeline_anchor: chapter.timeline_anchor,
        kind: 'world_update',
        summary,
      })
      if (!worldUpdates.includes(summary)) {
        worldUpdates.push(summary)
      }
    })
    chapter.chapter_tasks.forEach((task, index) => {
      const normalized = normalizeTask(task, chapter.chapter_number, index)
      tasks.set(normalized.task_id, normalized)
    })
    chapter.planned_loops.forEach((loop, index) => {
      const loopId = String(loop.loop_id ?? `chapter-${chapter.chapter_number}-loop-${index + 1}`)
      loops.set(loopId, {
        ...loop,
        loop_id: loopId,
        title: loop.title,
        summary: loop.summary,
        label: loop.title || loop.summary || null,
        status: loop.status,
        due_end_chapter: loop.due_end_chapter ?? null,
        payoff_due_chapter: loop.due_end_chapter ?? null,
      } satisfies BlueprintContinuityLoop)
    })
    chapter.relationship_beats.forEach((beat: PlannedRelationshipBeat) => {
      if (!beat.source_character.trim() || !beat.target_character.trim() || !beat.summary.trim()) {
        return
      }
      relationshipStates.set(`${beat.source_character}|${beat.target_character}`, {
        source_character: beat.source_character.trim(),
        target_character: beat.target_character.trim(),
        latest_summary: beat.summary.trim(),
        source_chapter: chapter.chapter_number,
      })
    })
  })

  return {
    last_planned_chapter: ordered.at(-1)?.chapter_number ?? 0,
    open_tasks: Array.from(tasks.values()).filter((task) => ['new', 'in_progress'].includes(task.status)),
    resolved_tasks: Array.from(tasks.values()).filter((task) => ['resolved', 'failed'].includes(task.status)),
    active_loops: Array.from(loops.values()).filter((loop) => String(loop.status ?? 'open') !== 'resolved'),
    recent_events: recentEvents.slice(-12),
    relationship_states: Array.from(relationshipStates.values()),
    world_updates: worldUpdates.slice(-8),
  }
}

export function deriveStoryArcsFromRoadmapDraft(
  roadmap: ChapterRoadmapItem[],
  baseStoryArcs: StoryArcPlan[] = [],
  expandedArcNumbers: number[] = [],
): StoryArcPlan[] {
  if (baseStoryArcs.length > 0) {
    /**
     * 正常路径下以后端阶段骨架为准，再把章节草稿反推为阶段进度。
     * 这样既能保留后端规划出的阶段边界，也能让前端在手改草稿后立即看到进度变化。
     */
    const grouped = new Map<string, ChapterRoadmapItem[]>()
    roadmap.forEach((item) => {
      const rows = grouped.get(item.story_stage.trim()) ?? []
      rows.push(item)
      grouped.set(item.story_stage.trim(), rows)
    })
    return decorateArcGenerationGate(
      baseStoryArcs.map((arc) => {
        const rows = grouped.get(arc.title.trim()) ?? []
        const ordered = [...rows].sort((left, right) => left.chapter_number - right.chapter_number)
        const chapterTargetCount = Math.max(1, arc.end_chapter - arc.start_chapter + 1)
        const generatedChapterCount = ordered.length
        const nextChapterNumber =
          generatedChapterCount >= chapterTargetCount ? null : arc.start_chapter + generatedChapterCount
        const completed = expandedArcNumbers.includes(arc.arc_number) || generatedChapterCount >= chapterTargetCount
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
              : completed
                ? 'completed'
                : ordered.length > 0
                  ? 'in_progress'
                  : 'draft',
          has_chapters: ordered.length > 0,
          generated_chapter_count: generatedChapterCount,
          chapter_target_count: chapterTargetCount,
          next_chapter_number: nextChapterNumber,
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

  /**
   * 兜底路径：如果阶段骨架缺失，就按章节中的 story_stage 粗略拼出本地阶段视图。
   * 这里只负责保证 UI 可展示，不负责替代正式阶段规划。
   */
  return decorateArcGenerationGate(
    Array.from(grouped.entries()).map(([title, rows], index) => {
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
        status: 'completed',
        has_chapters: true,
        generated_chapter_count: ordered.length,
        chapter_target_count: ordered.length,
        next_chapter_number: null,
        can_generate_next_chapter: false,
        blocking_arc_number: null,
        expansion_issue_count: 0,
      }
    }),
  )
}

export function buildLocalRoadmapIssues(
  storyArcs: StoryArcPlan[],
  roadmap: ChapterRoadmapItem[],
  _expandedArcNumbers: number[] = [],
): RoadmapValidationIssue[] {
  /**
   * 本地问题列表只覆盖“足以指导工作台交互”的那部分规则：
   * - 缺少关键结构字段；
   * - 时间线/依赖关系明显异常；
   * - 哪个阶段此刻允许生成下一章。
   * 更重的世界观、关系图谱冲突仍以服务端验证结果为准。
   */
  const issues: RoadmapValidationIssue[] = []
  const stageArcMap = new Map(storyArcs.map((arc) => [arc.title, arc.arc_number]))
  let previous: ChapterRoadmapItem | null = null
  let repeatedFunctionCount = 0
  const latestLoops = new Map<string, { chapterNumber: number; loop: PlannedLoopItem; storyStage: string }>()

  roadmap.forEach((item) => {
    const arcNumber = stageArcMap.get(item.story_stage) ?? null
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
    if (item.key_events.length === 0) {
      issues.push({
        severity: 'fatal',
        type: 'missing_key_events',
        message: `第 ${item.chapter_number} 章缺少结构化关键事件。`,
        chapter_number: item.chapter_number,
        story_stage: item.story_stage,
        arc_number: arcNumber,
        suggested_action: 'edit_chapter',
      })
    }
    if (item.chapter_tasks.length === 0 && item.planned_loops.length === 0) {
      issues.push({
        severity: 'fatal',
        type: 'missing_task_or_loop_progress',
        message: `第 ${item.chapter_number} 章既没有任务变化，也没有伏笔推进。`,
        chapter_number: item.chapter_number,
        story_stage: item.story_stage,
        arc_number: arcNumber,
        suggested_action: 'edit_chapter',
      })
    }
    /**
     * 本地伏笔校验需要尽量贴近后端 verifier：
     * - 标题/摘要/最迟兑现章缺失都属于 fatal；
     * - 开始章不能晚于截止章；
     * - 截止章不能早于引入章；
     * - 当前章已经超过截止章但伏笔仍未回收，也要立刻报 fatal。
     */
    item.planned_loops.forEach((loop) => {
      const loopLabel = formatLoopDisplay(loop)
      latestLoops.set(loop.loop_id, {
        chapterNumber: item.chapter_number,
        loop,
        storyStage: item.story_stage,
      })
      if (!loop.title.trim()) {
        issues.push({
          severity: 'fatal',
          type: 'loop_missing_title',
          message: `第 ${item.chapter_number} 章的伏笔“${loopLabel}”缺少标题。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'edit_chapter',
        })
      }
      if (!loop.summary.trim()) {
        issues.push({
          severity: 'fatal',
          type: 'loop_missing_summary',
          message: `第 ${item.chapter_number} 章的伏笔“${loopLabel}”缺少摘要说明。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'edit_chapter',
        })
      }
      if (!Number.isFinite(loop.due_end_chapter)) {
        issues.push({
          severity: 'fatal',
          type: 'loop_missing_due_end',
          message: `第 ${item.chapter_number} 章的伏笔“${loopLabel}”缺少最迟兑现章。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'edit_chapter',
        })
      } else {
        if (loop.due_end_chapter < item.chapter_number) {
          issues.push({
            severity: 'fatal',
            type: 'loop_due_end_before_intro',
            message: `第 ${item.chapter_number} 章的伏笔“${loopLabel}”最迟兑现章早于引入章。`,
            chapter_number: item.chapter_number,
            story_stage: item.story_stage,
            arc_number: arcNumber,
            suggested_action: 'edit_chapter',
          })
        }
        if (item.chapter_number > loop.due_end_chapter && loop.status !== 'resolved') {
          issues.push({
            severity: 'fatal',
            type: 'loop_overdue',
            message: `第 ${item.chapter_number} 章的伏笔“${loopLabel}”已超过回收窗口仍未解决。`,
            chapter_number: item.chapter_number,
            story_stage: item.story_stage,
            arc_number: arcNumber,
            suggested_action: 'regenerate_last_chapter',
          })
        }
      }
      if (
        typeof loop.due_start_chapter === 'number' &&
        Number.isFinite(loop.due_end_chapter) &&
        loop.due_start_chapter > loop.due_end_chapter
      ) {
        issues.push({
          severity: 'fatal',
          type: 'loop_due_window_invalid',
          message: `第 ${item.chapter_number} 章的伏笔“${loopLabel}”开始章晚于最迟兑现章。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'edit_chapter',
        })
      }
    })
    if (previous) {
      if (!item.depends_on_chapters.includes(previous.chapter_number)) {
        issues.push({
          severity: 'fatal',
          type: 'missing_previous_dependency',
          message: `第 ${item.chapter_number} 章没有承接上一章（第 ${previous.chapter_number} 章）。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'edit_chapter',
        })
      }
      if (item.timeline_anchor && item.timeline_anchor === previous.timeline_anchor) {
        issues.push({
          severity: 'fatal',
          type: 'timeline_not_advanced',
          message: `第 ${item.chapter_number} 章时间锚点没有相对上一章推进。`,
          chapter_number: item.chapter_number,
          story_stage: item.story_stage,
          arc_number: arcNumber,
          suggested_action: 'regenerate_last_chapter',
        })
      }
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
          suggested_action: 'regenerate_last_chapter',
        })
      }
    }
    previous = item
  })

  const lastPlannedChapterNumber = roadmap.at(-1)?.chapter_number ?? 0
  latestLoops.forEach(({ chapterNumber, loop, storyStage }, loopId) => {
    if (loop.status === 'resolved' || !Number.isFinite(loop.due_end_chapter) || loop.due_end_chapter >= lastPlannedChapterNumber) {
      return
    }
    issues.push({
      severity: 'fatal',
      type: 'loop_still_overdue',
      message: `伏笔“${formatLoopDisplay({ ...loop, loop_id: loopId })}”已经过了最迟回收窗口但仍未解决。`,
      chapter_number: chapterNumber,
      story_stage: storyStage,
      arc_number: stageArcMap.get(storyStage) ?? null,
      suggested_action: 'review_arc',
    })
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
        suggested_action: 'review_arc',
      })
    }
    if (arc.next_chapter_number !== null) {
      issues.push({
        severity: 'warning',
        type: 'arc_not_completed',
        message: arc.can_generate_next_chapter
          ? `阶段“${arc.title}”当前仅完成 ${arc.generated_chapter_count}/${arc.chapter_target_count} 章，请继续生成第 ${arc.next_chapter_number} 章。`
          : `阶段“${arc.title}”尚未轮到生成，请先完成第 ${arc.blocking_arc_number} 幕。`,
        chapter_number: arc.next_chapter_number,
        story_stage: arc.title,
        arc_number: arc.arc_number,
        suggested_action: arc.can_generate_next_chapter ? 'generate_next_chapter' : 'review_arc',
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
    reasons.push(`仍有阶段未完成章节生成：第 ${missingArcs.map((item) => item.arc_number).join('、')} 幕。`)
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
