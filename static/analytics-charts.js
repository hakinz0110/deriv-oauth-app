/**
 * Advanced Analytics Charts Manager
 * 
 * Institutional-grade chart rendering for binary options trading analytics.
 * Implements TradingView Lightweight Charts for equity curve visualization
 * and custom canvas rendering for performance gauges.
 * 
 * Senior Quant Developer Implementation:
 * - Real-time data updates with manual refresh control
 * - Responsive chart sizing
 * - Professional color schemes
 * - Optimized rendering performance
 */

class AnalyticsChartsManager {
    constructor() {
        this.charts = {};
        this.currentTimeframe = '1D';
        this.isRefreshing = false;
        this.symbolPerformanceData = [];
        this.strategiesData = [];
    }

    /**
     * Initialize all analytics charts
     */
    async initialize() {
        console.log('Analytics Charts: Initializing...');
        
        // Initialize equity curve chart
        this.initEquityCurveChart();
        
        // Initialize daily P/L chart
        this.initDailyPnLChart();
        
        // Load initial data
        await this.refreshAllCharts();
        
        // Setup timeframe toggles
        this.setupTimeframeToggles();
        
        // Setup refresh button
        this.setupRefreshButton();
        
        // Setup table sorting
        this.setupTableSorting();
        
        console.log('Analytics Charts: Initialized successfully');
    }

    /**
     * Initialize TradingView Lightweight Charts for equity curve
     */
    initEquityCurveChart() {
        const container = document.getElementById('equity-curve-chart');
        if (!container) return;

        // Create chart with professional styling
        this.charts.equityCurve = LightweightCharts.createChart(container, {
            layout: {
                background: { color: 'transparent' },
                textColor: '#333',
            },
            grid: {
                vertLines: { color: '#f0f0f0' },
                horzLines: { color: '#f0f0f0' },
            },
            width: container.clientWidth,
            height: 400,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#e0e0e0',
            },
            rightPriceScale: {
                borderColor: '#e0e0e0',
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
        });

        // Add area series for equity curve
        this.charts.equitySeries = this.charts.equityCurve.addAreaSeries({
            topColor: 'rgba(124, 58, 237, 0.4)',
            bottomColor: 'rgba(124, 58, 237, 0.0)',
            lineColor: 'rgba(124, 58, 237, 1)',
            lineWidth: 2,
            priceFormat: {
                type: 'price',
                precision: 2,
                minMove: 0.01,
            },
        });

        // Handle resize
        window.addEventListener('resize', () => {
            if (this.charts.equityCurve) {
                this.charts.equityCurve.applyOptions({
                    width: container.clientWidth
                });
            }
        });
    }

    /**
     * Initialize daily P/L bar chart container
     */
    initDailyPnLChart() {
        const container = document.getElementById('daily-pnl-chart');
        if (!container) return;

        // Create canvas for custom bar chart
        const canvas = document.createElement('canvas');
        canvas.id = 'daily-pnl-canvas';
        canvas.width = container.clientWidth;
        canvas.height = 300;
        container.appendChild(canvas);

        // Handle resize
        window.addEventListener('resize', () => {
            if (canvas) {
                canvas.width = container.clientWidth;
                this.renderDailyPnLChart();
            }
        });
    }

    /**
     * Refresh all charts with latest data
     */
    async refreshAllCharts() {
        if (this.isRefreshing) return;

        this.isRefreshing = true;
        this.showRefreshingState();

        try {
            // Fetch all data in parallel for performance
            const [equityData, dailyPnLData, symbolData, strategiesData] = await Promise.all([
                this.fetchEquityCurve(),
                this.fetchDailyPnL(),
                this.fetchSymbolPerformance(),
                this.fetchTopStrategies()
            ]);

            // Render charts
            this.renderEquityCurve(equityData);
            this.renderDailyPnLChart(dailyPnLData);
            this.renderSymbolTable(symbolData);
            this.renderStrategiesTable(strategiesData);

            // Store data for sorting
            this.symbolPerformanceData = symbolData;
            this.strategiesData = strategiesData;

            this.hideRefreshingState();
        } catch (error) {
            console.error('Failed to refresh charts:', error);
            this.showError('Failed to load analytics data. Please try again.');
            this.hideRefreshingState();
        } finally {
            this.isRefreshing = false;
        }
    }

