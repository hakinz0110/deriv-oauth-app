// Simple cache loader for pages that don't need WebSocket connection
// Just displays cached data from localStorage

class SimpleCacheLoader {
    constructor() {
        this.CACHE_KEY = 'deriv_app_data';
    }

    load() {
        try {
            const cached = localStorage.getItem(this.CACHE_KEY);
            if (!cached) return null;

            const cacheData = JSON.parse(cached);
            return cacheData.data;
        } catch (error) {
            console.error('Failed to load cache:', error);
            return null;
        }
    }

    displayCachedData() {
        const data = this.load();
        
        if (!data) {
            console.log('No cached data available');
            return;
        }

        console.log('Loading cached data');

        // Update balance if element exists
        const balanceElement = document.getElementById('total-balance');
        if (balanceElement && data.balance) {
            balanceElement.textContent = data.balance.balance.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        // Update currency if element exists
        const currencyElement = document.getElementById('balance-currency');
        if (currencyElement && data.balance) {
            currencyElement.textContent = data.balance.currency || '';
        }

        // Update account type if element exists
        const accountTypeElement = document.getElementById('account-type');
        if (accountTypeElement && data.account) {
            const accountType = data.account.account_type || 'Demo';
            const currency = data.account.currency || 'USD';
            accountTypeElement.textContent = `${accountType} · ${currency}`;
        }

        // Update account ID in settings if element exists
        const accountIdElement = document.getElementById('account-id');
        if (accountIdElement && data.account) {
            accountIdElement.textContent = data.account.account_id || 'N/A';
        }

        // Update any balance display elements
        const balanceDisplays = document.querySelectorAll('[data-balance]');
        balanceDisplays.forEach(el => {
            if (data.balance) {
                el.textContent = data.balance.balance.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }
        });
    }
}

// Auto-load on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Loading cached data...');
    const loader = new SimpleCacheLoader();
    loader.displayCachedData();
});
