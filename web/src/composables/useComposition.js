import { ref, computed } from 'vue'

/**
 * useComposition — single source of truth for the Result "Workbench".
 *
 * Models the data's true hierarchy:
 *   artifact (input file) → extracted files (binaries) → components (deps) → detail
 *
 * Crucially separates a binary's IDENTITY (`main_program`) from its
 * DEPENDENCIES (static/dynamic). Identity is shown on the file row and is
 * NOT counted among "components". Version & confidence come from versions[0].
 *
 * @param resultData  ref/computed yielding the full result object
 *                    ({ input_file, extraction, detection_results } | null)
 */

const LINKAGE_TEXT = { main: 'main', static: 'static', dynamic: 'dynamic' }

export function basename(p) {
  if (!p) return ''
  const parts = String(p).split('/')
  return parts[parts.length - 1] || ''
}

export function formatSizeKb(kb) {
  if (kb == null || isNaN(kb)) return ''
  if (kb >= 1024) return (kb / 1024).toFixed(1) + ' MB'
  return Math.round(kb) + ' KB'
}

export function isReviewConfidence(c) {
  return c === 'medium' || c === 'low'
}
export function isUnknownConfidence(c) {
  return !c || c === 'unknown'
}
export function confLabel(c) {
  return c && c !== 'unknown' ? c : 'unknown'
}

function occKey(bi, linkage, name, module, i) {
  return `${bi}|${linkage}|${name}|${module || '-'}|${i}`
}

function ver(lib) {
  const v = lib && lib.versions && lib.versions[0]
  return v && v.version && v.version !== 'unknown' ? v.version : null
}
function conf(lib) {
  const v = lib && lib.versions && lib.versions[0]
  return (v && v.confidence) || 'unknown'
}

