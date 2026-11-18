/**
 * CricImpact Phase 2 - Batting Analytics Embed Wrapper
 * Stage B6: Integrated Batting & Bowling Analytics Frontend
 * 
 * Provides seamless integration of existing validated Phase 2 Batting Analytics:
 * - HPP Dashboard (docs/worm_graph/hpp_dashboard.html)
 * - Worm Graph (docs/worm_graph/worm_graph.html)
 * - HPP Explorer (docs/worm_graph/hpp_explorer.html)
 * 
 * Strictly preserves 100% of existing batting code without any modifications.
 */

export function renderBattingEmbed(container, params = {}) {
  // Determine which batting view to embed
  const view = params.view || 'dashboard'; // 'dashboard', 'worm', or 'explorer'

  let targetUrl = '/batting/hpp_dashboard.html';
  let title = 'Batting High-Pressure Performance (HPP) Dashboard';
  let subtitle = 'Evaluate batting contributions under leverage, pressure curves, and match-state context.';

  if (view === 'worm') {
    targetUrl = '/batting/worm_graph.html';
    title = 'Dynamic Match Worm Graph';
    subtitle = 'Interactive match trajectory and pressure-adjusted run chase worm visualization.';
  } else if (view === 'explorer') {
    targetUrl = '/batting/hpp_explorer.html';
    title = 'HPP Batter Stint Explorer';
    subtitle = 'Detailed ball-by-ball stint analysis and par curve comparisons.';
  }

  container.innerHTML = `
    <div class="space-y-4 animate-fadeIn flex flex-col h-[calc(100vh-6rem)]">
      <!-- Batting Header & Tab Switcher -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-200 flex-shrink-0">
        <div>
          <div class="flex items-center space-x-2 text-xs font-bold text-pink-600 uppercase tracking-wider mb-1">
            <span>Batting Analytics System</span>
            <span>&bull;</span>
            <span class="text-slate-500">Phase 2 Production Asset</span>
          </div>
          <h1 class="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">${title}</h1>
          <p class="text-slate-500 text-xs mt-0.5">${subtitle}</p>
        </div>

        <div class="flex items-center space-x-2">
          <!-- View Switcher Tabs -->
          <div class="flex bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-bold">
            <a href="#/batting/dashboard" class="px-3 py-1.5 rounded-lg transition-colors ${view === 'dashboard' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}">
              HPP Dashboard
            </a>
            <a href="#/batting/worm" class="px-3 py-1.5 rounded-lg transition-colors ${view === 'worm' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}">
              Worm Graph
            </a>
            <a href="#/batting/explorer" class="px-3 py-1.5 rounded-lg transition-colors ${view === 'explorer' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}">
              Stint Explorer
            </a>
          </div>

          <!-- Open In New Window Button -->
          <a href="${targetUrl}" target="_blank" rel="noopener noreferrer" class="p-2 text-slate-500 hover:text-slate-800 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors shadow-sm" title="Open in new window">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
            </svg>
          </a>
        </div>
      </div>

      <!-- Embedded Iframe Container -->
      <div class="flex-1 w-full bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden relative">
        <iframe 
          id="batting-iframe"
          src="${targetUrl}" 
          class="w-full h-full border-0 rounded-2xl" 
          title="${title}"
          loading="lazy">
        </iframe>
      </div>
    </div>
  `;
}