    /**
     * Fetch equity curve data from API
     */
    async fetchEquityCurve() {
        const response = await fetch(`/api/analytics/equity-curve?timeframe=${this.currentTimeframe}`, {
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const result = await response.json();
        return result.data;
    }

    /**
     * Fetch daily P/L data from API
     */
    async fetchDailyPnL() {
        // For daily P/L, use appropriate timeframe
        const pnlTimeframe = this.getPnLTimeframe();
        
        const response = await fetch(`/api/analytics/daily-pnl?timeframe=${pnlTimeframe}`, {
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const result = await response.json();
        return result.data;
    }

    /**
     * Fetch symbol performance data from API
     */
    async fetchSymbolPerformance() {
        const response = await fetch('/api/analytics/symbols?timeframe=all', {
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const result = await response.json();
        return result.data.data || [];
    }

    /**
     * Fetch top strategies data from API
     */
    async fetchTopStrategies() {
        const response = await fetch('/api/analytics/top-strategies?timeframe=all&limit=10', {
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const result = await response.json();
        return result.data.data || [];
    }

    /**
     * Render equity curve chart
     */
    renderEquityCurve(data) {
        if (!this.charts.equitySeries || !data.data) return;

        // Set data to chart
        this.charts.equitySeries.setData(data.data);

        // Fit content to visible range
        this.charts.equityCurve.timeScale().fitContent();

        // Update summary stats
        this.updateEquityStats(data);
    }

    /**
     * Update equity curve summary statistics
     */
    updateEquityStats(data) {
        const currentBalance = document.getElementById('equity-current-balance');
        const peakBalance = document.getElementById('equity-peak-balance');
        const totalTrades = document.getElementById('equity-total-trades');

        if (currentBalance) {
            const sign = data.current_balance >= 0 ? '+' : '';
            currentBalance.textContent = `${sign}$${data.current_balance.toFixed(2)}`;
            currentBalance.className = data.current_balance >= 0 ? 'text-green-600' : 'text-red-600';
        }

        if (peakBalance) {
            peakBalance.textContent = `$${data.peak_balance.toFixed(2)}`;
        }

        if (totalTrades) {
            totalTrades.textContent = data.total_trades || 0;
        }
    }

    /**
     * Render daily P/L bar chart using canvas
     */
    renderDailyPnLChart(data) {
        const canvas = document.getElementById('daily-pnl-canvas');
        if (!canvas || !data.data) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        const dailyData = data.data;
        if (dailyData.length === 0) {
            ctx.fillStyle = '#999';
            ctx.font = '14px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No data available', width / 2, height / 2);
            return;
        }

        // Calculate scales
        const padding = 40;
        const barWidth = (width - padding * 2) / dailyData.length;
        const maxPnL = Math.max(...dailyData.map(d => Math.abs(d.pnl)));
        const yScale = (height - padding * 2) / (maxPnL * 2);

        // Draw zero line
        const zeroY = height / 2;
        ctx.strokeStyle = '#ccc';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding, zeroY);
        ctx.lineTo(width - padding, zeroY);
        ctx.stroke();

        // Draw bars
        dailyData.forEach((day, index) => {
            const x = padding + index * barWidth;
            const barHeight = Math.abs(day.pnl) * yScale;
            const y = day.pnl >= 0 ? zeroY - barHeight : zeroY;

            // Set color based on profit/loss
            ctx.fillStyle = day.pnl >= 0 ? '#10b981' : '#ef4444';
            ctx.fillRect(x + 2, y, barWidth - 4, barHeight);
        });

        // Update summary stats
        this.updateDailyPnLStats(data);
    }

    /**
     * Update daily P/L summary statistics
     */
    updateDailyPnLStats(data) {
        const profitDays = document.getElementById('pnl-profit-days');
        const lossDays = document.getElementById('pnl-loss-days');
        const bestDay = document.getElementById('pnl-best-day');
        const worstDay = document.getElementById('pnl-worst-day');

        if (profitDays) profitDays.textContent = data.total_profit_days || 0;
        if (lossDays) lossDays.textContent = data.total_loss_days || 0;
        if (bestDay) bestDay.textContent = `$${data.best_day.toFixed(2)}`;
        if (worstDay) worstDay.textContent = `$${data.worst_day.toFixed(2)}`;
    }

    /**
     * Render symbol performance table
     */
    renderSymbolTable(symbols) {
        const tbody = document.getElementById('symbol-performance-tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (symbols.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="px-4 py-8 text-center text-gray-500">
                        No symbol data available
                    </td>
                </tr>
            `;
            return;
        }

        symbols.forEach(symbol => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            row.innerHTML = `
                <td class="px-4 py-3 font-semibold text-gray-900">${symbol.symbol}</td>
                <td class="px-4 py-3 text-gray-600">${symbol.trades}</td>
                <td class="px-4 py-3">
                    <span class="${this.getWinRateColorClass(symbol.win_rate)} font-semibold">
                        ${symbol.win_rate.toFixed(1)}%
                    </span>
                </td>
                <td class="px-4 py-3">
                    <span class="${symbol.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'} font-semibold">
                        ${symbol.total_pnl >= 0 ? '+' : ''}$${symbol.total_pnl.toFixed(2)}
                    </span>
                </td>
                <td class="px-4 py-3 text-gray-600">$${symbol.avg_pnl.toFixed(2)}</td>
                <td class="px-4 py-3">
                    <span class="${this.getProfitFactorColorClass(symbol.profit_factor)} font-semibold">
                        ${symbol.profit_factor.toFixed(2)}
                    </span>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    /**
     * Render top strategies table
     */
    renderStrategiesTable(strategies) {
        const tbody = document.getElementById('strategies-performance-tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (strategies.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="px-4 py-8 text-center text-gray-500">
                        No strategy data available
                    </td>
                </tr>
            `;
            return;
        }

        strategies.forEach((strategy, index) => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            row.innerHTML = `
                <td class="px-4 py-3 font-semibold text-gray-900">#${index + 1}</td>
                <td class="px-4 py-3 text-gray-900">${strategy.strategy_name}</td>
                <td class="px-4 py-3 text-gray-600">${strategy.trades}</td>
                <td class="px-4 py-3">
                    <span class="${this.getWinRateColorClass(strategy.win_rate)} font-semibold">
                        ${strategy.win_rate.toFixed(1)}%
                    </span>
                </td>
                <td class="px-4 py-3">
                    <span class="${this.getProfitFactorColorClass(strategy.profit_factor)} font-semibold">
                        ${strategy.profit_factor.toFixed(2)}
                    </span>
                </td>
                <td class="px-4 py-3">
                    <span class="${strategy.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'} font-semibold">
                        ${strategy.total_pnl >= 0 ? '+' : ''}$${strategy.total_pnl.toFixed(2)}
                    </span>
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    /**
     * Get CSS color class for win rate
     */
    getWinRateColorClass(winRate) {
        if (winRate >= 60) return 'text-green-600';
        if (winRate >= 50) return 'text-yellow-600';
        return 'text-red-600';
    }

    /**
     * Get CSS color class for profit factor
     */
    getProfitFactorColorClass(pf) {
        if (pf >= 2.0) return 'text-green-600';
        if (pf >= 1.5) return 'text-green-500';
        if (pf >= 1.0) return 'text-yellow-600';
        return 'text-red-600';
    }

    /**
     * Get appropriate P/L timeframe based on equity timeframe
     */
    getPnLTimeframe() {
        const map = {
            '1H': '1W',
            '4H': '1W',
            '1D': '1W',
            '1W': '1M',
            '1M': '3M',
            'All': 'All'
        };
        return map[this.currentTimeframe] || '1M';
    }

    /**
     * Setup timeframe toggle buttons
     */
    setupTimeframeToggles() {
        const toggles = document.querySelectorAll('[data-chart-timeframe]');

        toggles.forEach(toggle => {
            // Set active state
            if (toggle.dataset.chartTimeframe === this.currentTimeframe) {
                toggle.classList.add('bg-purple-600', 'text-white');
                toggle.classList.remove('text-gray-600', 'hover:bg-gray-100');
            }

            // Add click handler
            toggle.addEventListener('click', async (e) => {
                const newTimeframe = e.target.dataset.chartTimeframe;

                if (newTimeframe !== this.currentTimeframe) {
                    // Update active state
                    toggles.forEach(t => {
                        t.classList.remove('bg-purple-600', 'text-white');
                        t.classList.add('text-gray-600', 'hover:bg-gray-100');
                    });

                    e.target.classList.add('bg-purple-600', 'text-white');
                    e.target.classList.remove('text-gray-600', 'hover:bg-gray-100');

                    // Update timeframe and refresh
                    this.currentTimeframe = newTimeframe;
                    await this.refreshAllCharts();
                }
            });
        });
    }

    /**
     * Setup manual refresh button
     */
    setupRefreshButton() {
        const refreshBtn = document.getElementById('refresh-analytics-btn');
        if (!refreshBtn) return;

        refreshBtn.addEventListener('click', async () => {
            await this.refreshAllCharts();
        });
    }

    /**
     * Setup table sorting functionality
     */
    setupTableSorting() {
        const headers = document.querySelectorAll('[data-sort-table]');

        headers.forEach(header => {
            header.addEventListener('click', (e) => {
                const table = e.target.dataset.sortTable;
                const column = e.target.dataset.sortColumn;
                this.sortTable(table, column);
            });
        });
    }

    /**
     * Sort table by column
     */
    sortTable(tableName, column) {
        let data = tableName === 'symbols' ? this.symbolPerformanceData : this.strategiesData;
        
        // Toggle sort direction
        const currentDir = this[`${tableName}SortDir`] || 'desc';
        const newDir = currentDir === 'desc' ? 'asc' : 'desc';
        this[`${tableName}SortDir`] = newDir;

        // Sort data
        data.sort((a, b) => {
            const valA = a[column];
            const valB = b[column];
            
            if (typeof valA === 'string') {
                return newDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
            } else {
                return newDir === 'asc' ? valA - valB : valB - valA;
            }
        });

        // Re-render table
        if (tableName === 'symbols') {
            this.renderSymbolTable(data);
        } else {
            this.renderStrategiesTable(data);
        }
    }

    /**
     * Show refreshing state
     */
    showRefreshingState() {
        const refreshBtn = document.getElementById('refresh-analytics-btn');
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = `
                <svg class="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Refreshing...
            `;
        }

        // Show loading on charts
        const containers = ['equity-curve-chart', 'daily-pnl-chart'];
        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('opacity-50', 'animate-pulse');
        });
    }

    /**
     * Hide refreshing state
     */
    hideRefreshingState() {
        const refreshBtn = document.getElementById('refresh-analytics-btn');
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = `
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                </svg>
                Refresh Analytics
            `;
        }

        // Remove loading from charts
        const containers = ['equity-curve-chart', 'daily-pnl-chart'];
        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('opacity-50', 'animate-pulse');
        });
    }

    /**
     * Show error message
     */
    showError(message) {
        const errorContainer = document.getElementById('analytics-error-container');
        if (!errorContainer) return;

        errorContainer.textContent = message;
        errorContainer.classList.remove('hidden');

        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorContainer.classList.add('hidden');
        }, 5000);
    }
}

// Global instance
let analyticsChartsManager;

// Initialize when DOM is ready and TradingView Charts library is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Check if we're on analytics page
    if (document.getElementById('equity-curve-chart')) {
        console.log('Analytics Charts: Starting initialization...');
        
        // Wait for TradingView Lightweight Charts to load
        if (typeof LightweightCharts !== 'undefined') {
            analyticsChartsManager = new AnalyticsChartsManager();
            analyticsChartsManager.initialize();
        } else {
            console.error('TradingView Lightweight Charts not loaded!');
        }
    }
});
