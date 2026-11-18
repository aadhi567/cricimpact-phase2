/**
 * CricImpact Phase 2 — MetricCard Reusable Component
 * Renders consistent, light-themed KPI cards with Pink + Blue accents.
 */

export function renderMetricCard({
  title,
  value,
  unit = '',
  subtitle = '',
  accent = 'blue', // 'blue', 'pink', 'deep-blue', 'green', 'amber'
  icon = '',
  tooltip = '',
}) {
  let borderClass = 'border-t-3 border-[#3B82F6]';
  let badgeClass = 'text-[#2563EB] bg-[#EFF6FF]';
  let iconBgClass = 'bg-[#EFF6FF] text-[#3B82F6]';

  if (accent === 'pink') {
    borderClass = 'border-t-3 border-[#EC4899]';
    badgeClass = 'text-[#DB2777] bg-[#FDF2F8]';
    iconBgClass = 'bg-[#FDF2F8] text-[#EC4899]';
  } else if (accent === 'deep-blue') {
    borderClass = 'border-t-3 border-[#1E3A8A]';
    badgeClass = 'text-[#1E3A8A] bg-[#DBEAFE]';
    iconBgClass = 'bg-[#DBEAFE] text-[#1E3A8A]';
  } else if (accent === 'green') {
    borderClass = 'border-t-3 border-[#16A34A]';
    badgeClass = 'text-[#16A34A] bg-[#DCFCE7]';
    iconBgClass = 'bg-[#DCFCE7] text-[#16A34A]';
  } else if (accent === 'amber') {
    borderClass = 'border-t-3 border-[#D97706]';
    badgeClass = 'text-[#D97706] bg-[#FEF3C7]';
    iconBgClass = 'bg-[#FEF3C7] text-[#D97706]';
  }

  return `
    <div class="card-base p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-sm hover:shadow-md transition ${borderClass} relative">
      <div class="flex items-center justify-between gap-2 mb-2">
        <span class="text-xs font-bold uppercase tracking-wider text-[#64748B] flex items-center gap-1.5" title="${tooltip}">
          ${title}
          ${tooltip ? `<svg class="w-3.5 h-3.5 text-[#94A3B8]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>` : ''}
        </span>
        ${icon ? `<div class="w-7 h-7 rounded-lg ${iconBgClass} flex items-center justify-center">${icon}</div>` : ''}
      </div>

      <div class="flex items-baseline gap-1.5 my-1">
        <span class="text-2xl font-black text-[#0F172A] tracking-tight">${value}</span>
        ${unit ? `<span class="text-xs font-semibold text-[#64748B]">${unit}</span>` : ''}
      </div>

      ${subtitle ? `<div class="text-[11px] text-[#64748B] mt-1.5 leading-snug">${subtitle}</div>` : ''}
    </div>
  `;
}
