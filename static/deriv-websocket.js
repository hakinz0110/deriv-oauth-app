// Deriv WebSocket connection manager for real-time balance streaming
class DerivWebSocketClient {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.subscriptions = new Map();
    }

    async connect() {
        try {
            console.log('Starting WebSocket connection flow...');
            
            // 1. Get list of accounts
            console.log('Step 1: Fetching accounts...');
            const accountsRes = await fetch('/accounts', {
                credentials: 'same-origin'  // Include session cookies
            });
            
            if (!accountsRes.ok) {
                console.error('Failed to fetch accounts:', accountsRes.status, accountsRes.statusText);
                const error = await accountsRes.json().catch(() => ({}));
                console.error('Error details:', error);
                return;
            }
            
            const accountsData = await accountsRes.json();
            console.log('Accounts data:', accountsData);
            
            if (!accountsData.accounts || accountsData.accounts.length === 0) {
                console.error('No accounts found for user');
                this.showError('No trading accounts found. Please create an account first.');
                return;
            }

            // 2. Select first active account
            console.log('Step 2: Selecting account...');
            const account = accountsData.accounts.find(acc => acc.status === 'active');
            if (!account) {
                console.error('No active account found');
                this.showError('No active accounts available');
                return;
            }
            
            console.log('Selected account:', account.account_id, account.account_type);

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
            };

        } catch (error) {
            console.error('Connection error:', error);
            this.showError('Failed to establish connection: ' + error.message);
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
            this.updateBalance(message.balance);
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

    updateBalance(balanceData) {
        console.log('Updating UI with balance:', balanceData);
        
        // Update balance amount
        const balanceElement = document.getElementById('total-balance');
        if (balanceElement && typeof balanceData.balance === 'number') {
            balanceElement.textContent = balanceData.balance.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        // Update currency
        const currencyElement = document.getElementById('balance-currency');
        if (currencyElement && balanceData.currency) {
            currencyElement.textContent = balanceData.currency;
        }

        // Update account type badge if present
        const accountTypeElement = document.getElementById('account-type');
        if (accountTypeElement && balanceData.loginid) {
            // Extract account type from loginid (e.g., "VRTC" = demo, "CR" = real)
            const isDemoAccount = balanceData.loginid && balanceData.loginid.startsWith('VRT');
            accountTypeElement.textContent = `${isDemoAccount ? 'Demo' : 'Real'} · ${balanceData.currency || 'USD'}`;
        }
    }

    showError(message) {
        console.error('Showing error to user:', message);
        // Could display this in the UI instead of just console
        const balanceElement = document.getElementById('total-balance');
        if (balanceElement) {
            balanceElement.textContent = 'Error';
        }
    }

    disconnect() {
        if (this.ws) {
            console.log('Disconnecting WebSocket...');
            this.ws.close();
            this.ws = null;
            this.connected = false;
        }
    }
}

// Initialize on page load
let derivClient;

document.addEventListener('DOMContentLoaded', () => {
    console.log('=== HTS Trade WebSocket Client Starting ===');
    derivClient = new DerivWebSocketClient();
    derivClient.connect();
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (derivClient) {
        derivClient.disconnect();
    }
});
