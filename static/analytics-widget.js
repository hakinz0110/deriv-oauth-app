/**
 * Real-time Analytics Widget for Dashboard
 * Displays live trading performance metrics with auto-refresh on trade completion
 */

class AnalyticsWidget {
    constructor() {
        this.timeframe = localStorage.getItem('analytics_timeframe') || 'daily';
        this.lastPollTime = null;
        this.pollInterval = 10000; // Poll every 10 seconds for trade closures
        this.refreshThrottle = 2000; // Min 2s between analytics refreshes
        this.lastRefreshTime = 0;
        this.charts = {};
    }

    /**
     * Initialize analytics widget
     */
    async initialize() {
        console.log('Analytics Widget: Initializing...');
        
        // Load initial analytics data
        await this.loadAnalytics();
        
        // Start polling for trade closures
        this.startPolling();
        
        // Set up timeframe toggle handlers
        this.setupTimeframeToggles();
        
        console.log('Analytics Widget: Initialized successfully');
    }

    /**
     * Load analytics data from API
     */
    async loadAnalytics() {
        try {
            // Show loading state
            this.showLoadingState();
            
            const response = await fetch(`/api/analytics/overview?timeframe=${this.timeframe}`, {
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error(`API returned ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.renderAnalytics(data.data);
            } else {
                throw new Error(data.message || 'Failed to load analytics');
            }
        } catch (error) {
            console.error('Failed to load analytics:', error);
            this.showErrorState(error.message);
        }
    }

    /**
     * Render analytics widgets on dashboard
     */
    renderAnalytics(data) {
        console.log('Rendering analytics:', data);
        
        // Update win rate widget
        this.updateWinRate(data.win_rate);
        
        // Update profit factor
        this.updateProfitFactor(data.profit_factor);
        
        // Update total P/L
        this.updateTotalPnL(data.summary);
        
        // Update trades count
        this.updateTradesCount(data.summary);
        
        // Update max drawdown
        this.updateMaxDrawdown(data.max_drawdown);
        
        // Update expectancy
        this.updateExpectancy(data.expectancy);
        
        // Hide loading state
        this.hideLoadingState();
    }

    /**
     * Update win rate widget with gauge chart
     */
    updateWinRate(winRateData) {
        const element = document.getElementById('win-rate-value');
        if (!element) return;
        
        const winRate = winRateData.win_rate || 0;
        element.textContent = `${winRate.toFixed(1)}%`;
        
        // Color code based on performance
        element.classList.remove('text-green-600', 'text-yellow-600', 'text-red-600');
        if (winRate >= 60) {
            element.classList.add('text-green-600');
        } else if (winRate >= 50) {
            element.classList.add('text-yellow-600');
        } else {
            element.classList.add('text-red-600');
        }
        
        // Update subtitle
        const subtitle = document.getElementById('win-rate-subtitle');
        if (subtitle) {
            subtitle.textContent = `${winRateData.winning_trades}W / ${winRateData.losing_trades}L`;
        }
    }

    /**
     * Update profit factor display
     */
    updateProfitFactor(pfData) {
        const element = document.getElementById('profit-factor-value');
        if (!element) return;
        
        const pf = pfData.profit_factor || 0;
        element.textContent = pf.toFixed(2);
        
        // Update rating badge
        const ratingBadge = document.getElementById('pf-rating');
        if (ratingBadge) {
            const ratingText = {
                'excellent': 'Excellent',
                'very_good': 'Very Good',
                'good': 'Good',
                'mediocre': 'Mediocre',
                'losing': 'Losing'
            }[pfData.rating] || 'N/A';
            
            ratingBadge.textContent = ratingText;
            
            // Color code
            ratingBadge.classList.remove('bg-green-100', 'text-green-700', 'bg-yellow-100', 'text-yellow-700', 'bg-red-100', 'text-red-700');
            if (pfData.rating === 'excellent' || pfData.rating === 'very_good') {
                ratingBadge.classList.add('bg-green-100', 'text-green-700');
            } else if (pfData.rating === 'good' || pfData.rating === 'mediocre') {
                ratingBadge.classList.add('bg-yellow-100', 'text-yellow-700');
            } else {
                ratingBadge.classList.add('bg-red-100', 'text-red-700');
            }
        }
    }

    /**
     * Update total P/L display
     */
    updateTotalPnL(summary) {
        const element = document.getElementById('analytics-total-pnl');
        if (!element) return;
        
        const totalPnL = summary.total_pnl || 0;
        const sign = totalPnL >= 0 ? '+' : '';
        element.textContent = `${sign}$${totalPnL.toFixed(2)}`;
        
        // Color code
        element.classList.remove('text-green-600', 'text-red-600', 'text-gray-600');
        if (totalPnL > 0) {
            element.classList.add('text-green-600');
        } else if (totalPnL < 0) {
            element.classList.add('text-red-600');
        } else {
            element.classList.add('text-gray-600');
        }
    }

    /**
     * Update trades count
     */
    updateTradesCount(summary) {
        const element = document.getElementById('analytics-trades-count');
        if (!element) return;
        
        element.textContent = summary.total_trades || 0;
    }

    /**
     * Update max drawdown display
     */
    updateMaxDrawdown(ddData) {
        const element = document.getElementById('max-drawdown-value');
        if (!element) return;
        
        const dd = ddData.max_drawdown_pct || 0;
        element.textContent = `${dd.toFixed(1)}%`;
        
        // Color code (lower is better)
        element.classList.remove('text-green-600', 'text-yellow-600', 'text-red-600');
        if (dd < 10) {
            element.classList.add('text-green-600');
        } else if (dd < 20) {
            element.classList.add('text-yellow-600');
        } else {
            element.classList.add('text-red-600');
        }
    }

    /**
     * Update expectancy display
     */
    updateExpectancy(expData) {
        const element = document.getElementById('expectancy-value');
        if (!element) return;
        
        const exp = expData.expectancy || 0;
        const sign = exp >= 0 ? '+' : '';
        element.textContent = `${sign}$${exp.toFixed(2)}`;
        
        // Color code
        element.classList.remove('text-green-600', 'text-yellow-600', 'text-red-600');
        if (expData.assessment === 'excellent' || expData.assessment === 'good') {
            element.classList.add('text-green-600');
        } else if (expData.assessment === 'positive') {
            element.classList.add('text-yellow-600');
        } else {
            element.classList.add('text-red-600');
        }
    }

    /**
     * Start polling for trade closures
     */
    startPolling() {
        setInterval(() => this.checkForTradeClosures(), this.pollInterval);
    }

    /**
     * Check for recent trade closures and refresh if found
     */
    async checkForTradeClosures() {
        try {
            const since = this.lastPollTime || new Date(Date.now() - 60000).toISOString();
            
            const response = await fetch(`/api/bot/recent-closures?since=${since}&limit=5`, {
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.status === 'success' && data.count > 0) {
                    console.log(`Analytics Widget: Detected ${data.count} trade closure(s), refreshing...`);
                    
                    // Throttle refresh
                    const now = Date.now();
                    if (now - this.lastRefreshTime >= this.refreshThrottle) {
                        await this.loadAnalytics();
                        this.lastRefreshTime = now;
                    }
                }
            }
            
            this.lastPollTime = new Date().toISOString();
        } catch (error) {
            console.error('Failed to check for trade closures:', error);
        }
    }

    /**
     * Setup timeframe toggle buttons
     */
    setupTimeframeToggles() {
        const toggles = document.querySelectorAll('[data-analytics-timeframe]');
        
        toggles.forEach(toggle => {
            // Set active state
            if (toggle.dataset.analyticsTimeframe === this.timeframe) {
                toggle.classList.add('bg-purple-600', 'text-white');
                toggle.classList.remove('text-gray-600', 'hover:bg-gray-100');
            }
            
            // Add click handler
            toggle.addEventListener('click', async (e) => {
                const newTimeframe = e.target.dataset.analyticsTimeframe;
                
                if (newTimeframe !== this.timeframe) {
                    // Update active state
                    toggles.forEach(t => {
                        t.classList.remove('bg-purple-600', 'text-white');
                        t.classList.add('text-gray-600', 'hover:bg-gray-100');
                    });
                    
                    e.target.classList.add('bg-purple-600', 'text-white');
                    e.target.classList.remove('text-gray-600', 'hover:bg-gray-100');
                    
                    // Update timeframe and reload
                    this.timeframe = newTimeframe;
                    localStorage.setItem('analytics_timeframe', newTimeframe);
                    
                    await this.loadAnalytics();
                }
            });
        });
    }

    /**
     * Show loading skeleton
     */
    showLoadingState() {
        // Add loading class to widgets
        const widgets = document.querySelectorAll('[data-analytics-widget]');
        widgets.forEach(widget => {
            widget.classList.add('animate-pulse', 'opacity-50');
        });
    }

    /**
     * Hide loading skeleton
     */
    hideLoadingState() {
        const widgets = document.querySelectorAll('[data-analytics-widget]');
        widgets.forEach(widget => {
            widget.classList.remove('animate-pulse', 'opacity-50');
        });
    }

    /**
     * Show error state
     */
    showErrorState(message) {
        console.error('Analytics error:', message);
        
        // Show error indicator (simple approach - replace with better UI if needed)
        const errorContainer = document.getElementById('analytics-error');
        if (errorContainer) {
            errorContainer.textContent = `Analytics unavailable: ${message}`;
            errorContainer.classList.remove('hidden');
        }
        
        this.hideLoadingState();
    }
}

// Global instance
let analyticsWidget;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're on dashboard page
    if (document.getElementById('analytics-widgets-container')) {
        console.log('Analytics Widget: Starting initialization...');
        analyticsWidget = new AnalyticsWidget();
        analyticsWidget.initialize();
    }
});
