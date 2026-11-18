/**
 * CricImpact Phase 2 — ContributionChart Component
 * Wraps Chart.js rendering with the strict Pink + Blue visual identity.
 * 
 * Supports both canvas element / ID, and flexible config signatures.
 */

// Track active Chart.js instances to ensure clean destruction before redraw
const activeCharts = new Map();

export function destroyChart(target) {
  const canvas = typeof target === 'string' ? document.getElementById(target) : target;
  if (!canvas) return;

  if (activeCharts.has(canvas)) {
    try {
      activeCharts.get(canvas).destroy();
    } catch (_) {}
    activeCharts.delete(canvas);
  } else if (canvas.id && activeCharts.has(canvas.id)) {
    try {
      activeCharts.get(canvas.id).destroy();
    } catch (_) {}
    activeCharts.delete(canvas.id);
  }
}

function resolveCanvas(target) {
  if (!target) return null;
  return typeof target === 'string' ? document.getElementById(target) : target;
}

/**
 * Universal Bar Chart Renderer
 */
export function renderBarChart(target, arg2, arg3, arg4) {
  const canvas = resolveCanvas(target);
  if (!canvas || !window.Chart) return null;
  destroyChart(canvas);

  let dataConfig;
  let options = {};

  if (arg2 && typeof arg2 === 'object' && arg2.datasets) {
    dataConfig = arg2;
    options = arg3 || {};
  } else {
    dataConfig = { labels: arg2, datasets: arg3 };
    options = arg4 || {};
  }

  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          font: { family: '-apple-system, sans-serif', size: 11, weight: '600' },
          color: '#0F172A',
          boxWidth: 12,
        },
      },
      tooltip: {
        backgroundColor: '#0F172A',
        titleFont: { size: 12, weight: 'bold' },
        bodyFont: { size: 11 },
        padding: 10,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { size: 11 }, color: '#64748B' },
      },
      y: {
        grid: { color: '#F1F5F9' },
        ticks: { font: { size: 11 }, color: '#64748B' },
      },
    },
    ...options,
  };

  const chart = new window.Chart(canvas, {
    type: 'bar',
    data: dataConfig,
    options: defaultOptions,
  });

  activeCharts.set(canvas, chart);
  if (canvas.id) activeCharts.set(canvas.id, chart);
  return chart;
}

export const createBarChart = renderBarChart;

/**
 * Universal Line Chart Renderer
 */
export function renderLineChart(target, arg2, arg3, arg4) {
  const canvas = resolveCanvas(target);
  if (!canvas || !window.Chart) return null;
  destroyChart(canvas);

  let dataConfig;
  let options = {};

  if (arg2 && typeof arg2 === 'object' && arg2.datasets) {
    dataConfig = arg2;
    options = arg3 || {};
  } else {
    dataConfig = { labels: arg2, datasets: arg3 };
    options = arg4 || {};
  }

  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: { font: { size: 11, weight: '600' }, color: '#0F172A', boxWidth: 12 },
      },
      tooltip: {
        backgroundColor: '#0F172A',
        padding: 10,
        cornerRadius: 8,
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: '#64748B' } },
      y: { grid: { color: '#F1F5F9' }, ticks: { color: '#64748B' } },
    },
    ...options,
  };

  const chart = new window.Chart(canvas, {
    type: 'line',
    data: dataConfig,
    options: defaultOptions,
  });

  activeCharts.set(canvas, chart);
  if (canvas.id) activeCharts.set(canvas.id, chart);
  return chart;
}

export const createLineChart = renderLineChart;

/**
 * Universal Radar Chart Renderer
 */
export function renderRadarChart(target, arg2, arg3, arg4) {
  const canvas = resolveCanvas(target);
  if (!canvas || !window.Chart) return null;
  destroyChart(canvas);

  let dataConfig;
  let options = {};

  if (arg2 && typeof arg2 === 'object' && arg2.datasets) {
    dataConfig = arg2;
    options = arg3 || {};
  } else {
    dataConfig = { labels: arg2, datasets: arg3 };
    options = arg4 || {};
  }

  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: { font: { size: 11, weight: 'bold' }, color: '#0F172A' },
      },
    },
    scales: {
      r: {
        angleLines: { color: '#E2E8F0' },
        grid: { color: '#E2E8F0' },
        pointLabels: { font: { size: 11, weight: '600' }, color: '#0F172A' },
        ticks: { backdropColor: 'transparent', font: { size: 9 }, color: '#94A3B8' },
      },
    },
    ...options,
  };

  const chart = new window.Chart(canvas, {
    type: 'radar',
    data: dataConfig,
    options: defaultOptions,
  });

  activeCharts.set(canvas, chart);
  if (canvas.id) activeCharts.set(canvas.id, chart);
  return chart;
}

export const createRadarChart = renderRadarChart;

/**
 * Universal Doughnut / Pie Chart Renderer
 */
export function renderDoughnutChart(target, arg2, arg3, arg4, arg5) {
  const canvas = resolveCanvas(target);
  if (!canvas || !window.Chart) return null;
  destroyChart(canvas);

  let dataConfig;
  let options = {};

  if (arg2 && typeof arg2 === 'object' && arg2.datasets) {
    dataConfig = arg2;
    options = arg3 || {};
  } else {
    dataConfig = {
      labels: arg2,
      datasets: [{
        data: arg3,
        backgroundColor: arg4 || ['#3B82F6', '#EC4899', '#1E3A8A'],
        borderWidth: 2,
        borderColor: '#FFFFFF',
      }],
    };
    options = arg5 || {};
  }

  const chart = new window.Chart(canvas, {
    type: 'doughnut',
    data: dataConfig,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 12 } },
      },
      cutout: '65%',
      ...options,
    },
  });

  activeCharts.set(canvas, chart);
  if (canvas.id) activeCharts.set(canvas.id, chart);
  return chart;
}

export const createDoughnutChart = renderDoughnutChart;
