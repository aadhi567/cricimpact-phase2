/**
 * CricImpact Phase 2 — Integrated Navigation Component
 * Provides responsive sidebar and mobile drawer with Pink + Blue active states.
 */

export class Navigation {
  constructor(containerId = 'sidebar-container') {
    this.container = document.getElementById(containerId);
    this.currentHash = window.location.hash || '#/overview';
  }

  render() {
    if (!this.container) return;

    this.container.innerHTML = `
      <aside class="w-64 bg-white border-r border-[#E2E8F0] min-h-screen flex flex-col justify-between shadow-sm z-30">
        <div>
          <!-- Brand Logo Header -->
          <div class="p-5 border-b border-[#E2E8F0] flex items-center justify-between">
            <a href="#/overview" class="flex items-center gap-3 no-underline">
              <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#EC4899] to-[#3B82F6] flex items-center justify-center text-white font-black text-lg shadow-sm">
                C2
              </div>
              <div>
                <span class="text-base font-black tracking-tight text-[#0F172A] block leading-none">CricImpact</span>
                <span class="text-[10px] font-bold uppercase tracking-widest text-[#DB2777] block mt-0.5">Phase 2 Platform</span>
              </div>
            </a>
          </div>

          <!-- Navigation Links -->
          <nav class="p-3 space-y-6 text-xs font-semibold" id="nav-links-container" aria-label="Primary">
            <!-- MAIN -->
            <div>
              <div class="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-[#94A3B8]">Main</div>
              <ul class="space-y-0.5 list-none p-0 m-0">
                <li>
                  <a href="#/overview" data-route="#/overview" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg aria-hidden="true" class="w-4 h-4 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
                    <span>Overview</span>
                  </a>
                </li>
                <li>
                  <a href="#/pressure-reliability" data-route="#/pressure-reliability" class="nav-item flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <span class="flex items-center gap-2.5">
                      <svg aria-hidden="true" class="w-4 h-4 text-[#1E3A8A]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                      <span>Pressure Reliability</span>
                    </span>
                    <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#EFF6FF] text-[#1E3A8A]">PRI</span>
                  </a>
                </li>
              </ul>
            </div>

            <!-- BATTING ANALYTICS -->
            <div>
              <div class="px-3 mb-1.5 flex items-center justify-between">
                <span class="text-[10px] font-bold uppercase tracking-wider text-[#94A3B8]">Batting Analytics</span>
                <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#EFF6FF] text-[#2563EB]">HPP + HPC</span>
              </div>
              <ul class="space-y-0.5 list-none p-0 m-0">
                <li>
                  <a href="#/batting/dashboard" data-route="#/batting/dashboard" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg aria-hidden="true" class="w-4 h-4 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                    <span>HPP Dashboard</span>
                  </a>
                </li>
                <li>
                  <a href="#/batting/explorer" data-route="#/batting/explorer" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg aria-hidden="true" class="w-4 h-4 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                    <span>HPP Explorer</span>
                  </a>
                </li>
                <li>
                  <a href="#/batting/players/Abhishek%20Sharma" data-route="#/batting/players" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg aria-hidden="true" class="w-4 h-4 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                    <span>Batter Profiles</span>
                  </a>
                </li>
                <li>
                  <a href="#/batting/compare" data-route="#/batting/compare" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg aria-hidden="true" class="w-4 h-4 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg>
                    <span>Batter Comparison</span>
                  </a>
                </li>
                <li>
                  <a href="#/batting/worm_graph" data-route="#/batting/worm_graph" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg aria-hidden="true" class="w-4 h-4 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/></svg>
                    <span>Match Worm Graph</span>
                  </a>
                </li>
              </ul>
            </div>

            <!-- BOWLING ANALYTICS -->
            <div>
              <div class="px-3 mb-1.5 flex items-center justify-between">
                <span class="text-[10px] font-bold uppercase tracking-wider text-[#94A3B8]">Bowling Analytics</span>
                <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#FDF2F8] text-[#DB2777]">BCM + PCS</span>
              </div>
              <ul class="space-y-0.5 list-none p-0 m-0">
                <li>
                  <a href="#/bowling/dashboard" data-route="#/bowling/dashboard" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg class="w-4 h-4 text-[#EC4899]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/></svg>
                    <span>Bowling Dashboard</span>
                  </a>
                </li>
                <li>
                  <a href="#/bowling/leaderboard" data-route="#/bowling/leaderboard" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg class="w-4 h-4 text-[#EC4899]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/></svg>
                    <span>Bowling Leaderboard</span>
                  </a>
                </li>
                <li>
                  <a href="#/bowling/players/4722" data-route="#/bowling/players" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg class="w-4 h-4 text-[#EC4899]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                    <span>Bowler Profiles</span>
                  </a>
                </li>
                <li>
                  <a href="#/bowling/compare" data-route="#/bowling/compare" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg class="w-4 h-4 text-[#EC4899]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg>
                    <span>Bowler Comparison</span>
                  </a>
                </li>
                <li>
                  <a href="#/bowling/matches" data-route="#/bowling/matches" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg class="w-4 h-4 text-[#EC4899]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
                    <span>Match & Spell Analysis</span>
                  </a>
                </li>
              </ul>
            </div>

            <!-- OTHER -->
            <div>
              <div class="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-[#94A3B8]">Platform</div>
              <ul class="space-y-0.5 list-none p-0 m-0">
                <li>
                  <a href="#/settings" data-route="#/settings" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition">
                    <svg class="w-4 h-4 text-[#64748B]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                    <span>System Settings & Meta</span>
                  </a>
                </li>
              </ul>
            </div>
          </nav>
        </div>

        <!-- Footer / Model Attribution Status -->
        <div class="p-4 border-t border-[#E2E8F0] bg-[#F8FAFC]">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-[#16A34A] animate-pulse"></span>
            <span class="text-[11px] font-semibold text-[#0F172A]">HPP + BCM + PCS + PRI</span>
          </div>
          <p class="text-[10px] text-[#64748B] mt-1 leading-tight">798 Matches &bull; 12,888 Batting Stints<br>190,575 Bowling Deliveries Live</p>
        </div>
      </aside>
    `;

    this.updateActiveLink(window.location.hash || '#/overview');
  }

  updateActiveLink(hash) {
    this.currentHash = hash;
    const items = document.querySelectorAll('.nav-item');
    items.forEach((item) => {
      const routeAttr = item.getAttribute('data-route');
      const isMatch = hash.startsWith(routeAttr) || (routeAttr === '#/batting/explorer' && hash.startsWith('#/batting/leaderboard')) || (routeAttr === '#/batting/worm_graph' && hash.startsWith('#/batting/worm'));

      if (isMatch) {
        item.classList.add('bg-gradient-to-r', 'from-[#FDF2F8]', 'to-[#EFF6FF]', 'text-[#0F172A]', 'border-l-4', 'border-[#EC4899]', 'font-bold');
        item.classList.remove('text-[#64748B]');
        item.setAttribute('aria-current', 'page');
      } else {
        item.classList.remove('bg-gradient-to-r', 'from-[#FDF2F8]', 'to-[#EFF6FF]', 'text-[#0F172A]', 'border-l-4', 'border-[#EC4899]', 'font-bold');
        item.classList.add('text-[#64748B]');
        item.removeAttribute('aria-current');
      }
    });
  }
}
