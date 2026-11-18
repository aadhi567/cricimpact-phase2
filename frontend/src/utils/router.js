/**
 * CricImpact Phase 2 — Client-Side Hash Router
 * Stage B6: Integrated Batting & Bowling Analytics Frontend
 * 
 * Supports dynamic routing, parameter extraction (:id), query string parsing,
 * and container-aware page mounting.
 */

export class Router {
  constructor(container, defaultRoute = '#/overview') {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.defaultRoute = defaultRoute;
    this.routes = {};
    this.currentRoute = '';
    this.routeParams = {};
    this.onRouteChangedCallbacks = [];

    window.addEventListener('hashchange', () => this.handleRoute());
  }

  addRoute(pattern, handler) {
    this.routes[pattern] = handler;
    return this;
  }

  registerRoute(pattern, handler) {
    return this.addRoute(pattern, handler);
  }

  onRouteChanged(callback) {
    this.onRouteChangedCallbacks.push(callback);
    return this;
  }

  navigate(hash) {
    if (window.location.hash === hash) {
      this.handleRoute();
    } else {
      window.location.hash = hash;
    }
  }

  handleRoute() {
    const fullHash = window.location.hash || this.defaultRoute;
    const [pathPart, queryPart] = fullHash.split('?');
    // Normalize path: '#/bowling/dashboard' -> '/bowling/dashboard'
    let path = pathPart.replace(/^#/, '').trim();
    if (!path.startsWith('/')) path = '/' + path;

    let matchedHandler = null;
    let extractedParams = {};

    // Match exact or parameterized routes
    for (const [pattern, handler] of Object.entries(this.routes)) {
      let cleanPattern = pattern.replace(/^#/, '').trim();
      if (!cleanPattern.startsWith('/')) cleanPattern = '/' + cleanPattern;

      // Convert pattern like '/bowling/profile/:id' to RegExp
      const regexStr = '^' + cleanPattern.replace(/:([a-zA-Z0-9_]+)/g, '(?<$1>[^/]+)') + '$';
      const patternRegex = new RegExp(regexStr);
      const match = path.match(patternRegex);

      if (match) {
        matchedHandler = handler;
        extractedParams = match.groups || {};
        break;
      }
    }

    // Parse query params if present
    const queryParams = {};
    if (queryPart) {
      new URLSearchParams(queryPart).forEach((val, key) => {
        queryParams[key] = val;
      });
    }

    this.currentRoute = fullHash;
    this.routeParams = { ...extractedParams, ...queryParams, query: queryParams };

    // Trigger listeners
    this.onRouteChangedCallbacks.forEach((cb) => cb(fullHash, this.routeParams));

    if (matchedHandler) {
      try {
        matchedHandler(this.container, this.routeParams);
      } catch (err) {
        console.error('Route handler error:', err);
        if (this.container) {
          this.container.innerHTML = `
            <div class="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800">
              <h2 class="font-bold text-base mb-1">Page Rendering Error</h2>
              <p class="text-xs font-mono">${err.message}</p>
            </div>
          `;
        }
      }
    } else if (this.routes['*']) {
      this.routes['*'](this.container, this.routeParams);
    } else {
      console.warn(`No route matched for: ${path}. Navigating to ${this.defaultRoute}`);
      this.navigate(this.defaultRoute);
    }
  }

  init() {
    if (!window.location.hash) {
      window.location.hash = this.defaultRoute;
    }
    this.handleRoute();
  }
}
