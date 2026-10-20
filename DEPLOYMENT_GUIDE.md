# Complete Supabase Integration - Ready to Deploy

## ✅ What's Connected

### Backend (Flask)
- ✅ `session_service.py` - Uses Supabase for session persistence
- ✅ `supabase_service.py` - Complete database operations
- ✅ `routes.py` - Two new endpoints:
  - `POST /api/save-balance` - Saves balance from WebSocket
  - `POST /api/save-trade` - Saves trades to database

### Frontend (JavaScript)
- ✅ `deriv-websocket.js` - Calls backend to save balance updates
- ✅ Automatic persistence - Every balance update → Supabase

### Database (Supabase)
- ✅ Uses your existing `sessions` table
- ✅ Uses your existing `users` table
- ✅ Uses your existing `trades` table
- ✅ No schema changes needed!

## 🔄 Complete Data Flow

```
User Action: Login
  ↓
Flask OAuth callback
  ↓
session_service.store_tokens()
  ↓
Saves to: Flask session + Supabase sessions table
```

```
User Action: Select Account
  ↓
POST /accounts/select
  ↓
session_service.set_selected_account()
  ↓
Saves to: Flask session + Supabase sessions.account_data
```

```
WebSocket: Balance Update Received
  ↓
deriv-websocket.js.updateBalance()
  ↓
POST /api/save-balance
  ↓
session_service.set_selected_account() [with new balance]
  ↓
Saves to: Supabase sessions.account_data.balance
```

```
User Action: Navigate to History Page
  ↓
session_service.get_selected_account()
  ↓
Checks Flask session (empty after navigation)
  ↓
Falls back to Supabase
  ↓
Restores account + balance to Flask session
  ↓
UI displays: Balance, Currency, Account Type ✓
```

## 📋 Deployment Checklist

### Step 1: Get Supabase Credentials
1. Go to https://app.supabase.com
2. Select your project
3. Settings → API
4. Copy:
   - Project URL (e.g., `https://abc123.supabase.co`)
   - `anon` public key

### Step 2: Local Testing
```bash
# Update .env
echo "SUPABASE_URL=https://your-project.supabase.co" >> .env
echo "SUPABASE_ANON_KEY=your-anon-key-here" >> .env

# Install dependencies
pip install -r requirements.txt

# Run locally
python run.py
```

### Step 3: Test the Flow
1. Login via Deriv OAuth → ✅ Check Supabase `sessions` table
2. Dashboard loads balance → ✅ See balance in UI
3. Click History → ✅ Balance still shows (not N/A)
4. Refresh page → ✅ Balance restored from Supabase

### Step 4: Deploy to Railway/Render

**Railway:**
1. Go to your Railway project
2. Variables tab
3. Add:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key-here
   ```
4. Redeploy

**Render:**
1. Go to your Render dashboard
2. Environment → Environment Variables
3. Add the same variables
4. Redeploy

## 🔍 Verify It Works

### Check Sessions Table
```sql
-- Run in Supabase SQL Editor
SELECT session_id, user_id, selected_account_id, 
       account_data->>'balance' as balance,
       account_data->>'currency' as currency,
       updated_at
FROM sessions
ORDER BY updated_at DESC
LIMIT 10;
```

You should see:
- New rows on every login
- `account_data` with balance/currency
- `selected_account_id` set
- `updated_at` changes on balance updates

### Check Browser Console
Open DevTools → Console, you'll see:
```
=== HTS Trade WebSocket Client Starting ===
Starting WebSocket connection flow...
Step 1: Fetching accounts...
Accounts data: {...}
Step 2: Selecting account...
...
✓ WebSocket connected successfully
Balance update received: {balance: 10500, currency: "USD"}
✓ Balance saved to database
```

## 🚨 Troubleshooting

**Issue: "ModuleNotFoundError: No module named 'supabase'"**
- **Fix:** Run `pip install -r requirements.txt`

**Issue: "MISSING_CREDENTIALS" error**
- **Fix:** Add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to `.env`

**Issue: Balance still shows N/A after refresh**
- **Check:** Are credentials correct in `.env`?
- **Check:** Is `sessions` table accessible? (RLS policies)
- **Check:** Browser console for errors

**Issue: "Failed to save balance to database"**
- **Check:** Is user authenticated? (needs valid session)
- **Check:** Supabase URL is reachable from server
- **Check:** No RLS policies blocking INSERT on sessions table

## 📊 What Gets Saved

| Event | Saved To | Data |
|-------|----------|------|
| User logs in | `sessions` | access_token, expires_at |
| Account selected | `sessions.account_data` | account_id, type, currency |
| Balance update | `sessions.account_data` | balance (real-time) |
| Trade executed | `trades` | All trade details |
| Page navigation | Nothing (reads from DB) | - |

## 🎯 Next Steps

1. ✅ Add Supabase credentials
2. ✅ Deploy to Railway/Render
3. ✅ Test complete flow
4. 🔜 Add trade history page (reads from `trades` table)
5. 🔜 Add bot status persistence
6. 🔜 Add analytics tracking

All endpoints are connected and ready to go!
