<template>
  <div class="docs-page">
    <!-- Main Content -->
    <main class="docs-main">
      <!-- Hero Section -->
      <section class="hero-section">
        <div class="highlight-box">
          <h2>The most accurate binary library detection platform</h2>
        </div>
        <p class="hero-text">
          BLADE brings you the most <a href="#features" class="text-link">accurate detection</a> available for binary analysis.
          Our detection engine delivers exceptional precision and reliability, with multi-dimensional feature matching
          adding ultra scalability through parallel processing.
        </p>
        <p class="hero-text">
          Our advanced <a href="#features" class="text-link">feature extraction</a> unlocks <strong>comprehensive analysis</strong>,
          bringing research-grade detection to production environments. We offer a range of
          <a href="#workflow" class="text-link">analysis options</a> to cover all your security and compliance requirements.
        </p>
        <p class="hero-text powered-by">
          BLADE powers <a href="#" class="text-link">Tier 0 analysis</a> at:
        </p>
      </section>

      <!-- Logo Grid -->
      <section class="logo-section">
        <div class="logo-grid">
          <div class="logo-item">
            <span class="logo-text">Research Lab A</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Security Team B</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Enterprise C</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">University D</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Company E</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Institute F</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Lab G</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Team H</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Corp I</span>
          </div>
          <div class="logo-item">
            <span class="logo-text">Research J</span>
          </div>
        </div>
      </section>

      <!-- Testimonial -->
      <section class="testimonial-section">
        <blockquote class="testimonial">
          <p>"We chose BLADE to analyze our most critical firmware and IoT devices, processing thousands of binaries
          with precise library identification and vulnerability mapping."</p>
        </blockquote>
        <p class="testimonial-author">— Security Research Team @Major Tech Company</p>
      </section>

      <!-- Tabs Section -->
      <section class="tabs-section">
        <div class="tabs-header">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            :class="['tab-btn', { active: activeTab === tab.id }]"
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="tab-content">
          <!-- String Features Tab -->
          <div v-if="activeTab === 'strings'" class="tab-panel">
            <p class="tab-description">
              <a href="#" class="text-link">String features</a> allow binary analysis to
              <a href="#" class="text-link">identify libraries through unique string patterns</a> —
              enabling a signature-based detection system matching strings across millions of library versions,
              all processed through a single analysis pipeline.
            </p>
            <p class="tab-description">
              String extraction was developed by security researchers to scale their binary analysis to
              petabytes of firmware across thousands of devices. Now maintained and optimized by BLADE,
              string matching powers the detection of some of the most critical systems: embedded devices,
              IoT firmware, automotive ECUs, and more.
            </p>

            <!-- Architecture Diagram -->
            <div class="architecture-diagram">
              <div class="diagram-box gateway">
                <span>Feature Extractor</span>
              </div>
              <div class="diagram-connector"></div>
              <div class="diagram-row">
                <div class="diagram-branch">
                  <div class="diagram-box primary">String DB</div>
                  <div class="diagram-sub-row">
                    <div class="diagram-box replica">Index 1</div>
                    <div class="diagram-box replica">Index 2</div>
                  </div>
                </div>
                <div class="diagram-branch">
                  <div class="diagram-box primary">Function DB</div>
                  <div class="diagram-sub-row">
                    <div class="diagram-box replica">Index 1</div>
                    <div class="diagram-box replica">Index 2</div>
                  </div>
                </div>
                <div class="diagram-branch">
                  <div class="diagram-box primary">Symbol DB</div>
                  <div class="diagram-sub-row">
                    <div class="diagram-box replica">Index 1</div>
                    <div class="diagram-box replica">Index 2</div>
                  </div>
                </div>
              </div>
            </div>

            <blockquote class="testimonial inner">
              <p>"Our migration to BLADE's detection engine is more than just a technological upgrade;
              it's a strategic move to future-proof our security analysis for the next decade and beyond."</p>
            </blockquote>
            <p class="testimonial-author">— Security Architect @Enterprise Software Company</p>
          </div>

          <!-- Function Names Tab -->
          <div v-if="activeTab === 'functions'" class="tab-panel">
            <p class="tab-description">
              <a href="#" class="text-link">Function name analysis</a> provides deep insight into
              <a href="#" class="text-link">library API usage and version identification</a> —
              enabling precise version pinpointing through exported symbol matching.
            </p>
            <p class="tab-description">
              Function signatures are extracted from binary files and compared against our comprehensive
              database of 50,000+ library versions. This approach is particularly effective for
              statically linked libraries where string-based detection may be insufficient.
            </p>

            <div class="feature-metrics">
              <div class="metric-card">
                <div class="metric-value">50,000+</div>
                <div class="metric-label">Library Versions</div>
              </div>
              <div class="metric-card">
                <div class="metric-value">10M+</div>
                <div class="metric-label">Function Signatures</div>
              </div>
              <div class="metric-card">
                <div class="metric-value">99.2%</div>
                <div class="metric-label">Match Accuracy</div>
              </div>
            </div>

            <blockquote class="testimonial inner">
              <p>"The function-level analysis gave us visibility into statically linked dependencies
              we never knew existed in our legacy codebase."</p>
            </blockquote>
            <p class="testimonial-author">— Principal Engineer @Firmware Company</p>
          </div>

          <!-- Vulnerability Tab -->
          <div v-if="activeTab === 'vulnerabilities'" class="tab-panel">
            <p class="tab-description">
              <a href="#" class="text-link">Vulnerability correlation</a> automatically maps detected libraries to
              <a href="#" class="text-link">known CVEs and security advisories</a> —
              providing actionable security intelligence for your binary assets.
            </p>
            <p class="tab-description">
              Our vulnerability database is continuously updated with the latest CVE entries,
              security advisories, and patch information. Each detected library version is
              cross-referenced against this database to identify potential security risks.
            </p>

            <div class="vuln-stats">
              <div class="stat-row">
                <div class="stat-item">
                  <span class="stat-label">CVEs Indexed</span>
                  <span class="stat-value">10,000+</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Update Frequency</span>
                  <span class="stat-value">Daily</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Advisory Sources</span>
                  <span class="stat-value">NVD, OSV, GitHub</span>
                </div>
              </div>
            </div>

            <blockquote class="testimonial inner">
              <p>"BLADE's vulnerability mapping helped us identify 23 critical CVEs in our embedded
              device firmware that our previous tools completely missed."</p>
            </blockquote>
            <p class="testimonial-author">— CISO @Connected Device Manufacturer</p>
          </div>
        </div>
      </section>

      <!-- Performance Section -->
      <section class="performance-section">
        <h3 class="section-title">Performance</h3>
        <p class="section-text">
          <a href="#" class="text-link">BLADE Engine</a> allows you to analyze binaries on the fastest
          infrastructure available. Our optimized algorithms unlock rapid analysis and drastically
          lower processing times compared to traditional binary analysis tools.
        </p>

        <!-- Metrics Dashboard -->
        <div class="metrics-dashboard">
          <div class="metrics-header">
            <div class="metric-col">
              <div class="metric-title">Analysis Time</div>
              <div class="metric-data">3 - 5s <span class="metric-note">avg</span></div>
            </div>
            <div class="metric-col">
              <div class="metric-title">Queue Status</div>
              <div class="metric-data success">No delays</div>
            </div>
            <div class="metric-col">
              <div class="metric-title">Libraries Checked</div>
              <div class="metric-data">5,000+ / scan</div>
            </div>
            <div class="metric-col">
              <div class="metric-title">Features Extracted</div>
              <div class="metric-data">10k - 50k / file</div>
            </div>
            <div class="metric-col">
              <div class="metric-title">Errors</div>
              <div class="metric-data success">No errors</div>
            </div>
          </div>
          <div class="metrics-chart">
            <div class="chart-row">
              <span class="chart-label">Dec 15</span>
              <span class="chart-label">Dec 16</span>
              <span class="chart-label">Dec 17</span>
              <span class="chart-label">Dec 18</span>
              <span class="chart-label">Last 24 hours</span>
            </div>
            <div class="chart-bars">
              <div class="chart-bar" style="height: 60%"></div>
              <div class="chart-bar" style="height: 45%"></div>
              <div class="chart-bar" style="height: 80%"></div>
              <div class="chart-bar" style="height: 55%"></div>
              <div class="chart-bar active" style="height: 70%"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- Features List -->
      <section class="features-section">
        <h3 class="section-title">Core Capabilities</h3>

        <div class="feature-list">
          <div class="feature-item">
            <div class="feature-icon">
              <SearchOutlined />
            </div>
            <div class="feature-content">
              <h4>Multi-format Support</h4>
              <p>Analyze ELF, PE, Mach-O, and other binary formats with unified detection capabilities.</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">
              <DatabaseOutlined />
            </div>
            <div class="feature-content">
              <h4>Comprehensive Database</h4>
              <p>Access our curated database of 5,000+ open-source libraries with version-specific signatures.</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">
              <SafetyOutlined />
            </div>
            <div class="feature-content">
              <h4>Security Intelligence</h4>
              <p>Automatic correlation with CVE databases and security advisories for risk assessment.</p>
            </div>
          </div>

          <div class="feature-item">
            <div class="feature-icon">
              <FileTextOutlined />
            </div>
            <div class="feature-content">
              <h4>Detailed Reports</h4>
              <p>Generate comprehensive analysis reports with actionable findings and recommendations.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- CTA Section -->
      <section class="cta-section">
        <div class="cta-content">
          <h3>Ready to analyze your binaries?</h3>
          <p>Start with our free tier — no credit card required.</p>
          <router-link to="/" class="cta-button">
            Get Started
            <ArrowRightOutlined />
          </router-link>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  SearchOutlined,
  DatabaseOutlined,
  SafetyOutlined,
  FileTextOutlined,
  ArrowRightOutlined
} from '@ant-design/icons-vue'

