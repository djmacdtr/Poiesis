/**
 * 路线右侧 inspector：
 * 统一承接章节路线步骤里的五种上下文模式：
 * 1. 当前阶段摘要
 * 2. 问题详情
 * 3. 修复提案详情
 * 4. 执行结果详情
 * 5. 章节细修表单
 *
 * 这样主区就不需要再同时承担“阶段卡 + 修复卡 + 长表单”的三重负担，
 * 维护者也能在一个组件里看清楚 inspector 切换规则，而不是追 JSX 条件分支。
 */
import { Link } from 'react-router-dom'
import type {
  BlueprintContinuityState,
  ChapterRoadmapItem,
  CreativeIssue,
  CreativeRepairProposal,
  CreativeRepairRun,
  PlannedLoopItem,
  PlannedRelationshipBeat,
  PlannedTaskItem,
  StoryArcPlan,
  RoadmapValidationIssue,
} from '@/types'
import {
  formatCreativeDiffFieldLabel,
  formatCreativeDiffValue,
  formatCreativeIssueStatusLabel,
  formatCreativeIssueTypeLabel,
  formatCreativeRepairabilityLabel,
  formatCreativeRiskLabel,
  formatReviewStatusLabel,
  formatCreativeRunStatusLabel,
  formatCreativeSourceLayerLabel,
  formatCreativeStrategyLabel,
  formatLoopStatusLabel,
  formatSceneStatusLabel,
  parseLoopStatusValue,
} from '@/lib/display-labels'

type RoadmapInspectorMode = 'summary' | 'issue' | 'proposal' | 'run' | 'chapter'

export interface RoadmapInspectorState {
  mode: RoadmapInspectorMode
  issue: CreativeIssue | null
  proposal: CreativeRepairProposal | null
  run: CreativeRepairRun | null
  chapter: ChapterRoadmapItem | null
}

interface RoadmapInspectorPanelProps {
  state: RoadmapInspectorState
  currentActionableArc: StoryArcPlan | null
  chapterActionArc: StoryArcPlan | null
  continuityState: BlueprintContinuityState
  selectedRoadmapChapterIssues: RoadmapValidationIssue[]
  pendingRoadmapChapterNumber: number | null
  canRegenerateFocusedRoadmapChapter: boolean
  joinTags: (values: string[]) => string
  parseTags: (value: string) => string[]
  serializeChapterTasks: (tasks: PlannedTaskItem[]) => string
  parseChapterTasks: (value: string) => PlannedTaskItem[]
  serializeRelationshipBeats: (beats: PlannedRelationshipBeat[]) => string
  parseRelationshipBeats: (value: string) => PlannedRelationshipBeat[]
  parseOptionalChapterNumber: (value: string) => number | null
  updateRoadmapChapterByNumber: (
    chapterNumber: number,
    updater: (item: ChapterRoadmapItem) => ChapterRoadmapItem,
  ) => void
  updateRoadmapLoopByIndex: (
    chapterNumber: number,
    loopIndex: number,
    updater: (item: PlannedLoopItem) => PlannedLoopItem,
  ) => void
  addRoadmapLoop: (chapterNumber: number, dueEndChapter: number) => void
  removeRoadmapLoop: (chapterNumber: number, loopIndex: number) => void
  onRegenerateChapter: (arcNumber: number, chapterNumber: number) => void
  reviewQueueHref: string
}

