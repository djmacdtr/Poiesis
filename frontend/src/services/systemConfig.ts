/**
 * 系统配置 API 服务
 */
import { get, post } from '@/services/http'

/** 系统配置状态（不含明文 Key） */
export interface SystemConfigStatus {
  has_openai_api_key: boolean
  has_anthropic_api_key: boolean
  has_siliconflow_api_key: boolean
  embedding_provider: 'local' | 'remote' | null
  embedding_provider_effective: 'local' | 'remote'
  embedding_service_health: {
    provider: 'remote'
    reachable: boolean
    url: string
    status: 'ok' | 'unreachable' | 'error'
    error_msg: string | null
    checked_at: string
  } | null
  default_chapter_count: number | null
}

/** 保存系统配置请求体 */
export interface SystemConfigRequest {
  openai_api_key?: string
  anthropic_api_key?: string
  siliconflow_api_key?: string
  embedding_provider?: 'local' | 'remote'
  default_chapter_count?: number
}

/** 获取当前系统配置状态 */
export function getSystemConfig(): Promise<SystemConfigStatus> {
  return get<SystemConfigStatus>('/api/system/config')
}

/** 保存系统配置 */
export function saveSystemConfig(data: SystemConfigRequest): Promise<SystemConfigStatus> {
  return post<SystemConfigStatus>('/api/system/config', data)
}

/** 初始化世界 */
export function initWorld(seedPath?: string): Promise<{ status: string; message: string }> {
  return post('/api/system/init', seedPath ? { seed_path: seedPath } : {})
}
