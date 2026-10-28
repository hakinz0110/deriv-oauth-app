/**
 * Bot Status Manager - Real-time WebSocket Updates
 * =================================================
 * Manages bot status via polling (WebSocket push to be implemented server-side later)
 * Provides real-time updates to all bot control widgets on the page
 */

class BotStatusManager {
    constructor() {
        this.botData = null;
        this.isRunning = false;
        this.pollingInterval = null;
        this.listeners = [];
        this.updateInterval = 3000; // 3 seconds
    }

    /**
     * Start monitoring bot status
     */
    async start() {
        // Initial fetch
        await this.fetchBotStatus();
        
        // Start polling
        this.pollingInterval = setInterval(() => {
            this.fetchBotStatus();
        }, this.updateInterval);
    }

    /**
     * Stop monitoring
     */
    stop() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    /**
     * Fetch bot status from API
     */
    async fetchBotStatus() {
        try {
            const response = await fetch('/api/bot/status');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.botData = data.bot;
                this.isRunning = data.is_running;
                
                // Notify all listeners
                this.notifyListeners({
                    type: 'status_update',
                    bot: data.bot,
                    executor: data.executor_status,
                    isRunning: data.is_running
                });
            }
        } catch (error) {
            console.error('Failed to fetch bot status:', error);
            this.notifyListeners({
                type: 'error',
                message: 'Failed to fetch bot status'
            });
        }
    }

    /**
     * Register listener for bot status updates
     */
    addListener(callback) {
        this.listeners.push(callback);
    }

    /**
     * Remove listener
     */
    removeListener(callback) {
        this.listeners = this.listeners.filter(cb => cb !== callback);
    }

    /**
     * Notify all listeners
     */
    notifyListeners(data) {
        this.listeners.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error('Listener error:', error);
            }
        });
    }

    /**
     * Start bot
     */
    async startBot() {
        try {
            const response = await fetch('/api/bot/start', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.fetchBotStatus();
                return { success: true, message: data.message };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    /**
     * Stop bot
     */
    async stopBot() {
        try {
            const response = await fetch('/api/bot/stop', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.fetchBotStatus();
                return { success: true, message: data.message };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    /**
     * Pause bot
     */
    async pauseBot() {
        try {
            const response = await fetch('/api/bot/pause', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.fetchBotStatus();
                return { success: true, message: data.message };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    /**
     * Resume bot
     */
    async resumeBot() {
        try {
            const response = await fetch('/api/bot/resume', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.fetchBotStatus();
                return { success: true, message: data.message };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    /**
     * Update bot configuration
     */
    async updateConfig(config) {
        try {
            const response = await fetch('/api/bot/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.fetchBotStatus();
                return { success: true, message: data.message };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    /**
     * Set active trading systems
     */
    async setTradingSystems(systemIds) {
        try {
            const response = await fetch('/api/bot/trading-systems', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ trading_system_ids: systemIds })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.fetchBotStatus();
                return { success: true, message: data.message };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    /**
     * Get bot logs
     */
    async getLogs(limit = 50, eventType = null) {
        try {
            let url = `/api/bot/logs?limit=${limit}`;
            if (eventType) {
                url += `&event_type=${eventType}`;
            }
            
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.status === 'success') {
                return { success: true, logs: data.logs };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    /**
     * Get current bot status
     */
    getStatus() {
        return {
            bot: this.botData,
            isRunning: this.isRunning
        };
    }
}

// Global instance
window.botStatusManager = new BotStatusManager();

// Auto-start when page loads
document.addEventListener('DOMContentLoaded', () => {
    if (window.botStatusManager) {
        window.botStatusManager.start();
    }
});

// Stop when page unloads
window.addEventListener('beforeunload', () => {
    if (window.botStatusManager) {
        window.botStatusManager.stop();
    }
});