export function RoadmapInspectorPanel({
  state,
  currentActionableArc,
  chapterActionArc,
  continuityState,
  selectedRoadmapChapterIssues,
  pendingRoadmapChapterNumber,
  canRegenerateFocusedRoadmapChapter,
  joinTags,
  parseTags,
  serializeChapterTasks,
  parseChapterTasks,
  serializeRelationshipBeats,
  parseRelationshipBeats,
  parseOptionalChapterNumber,
  updateRoadmapChapterByNumber,
  updateRoadmapLoopByIndex,
  addRoadmapLoop,
  removeRoadmapLoop,
  onRegenerateChapter,
  reviewQueueHref,
}: RoadmapInspectorPanelProps) {
  const issueContext = state.issue?.context_payload ?? {}
  const reviewId = Number(issueContext.review_id ?? 0) || null
  const reviewRunId = Number(issueContext.run_id ?? 0) || null
  const reviewChapterNumber = Number(issueContext.chapter_number ?? 0) || null
  const reviewSceneNumber = Number(issueContext.scene_number ?? 0) || null
  const reviewEventCount = Number(issueContext.event_count ?? 0) || 0
  const reviewStatus = String(issueContext.review_status ?? '').trim()
  const reviewReason = String(issueContext.reason ?? '').trim()
  const reviewSceneStatus = String(issueContext.scene_status ?? '').trim()
  const reviewLatestResultSummary = String(issueContext.latest_result_summary ?? '').trim()
  const reviewPatchText = String(issueContext.patch_text ?? '').trim()

  if (state.mode === 'proposal' && state.proposal) {
    return (
      <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-stone-900">修复提案详情</h4>
            <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">
              {formatCreativeStrategyLabel(state.proposal.strategy_type)}
            </span>
          </div>
          <p className="text-sm leading-6 text-stone-700">{state.proposal.summary}</p>
          <div className="grid gap-2 text-xs text-stone-600">
            <div className="rounded-2xl bg-stone-50 px-3 py-3">
              风险等级：{formatCreativeRiskLabel(state.proposal.risk_level)} ·
              {state.proposal.requires_llm ? ' 需要模型改写' : ' 结构补丁'}
            </div>
            {state.proposal.strategy_type === 'arc_rewrite' ? (
              <div className="rounded-2xl bg-sky-50 px-3 py-3 text-sky-800">
                本提案只会重写当前幕的结构内容，并清空该幕已生成章节以重新展开；不会改动整书分幕章号，也不会重排后续幕。
              </div>
            ) : null}
            {state.proposal.diff_preview.map((item, index) => (
              <div key={`${state.proposal?.proposal_id}-${index}`} className="rounded-2xl bg-stone-50 px-3 py-3">
                <p className="font-medium text-stone-800">
                  {formatCreativeDiffFieldLabel(String(item.field_name ?? item.kind ?? ''))}
                </p>
                <p className="mt-1 leading-5">
                  变更前：{formatCreativeDiffValue(String(item.field_name ?? ''), item.before)}
                  <br />
                  变更后：{formatCreativeDiffValue(String(item.field_name ?? ''), item.after)}
                </p>
              </div>
            ))}
          </div>
          {state.proposal.expected_post_conditions.length > 0 ? (
            <div className="rounded-2xl bg-emerald-50 px-3 py-3 text-xs text-emerald-700">
              <p className="font-medium">预期后置条件</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {state.proposal.expected_post_conditions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </section>
    )
  }

  if (state.mode === 'run' && state.run) {
    return (
      <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-stone-900">执行结果详情</h4>
            <span className="rounded-full bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-700">
              {formatCreativeRunStatusLabel(state.run.status)}
            </span>
          </div>
          <div className="grid gap-2 text-xs text-stone-600">
            <div className="rounded-2xl bg-stone-50 px-3 py-3">
              执行前快照：{state.run.before_snapshot_ref || '未记录'}
            </div>
            <div className="rounded-2xl bg-stone-50 px-3 py-3">
              执行后快照：{state.run.after_snapshot_ref || '未记录'}
            </div>
          </div>
          <div className="space-y-2">
            {state.run.logs.length > 0 ? (
              state.run.logs.map((log, index) => (
                <div key={`${state.run?.run_id}-${index}`} className="rounded-2xl bg-stone-50 px-3 py-3 text-xs leading-5 text-stone-600">
                  {log}
                </div>
              ))
            ) : (
              <div className="rounded-2xl bg-stone-50 px-3 py-3 text-xs text-stone-500">当前没有附加日志。</div>
            )}
          </div>
          {state.run.error_message ? (
            <div className="rounded-2xl bg-rose-50 px-3 py-3 text-xs text-rose-700">
              {state.run.error_message}
            </div>
          ) : null}
        </div>
      </section>
    )
  }

  if (state.mode === 'issue' && state.issue) {
    return (
      <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-stone-900">问题详情</h4>
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                state.issue.severity === 'fatal' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'
              }`}
            >
              {state.issue.severity === 'fatal' ? '严重问题' : '提醒'}
            </span>
          </div>
          <p className="text-sm leading-6 text-stone-700">{state.issue.message}</p>
          <div className="grid gap-2 text-xs text-stone-600">
            <div className="rounded-2xl bg-stone-50 px-3 py-3">
              来源层：{formatCreativeSourceLayerLabel(state.issue.source_layer)} · 问题状态：
              {formatCreativeIssueStatusLabel(state.issue.status)}
            </div>
            <div className="rounded-2xl bg-stone-50 px-3 py-3">
              问题类型：{formatCreativeIssueTypeLabel(state.issue.issue_type)}
            </div>
            <div className="rounded-2xl bg-stone-50 px-3 py-3">
              修复方式：{formatCreativeRepairabilityLabel(state.issue.repairability)}
              {state.issue.suggested_strategy ? ` · 建议策略：${formatCreativeStrategyLabel(state.issue.suggested_strategy)}` : ''}
            </div>
            {state.issue.source_layer === 'roadmap' && state.issue.suggested_strategy === 'arc_rewrite' ? (
              <div className="rounded-2xl bg-amber-50 px-3 py-3 text-amber-800">
                这类阶段级问题默认只作为审查提示，不会自动混入“为当前问题生成修复方案”。如果你判断这一幕骨架确实已经写偏，再单独生成骨架修复方案会更稳妥。
              </div>
            ) : null}
            {state.issue.source_layer === 'review' ? (
              <>
                <div className="rounded-2xl bg-sky-50 px-3 py-3 text-sky-800">
                  审阅队列当前先以只读方式接入控制面。你可以先在这里查看待处理原因，再跳到审阅页执行“通过 / 重试 / 修补”。
                </div>
                <div className="rounded-2xl bg-stone-50 px-3 py-3">
                  审阅项：#{reviewId ?? '未记录'} · 任务：#{reviewRunId ?? '未记录'} · 第 {reviewChapterNumber ?? '未标注'} 章 / 场景{' '}
                  {reviewSceneNumber ?? '未标注'}
                </div>
                <div className="rounded-2xl bg-stone-50 px-3 py-3">
                  场景状态：{formatSceneStatusLabel(reviewSceneStatus)} · 审阅状态：{formatReviewStatusLabel(reviewStatus)} · 历史动作：
                  {reviewEventCount} 次
                </div>
                {reviewReason ? (
                  <div className="rounded-2xl bg-stone-50 px-3 py-3">
                    <p className="font-medium text-stone-800">待审阅原因</p>
                    <p className="mt-1 leading-5 text-stone-600">{reviewReason}</p>
                  </div>
                ) : null}
                {reviewLatestResultSummary ? (
                  <div className="rounded-2xl bg-stone-50 px-3 py-3">
                    <p className="font-medium text-stone-800">最近处理结果</p>
                    <p className="mt-1 leading-5 text-stone-600">{reviewLatestResultSummary}</p>
                  </div>
                ) : null}
                {reviewPatchText ? (
                  <div className="rounded-2xl bg-stone-50 px-3 py-3">
                    <p className="font-medium text-stone-800">当前修补要求</p>
                    <p className="mt-1 whitespace-pre-wrap leading-5 text-stone-600">{reviewPatchText}</p>
                  </div>
                ) : null}
                <Link
                  to={reviewQueueHref}
                  className="inline-flex rounded-xl bg-stone-900 px-3 py-2 text-xs font-medium text-white hover:bg-stone-800"
                >
                  前往审阅队列处理
                </Link>
              </>
            ) : state.issue.source_layer !== 'roadmap' ? (
              <div className="rounded-2xl bg-sky-50 px-3 py-3 text-sky-700">
                当前层已经接入统一问题队列，但暂未接入可执行修复。请先结合原场景/审阅页面人工处理。
              </div>
            ) : null}
          </div>
        </div>
      </section>
    )
  }

  if (state.mode === 'chapter' && state.chapter) {
    const chapter = state.chapter
    return (
      <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
        {/* 章节细修固定在右栏，是为了保证主区始终保留阶段工作台和章节列表。 */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h4 className="text-base font-semibold text-stone-900">
              第 {chapter.chapter_number} 章 · {chapter.title || '未命名章节'}
            </h4>
            <p className="mt-1 text-sm text-stone-500">
              当前阶段：{chapter.story_stage || '未标注'} · 时间锚点：{chapter.timeline_anchor || '未标注'}
            </p>
          </div>
          {canRegenerateFocusedRoadmapChapter && chapterActionArc ? (
            <button
              type="button"
              onClick={() => onRegenerateChapter(chapterActionArc.arc_number, chapter.chapter_number)}
              disabled={pendingRoadmapChapterNumber === chapter.chapter_number}
              className="rounded-xl bg-amber-600 px-3 py-2 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50"
            >
              {pendingRoadmapChapterNumber === chapter.chapter_number ? '重生成中…' : '重生成本章'}
            </button>
          ) : null}
        </div>

        <div className="mt-4 space-y-3">
          <details open className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
            <summary className="cursor-pointer text-sm font-medium text-stone-700">基础信息</summary>
            <div className="mt-3 space-y-3">
              <input
                value={chapter.title}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({ ...item, title: event.target.value }))
                }
                placeholder="章节标题"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
              <div className="grid gap-3 md:grid-cols-2">
                <input
                  value={chapter.story_stage}
                  onChange={(event) =>
                    updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                      ...item,
                      story_stage: event.target.value,
                    }))
                  }
                  placeholder="所属阶段"
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                />
                <input
                  value={chapter.timeline_anchor}
                  onChange={(event) =>
                    updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                      ...item,
                      timeline_anchor: event.target.value,
                    }))
                  }
                  placeholder="时间线锚点"
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                />
              </div>
              <textarea
                value={chapter.goal}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({ ...item, goal: event.target.value }))
                }
                rows={2}
                placeholder="章节目标"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
              <textarea
                value={chapter.core_conflict}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                    ...item,
                    core_conflict: event.target.value,
                  }))
                }
                rows={2}
                placeholder="核心冲突"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
            </div>
          </details>

          <details open className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
            <summary className="cursor-pointer text-sm font-medium text-stone-700">主线与事件</summary>
            <div className="mt-3 space-y-3">
              <textarea
                value={chapter.story_progress}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                    ...item,
                    story_progress: event.target.value,
                  }))
                }
                rows={3}
                placeholder="这一章真正推进了什么主线事实"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
              <textarea
                value={joinTags(chapter.key_events)}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                    ...item,
                    key_events: parseTags(event.target.value),
                  }))
                }
                rows={2}
                placeholder="关键事件，多项可用逗号分隔"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
              <div className="grid gap-3 md:grid-cols-2">
                <textarea
                  value={joinTags(chapter.character_progress)}
                  onChange={(event) =>
                    updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                      ...item,
                      character_progress: parseTags(event.target.value),
                    }))
                  }
                  rows={2}
                  placeholder="人物推进"
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                />
                <textarea
                  value={joinTags(chapter.relationship_progress)}
                  onChange={(event) =>
                    updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                      ...item,
                      relationship_progress: parseTags(event.target.value),
                    }))
                  }
                  rows={2}
                  placeholder="关系推进"
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                />
                <textarea
                  value={joinTags(chapter.new_reveals)}
                  onChange={(event) =>
                    updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                      ...item,
                      new_reveals: parseTags(event.target.value),
                    }))
                  }
                  rows={2}
                  placeholder="新揭示"
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                />
                <textarea
                  value={joinTags(chapter.world_updates)}
                  onChange={(event) =>
                    updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                      ...item,
                      world_updates: parseTags(event.target.value),
                    }))
                  }
                  rows={2}
                  placeholder="世界更新"
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                />
              </div>
            </div>
          </details>

          <details open className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
            <summary className="cursor-pointer text-sm font-medium text-stone-700">任务与关系推进</summary>
            <div className="mt-3 space-y-3">
              <textarea
                value={serializeChapterTasks(chapter.chapter_tasks)}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                    ...item,
                    chapter_tasks: parseChapterTasks(event.target.value),
                  }))
                }
                rows={3}
                placeholder="任务变化：一行一个，推荐格式 任务摘要|任务状态|人物A,人物B|最迟章号|任务标识"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
              <textarea
                value={serializeRelationshipBeats(chapter.relationship_beats)}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                    ...item,
                    relationship_beats: parseRelationshipBeats(event.target.value),
                  }))
                }
                rows={3}
                placeholder="关系推进：一行一个，格式 角色A->角色B|推进摘要"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
            </div>
          </details>

          <details open className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
            <summary className="cursor-pointer text-sm font-medium text-stone-700">伏笔</summary>
            <div className="mt-3 rounded-2xl border border-stone-200 bg-white p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-stone-800">结构化伏笔</p>
                  <p className="mt-1 text-xs leading-5 text-stone-500">
                    伏笔必须填写标题、摘要和最迟兑现章。这样右栏细修和连续性校对看到的是同一套强约束数据。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => addRoadmapLoop(chapter.chapter_number, chapterActionArc?.end_chapter ?? chapter.chapter_number)}
                  className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                >
                  新增伏笔
                </button>
              </div>

              <div className="mt-3 space-y-3">
                {chapter.planned_loops.length > 0 ? (
                  chapter.planned_loops.map((loop, loopIndex) => (
                    <div key={loop.loop_id} className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-stone-800">伏笔 {loopIndex + 1}</p>
                        <button
                          type="button"
                          onClick={() => removeRoadmapLoop(chapter.chapter_number, loopIndex)}
                          className="text-xs font-medium text-rose-600 hover:text-rose-700"
                        >
                          删除
                        </button>
                      </div>
                      <div className="mt-3 grid gap-3">
                        <input
                          value={loop.title}
                          onChange={(event) =>
                            updateRoadmapLoopByIndex(chapter.chapter_number, loopIndex, (current) => ({
                              ...current,
                              title: event.target.value,
                            }))
                          }
                          placeholder="伏笔标题（必填）"
                          className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                        />
                        <textarea
                          value={loop.summary}
                          onChange={(event) =>
                            updateRoadmapLoopByIndex(chapter.chapter_number, loopIndex, (current) => ({
                              ...current,
                              summary: event.target.value,
                            }))
                          }
                          rows={2}
                          placeholder="伏笔摘要（必填）"
                          className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                        />
                        <div className="grid gap-3 md:grid-cols-3">
                          <select
                            value={loop.status}
                            onChange={(event) =>
                              updateRoadmapLoopByIndex(chapter.chapter_number, loopIndex, (current) => ({
                                ...current,
                                status: parseLoopStatusValue(event.target.value),
                              }))
                            }
                            className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                          >
                            <option value="open">{formatLoopStatusLabel('open')}</option>
                            <option value="progressed">{formatLoopStatusLabel('progressed')}</option>
                            <option value="resolved">{formatLoopStatusLabel('resolved')}</option>
                          </select>
                          <input
                            type="number"
                            min={chapter.chapter_number}
                            value={loop.due_start_chapter ?? ''}
                            onChange={(event) =>
                              updateRoadmapLoopByIndex(chapter.chapter_number, loopIndex, (current) => ({
                                ...current,
                                due_start_chapter: parseOptionalChapterNumber(event.target.value),
                              }))
                            }
                            placeholder="开始进入章"
                            className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                          />
                          <input
                            type="number"
                            min={chapter.chapter_number}
                            value={loop.due_end_chapter}
                            onChange={(event) =>
                              updateRoadmapLoopByIndex(chapter.chapter_number, loopIndex, (current) => ({
                                ...current,
                                due_end_chapter:
                                  parseOptionalChapterNumber(event.target.value) ?? chapter.chapter_number,
                              }))
                            }
                            placeholder="最迟兑现章（必填）"
                            className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                          />
                        </div>
                        <input
                          value={joinTags(loop.related_characters)}
                          onChange={(event) =>
                            updateRoadmapLoopByIndex(chapter.chapter_number, loopIndex, (current) => ({
                              ...current,
                              related_characters: parseTags(event.target.value),
                            }))
                          }
                          placeholder="关联人物，多项可用逗号分隔"
                          className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                        />
                        <details className="rounded-xl border border-stone-200 bg-white p-3">
                          <summary className="cursor-pointer text-xs font-medium text-stone-600">更多伏笔字段</summary>
                          <div className="mt-3 space-y-3">
                            <textarea
                              value={joinTags(loop.resolution_requirements)}
                              onChange={(event) =>
                                updateRoadmapLoopByIndex(chapter.chapter_number, loopIndex, (current) => ({
                                  ...current,
                                  resolution_requirements: parseTags(event.target.value),
                                }))
                              }
                              rows={2}
                              placeholder="回收条件，多项可用逗号分隔"
                              className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                            />
                          </div>
                        </details>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="rounded-xl border border-dashed border-stone-300 px-3 py-4 text-sm text-stone-500">
                    当前章节还没有结构化伏笔。新增时请直接填写回收边界，避免线索无限拖延。
                  </p>
                )}
              </div>
            </div>
          </details>

          <details open className="rounded-2xl border border-stone-200 bg-stone-50 p-3">
            <summary className="cursor-pointer text-sm font-medium text-stone-700">结构告警</summary>
            <div className="mt-3 space-y-3">
              <input
                value={chapter.depends_on_chapters.join('，')}
                onChange={(event) =>
                  updateRoadmapChapterByNumber(chapter.chapter_number, (item) => ({
                    ...item,
                    depends_on_chapters: parseTags(event.target.value)
                      .map((value) => Number(value))
                      .filter((value) => Number.isFinite(value)),
                  }))
                }
                placeholder="承接章节，例如 12，13"
                className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
              />
              {selectedRoadmapChapterIssues.length > 0 ? (
                <div className="space-y-2">
                  {selectedRoadmapChapterIssues.map((issue, index) => (
                    <div
                      key={`${issue.type}-${index}`}
                      className={`rounded-2xl px-3 py-3 text-xs ${
                        issue.severity === 'fatal' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'
                      }`}
                    >
                      {issue.message}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rounded-2xl bg-emerald-50 px-3 py-3 text-xs text-emerald-700">
                  当前章节没有额外结构告警，可以继续细修或返回阶段工作台生成下一章。
                </p>
              )}
            </div>
          </details>
        </div>
      </section>
    )
  }

  return (
    <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-stone-900">
            {currentActionableArc ? `第 ${currentActionableArc.arc_number} 幕摘要` : '路线摘要'}
          </h4>
          {currentActionableArc ? (
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
              当前可行动阶段
            </span>
          ) : null}
        </div>
        <p className="text-sm leading-6 text-stone-700">
          {currentActionableArc?.purpose || '当前还没有可行动阶段，请先生成阶段骨架。'}
        </p>
        <div className="grid gap-2 text-xs text-stone-600">
          <div className="rounded-2xl bg-stone-50 px-3 py-3">
            未完成任务：{continuityState.open_tasks.length} 项 · 活跃伏笔：{continuityState.active_loops.length} 条
          </div>
          <div className="rounded-2xl bg-stone-50 px-3 py-3">
            最近事件：{continuityState.recent_events.slice(0, 2).map((item) => item.summary).join('；') || '暂无'}
          </div>
          {continuityState.relationship_states.length > 0 ? (
            <div className="rounded-2xl bg-stone-50 px-3 py-3">
              最新关系态：
              {continuityState.relationship_states
                .slice(0, 2)
                .map((item) => `${item.source_character}→${item.target_character}：${item.latest_summary || '未写摘要'}`)
                .join('；')}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
