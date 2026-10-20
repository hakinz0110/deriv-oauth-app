// Check if user is authenticated, if not redirect to login
async function checkAuthentication() {
    try {
        const response = await fetch('/accounts/selected', {
            credentials: 'same-origin'
        });
        
        if (response.status === 401 || response.status === 403) {
            // Not authenticated - redirect to login
            console.log('Not authenticated, redirecting to login...');
            window.location.href = '/login';
            return false;
        }
        
        if (response.ok) {
            const data = await response.json();
            if (data.selected_account) {
                // Show cached account data immediately
                updateUIWithAccount(data.selected_account);
                return true;
            }
        }
        
        return false;
    } catch (error) {
        console.error('Auth check failed:', error);
        return false;
    }
}

function updateUIWithAccount(account) {
    // Update account type
    const accountTypeEl = document.getElementById('account-type');
    if (accountTypeEl) {
        accountTypeEl.textContent = `${account.account_type || 'Demo'} · ${account.currency || 'USD'}`;
    }
    
    // Update balance if available
    if (account.balance !== undefined) {
        const balanceEl = document.getElementById('total-balance');
        if (balanceEl) {
            balanceEl.textContent = parseFloat(account.balance).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }
        
        const currencyEl = document.getElementById('balance-currency');
        if (currencyEl && account.currency) {
            currencyEl.textContent = account.currency;
        }
    }
}

// Run on page load
document.addEventListener('DOMContentLoaded', async () => {
    const isAuth = await checkAuthentication();
    
    if (!isAuth) {
        // Show loading or redirect
        console.log('Waiting for authentication...');
    }
});
