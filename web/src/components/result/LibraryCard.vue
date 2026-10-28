<template>
  <!-- Col 4: COMPONENT INFORMATION (slides in when a component is selected) -->
  <section class="info-col">
    <div class="info-head">
      <span class="info-eyebrow">COMPONENT INFORMATION</span>
      <div class="info-spacer"></div>
      <button class="info-close" aria-label="Close" @click="$emit('close')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M6 6l12 12M18 6 6 18" /></svg>
      </button>
    </div>

    <div class="info-body">
      <div class="info-top">
        <div class="name-row">
          <a
            v-if="occurrence.giturl"
            :href="occurrence.giturl"
            target="_blank"
            rel="noopener noreferrer"
            class="comp-name link"
          >
            {{ occurrence.name }}
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="ext-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4M14 4h6m0 0v6m0-6L9 15" /></svg>
          </a>
          <span v-else class="comp-name">{{ occurrence.name }}</span>
          <span v-if="occurrence.hasModule" class="module-chip">{{ occurrence.module }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-version" :class="{ unknown: !occurrence.versionKnown }">{{ occurrence.versionKnown ? occurrence.version : 'version unknown' }}</span>
          <span class="meta-linkage">{{ occurrence.linkage }}</span>
          <span class="meta-conf" :style="{ color: confColor }">
            <span class="conf-dot" :class="dotClass"></span>{{ confText }}
          </span>
        </div>
      </div>

      <div class="info-sections">
        <p v-if="occurrence.description" class="desc">{{ occurrence.description }}</p>

        <template v-if="occurrence.userExplanation">
          <div class="label">Why we think so</div>
          <div class="reasoning-box">{{ occurrence.userExplanation }}</div>
        </template>

        <template v-if="occurrence.evidences && occurrence.evidences.length">
          <div class="label ev">Evidence</div>
          <div class="evidence-list">
            <div v-for="(e, i) in occurrence.evidences" :key="i" class="evidence-item">
              <span class="evidence-dot"></span>
              <span class="evidence-text">{{ e }}</span>
            </div>
          </div>
        </template>

        <div class="label ev">Found in</div>
        <div class="loc-row">
          <span class="loc-binary">{{ occurrence.inBinaryName }}</span>
          <span class="loc-linkage">{{ occurrence.linkage }}</span>
        </div>

        <template v-if="occurrence.alsoFoundIn && occurrence.alsoFoundIn.length">
          <div class="label ev spaced">Also found in</div>
          <div class="also-list">
            <div v-for="(loc, i) in occurrence.alsoFoundIn" :key="i" class="loc-row">
              <span class="loc-binary secondary">{{ loc.binary }}</span>
              <span class="loc-linkage">{{ loc.linkText }}</span>
            </div>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { isReviewConfidence, isUnknownConfidence, confLabel } from '../../composables/useComposition'

const props = defineProps({
  occurrence: { type: Object, required: true }
})
defineEmits(['close'])

const confColor = computed(() => {
  if (isReviewConfidence(props.occurrence.confidence)) return 'var(--warn)'
  if (isUnknownConfidence(props.occurrence.confidence)) return 'var(--text-3)'
  return 'var(--text-2)'
})
const dotClass = computed(() => {
  if (isReviewConfidence(props.occurrence.confidence)) return 'review'
  if (isUnknownConfidence(props.occurrence.confidence)) return 'unknown'
  return 'high'
})
const confText = computed(() => confLabel(props.occurrence.confidence))
</script>

<style scoped>
.info-col {
  width: 336px;
  flex-shrink: 0;
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r3);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideIn .18s ease;
}

.info-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 16px;
  border-bottom: 1px solid var(--line);
  background: var(--surface-2);
}
.info-eyebrow {
  font-size: var(--t-micro);
  font-weight: 700;
  letter-spacing: .06em;
  color: var(--text-3);
}
.info-spacer {
  flex: 1;
}
.info-close {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r1);
  color: var(--text-3);
}
.info-close:hover {
  background: var(--surface-3);
  color: var(--text-1);
}

.info-body {
  flex: 1;
  overflow-y: auto;
}
.info-top {
  padding: 16px 16px 0;
}
.name-row {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.comp-name {
  font-family: var(--mono-font);
  font-size: var(--t-h1);
  font-weight: 600;
  color: var(--text-1);
  word-break: break-word;
}
.comp-name.link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: color .15s;
}
.comp-name.link:hover {
  color: var(--accent);
}
.ext-icon {
  opacity: .45;
  flex-shrink: 0;
}
.module-chip {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-2);
  background: var(--surface-3);
  border-radius: var(--r1);
  padding: 2px 7px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--t-meta);
  color: var(--text-3);
}
.meta-version {
  font-family: var(--mono-font);
  color: var(--text-2);
}
.meta-version.unknown {
  color: var(--text-3);
}
.meta-linkage {
  color: var(--text-3);
}
.meta-conf {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.conf-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.conf-dot.high {
  background: var(--text-2);
}
.conf-dot.review {
  background: var(--warn);
}
.conf-dot.unknown {
  border: 1.5px solid var(--text-3);
  box-sizing: border-box;
}

.info-sections {
  padding: 14px 16px 18px;
}
.desc {
  font-size: var(--t-sm);
  color: var(--text-2);
  line-height: 1.55;
  margin: 0 0 16px;
}
.label {
  font-size: var(--t-meta);
  color: var(--text-3);
  margin-bottom: 6px;
}
.label.ev {
  margin-bottom: 7px;
}
.label.spaced {
  margin-top: 14px;
}
.reasoning-box {
  padding: 10px 12px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--r2);
  font-size: var(--t-meta);
  color: var(--text-2);
  line-height: 1.55;
  margin-bottom: 16px;
}
.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 16px;
}
.evidence-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.evidence-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--text-3);
  margin-top: 7px;
  flex-shrink: 0;
}
.evidence-text {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-2);
  line-height: 1.55;
  word-break: break-word;
}
.loc-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 11px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--r2);
}
.loc-binary {
  flex: 1;
  min-width: 0;
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.loc-binary.secondary {
  color: var(--text-2);
}
.loc-linkage {
  font-size: var(--t-micro);
  color: var(--text-3);
  flex-shrink: 0;
}
.also-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