const activeTab = ref('strings')

const tabs = [
  { id: 'strings', label: 'String Features' },
  { id: 'functions', label: 'Function Names' },
  { id: 'vulnerabilities', label: 'Vulnerabilities' }
]
</script>

<style scoped>
/* Base Styles */
.docs-page {
  background: var(--bg);
  color: var(--text-1);
  font-family: var(--mono-font);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: 15px;
  line-height: 1.7;
}

.docs-main {
  max-width: 900px;
  margin: 0 auto;
  padding: 3rem 2rem 4rem;
}

/* Hero Section */
.hero-section {
  margin-bottom: 3rem;
}

.highlight-box {
  border-left: 4px solid var(--accent);
  padding-left: 1rem;
  margin-bottom: 1.5rem;
}

.highlight-box h2 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-1);
  margin: 0;
  line-height: 1.4;
}

.hero-text {
  font-size: 1rem;
  line-height: 1.75;
  color: var(--text-2);
  margin-bottom: 1rem;
}

.hero-text strong {
  color: var(--text-1);
  font-weight: 600;
}

.powered-by {
  margin-top: 2rem;
}

.text-link {
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
}

.text-link:hover {
  text-decoration: underline;
}

/* Logo Grid */
.logo-section {
  margin-bottom: 3rem;
}

