# Supabase Integration Guide

## Your Existing Schema

Your Supabase database has these tables:
- **users**: User accounts with Deriv OAuth data
- **sessions**: Session management with tokens and account data
- **bots**: Trading bot configurations
- **trades**: Trade history and open positions
- **signals**: Trading signals
- **notifications**: User notifications
- **user_preferences**: User settings (stake, duration, theme, etc.)
- **analytics_events**: Event tracking
- **api_connections**: External API connection status
- **And more...**

## Setup Steps

### 1. Get Supabase Credentials

1. Go to https://app.supabase.com
2. Select your project
3. Go to **Settings → API**
4. Copy these values:
   - **Project URL** (e.g., https://xyz.supabase.co)
   - **anon/public key** (safe to use in frontend)

### 2. Update .env File

Add to your `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key-here
```

### 3. Install Dependencies

```bash
pip install supabase==2.3.0 postgrest==0.13.0
```

### 4. Test Connection

```python
from app.supabase_service import SupabaseService

# Test the connection
client = SupabaseService.get_client()
print("✓ Supabase connected!")
```

## Usage Examples

### Save Session After OAuth

```python
from app.supabase_service import SupabaseService

# After successful OAuth callback
SupabaseService.save_session(
    session_id=session['session_id'],
    user_id=user_email,  # or Deriv loginid
    access_token=access_token,
    account_data={'account_id': 'DOT123', 'currency': 'USD'},
    expires_at=datetime.now() + timedelta(hours=1)
)
```

### Get Session on Page Load

```python
# Load session from database
session_data = SupabaseService.get_session(session['session_id'])

if session_data and session_data['expires_at'] > datetime.now():
    # Session valid - restore tokens
    access_token = session_data['access_token']
    account = session_data['account_data']
```

### Save Balance Updates

```python
# When WebSocket receives balance update
SupabaseService.save_session(
    session_id=session['session_id'],
    user_id=user_id,
    access_token=access_token,
    account_data={'balance': 10500.50, 'currency': 'USD'},
    expires_at=expires_at
)
```

### Save Trades

```python
# When trade is executed
SupabaseService.save_trade(
    user_id=user_id,
    trade_data={
        'direction': 'CALL',
        'symbol': 'R_100',
        'contract_type': 'MULTUP',
        'stake': 10.00,
        'entry_price': 1234.56,
        'contract_id': 'abc123',
        'is_manual': True
    }
)
```

### Get User Trades

```python
# Get last 50 trades
trades = SupabaseService.get_user_trades(user_id, limit=50)

# Get only open trades
open_trades = SupabaseService.get_open_trades(user_id)
```

## Benefits Over localStorage

✅ **Persistent**: Data survives browser clearing, works across devices
✅ **Server-side**: Secure token storage, not exposed in browser
✅ **Real-time**: Supabase Realtime for live updates (optional)
✅ **Scalable**: PostgreSQL database, handles millions of records
✅ **Queryable**: SQL queries, filtering, aggregation
✅ **Secure**: Row Level Security (RLS) policies

## Next Steps

1. Add Supabase credentials to `.env`
2. Test connection locally
3. Update session management to use Supabase
4. Add WebSocket → Supabase sync for balance updates
5. Deploy to Railway/Render with environment variables

## RLS (Row Level Security)

Your Supabase tables should have RLS policies. Example:

```sql
-- Users can only read their own sessions
CREATE POLICY "Users can view own sessions"
ON sessions FOR SELECT
USING (user_id = auth.uid());

-- Users can only insert their own trades
CREATE POLICY "Users can insert own trades"
ON trades FOR INSERT
WITH CHECK (user_id = auth.uid());
```

Check your existing RLS policies in Supabase → Authentication → Policies
