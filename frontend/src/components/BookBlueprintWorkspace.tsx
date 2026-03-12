/**
 * 蓝图工作台：在同一页面里逐层生成、编辑并确认整书蓝图。
 */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  confirmCharacterBlueprint,
  confirmRoadmap,
  confirmWorldBlueprint,
  generateCharacterBlueprint,
  generateConceptVariants,
  generateRoadmap,
  generateWorldBlueprint,
  regenerateConceptVariant,
  replanBlueprint,
  saveCreationIntent,
  selectConceptVariant,
} from '@/services/books'
import type {
  BookBlueprint,
  ChapterRoadmapItem,
  CharacterBlueprint,
  CreationIntent,
  WorldBlueprint,
} from '@/types'

interface BookBlueprintWorkspaceProps {
  bookId: number
  blueprint: BookBlueprint | undefined
}

function parseTags(value: string): string[] {
  return value
    .split(/[,，、\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function joinTags(values: string[]): string {
  return values.join('，')
}

function defaultIntent(): CreationIntent {
  return {
    genre: '',
    themes: [],
    tone: '',
    protagonist_prompt: '',
    conflict_prompt: '',
    ending_preference: '',
    forbidden_elements: [],
    length_preference: '12',
    target_experience: '',
    variant_preference: '',
  }
}

export function BookBlueprintWorkspace({ bookId, blueprint }: BookBlueprintWorkspaceProps) {
  const queryClient = useQueryClient()
  const [intentDraft, setIntentDraft] = useState<CreationIntent>(defaultIntent)
  const [themesText, setThemesText] = useState('')
  const [forbiddenText, setForbiddenText] = useState('')
  const [worldFeedback, setWorldFeedback] = useState('')
  const [characterFeedback, setCharacterFeedback] = useState('')
  const [roadmapFeedback, setRoadmapFeedback] = useState('')
  const [worldDraft, setWorldDraft] = useState<WorldBlueprint | null>(null)
  const [characterDraft, setCharacterDraft] = useState<CharacterBlueprint[]>([])
  const [roadmapDraft, setRoadmapDraft] = useState<ChapterRoadmapItem[]>([])
  const [replanStart, setReplanStart] = useState(1)
  const [replanReason, setReplanReason] = useState('')
  const [replanGuidance, setReplanGuidance] = useState('')

  const refreshBlueprint = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['books'] }),
      queryClient.invalidateQueries({ queryKey: ['bookBlueprint', bookId] }),
      queryClient.invalidateQueries({ queryKey: ['canon', bookId] }),
      queryClient.invalidateQueries({ queryKey: ['loopBoard'] }),
    ])
  }

  useEffect(() => {
    const nextIntent = blueprint?.intent ?? defaultIntent()
    setIntentDraft(nextIntent)
    setThemesText(joinTags(nextIntent.themes))
    setForbiddenText(joinTags(nextIntent.forbidden_elements))
    setWorldDraft(blueprint?.world_draft ?? blueprint?.world_confirmed ?? null)
    setCharacterDraft(blueprint?.character_draft ?? blueprint?.character_confirmed ?? [])
    setRoadmapDraft(blueprint?.roadmap_draft ?? blueprint?.roadmap_confirmed ?? [])
    const lockedRoadmap = blueprint?.roadmap_confirmed ?? []
    const lastChapter = lockedRoadmap.length > 0 ? lockedRoadmap[lockedRoadmap.length - 1]!.chapter_number : 1
    setReplanStart(Math.max(1, Math.min(replanStart, lastChapter)))
  }, [blueprint])

  const saveIntentMutation = useMutation({
    mutationFn: () =>
      saveCreationIntent(bookId, {
        ...intentDraft,
        themes: parseTags(themesText),
        forbidden_elements: parseTags(forbiddenText),
      }),
    onSuccess: async () => {
      toast.success('创作意图已保存')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateConceptMutation = useMutation({
    mutationFn: () => generateConceptVariants(bookId),
    onSuccess: async () => {
      toast.success('已生成 3 版候选方向')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const selectVariantMutation = useMutation({
    mutationFn: (variantId: number) => selectConceptVariant(bookId, variantId),
    onSuccess: async () => {
      toast.success('已选定候选方向，进入世界观阶段')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const regenerateVariantMutation = useMutation({
    mutationFn: (variantId: number) => regenerateConceptVariant(bookId, variantId),
    onSuccess: async () => {
      toast.success('已重生成这一版候选方向')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateWorldMutation = useMutation({
    mutationFn: () => generateWorldBlueprint(bookId, { feedback: worldFeedback }),
    onSuccess: async (payload) => {
      setWorldDraft(payload.world_draft)
      toast.success('世界观草稿已生成')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmWorldMutation = useMutation({
    mutationFn: () => confirmWorldBlueprint(bookId, worldDraft),
    onSuccess: async () => {
      toast.success('世界观已确认')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateCharacterMutation = useMutation({
    mutationFn: () => generateCharacterBlueprint(bookId, { feedback: characterFeedback }),
    onSuccess: async (payload) => {
      setCharacterDraft(payload.character_draft)
      toast.success('人物蓝图草稿已生成')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmCharacterMutation = useMutation({
    mutationFn: () => confirmCharacterBlueprint(bookId, characterDraft),
    onSuccess: async () => {
      toast.success('人物蓝图已确认')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateRoadmapMutation = useMutation({
    mutationFn: () => generateRoadmap(bookId, { feedback: roadmapFeedback }),
    onSuccess: async (payload) => {
      setRoadmapDraft(payload.roadmap_draft)
      toast.success('章节路线草稿已生成')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmRoadmapMutation = useMutation({
    mutationFn: () => confirmRoadmap(bookId, roadmapDraft),
    onSuccess: async () => {
      toast.success('整书蓝图已锁定，可以开始正文写作')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const replanMutation = useMutation({
    mutationFn: () =>
      replanBlueprint(bookId, {
        starting_chapter: replanStart,
        reason: replanReason,
        guidance: replanGuidance,
      }),
    onSuccess: async (payload) => {
      setRoadmapDraft(payload.roadmap_confirmed)
      toast.success('未来章节已生成新蓝图版本')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const selectedVariantId = blueprint?.selected_variant_id
  const canGenerateCharacters = Boolean(blueprint?.world_confirmed)
  const canGenerateRoadmap = Boolean(blueprint?.world_confirmed && blueprint?.character_confirmed.length)
  const revisions = blueprint?.revisions ?? []
  const roadmapToShow = blueprint?.roadmap_confirmed.length ? blueprint.roadmap_confirmed : roadmapDraft
  const activeRevisionLabel = useMemo(() => {
    const active = revisions.find((item) => item.is_active)
    return active ? `v${active.revision_number}` : '未锁定'
  }, [revisions])

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-stone-800">创作蓝图工作台</h3>
            <p className="mt-1 text-sm text-stone-500">
              当前状态：{blueprint?.status ?? '未初始化'} · 当前步骤：{blueprint?.current_step ?? 'intent'} · 生效版本：{activeRevisionLabel}
            </p>
          </div>
          {revisions.length > 0 && (
            <div className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-600">
              已有 {revisions.length} 个蓝图版本
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">题材</label>
            <input
              value={intentDraft.genre}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, genre: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">整体基调</label>
            <input
              value={intentDraft.tone}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, tone: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">主题关键词</label>
            <input
              value={themesText}
              onChange={(e) => setThemesText(e.target.value)}
              placeholder="多个关键词用逗号分隔"
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">目标体验</label>
            <input
              value={intentDraft.target_experience}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, target_experience: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">主角提示</label>
            <textarea
              value={intentDraft.protagonist_prompt}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, protagonist_prompt: e.target.value }))}
              rows={3}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">核心冲突</label>
            <textarea
              value={intentDraft.conflict_prompt}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, conflict_prompt: e.target.value }))}
              rows={3}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">结局倾向</label>
            <input
              value={intentDraft.ending_preference}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, ending_preference: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">候选分歧偏好</label>
            <select
              value={intentDraft.variant_preference}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, variant_preference: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
            >
              <option value="">默认分歧策略</option>
              <option value="人物差异优先">人物差异优先</option>
              <option value="世界差异优先">世界差异优先</option>
              <option value="结局差异优先">结局差异优先</option>
              <option value="尽量风格拉开">尽量风格拉开</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">禁用元素</label>
            <input
              value={forbiddenText}
              onChange={(e) => setForbiddenText(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => saveIntentMutation.mutate()}
            disabled={saveIntentMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saveIntentMutation.isPending ? '保存中…' : '保存创作意图'}
          </button>
          <button
            onClick={() => generateConceptMutation.mutate()}
            disabled={generateConceptMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateConceptMutation.isPending ? '生成中…' : '生成 3 版候选方向'}
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">候选方向</h3>
          <p className="mt-1 text-sm text-stone-500">先选定一条整书方向，再进入世界观、人物和章节路线细化。</p>
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {(blueprint?.concept_variants ?? []).map((variant) => (
            <article
              key={variant.id ?? variant.variant_no}
              className={`rounded-xl border p-4 ${
                selectedVariantId === variant.id ? 'border-emerald-500 bg-emerald-50/60' : 'border-stone-200'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-stone-800">方向 {variant.variant_no}</h4>
                {selectedVariantId === variant.id && <span className="text-xs text-emerald-700">已选中</span>}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-stone-600">
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">主驱动</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.core_driver || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">策略</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.variant_strategy || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">冲突源</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.conflict_source || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">世界结构</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.world_structure || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">主角弧线</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.protagonist_arc_mode || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">气质</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.tone_signature || '未标注'}</p>
                </div>
              </div>
              <p className="mt-3 text-sm font-medium text-stone-800">{variant.hook}</p>
              <p className="mt-2 text-sm text-stone-600">{variant.world_pitch}</p>
              <p className="mt-2 text-sm text-stone-600">{variant.main_arc_pitch}</p>
              <p className="mt-2 text-sm text-stone-500">结局倾向：{variant.ending_pitch}</p>
              {variant.diversity_note && (
                <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  {variant.diversity_note}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {variant.differentiators.map((item) => (
                  <span key={item} className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">
                    {item}
                  </span>
                ))}
              </div>
              <div className="mt-4 grid gap-2">
                <button
                  onClick={() => variant.id && selectVariantMutation.mutate(variant.id)}
                  disabled={!variant.id || selectVariantMutation.isPending}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-white disabled:opacity-50"
                >
                  选择这一版
                </button>
                <button
                  onClick={() => variant.id && regenerateVariantMutation.mutate(variant.id)}
                  disabled={
                    !variant.id ||
                    Boolean(selectedVariantId) ||
                    regenerateVariantMutation.isPending ||
                    selectVariantMutation.isPending
                  }
                  className="w-full rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-700 hover:bg-stone-200 disabled:opacity-50"
                >
                  {regenerateVariantMutation.isPending ? '重生成中…' : '仅重生成这一版'}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">世界观蓝图</h3>
          <p className="mt-1 text-sm text-stone-500">先锁定世界硬规则，再让人物和章节路线在这套约束内展开。</p>
        </div>
        <textarea
          value={worldFeedback}
          onChange={(e) => setWorldFeedback(e.target.value)}
          rows={2}
          placeholder="可选：补充本层微调要求，例如“更偏江湖感，不要过强神怪设定”。"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateWorldMutation.mutate()}
            disabled={!selectedVariantId || generateWorldMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateWorldMutation.isPending ? '生成中…' : '生成世界观草稿'}
          </button>
          <button
            onClick={() => confirmWorldMutation.mutate()}
            disabled={!worldDraft || confirmWorldMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmWorldMutation.isPending ? '确认中…' : '确认世界观'}
          </button>
        </div>
        {worldDraft && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-stone-500 mb-1">世界概述</label>
              <textarea
                value={worldDraft.setting_summary}
                onChange={(e) => setWorldDraft({ ...worldDraft, setting_summary: e.target.value })}
                rows={4}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-500 mb-1">力量体系</label>
              <textarea
                value={worldDraft.power_system}
                onChange={(e) => setWorldDraft({ ...worldDraft, power_system: e.target.value })}
                rows={3}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-stone-500 mb-1">阵营</label>
                <textarea
                  value={joinTags(worldDraft.factions)}
                  onChange={(e) => setWorldDraft({ ...worldDraft, factions: parseTags(e.target.value) })}
                  rows={4}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-500 mb-1">禁改事实</label>
                <textarea
                  value={joinTags(worldDraft.taboo_rules)}
                  onChange={(e) => setWorldDraft({ ...worldDraft, taboo_rules: parseTags(e.target.value) })}
                  rows={4}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">不可变规则</p>
              {worldDraft.immutable_rules.map((rule, index) => (
                <div key={`${rule.key}-${index}`} className="grid gap-2 md:grid-cols-[180px_minmax(0,1fr)_120px]">
                  <input
                    value={rule.key}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        immutable_rules: worldDraft.immutable_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, key: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={rule.description}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        immutable_rules: worldDraft.immutable_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, description: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={rule.category ?? ''}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        immutable_rules: worldDraft.immutable_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, category: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">人物蓝图</h3>
          <p className="mt-1 text-sm text-stone-500">角色核心动机、不可突变特质和关系约束会作为后续正文的强校验来源。</p>
        </div>
        <textarea
          value={characterFeedback}
          onChange={(e) => setCharacterFeedback(e.target.value)}
          rows={2}
          placeholder="可选：补充本层微调要求，例如“主角不要太正统，要更复杂一些”。"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateCharacterMutation.mutate()}
            disabled={!canGenerateCharacters || generateCharacterMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateCharacterMutation.isPending ? '生成中…' : '生成人物蓝图'}
          </button>
          <button
            onClick={() => confirmCharacterMutation.mutate()}
            disabled={characterDraft.length === 0 || confirmCharacterMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmCharacterMutation.isPending ? '确认中…' : '确认人物蓝图'}
          </button>
        </div>
        <div className="space-y-3">
          {characterDraft.map((character, index) => (
            <article key={`${character.name}-${index}`} className="rounded-xl border border-stone-200 p-4 space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">姓名</label>
                  <input
                    value={character.name}
                    onChange={(e) =>
                      setCharacterDraft((prev) =>
                        prev.map((item, itemIndex) => (itemIndex === index ? { ...item, name: e.target.value } : item)),
                      )
                    }
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">定位</label>
                  <input
                    value={character.role}
                    onChange={(e) =>
                      setCharacterDraft((prev) =>
                        prev.map((item, itemIndex) => (itemIndex === index ? { ...item, role: e.target.value } : item)),
                      )
                    }
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <textarea
                value={character.public_persona}
                onChange={(e) =>
                  setCharacterDraft((prev) =>
                    prev.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, public_persona: e.target.value } : item,
                    ),
                  )
                }
                rows={2}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={character.core_motivation}
                onChange={(e) =>
                  setCharacterDraft((prev) =>
                    prev.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, core_motivation: e.target.value } : item,
                    ),
                  )
                }
                placeholder="核心动机"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={character.fatal_flaw}
                onChange={(e) =>
                  setCharacterDraft((prev) =>
                    prev.map((item, itemIndex) => (itemIndex === index ? { ...item, fatal_flaw: e.target.value } : item)),
                  )
                }
                placeholder="致命缺口"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">章节路线</h3>
          <p className="mt-1 text-sm text-stone-500">锁定整书章节走向后，后续 scene 写作会在该路线内做受控扩写。</p>
        </div>
        <textarea
          value={roadmapFeedback}
          onChange={(e) => setRoadmapFeedback(e.target.value)}
          rows={2}
          placeholder="可选：补充本层微调要求，例如“前 3 章开局更猛，中段节奏更压抑”。"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateRoadmapMutation.mutate()}
            disabled={!canGenerateRoadmap || generateRoadmapMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateRoadmapMutation.isPending ? '生成中…' : '生成章节路线'}
          </button>
          <button
            onClick={() => confirmRoadmapMutation.mutate()}
            disabled={roadmapDraft.length === 0 || confirmRoadmapMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmRoadmapMutation.isPending ? '锁定中…' : '锁定整书蓝图'}
          </button>
        </div>
        <div className="space-y-3">
          {roadmapDraft.map((item, index) => (
            <article key={item.chapter_number} className="rounded-xl border border-stone-200 p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-stone-800">第 {item.chapter_number} 章</h4>
                <span className="text-xs text-stone-500">
                  计划线索 {item.planned_loops.length} 条
                </span>
              </div>
              <input
                value={item.title}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) => (rowIndex === index ? { ...row, title: e.target.value } : row)),
                  )
                }
                placeholder="章节标题"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <textarea
                value={item.goal}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) => (rowIndex === index ? { ...row, goal: e.target.value } : row)),
                  )
                }
                rows={2}
                placeholder="章节目标"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <textarea
                value={item.core_conflict}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, core_conflict: e.target.value } : row,
                    ),
                  )
                }
                rows={2}
                placeholder="核心冲突"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={item.turning_point}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, turning_point: e.target.value } : row,
                    ),
                  )
                }
                placeholder="关键转折"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={item.closure_function}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, closure_function: e.target.value } : row,
                    ),
                  )
                }
                placeholder="结尾功能"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                人物推进：{item.character_progress.length > 0 ? item.character_progress.join('；') : '未指定'}
              </div>
            </article>
          ))}
          {roadmapToShow.length === 0 && (
            <div className="rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
              还没有章节路线。请先确认世界观和人物蓝图，再生成整书章节走向。
            </div>
          )}
        </div>
      </section>

      {blueprint?.status === 'locked' && (
        <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
          <div>
            <h3 className="text-base font-semibold text-stone-800">未来章节重规划</h3>
            <p className="mt-1 text-sm text-stone-500">只允许重规划未来未发布章节，不会改写已发布内容及其核心事实。</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-stone-500 mb-1">起始章节</label>
              <input
                type="number"
                min={1}
                value={replanStart}
                onChange={(e) => setReplanStart(Number(e.target.value))}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-stone-500 mb-1">重规划原因</label>
              <input
                value={replanReason}
                onChange={(e) => setReplanReason(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
          <textarea
            value={replanGuidance}
            onChange={(e) => setReplanGuidance(e.target.value)}
            rows={3}
            placeholder="例如：保留主线复仇，但让中段感情线更痛，增加误会与错位。"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          />
          <button
            onClick={() => replanMutation.mutate()}
            disabled={replanMutation.isPending}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {replanMutation.isPending ? '重规划中…' : '生成新蓝图版本'}
          </button>
          <div className="rounded-xl bg-stone-50 p-3 text-sm text-stone-600">
            版本历史：
            {revisions.length > 0 ? (
              <ul className="mt-2 space-y-1">
                {revisions.map((item) => (
                  <li key={item.id}>
                    v{item.revision_number}
                    {item.is_active ? '（当前生效）' : ''}
                    ：{item.change_reason || '未填写原因'}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="ml-2">暂无版本记录</span>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
