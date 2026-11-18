/**
 * CricImpact Phase 2 — LoadingSkeleton & ErrorState Components
 */

export function renderLoadingSkeleton(title = 'Loading analytics data...') {
  return `
    <div class="card-base p-8 bg-white border border-[#E2E8F0] rounded-xl shadow-sm text-center">
      <div class="flex items-center justify-center gap-3 mb-4">
        <svg class="animate-spin h-6 w-6 text-[#EC4899]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span class="text-sm font-bold text-[#0F172A]">${title}</span>
      </div>
      <div class="space-y-3 max-w-xl mx-auto">
        <div class="h-4 skeleton-pulse rounded w-3/4 mx-auto"></div>
        <div class="h-4 skeleton-pulse rounded w-1/2 mx-auto"></div>
        <div class="h-4 skeleton-pulse rounded w-5/6 mx-auto"></div>
      </div>
    </div>
  `;
}

export function renderErrorState(errorMessage = 'An error occurred while loading data.', onRetryAction = '') {
  return `
    <div class="card-base p-6 bg-[#FEF2F2] border border-[#FCA5A5] rounded-xl shadow-sm text-center">
      <div class="w-10 h-10 rounded-full bg-[#FEE2E2] text-[#DC2626] flex items-center justify-center mx-auto mb-3">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
      </div>
      <h3 class="text-sm font-bold text-[#991B1B] mb-1">Failed to Load Telemetry</h3>
      <p class="text-xs text-[#B91C1C] max-w-md mx-auto mb-4">${errorMessage}</p>
      ${onRetryAction ? `<button onclick="${onRetryAction}" class="btn-secondary text-xs px-3 py-1.5 border-[#DC2626] text-[#DC2626] hover:bg-[#FEE2E2]">Retry Request</button>` : ''}
    </div>
  `;
}
