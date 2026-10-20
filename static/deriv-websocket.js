// Deriv WebSocket connection manager for real-time balance streaming
class DerivWebSocketClient {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.subscriptions = new Map();
    }

    async connect() {
        try {
            // 1. Get list of accounts
            const accountsRes = await fetch('/accounts');
            const accountsData = await accountsRes.json();
            
            if (!accountsData.accounts || accountsData.accounts.length === 0) {
                console.error('No accounts found');
                return;
            }

            // 2. Select first active account (or let user choose)
            const account = accountsData.accounts.find(acc => acc.status === 'active');
            if (!account) {
                console.error('No active account found');
                return;
            }

            // 3. Select the account
            await fetch('/accounts/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: account.account_id })
            });

            // 4. Get WebSocket URL with OTP
            const wsRes = await fetch('/websocket/url');
            const wsData = await wsRes.json();

            if (!wsData.websocket_url) {
                console.error('No WebSocket URL received');
                return;
            }

            // 5. Connect to WebSocket
            this.ws = new WebSocket(wsData.websocket_url);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.connected = true;
                
                // Subscribe to balance updates
                this.subscribeToBalance();
            };

            this.ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                console.log('Received:', message);
                
                this.handleMessage(message);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.connected = false;
            };

        } catch (error) {
            console.error('Connection error:', error);
        }
    }

    subscribeToBalance() {
        if (!this.connected) return;

        const request = {
            balance: 1,
            subscribe: 1
        };

        this.ws.send(JSON.stringify(request));
        console.log('Subscribed to balance updates');
    }

    handleMessage(message) {
        // Handle balance updates
        if (message.balance) {
            this.updateBalance(message.balance);
        }

        // Handle subscription confirmation
        if (message.subscription) {
            console.log('Subscription confirmed:', message.subscription);
        }

        // Handle errors
        if (message.error) {
            console.error('API error:', message.error);
        }
    }

    updateBalance(balanceData) {
        // Update UI with balance data
        const balanceElement = document.getElementById('total-balance');
        if (balanceElement) {
            balanceElement.textContent = balanceData.balance || 'N/A';
        }

        const currencyElement = document.getElementById('balance-currency');
        if (currencyElement) {
            currencyElement.textContent = balanceData.currency || '';
        }

        console.log('Balance updated:', balanceData);
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
            this.connected = false;
        }
    }
}

// Initialize on page load
let derivClient;

document.addEventListener('DOMContentLoaded', () => {
    derivClient = new DerivWebSocketClient();
    derivClient.connect();
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (derivClient) {
        derivClient.disconnect();
    }
});
