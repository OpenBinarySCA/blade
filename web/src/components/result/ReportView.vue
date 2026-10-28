<template>
  <section class="report-card">
    <div class="report-inner">
      <div class="report-eyebrow">COMPOSITION REPORT</div>
      <h2 class="report-headline">{{ report.headline }}</h2>
      <p class="report-summary">{{ report.summary }}</p>

      <div v-for="rf in report.files" :key="rf.name" class="report-file">
        <div class="rf-head">
          <span class="rf-name">{{ rf.name }}</span>
          <span class="rf-id">identified as <span class="rf-id-val">{{ rf.identity }}</span></span>
        </div>
        <div v-if="rf.identityDesc" class="rf-desc">{{ rf.identityDesc }}</div>

        <template v-for="sg in rf.subs" :key="sg.label">
          <template v-if="sg.show">
            <div class="rsg-label">{{ sg.label }} · {{ sg.count }}</div>
            <div v-for="(ri, idx) in sg.items" :key="idx" class="ri">
              <div class="ri-head">
                <span class="ri-name">{{ ri.name }}</span>
                <span v-if="ri.hasModule" class="module-chip">{{ ri.module }}</span>
                <span class="ri-version">{{ ri.version }}</span>
                <span class="ri-conf" :style="{ color: confColor(ri.confidence) }">
                  <span class="conf-dot" :class="dotClass(ri.confidence)"></span>{{ confText(ri.confidence) }}
                </span>
              </div>
              <div v-if="ri.why" class="ri-why">{{ ri.why }}</div>
            </div>
          </template>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useComposition, isReviewConfidence, isUnknownConfidence, confLabel } from '../../composables/useComposition'

const props = defineProps({
  resultData: { type: Object, default: null }
})

const rd = computed(() => props.resultData)
const { report } = useComposition(rd)

function confColor(c) {
  if (isReviewConfidence(c)) return 'var(--warn)'
  if (isUnknownConfidence(c)) return 'var(--text-3)'
  return 'var(--text-2)'
}
function dotClass(c) {
  return isReviewConfidence(c) ? 'review' : isUnknownConfidence(c) ? 'unknown' : 'high'
}
function confText(c) {
  return confLabel(c)
}
</script>

<style scoped>
.report-card {
  width: 100%;
  background: var(--surface-1);
  border: 1px solid var(--line);
  border-radius: var(--r3);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.report-inner {
  padding: 26px 30px;
  max-width: 860px;
}
.report-eyebrow {
  font-size: var(--t-micro);
  font-weight: 700;
  letter-spacing: .1em;
  color: var(--text-3);
  margin-bottom: 10px;
}
.report-headline {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -.01em;
  color: var(--text-1);
  margin: 0 0 7px;
}
.report-summary {
  font-size: var(--t-sm);
  color: var(--text-2);
  line-height: 1.6;
  margin: 0 0 22px;
}

.report-file {
  margin-bottom: 24px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}
.rf-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.rf-name {
  font-family: var(--mono-font);
  font-size: var(--t-body);
  font-weight: 600;
  color: var(--text-1);
}
.rf-id {
  font-size: var(--t-meta);
  color: var(--text-3);
}
.rf-id-val {
  color: var(--text-2);
}
.rf-desc {
  font-size: var(--t-sm);
  color: var(--text-2);
  line-height: 1.6;
  margin-bottom: 8px;
}

.rsg-label {
  font-size: var(--t-micro);
  font-weight: 700;
  letter-spacing: .05em;
  color: var(--text-3);
  margin: 14px 0 6px;
}
.ri {
  padding: 9px 0;
  border-top: 1px solid var(--line-soft);
}
.ri-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
  flex-wrap: wrap;
}
.ri-name {
  font-family: var(--mono-font);
  font-size: var(--t-sm);
  font-weight: 500;
  color: var(--text-1);
}
.module-chip {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-2);
  background: var(--surface-3);
  border-radius: var(--r1);
  padding: 1px 6px;
}
.ri-version {
  font-family: var(--mono-font);
  font-size: var(--t-micro);
  color: var(--text-3);
}
.ri-conf {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--t-micro);
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
.ri-why {
  font-size: var(--t-meta);
  color: var(--text-3);
  line-height: 1.5;
}
</style>
