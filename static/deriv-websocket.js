// Deriv Data Cache Manager - Persists data across page navigation
class DerivDataCache {
    constructor() {
        this.CACHE_KEY = 'deriv_app_data';
        this.CACHE_EXPIRY = 5 * 60 * 1000; // 5 minutes
    }

    save(data) {
        const cacheData = {
            timestamp: Date.now(),
            data: data
        };
        localStorage.setItem(this.CACHE_KEY, JSON.stringify(cacheData));
    }

    load() {
        try {
            const cached = localStorage.getItem(this.CACHE_KEY);
            if (!cached) return null;

            const cacheData = JSON.parse(cached);
            const age = Date.now() - cacheData.timestamp;

            // Return cached data even if expired (it's better than N/A)
            // But mark it as stale
            return {
                ...cacheData.data,
                _isStale: age > this.CACHE_EXPIRY,
                _age: age
            };
        } catch (error) {
            console.error('Failed to load cache:', error);
            return null;
        }
    }

    clear() {
        localStorage.removeItem(this.CACHE_KEY);
    }

    update(field, value) {
        const cached = this.load();
        const data = cached || {};
        delete data._isStale;
        delete data._age;
        
        data[field] = value;
        this.save(data);
    }
}

// Deriv WebSocket connection manager for real-time balance streaming
class DerivWebSocketClient {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.subscriptions = new Map();
        this.cache = new DerivDataCache();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
    }

    async initialize() {
        // First, load and display cached data immediately
        this.loadCachedData();
        
        // Then connect to get fresh data
        await this.connect();
    }

    loadCachedData() {
        const cached = this.cache.load();
        
        if (!cached) {
            console.log('No cached data available');
            return;
        }

        console.log('Loading cached data (age:', Math.round(cached._age / 1000), 'seconds)');
        
        // Display cached balance
        if (cached.balance !== undefined) {
            this.updateBalance(cached.balance, true); // true = from cache
        }

        // Display cached account info
        if (cached.account) {
            this.updateAccountInfo(cached.account, true);
        }

        // Show stale indicator if data is old
        if (cached._isStale) {
            console.warn('Cached data is stale, fetching fresh data...');
        }
    }

    async connect() {
        try {
            console.log('Starting WebSocket connection flow...');
            
            // 1. Get list of accounts
            console.log('Step 1: Fetching accounts...');
            const accountsRes = await fetch('/accounts', {
                credentials: 'same-origin'
            });
            
            if (!accountsRes.ok) {
                console.error('Failed to fetch accounts:', accountsRes.status, accountsRes.statusText);
                const error = await accountsRes.json().catch(() => ({}));
                console.error('Error details:', error);
                this.handleConnectionError('Failed to fetch accounts');
                return;
            }
            
            const accountsData = await accountsRes.json();
            console.log('Accounts data:', accountsData);
            
            if (!accountsData.accounts || accountsData.accounts.length === 0) {
                console.error('No accounts found for user');
                this.showError('No trading accounts found. Please create an account first.');
                return;
            }

            // Cache accounts list
            this.cache.update('accounts', accountsData.accounts);

            // 2. Select first active account
            console.log('Step 2: Selecting account...');
            const account = accountsData.accounts.find(acc => acc.status === 'active');
            if (!account) {
                console.error('No active account found');
                this.showError('No active accounts available');
                return;
            }
            
            console.log('Selected account:', account.account_id, account.account_type);
            
            // Cache selected account
            this.cache.update('account', account);
            this.updateAccountInfo(account, false);

            // 3. Select the account via API
            console.log('Step 3: Setting selected account...');
            const selectRes = await fetch('/accounts/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ account_id: account.account_id })
            });
            
            if (!selectRes.ok) {
                console.error('Failed to select account:', selectRes.status);
                const error = await selectRes.json().catch(() => ({}));
                console.error('Error details:', error);
                this.handleConnectionError('Failed to select account');
                return;
            }
            
            console.log('Account selected successfully');

            // 4. Get WebSocket URL with OTP
            console.log('Step 4: Getting WebSocket URL...');
            const wsRes = await fetch('/websocket/url', {
                credentials: 'same-origin'
            });
            
            if (!wsRes.ok) {
                console.error('Failed to get WebSocket URL:', wsRes.status);
                const error = await wsRes.json().catch(() => ({}));
                console.error('Error details:', error);
                this.handleConnectionError('Failed to get WebSocket URL');
                return;
            }
            
            const wsData = await wsRes.json();
            console.log('WebSocket URL received');

            if (!wsData.websocket_url) {
                console.error('No WebSocket URL in response:', wsData);
                return;
            }

            // 5. Connect to WebSocket
            console.log('Step 5: Connecting to WebSocket...');
            this.ws = new WebSocket(wsData.websocket_url);

            this.ws.onopen = () => {
                console.log('✓ WebSocket connected successfully');
                this.connected = true;
                this.reconnectAttempts = 0;
                
                // Subscribe to balance updates
                this.subscribeToBalance();
            };

            this.ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                console.log('WebSocket message received:', message);
                
                this.handleMessage(message);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showError('WebSocket connection error');
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                this.connected = false;
                
                // Auto-reconnect if not intentional disconnect
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    console.log(`Reconnecting... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                    setTimeout(() => this.connect(), 2000);
                }
            };

        } catch (error) {
            console.error('Connection error:', error);
            this.handleConnectionError('Connection failed: ' + error.message);
        }
    }

    subscribeToBalance() {
        if (!this.connected) {
            console.error('Cannot subscribe: WebSocket not connected');
            return;
        }

        const request = {
            balance: 1,
            subscribe: 1
        };

        console.log('Sending balance subscription request:', request);
        this.ws.send(JSON.stringify(request));
    }

    handleMessage(message) {
        // Handle balance updates
        if (message.balance !== undefined) {
            console.log('Balance update received:', message.balance);
            
            // Cache the balance data
            this.cache.update('balance', message.balance);
            
            // Update UI
            this.updateBalance(message.balance, false);
        }

        // Handle subscription confirmation
        if (message.subscription) {
            console.log('✓ Subscription confirmed:', message.subscription.id);
        }

        // Handle errors
        if (message.error) {
            console.error('API error:', message.error);
            this.showError(message.error.message);
        }
    }

        updateBalance(balanceData, isFromCache = false) {
        console.log(`Updating UI with balance (${isFromCache ? 'cached' : 'live'}):`, balanceData);
        
        // Update balance amount
        const balanceElement = document.getElementById('total-balance');
        if (balanceElement && typeof balanceData.balance === 'number') {
            balanceElement.textContent = balanceData.balance.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            
            // Add visual indicator for cached data
            if (isFromCache) {
                balanceElement.style.opacity = '0.7';
            } else {
                balanceElement.style.opacity = '1';
            }
        }

        // Update currency
        const currencyElement = document.getElementById('balance-currency');
        if (currencyElement && balanceData.currency) {
            currencyElement.textContent = balanceData.currency;
        }
        
        // Save to backend (Supabase) if this is live data
        if (!isFromCache && typeof balanceData.balance === 'number') {
            this.saveBalanceToBackend(balanceData);
        }
    }
    
    async saveBalanceToBackend(balanceData) {
        try {
            const response = await fetch('/api/save-balance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    balance: balanceData.balance,
                    currency: balanceData.currency,
                    loginid: balanceData.loginid
                })
            });
            
            if (response.ok) {
                console.log('✓ Balance saved to database');
            } else {
                console.warn('Failed to save balance to database:', response.status);
            }
        } catch (error) {
            console.warn('Could not save balance to backend:', error);
            // Don't show error to user - this is a background save
        }
    }

    updateAccountInfo(account, isFromCache = false) {
        console.log(`Updating account info (${isFromCache ? 'cached' : 'live'}):`, account);
        
        const accountTypeElement = document.getElementById('account-type');
        if (accountTypeElement) {
            const accountType = account.account_type || 'Demo';
            const currency = account.currency || 'USD';
            accountTypeElement.textContent = `${accountType} · ${currency}`;
            
            // Add visual indicator for cached data
            if (isFromCache) {
                accountTypeElement.style.opacity = '0.7';
            } else {
                accountTypeElement.style.opacity = '1';
            }
        }

        // Update balance if available in account object
        if (account.balance !== undefined) {
            this.updateBalance({
                balance: account.balance,
                currency: account.currency
            }, isFromCache);
        }
    }

    handleConnectionError(message) {
        console.error('Connection error:', message);
        
        // Still show cached data even if connection fails
        const cached = this.cache.load();
        if (cached) {
            console.log('Showing cached data despite connection error');
        } else {
            this.showError(message);
        }
    }

    showError(message) {
        console.error('Showing error to user:', message);
        
        // Don't overwrite cached data with error message
        const cached = this.cache.load();
        if (cached && cached.balance) {
            console.log('Keeping cached balance visible despite error');
            return;
        }
        
        // Only show error if no cached data
        const balanceElement = document.getElementById('total-balance');
        if (balanceElement) {
            balanceElement.textContent = 'N/A';
        }
    }

    disconnect() {
        if (this.ws) {
            console.log('Disconnecting WebSocket...');
            this.ws.close(1000, 'User navigated away'); // 1000 = normal closure
            this.ws = null;
            this.connected = false;
        }

    async reconnect() {
        console.log('Reconnecting WebSocket for account switch...');
        
        // Disconnect existing connection
        this.disconnect();
        
        // Clear cache to force fresh data
        this.cache.clear();
        
        // Reset reconnect attempts
        this.reconnectAttempts = 0;
        
        // Reconnect
        await this.connect();
    }
    }
}

// Global instance
let derivClient;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('=== HTS Trade WebSocket Client Starting ===');
    derivClient = new DerivWebSocketClient();
    derivClient.initialize(); // Load cache first, then connect
});

// Clean up on page unload (but keep cache)
window.addEventListener('beforeunload', () => {
    if (derivClient) {
        derivClient.disconnect();
    }
});