.logo-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  overflow: hidden;
}

.logo-item {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 1rem;
  border-right: 1px solid var(--line-strong);
  border-bottom: 1px solid var(--line-strong);
}

.logo-item:nth-child(5n) {
  border-right: none;
}

.logo-item:nth-last-child(-n+5) {
  border-bottom: none;
}

.logo-text {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-2);
}

/* Testimonial */
.testimonial-section {
  margin-bottom: 3rem;
}

.testimonial {
  border-left: 4px solid var(--accent);
  padding-left: 1.25rem;
  margin: 0 0 0.75rem 0;
}

.testimonial.inner {
  margin-top: 2rem;
}

.testimonial p {
  font-size: 1rem;
  line-height: 1.7;
  color: var(--text-2);
  margin: 0;
}

.testimonial-author {
  font-size: 0.875rem;
  color: var(--text-3);
  margin: 0;
  padding-left: 1.5rem;
}

/* Tabs */
.tabs-section {
  margin-bottom: 3rem;
}

.tabs-header {
  display: flex;
  border-bottom: 1px solid var(--line-strong);
  margin-bottom: 1.5rem;
}

.tab-btn {
  flex: 1;
  padding: 1rem;
  background: var(--surface-1);
  border: 1px solid var(--line-strong);
  border-bottom: none;
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--text-3);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}

