/**
 * CricImpact Phase 2 — ErrorState Component
 * Stage B6: Integrated Batting & Bowling Analytics Frontend
 */

export function renderErrorState({ title = 'Failed to Load Data', message = 'An error occurred while loading analytics telemetry.', onRetry = '' } = {}) {
  const displayMsg = typeof message === 'string' ? message : (typeof arguments[0] === 'string' ? arguments[0] : 'An unexpected error occurred.');
  const retryAction = onRetry || (arguments[1] ? arguments[1] : '');

  return `
    <div class="p-6 bg-rose-50 border border-rose-200 rounded-2xl shadow-sm text-center max-w-lg mx-auto my-6 animate-fadeIn">
      <div class="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto mb-3">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
      </div>
      <h3 class="text-sm font-bold text-rose-900 mb-1">${title}</h3>
      <p class="text-xs text-rose-700 max-w-md mx-auto mb-4">${displayMsg}</p>
      ${retryAction ? `
        <button onclick="${retryAction}" class="px-4 py-2 bg-white text-rose-700 font-bold text-xs rounded-xl border border-rose-300 hover:bg-rose-100/60 shadow-xs transition-colors">
          Retry Request
        </button>
      ` : ''}
    </div>
  `;
}
