import { formatMoney, formatYen } from './format'
import type { InvestorProfileGeography } from './types'

export const PREFECTURES = [
  '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
  '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
  '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県',
  '岐阜県', '静岡県', '愛知県', '三重県',
  '滋賀県', '京都府', '大阪府', '兵庫県', '奈良県', '和歌山県',
  '鳥取県', '島根県', '岡山県', '広島県', '山口県',
  '徳島県', '香川県', '愛媛県', '高知県',
  '福岡県', '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県',
  '沖縄県',
] as const

const STRATEGY_LABELS: Record<string, string> = {
  buy_and_hold: '長期保有',
  flip: '再販',
  lease: '賃貸運用',
}

const IMPORT_METHOD_LABELS: Record<string, string> = {
  csv: 'CSV取り込み',
  chat: '対話入力',
}

const ASSET_CLASS_LABELS: Record<string, string> = {
  sfr: '戸建て',
  mf_2_4: '小規模一棟',
  mf_5_plus: '一棟マンション',
  condo: '区分マンション',
  townhouse: 'テラスハウス',
  land: '土地',
  multifamily: '共同住宅',
}

const PROPERTY_TYPE_LABELS: Record<string, string> = {
  sfr: '戸建て',
  condo: '区分マンション',
  townhouse: 'テラスハウス',
  multifamily: '共同住宅',
  land: '土地',
}

const RECOMMENDATION_LABELS: Record<string, string> = {
  HOLD: '保有継続',
  RAISE_RENT: '賃料改定',
  REFI: '借換検討',
  SELL: '売却検討',
  IMPROVE: '改修検討',
}

const RISK_TOLERANCE_LABELS: Record<string, string> = {
  low: '低め',
  moderate: '標準',
  medium: '標準',
  high: '高め',
}

const MARKET_OUTLOOK_LABELS: Record<string, string> = {
  neutral: '中立',
  bullish: '強気',
  bearish: '慎重',
}

const TRAJECTORY_LABELS: Record<string, string> = {
  none: '通常推移',
  neighborhood_trajectory: '周辺上昇トレンド',
  displacement_pressure: '需給ひっ迫',
  gentrifying: '更新進行',
}

const USER_ROLE_LABELS: Record<string, string> = {
  buyer: '購入主体',
  seller: '売却主体',
  both: '売買両方',
  investor: '投資家',
}

const LIFE_STAGE_LABELS: Record<string, string> = {
  first_time: '初回取得',
  relocating: '住み替え',
  investor: '投資拡大',
  downsizing: '縮小・売却',
  upgrading: '資産組み換え',
}

function compactJoin(parts: Array<string | null | undefined>): string {
  return parts.map((part) => part?.trim()).filter(Boolean).join(' ')
}

export function formatJpy(value: number | null | undefined): string {
  return formatMoney(value)
}

export function formatJpyCompact(value: number | null | undefined): string {
  return formatYen(value)
}

export function formatStrategyLabel(value?: string | null): string {
  if (!value) return '—'
  return STRATEGY_LABELS[value] ?? value
}

export function formatImportMethodLabel(value?: string | null): string {
  if (!value) return '—'
  return IMPORT_METHOD_LABELS[value] ?? value
}

export function formatAssetClassLabel(value?: string | null): string {
  if (!value) return '—'
  return ASSET_CLASS_LABELS[value] ?? value
}

export function formatPropertyTypeLabel(value?: string | null): string {
  if (!value) return '—'
  return PROPERTY_TYPE_LABELS[value] ?? ASSET_CLASS_LABELS[value] ?? value
}

export function formatRecommendationLabel(value?: string | null): string {
  if (!value) return '—'
  return RECOMMENDATION_LABELS[value] ?? value
}

export function formatRiskToleranceLabel(value?: string | null): string {
  if (!value) return '—'
  return RISK_TOLERANCE_LABELS[value] ?? value
}

export function formatMarketOutlookLabel(value?: string | null): string {
  if (!value) return '—'
  return MARKET_OUTLOOK_LABELS[value] ?? value
}

export function formatTrajectoryLabel(value?: string | null): string {
  if (!value) return '—'
  return TRAJECTORY_LABELS[value] ?? value
}

export function formatUserRoleLabel(value?: string | null): string {
  if (!value) return '—'
  return USER_ROLE_LABELS[value] ?? value
}

export function formatLifeStageLabel(value?: string | null): string {
  if (!value) return '—'
  return LIFE_STAGE_LABELS[value] ?? value
}

export function formatBooleanJa(value: boolean): string {
  return value ? 'あり' : 'なし'
}

export function formatJaDate(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('ja-JP')
}

export function formatJaDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ja-JP')
}

export function formatSearchRadius(radius?: number | null): string {
  if (radius === null || radius === undefined) return '—'
  return `${radius}km圏`
}

export function formatGeographySummary(
  geography?: InvestorProfileGeography | null,
): string {
  if (!geography) return '—'
  const parts = compactJoin([
    geography.zip ? `〒${geography.zip}` : null,
    geography.prefecture ?? geography.state,
    geography.municipality ?? geography.city,
    geography.ward,
    geography.neighborhood,
    geography.station ? `${geography.station}駅周辺` : null,
  ])
  return parts || '—'
}
