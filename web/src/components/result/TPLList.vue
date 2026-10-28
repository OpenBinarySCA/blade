<template>
  <!-- Col 2: EXTRACTED FILES -->
  <section class="col-files">
    <div class="col-head">
      <span class="eyebrow">EXTRACTED FILES</span>
      <span class="head-count">{{ files.length }}</span>
    </div>
    <div class="col-body">
      <div v-if="processing" class="busy">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.2" class="spinner"><path stroke-linecap="round" d="M12 3a9 9 0 1 0 9 9" /></svg>
        <span>Extracting files…</span>
      </div>
      <button
        v-for="f in files"
        :key="f.bi"
        class="file-row"
        :class="{ selected: selFile === f.bi }"
        @click="selectFile(f.bi)"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--text-2)" stroke-width="1.6" class="file-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M13 3v6h6" /></svg>
        <span class="file-text">
          <span class="file-name">{{ f.name }}</span>
          <span class="file-identity">{{ f.identity }}</span>
        </span>
        <span v-if="f.hasRisk" class="risk-dot"></span>
        <span class="file-count">{{ f.count }}</span>
      </button>
    </div>
  </section>

  <!-- Col 3: DETECTED COMPONENTS -->
  <section class="col-components">
    <div class="col-head">
      <span class="eyebrow">DETECTED COMPONENTS</span>
      <div class="head-spacer"></div>
      <span class="scope">{{ scopeLabel }}</span>
    </div>
    <div class="col-body comp-body">
      <div v-if="processing" class="busy big">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2.2" class="spinner"><path stroke-linecap="round" d="M12 3a9 9 0 1 0 9 9" /></svg>
        <span>Identifying components…</span>
      </div>
      <template v-else>
        <div v-for="card in componentCards" :key="card.label" class="sub-card">
          <div class="sub-head">
            <span class="sub-tag"></span>
            <span class="sub-label">{{ card.label }}</span>
            <span class="sub-count">{{ card.count }}</span>
          </div>
          <div v-if="card.empty" class="sub-empty">{{ card.emptyText }}</div>
          <button
            v-for="c in card.items"
            :key="c.occKey"
            class="comp-row"
            :class="{ selected: drawerOcc === c.occKey }"
            @click="openDrawer(c.occKey)"
          >
            <span class="comp-left">
              <span class="comp-name">{{ c.name }}</span>
              <span v-if="c.hasModule" class="module-chip">{{ c.module }}</span>
              <span v-if="c.hasFileLabel" class="in-file">in {{ c.fileLabel }}</span>
            </span>
            <span class="comp-version" :style="{ color: c.version ? 'var(--text-2)' : 'var(--text-3)' }">{{ c.version || '—' }}</span>
            <span class="comp-dot-wrap"><span class="comp-dot" :class="dotClass(c.confidence)"></span></span>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" stroke-width="1.8" class="comp-chev"><path stroke-linecap="round" stroke-linejoin="round" d="m9 6 6 6-6 6" /></svg>
          </button>
        </div>
      </template>
    </div>
  </section>

  <!-- Col 4: COMPONENT INFORMATION -->
  <LibraryCard v-if="selectedOccurrence" :occurrence="selectedOccurrence" @close="closeDrawer" />
</template>

<script setup>
import { computed } from 'vue'
import { useComposition, isReviewConfidence, isUnknownConfidence } from '../../composables/useComposition'
import LibraryCard from './LibraryCard.vue'

const props = defineProps({
  resultData: { type: Object, default: null },
  processing: { type: Boolean, default: false }
})

const rd = computed(() => props.resultData)
const {
  selFile, drawerOcc, files, componentCards, scopeLabel, selectedOccurrence,
  selectFile, openDrawer, closeDrawer
} = useComposition(rd)

function dotClass(c) {
  return isReviewConfidence(c) ? 'review' : isUnknownConfidence(c) ? 'unknown' : 'high'
}
</script>

<style scoped>
/* Shared column chrome */
.col-files,
.col-components {
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r3);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.col-files {
  width: 260px;
  flex-shrink: 0;
}
.col-components {
  flex: 1;
  min-width: 0;
}

.col-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 16px;
  border-bottom: 1px solid var(--line);
  background: var(--surface-2);
}
.col-files .col-head {
  padding: 11px 15px;
  gap: 7px;
}
.eyebrow {
  font-size: var(--t-micro);
  font-weight: 700;
  letter-spacing: .06em;
  color: var(--text-3);
}
.head-count {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
}
.head-spacer {
  flex: 1;
}
.scope {
  font-size: var(--t-micro);
  color: var(--text-3);
}

.col-body {
  flex: 1;
  overflow-y: auto;
}

.busy {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 44px 16px;
  color: var(--text-3);
  font-size: var(--t-sm);
}
.busy.big {
  padding: 50px 16px;
}
.spinner {
  animation: spin .9s linear infinite;
}

/* Col 2 file rows */
.file-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 13px;
  text-align: left;
  border-bottom: 1px solid var(--line-soft);
  transition: background .12s;
}
.file-row:hover {
  background: var(--surface-3);
}
.file-row.selected {
  background: var(--accent-dim);
  box-shadow: inset 3px 0 0 var(--accent);
}
.file-icon {
  flex-shrink: 0;
}
.file-text {
  flex: 1;
  min-width: 0;
}
.file-name {
  display: block;
  font-family: var(--mono-font);
  font-size: var(--t-sm);
  font-weight: 500;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.file-identity {
  display: block;
  font-size: var(--t-micro);
  color: var(--text-3);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.risk-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--warn);
  flex-shrink: 0;
}
.file-count {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
  flex-shrink: 0;
}

/* Col 3 component cards */
.comp-body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sub-card {
  border: 1px solid var(--line);
  border-radius: var(--r2);
  overflow: hidden;
  background: var(--surface-1);
}
.sub-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 13px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--line);
}
.sub-tag {
  width: 6px;
  height: 6px;
  border-radius: 2px;
  background: var(--text-3);
  flex-shrink: 0;
}
.sub-label {
  font-size: var(--t-micro);
  font-weight: 700;
  letter-spacing: .05em;
  color: var(--text-3);
}
.sub-count {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
}
.sub-empty {
  padding: 14px 13px;
  color: var(--text-3);
  font-size: var(--t-meta);
  opacity: .8;
}

.comp-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 16px;
  text-align: left;
  border-top: 1px solid var(--line-soft);
  transition: background .12s;
}
.comp-row:hover {
  background: var(--surface-2);
}
.comp-row.selected {
  background: var(--accent-dim);
}
.comp-left {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.comp-name {
  font-family: var(--mono-font);
  font-size: var(--t-sm);
  font-weight: 500;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.module-chip {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-2);
  background: var(--surface-3);
  border-radius: var(--r1);
  padding: 1px 6px;
  flex-shrink: 0;
}
.in-file {
  font-size: var(--t-micro);
  color: var(--text-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.comp-version {
  flex-shrink: 0;
  font-family: var(--mono-font);
  font-size: var(--t-micro);
}
.comp-dot-wrap {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.comp-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.comp-dot.high {
  background: var(--text-3);
  opacity: .45;
}
.comp-dot.review {
  background: var(--warn);
}
.comp-dot.unknown {
  border: 1.5px solid var(--text-3);
  box-sizing: border-box;
}
.comp-chev {
  flex-shrink: 0;
  opacity: .4;
}
</style>