.tab-btn:first-child {
  border-radius: 8px 0 0 0;
}

.tab-btn:last-child {
  border-radius: 0 8px 0 0;
  border-right: 1px solid var(--line-strong);
}

.tab-btn:not(:last-child) {
  border-right: none;
}

.tab-btn.active {
  background: var(--text-1);
  color: var(--accent-ink);
  border-color: var(--text-1);
}

.tab-btn:hover:not(.active) {
  background: var(--surface-3);
}

.tab-content {
  padding: 0.5rem 0;
}

.tab-panel {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.tab-description {
  font-size: 1rem;
  line-height: 1.75;
  color: var(--text-2);
  margin-bottom: 1rem;
}

/* Architecture Diagram */
.architecture-diagram {
  margin: 2.5rem 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.diagram-box {
  border: 2px solid var(--text-1);
  padding: 1rem 2rem;
  text-align: center;
  font-weight: 500;
  background: var(--surface-1);
  color: var(--text-1);
}

.diagram-box.gateway {
  background: repeating-linear-gradient(
    45deg,
    var(--surface-3),
    var(--surface-3) 2px,
    var(--surface-1) 2px,
    var(--surface-1) 8px
  );
  padding: 1.25rem 4rem;
  font-weight: 600;
}

.diagram-connector {
  width: 2px;
  height: 30px;
  background: var(--text-1);
  position: relative;
}

.diagram-connector::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 8px solid var(--text-1);
}

.diagram-row {
  display: flex;
  gap: 2rem;
  margin-top: 1.5rem;
  position: relative;
}

.diagram-row::before {
  content: '';
  position: absolute;
  top: -1.5rem;
  left: 50%;
  transform: translateX(-50%);
  width: 80%;
  height: 2px;
  border-top: 2px dashed var(--text-2);
}

.diagram-branch {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.diagram-box.primary {
  min-width: 120px;
}

.diagram-sub-row {
  display: flex;
  gap: 0.5rem;
}

.diagram-box.replica {
  font-size: 0.8rem;
  padding: 0.5rem 1rem;
  background: var(--surface-3);
}

/* Feature Metrics */
.feature-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin: 2rem 0;
}

.metric-card {
  text-align: center;
  padding: 1.5rem;
  background: var(--surface-1);
  border-radius: 8px;
  border: 1px solid var(--line-strong);
}

.metric-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--accent);
}

.metric-label {
  font-size: 0.875rem;
  color: var(--text-3);
  margin-top: 0.5rem;
}

/* Vulnerability Stats */
.vuln-stats {
  margin: 2rem 0;
  padding: 1.5rem;
  background: var(--surface-1);
  border-radius: 8px;
  border: 1px solid var(--line-strong);
}

.stat-row {
  display: flex;
  justify-content: space-between;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-item .stat-label {
  font-size: 0.8rem;
  color: var(--text-3);
}

.stat-item .stat-value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-1);
}

/* Performance Section */
.performance-section {
  margin-bottom: 3rem;
}

.section-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-1);
  margin-bottom: 1rem;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.section-text {
  font-size: 1rem;
  line-height: 1.75;
  color: var(--text-2);
  margin-bottom: 1.5rem;
}