export function useComposition(resultData) {
  const selFile = ref(null)     // null = all files; else binary index
  const drawerOcc = ref(null)   // occurrence key | null

  const bins = computed(() => {
    const dr = resultData.value && resultData.value.detection_results
    return Array.isArray(dr) ? dr : []
  })
  const single = computed(() => bins.value.length === 1)

  function binName(r, bi) {
    const tb = (r.analysis_data && r.analysis_data.target_binary) || {}
    return tb.binary_name || basename(tb.relative_path) || basename(r.binary_path) || `binary ${bi + 1}`
  }

  // ---- occurrence index (unique keys; the dup-key fix) ----
  const occIndex = computed(() => {
    const idx = {}
    bins.value.forEach((r, bi) => {
      const name = binName(r, bi)
      const push = (lib, linkage, i) => {
        if (!lib || !lib.name) return
        idx[occKey(bi, linkage, lib.name, lib.component_name, i)] = { lib, bi, binary: name, linkage }
      }
      if (r.main_program) push(r.main_program, 'main', 0)
      ;(r.detected_libraries || []).forEach((l, i) => push(l, 'static', i))
      ;(r.detected_dynamic_libraries || []).forEach((l, i) => push(l, 'dynamic', i))
    })
    return idx
  })

  // ---- cross-binary map for "also found in" ----
  const cmap = computed(() => {
    const m = new Map()
    bins.value.forEach((r, bi) => {
      const name = binName(r, bi)
      const add = (lib, linkage) => {
        if (!lib || !lib.name) return
        const k = lib.name + '|' + (ver(lib) || '')
        if (!m.has(k)) m.set(k, [])
        m.get(k).push({ bi, binary: name, linkage, module: lib.component_name || null })
      }
      add(r.main_program, 'main')
      ;(r.detected_libraries || []).forEach((l) => add(l, 'static'))
      ;(r.detected_dynamic_libraries || []).forEach((l) => add(l, 'dynamic'))
    })
    return m
  })

  // ---- per-file view models (Col 2) ----
  const files = computed(() =>
    bins.value.map((r, bi) => {
      const sd = r.detected_libraries || []
      const dd = r.detected_dynamic_libraries || []
      const deps = [...sd, ...dd]
      const hasRisk = deps.some((l) => isReviewConfidence(conf(l)))
      const m = r.main_program
      const identity = m && m.name ? m.name + (ver(m) ? ' ' + ver(m) : '') : 'unidentified'
      return {
        bi,
        name: binName(r, bi),
        identity,
        count: deps.length,
        hasRisk,
        failed: !!(r.error_message || r.succeed === false)
      }
    })
  )

  // ---- totals (DEPENDENCIES only — main/identity is not a component) ----
  const totals = computed(() => {
    let total = 0
    let high = 0
    let review = 0
    bins.value.forEach((r) => {
      const deps = [...(r.detected_libraries || []), ...(r.detected_dynamic_libraries || [])]
      deps.forEach((l) => {
        total++
        const c = conf(l)
        if (c === 'high') high++
        else if (isReviewConfidence(c)) review++
      })
    })
    return { total, binaries: bins.value.length, high, review, hasReview: review > 0 }
  })

  // ---- scoped component cards (Col 3): two cards (static / dynamic) ----
  function itemVM(lib, bi, linkage, i) {
    return {
      occKey: occKey(bi, linkage, lib.name, lib.component_name, i),
      name: lib.name,
      module: lib.component_name && lib.component_name !== lib.name ? lib.component_name : null,
      hasModule: !!(lib.component_name && lib.component_name !== lib.name),
      hasFileLabel: selFile.value === null && !single.value,
      fileLabel: binName(bins.value[bi], bi),
      version: ver(lib),
      confidence: conf(lib)
    }
  }

  const scope = computed(() =>
    selFile.value === null
      ? bins.value.map((r, bi) => ({ r, bi }))
      : (bins.value[selFile.value] ? [{ r: bins.value[selFile.value], bi: selFile.value }] : [])
  )

  const componentCards = computed(() => {
    const stat = []
    const dyn = []
    scope.value.forEach(({ r, bi }) => {
      ;(r.detected_libraries || []).forEach((l, i) => { if (l && l.name) stat.push(itemVM(l, bi, 'static', i)) })
      ;(r.detected_dynamic_libraries || []).forEach((l, i) => { if (l && l.name) dyn.push(itemVM(l, bi, 'dynamic', i)) })
    })
    return [
      { label: 'STATIC DEPENDENCIES', count: stat.length, empty: stat.length === 0, emptyText: 'No statically-linked components', items: stat },
      { label: 'DYNAMIC DEPENDENCIES', count: dyn.length, empty: dyn.length === 0, emptyText: 'No dynamically-linked components', items: dyn }
    ]
  })

  const scopeLabel = computed(() =>
    selFile.value === null ? 'all files' : binName(bins.value[selFile.value], selFile.value)
  )

  // ---- selected occurrence (Col 4) ----
  const selectedOccurrence = computed(() => {
    const ref0 = drawerOcc.value ? occIndex.value[drawerOcc.value] : null
    if (!ref0) return null
    const lib = ref0.lib
    const k = lib.name + '|' + (ver(lib) || '')
    const others = (cmap.value.get(k) || []).filter(
      (o) => !(o.bi === ref0.bi && o.linkage === ref0.linkage && (o.module || null) === (lib.component_name || null))
    )
    return {
      name: lib.name,
      module: lib.component_name && lib.component_name !== lib.name ? lib.component_name : null,
      hasModule: !!(lib.component_name && lib.component_name !== lib.name),
      giturl: lib.giturl || null,
      version: ver(lib),
      versionKnown: !!ver(lib),
      linkage: ref0.linkage,
      confidence: conf(lib),
      description: lib.description || '',
      userExplanation: lib.user_explanation || '',
      evidences: lib.evidences || [],
      inBinaryName: ref0.binary,
      alsoFoundIn: others.map((o) => ({ binary: o.binary, linkText: o.linkage + (o.module ? ' · ' + o.module : '') }))
    }
  })

  // ---- report view ----
  const report = computed(() => {
    const inf = resultData.value && resultData.value.input_file
    const t = totals.value
    const reportFiles = bins.value.map((r, bi) => {
      const m = r.main_program
      const identity = m && m.name ? m.name + (ver(m) ? ' ' + ver(m) : '') + ' · ' + confLabel(conf(m)) : 'unidentified'
      const mk = (arr) =>
        (arr || []).filter((l) => l && l.name).map((l) => ({
          name: l.name,
          module: l.component_name && l.component_name !== l.name ? l.component_name : null,
          hasModule: !!(l.component_name && l.component_name !== l.name),
          version: ver(l) || '—',
          confidence: conf(l),
          why: l.user_explanation || l.description || ''
        }))
      const sd = mk(r.detected_libraries)
      const dd = mk(r.detected_dynamic_libraries)
      return {
        name: binName(r, bi),
        identity,
        identityDesc: (m && m.description) || '',
        subs: [
          { label: 'STATIC DEPENDENCIES', count: sd.length, show: sd.length > 0, items: sd },
          { label: 'DYNAMIC DEPENDENCIES', count: dd.length, show: dd.length > 0, items: dd }
        ]
      }
    })
    const headline = `${t.total} ${t.total === 1 ? 'component' : 'components'} across ${t.binaries} ${t.binaries === 1 ? 'file' : 'files'}`
    const summary =
      `BLADE identified ${t.high} high-confidence component${t.high === 1 ? '' : 's'}` +
      (t.review > 0 ? ` and flagged ${t.review} for review` : '') +
      (inf ? `. Source: ${shortType(inf.readable_type)} · ${inf.file_size}.` : '.')
    return { headline, summary, files: reportFiles }
  })

  // ---- actions ----
  const selectFile = (bi) => {
    selFile.value = selFile.value === bi ? null : bi   // re-click → back to all
    drawerOcc.value = null
  }
  const openDrawer = (key) => { drawerOcc.value = key }
  const closeDrawer = () => { drawerOcc.value = null }

  return {
    // state
    selFile,
    drawerOcc,
    // derived
    bins,
    single,
    files,
    totals,
    componentCards,
    scopeLabel,
    selectedOccurrence,
    report,
    // actions
    selectFile,
    openDrawer,
    closeDrawer
  }
}

/** Short, readable label from the verbose `file` type string. */
export function shortType(readableType) {
  if (!readableType) return ''
  const seg = String(readableType).split(',')[0].trim()
  return seg.length > 28 ? seg.slice(0, 27) + '…' : seg
}
