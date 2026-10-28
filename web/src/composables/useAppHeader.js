import { reactive } from 'vue'

/**
 * Shared top-header state for the app shell (App.vue renders it).
 * App.vue sets a sensible default {crumb, title} on every route change;
 * a view (e.g. Result) may overwrite `title` afterwards with dynamic data
 * (the artifact file name). Contextual action buttons are injected via
 * <teleport to="#app-header-actions"> from the owning view.
 */
const state = reactive({
  crumb: '',
  title: ''
})

export function useAppHeader() {
  return state
}
