/**
 * Account Selector Overlay Component
 * Allows users to switch between trading accounts (demo/real)
 * with bot status detection and WebSocket reconnection
 */
class AccountSelector {
    constructor() {
        this.accounts = [];
        this.selectedAccountId = null;
        this.isBotRunning = false;
        this.isOpen = false;
        this.onAccountSwitch = null; // Callback when account changes
    }

    /**
     * Initialize the account selector
     * @param {Function} onSwitchCallback - Called when account is switched
     */
    async initialize(onSwitchCallback) {
        this.onAccountSwitch = onSwitchCallback;
        await this.loadAccounts();
        await this.loadSelectedAccount();
        this.attachEventListeners();
        this.updateBotStatus();
    }

    /**
     * Fetch all available accounts from API
     */
    async loadAccounts() {
        try {
            const response = await fetch('/accounts', {
                credentials: 'same-origin'
            });

            if (!response.ok) {
                console.error('Failed to load accounts:', response.status);
                return;
            }

            const data = await response.json();
            this.accounts = data.accounts || [];
            console.log('Loaded accounts:', this.accounts.length);
        } catch (error) {
            console.error('Error loading accounts:', error);
        }
    }

    /**
     * Get currently selected account from backend
     */
    async loadSelectedAccount() {
        try {
            const response = await fetch('/accounts/selected', {
                credentials: 'same-origin'
            });

            if (response.ok) {
                const data = await response.json();
                if (data.selected_account) {
                    this.selectedAccountId = data.selected_account.account_id;
                }
            }
        } catch (error) {
            console.error('Error loading selected account:', error);
        }
    }

    /**
     * Update bot running status from API
     */
    async updateBotStatus() {
        try {
            const response = await fetch('/api/bot/status', {
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.isBotRunning = (data.status === 'running');
            } else {
                this.isBotRunning = false;
            }
        } catch (error) {
            console.error('Error checking bot status:', error);
            this.isBotRunning = false;
        }
    }

    /**
     * Attach click listeners to account selector triggers
     */
    attachEventListeners() {
        console.log('[AccountSelector] Attaching event listeners...');
        
        // Dashboard header account selector trigger
        const headerTrigger = document.getElementById('account-selector-trigger');
        if (headerTrigger) {
            console.log('[AccountSelector] Found header trigger, attaching click handler');
            headerTrigger.addEventListener('click', (e) => {
                console.log('[AccountSelector] Header trigger clicked');
                e.stopPropagation();
                this.toggleDropdown();
            });
        } else {
            console.warn('[AccountSelector] Header trigger not found!');
        }

        // Legacy: Dashboard account type badge (fallback)
        const accountTypeBadge = document.querySelector('.demo-badge');
        if (accountTypeBadge) {
            console.log('[AccountSelector] Found legacy badge trigger');
            accountTypeBadge.style.cursor = 'pointer';
            accountTypeBadge.addEventListener('click', (e) => {
                console.log('[AccountSelector] Legacy badge clicked');
                e.stopPropagation();
                this.toggleDropdown();
            });
        }

        // Settings account selector trigger (if exists)
        const settingsSelector = document.getElementById('settings-account-selector');
        if (settingsSelector) {
            console.log('[AccountSelector] Found settings selector trigger');
            settingsSelector.addEventListener('click', (e) => {
                console.log('[AccountSelector] Settings selector clicked');
                e.stopPropagation();
                this.toggleDropdown();
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (this.isOpen && !e.target.closest('.account-dropdown')) {
                console.log('[AccountSelector] Closing dropdown (outside click)');
                this.closeDropdown();
            }
        });
        
        console.log('[AccountSelector] Event listeners attached successfully');
    }

    /**
     * Toggle dropdown visibility
     */
    toggleDropdown() {
        console.log('[AccountSelector] Toggle dropdown called, currently open:', this.isOpen);
        if (this.isOpen) {
            this.closeDropdown();
        } else {
            this.openDropdown();
        }
    }

    /**
     * Open the account selector dropdown
     */
    async openDropdown() {
        console.log('[AccountSelector] Opening dropdown...');
        
        // Update bot status before opening
        await this.updateBotStatus();
        console.log('[AccountSelector] Bot status:', this.isBotRunning ? 'RUNNING' : 'STOPPED');

        // Remove existing dropdown if any
        const existing = document.getElementById('account-selector-dropdown');
        if (existing) {
            console.log('[AccountSelector] Removing existing dropdown');
            existing.remove();
        }

        // Create dropdown overlay
        const dropdown = this.createDropdown();
        document.body.appendChild(dropdown);
        console.log('[AccountSelector] Dropdown created with', this.accounts.length, 'accounts');

        // Position dropdown
        this.positionDropdown(dropdown);

        this.isOpen = true;
        console.log('[AccountSelector] Dropdown opened successfully');
    }

    /**
     * Close the account selector dropdown
     */
    closeDropdown() {
        const dropdown = document.getElementById('account-selector-dropdown');
        if (dropdown) {
            dropdown.remove();
        }
        this.isOpen = false;
    }

    /**
     * Create dropdown HTML element
     */
    createDropdown() {
        const dropdown = document.createElement('div');
        dropdown.id = 'account-selector-dropdown';
        dropdown.className = 'account-dropdown';

        let html = '<div class="account-dropdown-header">Select Trading Account</div>';

        if (this.isBotRunning) {
            html += '<div class="account-dropdown-warning">⚠️ Stop bot to switch accounts</div>';
        }

        html += '<div class="account-dropdown-list">';

        if (this.accounts.length === 0) {
            html += '<div class="account-dropdown-empty">No accounts available</div>';
        } else {
            this.accounts.forEach(account => {
                const isSelected = account.account_id === this.selectedAccountId;
                const isDisabled = this.isBotRunning;
                
                const accountTypeLabel = account.account_type === 'demo' ? 'Demo' : 'Real';
                const balance = parseFloat(account.balance || 0).toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });

                html += `
                    <div class="account-dropdown-item ${isSelected ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}" 
                         data-account-id="${account.account_id}"
                         ${!isDisabled ? 'role="button" tabindex="0"' : ''}>
                        <div class="account-item-main">
                            <div class="account-item-id">${account.account_id}</div>
                            <div class="account-item-type">${accountTypeLabel}</div>
                        </div>
                        <div class="account-item-balance">
                            <span class="account-item-amount">${balance}</span>
                            <span class="account-item-currency">${account.currency || 'USD'}</span>
                        </div>
                        ${isSelected ? '<div class="account-item-check">✓</div>' : ''}
                    </div>
                `;
            });
        }

        html += '</div>';
        dropdown.innerHTML = html;

        // Attach click handlers to account items
        dropdown.querySelectorAll('.account-dropdown-item:not(.disabled)').forEach(item => {
            item.addEventListener('click', () => {
                const accountId = item.getAttribute('data-account-id');
                this.selectAccount(accountId);
            });
        });

        return dropdown;
    }

