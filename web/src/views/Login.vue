<template>
  <div class="login-split">
    <!-- Left: brand -->
    <div class="login-left">
      <div class="brand">
        <svg viewBox="0 0 28 28" width="25" height="25"><path d="M7 23 L18 5 L22 5 L11 23 Z" fill="var(--accent)" /></svg>
        <span class="brand-word">BLADE</span>
      </div>

      <div class="brand-statement">
        <div class="eyebrow">BINARY SCA · AGENT-ASSISTED</div>
        <h1 class="headline">See exactly what's inside your compiled C/C++ binaries.</h1>
        <p class="lede">Identify third-party libraries, pin versions, and map static &amp; dynamic dependencies — no source code required.</p>
      </div>

      <div class="stats">
        <div class="stat"><div class="stat-num">2.4k+</div>libraries indexed</div>
        <div class="stat"><div class="stat-num">98.1%</div>detection precision</div>
        <div class="stat"><div class="stat-num">3</div>formats parsed</div>
      </div>
    </div>

    <!-- Right: sign in -->
    <div class="login-right">
      <div class="signin">
        <h2 class="signin-title">Sign in</h2>
        <p class="signin-sub">Continue to your analysis workspace.</p>

        <div id="google-signin-button" class="google-button"></div>

        <p class="signin-foot">No account? <span class="link">Request access</span></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useGoogleAuth } from '../composables/useGoogleAuth'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const { isGoogleReady, renderGoogleButton } = useGoogleAuth()

onMounted(async () => {
  if (authStore.isLoggedIn) {
    await router.push(route.query.redirect ? String(route.query.redirect) : { name: 'upload' })
    return
  }

  const checkAndRender = () => {
    if (isGoogleReady.value) {
      renderGoogleButton('google-signin-button', {
        type: 'standard',
        theme: themeStore.isDark ? 'filled_black' : 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'rectangular',
        logo_alignment: 'left',
        width: 330
      })
    } else {
      setTimeout(checkAndRender, 200)
    }
  }
  checkAndRender()
})
</script>

<style scoped>
.login-split {
  height: 100vh;
  display: flex;
  background: var(--bg);
  color: var(--text-1);
}

/* Left */
.login-left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 44px 48px;
  background: var(--surface-1);
  border-right: 1px solid var(--line);
  overflow: hidden;
}
.brand {
  display: flex;
  align-items: center;
  gap: 11px;
}
.brand-word {
  font-weight: 700;
  font-size: var(--t-h1);
  letter-spacing: .14em;
  color: var(--text-1);
}
.brand-statement {
  max-width: 440px;
}
.eyebrow {
  font-size: var(--t-meta);
  letter-spacing: .18em;
  color: var(--text-3);
  margin-bottom: 20px;
}
.headline {
  font-size: 34px;
  line-height: 1.15;
  font-weight: 600;
  letter-spacing: -.02em;
  margin: 0 0 18px;
  color: var(--text-1);
}
.lede {
  color: var(--text-2);
  font-size: var(--t-sm);
  line-height: 1.6;
  margin: 0;
}
.stats {
  display: flex;
  gap: 30px;
  font-size: var(--t-meta);
  color: var(--text-3);
}
.stat-num {
  font-family: var(--mono-font);
  color: var(--text-1);
  font-size: var(--t-h1);
  margin-bottom: 3px;
}

/* Right */
.login-right {
  width: 460px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: var(--bg);
}
.signin {
  width: 100%;
  max-width: 330px;
}
.signin-title {
  font-size: var(--t-h1);
  font-weight: 600;
  color: var(--text-1);
  margin: 0 0 6px;
}
.signin-sub {
  color: var(--text-2);
  font-size: var(--t-sm);
  margin: 0 0 26px;
}
.google-button {
  display: flex;
  justify-content: center;
  min-height: 44px;
  margin-bottom: 18px;
}
.signin-foot {
  text-align: center;
  color: var(--text-3);
  font-size: var(--t-meta);
  margin: 0;
}
.signin-foot .link {
  color: var(--accent);
}

/* Responsive: hide the brand panel on narrow screens */
@media (max-width: 760px) {
  .login-left {
    display: none;
  }
  .login-right {
    width: 100%;
    flex: 1;
  }
}
</style>