/* Metrics Dashboard */
.metrics-dashboard {
  background: var(--surface-1);
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  overflow: hidden;
}

.metrics-header {
  display: flex;
  padding: 1rem;
  border-bottom: 1px solid var(--line-strong);
  gap: 1rem;
}

.metric-col {
  flex: 1;
  padding: 0.5rem;
}

.metric-title {
  font-size: 0.75rem;
  color: var(--text-3);
  margin-bottom: 0.25rem;
}

.metric-data {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-1);
}

.metric-data.success {
  color: var(--accent);
}

.metric-note {
  font-size: 0.75rem;
  color: var(--text-2);
  font-weight: 400;
}

.metrics-chart {
  padding: 1rem;
}

.chart-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.chart-label {
  font-size: 0.75rem;
  color: var(--text-2);
}

.chart-bars {
  display: flex;
  gap: 0.5rem;
  height: 60px;
  align-items: flex-end;
}

.chart-bar {
  flex: 1;
  background: var(--line-strong);
  border-radius: 2px;
  transition: background 0.2s ease;
}

.chart-bar.active {
  background: var(--accent);
}

/* Features Section */
.features-section {
  margin-bottom: 3rem;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.feature-item {
  display: flex;
  gap: 1rem;
  padding: 1.25rem;
  background: var(--surface-1);
  border-radius: 8px;
  border: 1px solid var(--line-strong);
  transition: border-color 0.2s ease;
}

.feature-item:hover {
  border-color: var(--accent);
}

.feature-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: var(--accent-ink);
  border-radius: 8px;
  font-size: 1.125rem;
}

.feature-content h4 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-1);
  margin: 0 0 0.5rem 0;
}

.feature-content p {
  font-size: 0.9375rem;
  color: var(--text-3);
  line-height: 1.6;
  margin: 0;
}

/* CTA Section */
.cta-section {
  margin-bottom: 2rem;
}

.cta-content {
  text-align: center;
  padding: 3rem 2rem;
  background: var(--surface-1);
  border-radius: 12px;
  border: 1px solid var(--line-strong);
}

.cta-content h3 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-1);
  margin: 0 0 0.5rem 0;
}

.cta-content p {
  font-size: 1rem;
  color: var(--text-3);
  margin: 0 0 1.5rem 0;
}

.cta-button {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.875rem 2rem;
  background: var(--text-1);
  color: var(--accent-ink);
  font-weight: 600;
  font-size: 1rem;
  border-radius: 8px;
  text-decoration: none;
  transition: all 0.2s ease;
  font-family: inherit;
}

.cta-button:hover {
  opacity: 0.9;
  transform: translateY(-2px);
}

/* Responsive */
@media (max-width: 768px) {
  .docs-main {
    padding: 2rem 1rem 3rem;
  }

  .logo-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .logo-item:nth-child(5n) {
    border-right: 1px solid var(--line-strong);
  }

  .logo-item:nth-child(2n) {
    border-right: none;
  }

  .logo-item:nth-last-child(-n+5) {
    border-bottom: 1px solid var(--line-strong);
  }

  .logo-item:nth-last-child(-n+2) {
    border-bottom: none;
  }

  .tabs-header {
    flex-direction: column;
  }

  .tab-btn {
    border-radius: 0 !important;
    border-right: 1px solid var(--line-strong) !important;
  }

  .tab-btn:first-child {
    border-radius: 8px 8px 0 0 !important;
  }

  .diagram-row {
    flex-direction: column;
    gap: 1.5rem;
  }

  .diagram-row::before {
    display: none;
  }

  .feature-metrics {
    grid-template-columns: 1fr;
  }

  .stat-row {
    flex-direction: column;
    gap: 1rem;
  }

  .metrics-header {
    flex-wrap: wrap;
  }

  .metric-col {
    flex: 0 0 calc(50% - 0.5rem);
  }
}
</style>