    /**
     * Position dropdown relative to trigger element
     */
    positionDropdown(dropdown) {
        const trigger = document.getElementById('account-selector-trigger') ||
                       document.querySelector('.demo-badge') || 
                       document.getElementById('settings-account-selector');
        
        if (trigger) {
            const rect = trigger.getBoundingClientRect();
            dropdown.style.position = 'fixed';
            dropdown.style.top = `${rect.bottom + 8}px`;
            dropdown.style.left = `${Math.max(8, rect.left)}px`; // Prevent off-screen on mobile
            dropdown.style.minWidth = '280px';
        }
    }

    /**
     * Select a trading account
     */
    async selectAccount(accountId) {
        if (accountId === this.selectedAccountId) {
            this.closeDropdown();
            return;
        }

        // Check bot status before switching
        if (this.isBotRunning) {
            const shouldStop = confirm(
                'Bot is currently running!\n\n' +
                'You must stop the bot before switching accounts.\n\n' +
                'Click OK to stop bot and switch, or Cancel to keep current account.'
            );
            
            if (!shouldStop) {
                this.closeDropdown();
                return;
            }

            // Stop the bot first
            try {
                const stopResponse = await fetch('/api/bot/stop', {
                    method: 'POST',
                    credentials: 'same-origin'
                });

                if (!stopResponse.ok) {
                    throw new Error('Failed to stop bot');
                }

                console.log('Bot stopped successfully');
            } catch (error) {
                console.error('Error stopping bot:', error);
                alert('Failed to stop bot. Please try stopping it manually first.');
                this.closeDropdown();
                return;
            }
        }

        try {
            // Find account object
            const account = this.accounts.find(acc => acc.account_id === accountId);
            if (!account) {
                console.error('Account not found:', accountId);
                return;
            }

            // Show loading state
            this.showLoadingState();

            // Call backend to select account
            const response = await fetch('/accounts/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ account_id: accountId })
            });

            if (!response.ok) {
                throw new Error('Failed to select account');
            }

            const result = await response.json();
            console.log('Account selection response:', result);

            // Update local state
            this.selectedAccountId = accountId;

            // Close dropdown
            this.closeDropdown();

            // Update UI immediately
            this.updateUIWithAccount(account);

            // Trigger callback if provided
            if (this.onAccountSwitch) {
                const callbackResult = await this.onAccountSwitch(account);
                // If callback returns false, don't reload
                if (callbackResult === false) {
                    return;
                }
            }

            // Reload page to refresh all data with new account
            console.log('Reloading page to apply account switch...');
            window.location.reload();

        } catch (error) {
            console.error('Error selecting account:', error);
            alert('Failed to switch account. Please try again.');
            // Reset loading state
            this.loadSelectedAccount().then(() => {
                if (this.selectedAccountId) {
                    const account = this.accounts.find(acc => acc.account_id === this.selectedAccountId);
                    if (account) {
                        this.updateUIWithAccount(account);
                    }
                }
            });
        }
    }

    /**
     * Show loading state during account switch
     */
    showLoadingState() {
        const accountTypeEl = document.getElementById('account-type');
        if (accountTypeEl) {
            accountTypeEl.textContent = 'Switching...';
            accountTypeEl.style.opacity = '0.6';
        }
    }

    /**
     * Update UI with selected account info
     */
    updateUIWithAccount(account) {
        const accountTypeEl = document.getElementById('account-type');
        if (accountTypeEl) {
            const typeLabel = account.account_type === 'demo' ? 'Demo' : 'Real';
            accountTypeEl.textContent = `${typeLabel} · ${account.currency || 'USD'}`;
            accountTypeEl.style.opacity = '1';
        }

        const balanceEl = document.getElementById('total-balance');
        if (balanceEl && account.balance !== undefined) {
            balanceEl.textContent = parseFloat(account.balance).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        const currencyEl = document.getElementById('balance-currency');
        if (currencyEl) {
            currencyEl.textContent = account.currency || 'USD';
        }
    }
}

// Export for use in pages
if (typeof window !== 'undefined') {
    window.AccountSelector = AccountSelector;
}
