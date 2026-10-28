/**
 * Notification Center - Smart Polling Architecture
 * In-app notification system with 10-second polling for real-time feel
 */

class NotificationCenter {
    constructor() {
        this.notifications = [];
        this.unreadCount = 0;
        this.pollInterval = 10000; // 10 seconds
        this.pollTimer = null;
        this.isOpen = false;
        this.lastPollTime = null;
    }

    /**
     * Initialize notification center
     */
    async initialize() {
        console.log('Notification Center: Initializing...');
        
        // Render bell icon in header
        this.renderBellIcon();
        
        // Initial load
        await this.refreshNotifications();
        
        // Start polling
        this.startPolling();
        
        // Attach event listeners
        this.attachEventListeners();
        
        console.log('Notification Center: Initialized successfully');
    }

    /**
     * Render bell icon in header (before account selector)
     */
    renderBellIcon() {
        const accountSelector = document.getElementById('account-selector-trigger');
        if (!accountSelector) {
            console.warn('Account selector not found, cannot render bell icon');
            return;
        }

        const bellIcon = document.createElement('div');
        bellIcon.id = 'notification-bell';
        bellIcon.className = 'relative cursor-pointer hover:bg-white hover:bg-opacity-20 p-2 rounded-lg transition';
        bellIcon.title = 'Notifications';
        bellIcon.innerHTML = `
            <svg class="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>
            </svg>
            <span id="notification-badge" class="hidden absolute -top-1 -right-1 bg-red-600 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">0</span>
        `;

        // Insert before account selector
        accountSelector.parentNode.insertBefore(bellIcon, accountSelector);
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        const bellIcon = document.getElementById('notification-bell');
        if (bellIcon) {
            bellIcon.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleDropdown();
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (this.isOpen && !e.target.closest('#notification-dropdown')) {
                this.closeDropdown();
            }
        });
    }

    /**
     * Start polling for new notifications
     */
    startPolling() {
        // Initial poll
        this.pollForUpdates();
        
        // Set up interval
        this.pollTimer = setInterval(() => {
            this.pollForUpdates();
        }, this.pollInterval);
        
        console.log(`Notification Center: Polling started (every ${this.pollInterval/1000}s)`);
    }

    /**
     * Stop polling
     */
    stopPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }

    /**
     * Poll for notification updates
     */
    async pollForUpdates() {
        try {
            const response = await fetch('/api/notifications/unread-count', {
                credentials: 'same-origin'
            });

            if (response.ok) {
                const data = await response.json();
                
                if (data.status === 'success') {
                    const newCount = data.unread_count;
                    
                    // Update badge if count changed
                    if (newCount !== this.unreadCount) {
                        console.log(`Notification Center: Unread count changed: ${this.unreadCount} → ${newCount}`);
                        this.unreadCount = newCount;
                        this.updateBadge();
                        
                        // If count increased, refresh full list
                        if (newCount > this.unreadCount || newCount > 0) {
                            await this.refreshNotifications();
                        }
                    }
                }
            }
            
            this.lastPollTime = new Date();
            
        } catch (error) {
            console.error('Failed to poll notifications:', error);
        }
    }

    /**
     * Refresh full notifications list
     */
    async refreshNotifications() {
        try {
            const response = await fetch('/api/notifications?limit=20', {
                credentials: 'same-origin'
            });

            if (response.ok) {
                const data = await response.json();
                
                if (data.status === 'success') {
                    this.notifications = data.notifications;
                    this.unreadCount = this.notifications.filter(n => !n.is_read).length;
                    this.updateBadge();
                    
                    // Update dropdown if open
                    if (this.isOpen) {
                        this.renderDropdown();
                    }
                }
            }
            
        } catch (error) {
            console.error('Failed to refresh notifications:', error);
        }
    }

    /**
     * Update badge count
     */
    updateBadge() {
        const badge = document.getElementById('notification-badge');
        if (!badge) return;

        if (this.unreadCount > 0) {
            badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    /**
     * Toggle notification dropdown
     */
    toggleDropdown() {
        if (this.isOpen) {
            this.closeDropdown();
        } else {
            this.openDropdown();
        }
    }

    /**
     * Open notification dropdown
     */
    async openDropdown() {
        // Refresh notifications before opening
        await this.refreshNotifications();
        
        // Remove existing dropdown
        const existing = document.getElementById('notification-dropdown');
        if (existing) {
            existing.remove();
        }

        // Create dropdown
        const dropdown = this.createDropdown();
        document.body.appendChild(dropdown);

        // Position dropdown
        this.positionDropdown(dropdown);

        this.isOpen = true;
    }

    /**
     * Close notification dropdown
     */
    closeDropdown() {
        const dropdown = document.getElementById('notification-dropdown');
        if (dropdown) {
            dropdown.remove();
        }
        this.isOpen = false;
    }

    /**
     * Create dropdown HTML
     */
    createDropdown() {
        const div = document.createElement('div');
        div.id = 'notification-dropdown';
        div.className = 'notification-dropdown';
        
        this.renderDropdown(div);
        
        return div;
    }

    /**
     * Render dropdown content
     */
    renderDropdown(container = null) {
        const dropdown = container || document.getElementById('notification-dropdown');
        if (!dropdown) return;

        let html = `
            <div class="notification-dropdown-header">
                <span class="font-semibold">Notifications</span>
                ${this.unreadCount > 0 ? `
                    <button id="mark-all-read-btn" class="text-xs text-purple-600 hover:text-purple-700 font-semibold">
                        Mark all as read
                    </button>
                ` : ''}
            </div>
        `;

        if (this.notifications.length === 0) {
            html += `
                <div class="notification-dropdown-empty">
                    <svg class="w-12 h-12 text-gray-300 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>
                    </svg>
                    <p class="text-gray-500">No notifications</p>
                </div>
            `;
        } else {
            html += '<div class="notification-dropdown-list">';
            
            this.notifications.forEach(notification => {
                html += this.renderNotificationItem(notification);
            });
            
            html += '</div>';
        }

        dropdown.innerHTML = html;

        // Attach event listeners
        if (this.unreadCount > 0) {
            const markAllBtn = dropdown.querySelector('#mark-all-read-btn');
            if (markAllBtn) {
                markAllBtn.addEventListener('click', () => this.markAllAsRead());
            }
        }

        dropdown.querySelectorAll('.notification-item').forEach(item => {
            item.addEventListener('click', () => {
                const notificationId = item.dataset.notificationId;
                const isRead = item.dataset.isRead === 'true';
                
                if (!isRead) {
                    this.markAsRead(notificationId);
                }
            });
        });
    }

    /**
     * Render single notification item
     */
    renderNotificationItem(notification) {
        const isRead = notification.is_read;
        const timeAgo = this.getTimeAgo(notification.created_at);
        
        const priorityColors = {
            'urgent': 'border-l-red-600',
            'high': 'border-l-orange-500',
            'normal': 'border-l-blue-500',
            'low': 'border-l-gray-400'
        };
        
        const priorityColor = priorityColors[notification.priority] || priorityColors['normal'];

        return `
            <div class="notification-item ${isRead ? 'read' : 'unread'} ${priorityColor}" 
                 data-notification-id="${notification.id}"
                 data-is-read="${isRead}">
                <div class="notification-content">
                    <div class="notification-title">${notification.title}</div>
                    <div class="notification-message">${notification.message}</div>
                    <div class="notification-time">${timeAgo}</div>
                </div>
                ${!isRead ? '<div class="notification-unread-dot"></div>' : ''}
            </div>
        `;
    }

    /**
     * Position dropdown
     */
    positionDropdown(dropdown) {
        const bellIcon = document.getElementById('notification-bell');
        
        if (bellIcon) {
            const rect = bellIcon.getBoundingClientRect();
            dropdown.style.position = 'fixed';
            dropdown.style.top = `${rect.bottom + 8}px`;
            dropdown.style.right = `${window.innerWidth - rect.right}px`;
            dropdown.style.minWidth = '360px';
            dropdown.style.maxWidth = '400px';
        }
    }

    /**
     * Mark notification as read
     */
    async markAsRead(notificationId) {
        try {
            const response = await fetch(`/api/notifications/${notificationId}/read`, {
                method: 'POST',
                credentials: 'same-origin'
            });

            if (response.ok) {
                // Update local state
                const notification = this.notifications.find(n => n.id === notificationId);
                if (notification) {
                    notification.is_read = true;
                }
                
                this.unreadCount = Math.max(0, this.unreadCount - 1);
                this.updateBadge();
                
                // Update dropdown
                if (this.isOpen) {
                    this.renderDropdown();
                }
            }
            
        } catch (error) {
            console.error('Failed to mark notification as read:', error);
        }
    }

    /**
     * Mark all notifications as read
     */
    async markAllAsRead() {
        try {
            const response = await fetch('/api/notifications/read-all', {
                method: 'POST',
                credentials: 'same-origin'
            });

            if (response.ok) {
                // Update local state
                this.notifications.forEach(n => n.is_read = true);
                this.unreadCount = 0;
                this.updateBadge();
                
                // Update dropdown
                if (this.isOpen) {
                    this.renderDropdown();
                }
            }
            
        } catch (error) {
            console.error('Failed to mark all as read:', error);
        }
    }

    /**
     * Get time ago string
     */
    getTimeAgo(timestamp) {
        const now = new Date();
        const time = new Date(timestamp);
        const diff = Math.floor((now - time) / 1000); // seconds

        if (diff < 60) return 'Just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
        
        return time.toLocaleDateString();
    }

    /**
     * Cleanup on page unload
     */
    destroy() {
        this.stopPolling();
        this.closeDropdown();
    }
}

// Global instance
let notificationCenter;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if header exists (authenticated pages)
    if (document.getElementById('account-selector-trigger')) {
        console.log('Notification Center: Starting initialization...');
        notificationCenter = new NotificationCenter();
        notificationCenter.initialize();
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (notificationCenter) {
        notificationCenter.destroy();
    }
});
