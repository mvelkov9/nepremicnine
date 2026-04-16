import type { ActivityFeedItem } from '../types/api'

type TranslateFn = (key: string, params?: Record<string, unknown>) => string

const ACTIVITY_CATEGORY_KEYS: Record<string, string> = {
  prediction: 'workbench.activityCategory.prediction',
  analysis: 'workbench.activityCategory.analysis',
  prepare: 'workbench.activityCategory.prepare',
  training: 'workbench.activityCategory.training',
  dataset: 'workbench.activityCategory.dataset',
  model_run: 'workbench.activityCategory.modelRun',
  workspace_created: 'workbench.activityCategory.savedView',
  workspace_updated: 'workbench.activityCategory.savedView',
  workspace_deleted: 'workbench.activityCategory.savedView',
  watchlist_added: 'workbench.activityCategory.watchlist',
  watchlist_removed: 'workbench.activityCategory.watchlist',
}

const ACTIVITY_FALLBACK_KEYS: Record<string, string> = {
  prediction: 'workbench.activityFallback.prediction',
  analysis: 'workbench.activityFallback.analysis',
  prepare: 'workbench.activityFallback.prepare',
  training: 'workbench.activityFallback.training',
  dataset: 'workbench.activityFallback.dataset',
  model_run: 'workbench.activityFallback.modelRun',
  workspace_created: 'workbench.activityFallback.workspaceCreated',
  workspace_updated: 'workbench.activityFallback.workspaceUpdated',
  workspace_deleted: 'workbench.activityFallback.workspaceDeleted',
  watchlist_added: 'workbench.activityFallback.watchlistAdded',
  watchlist_removed: 'workbench.activityFallback.watchlistRemoved',
}

export function humanizeActivityCategory(category?: string | null) {
  return String(category || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

export function activityCategoryLabel(category: string | null | undefined, t: TranslateFn) {
  const translationKey = category ? ACTIVITY_CATEGORY_KEYS[category] : ''
  if (translationKey) {
    const translated = t(translationKey)
    if (translated !== translationKey) return translated
  }
  return humanizeActivityCategory(category)
}

export function activityCategorySeverity(category?: string | null) {
  switch (category) {
    case 'prediction':
    case 'analysis':
      return 'info'
    case 'prepare':
    case 'training':
    case 'model_run':
      return 'warn'
    case 'dataset':
      return 'success'
    case 'workspace_created':
    case 'workspace_updated':
    case 'watchlist_added':
      return 'contrast'
    case 'workspace_deleted':
    case 'watchlist_removed':
      return 'secondary'
    default:
      return 'secondary'
  }
}

export function activitySummary(item: ActivityFeedItem, t: TranslateFn) {
  if (item.body) return item.body

  const translationKey = ACTIVITY_FALLBACK_KEYS[item.category]
  if (translationKey) {
    const translated = t(translationKey)
    if (translated !== translationKey) return translated
  }

  return humanizeActivityCategory(item.category)
}
