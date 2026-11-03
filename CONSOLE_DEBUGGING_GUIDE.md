# Console Debugging Guide - Account Toggle

## 🎯 What to Look For After Fix (Commit: d0ab17c)

After the latest deployment, when you **click to switch accounts**, you should see this **exact sequence** in the console:

### ✅ Expected Console Output (Success)

```javascript
// When you click Demo account:
[AccountSelector] User clicked account: DOT93136231
Account selection response: {status: "success", selected_account: {...}}
Reloading page to apply account switch...

// After page reloads:
Step 1: Fetching accounts...
Accounts data: {accounts: Array(2), count: 2, ...}
Step 2: Checking for existing selection...
[DEBUG] Server returned selected account: {selected_account: {account_id: "DOT93136231", ...}}
Using existing selected account: DOT93136231 demo  ← THIS MUST MATCH WHAT YOU CLICKED!
Step 3-4: Using pre-selected account, skipping API call
Updating account info (live): {account_id: "DOT93136231", account_type: "demo", ...}
```

### ❌ Problem Indicators (Needs Backend Fix)

**If you see this, the BACKEND is not saving your selection:**

```javascript
// You clicked Demo but server returns Real:
[AccountSelector] User clicked account: DOT93136231  ← You clicked Demo
Account selection response: {status: "success", ...}
Reloading page...

// After reload:
[DEBUG] Server returned selected account: {selected_account: {account_id: "ROT91837061", ...}}
Using existing selected account: ROT91837061 real  ← SERVER IGNORED YOUR CHOICE!
```

**This means:** The `/accounts/select` endpoint is accepting your request but NOT actually saving it to the session/database.

---

## 🐛 Console Errors Explained

### ⚠️ Expected/Harmless Errors (Can Ignore)

#### 1. Tailwind CDN Warning
```
cdn.tailwindcss.com should not be used in production
```
**Status:** Informational warning, not an error  
**Impact:** None - Tailwind works fine  
**Action:** Can be ignored

#### 2. Bot Status 500 Errors
```
GET /api/bot/status 500 (Internal Server Error)
GET /api/bot/recent-closures 500 (Internal Server Error)
```
**Status:** Expected when bot is not running  
**Impact:** None - handled gracefully  
**Action:** Normal behavior

#### 3. Admin Health 403
```
GET /api/admin/health 403 (Forbidden)
```
**Status:** Expected for non-admin users  
**Impact:** None - just checking permissions  
**Action:** Normal behavior

#### 4. BotStatusManager Debug Message
```
BotStatusManager not loaded yet - this is expected on first load
```
**Status:** Debug message, not an error  
**Impact:** None - script loads asynchronously  
**Action:** Normal behavior

### ❌ Real Errors (Need Investigation)

**None expected after this fix!**

---

## 🧪 Testing Checklist

After deployment (wait 5 min + hard refresh):

### Test 1: Switch Real → Demo

1. **Before click:** Note current account (e.g., "Real · USD")
2. **Click account badge**
3. **Click "Demo" account**
4. **Watch console** - should see:
   ```
   [AccountSelector] User clicked account: DOT93136231
   ```
5. **Page reloads automatically**
6. **After reload** - check console for:
   ```
   [DEBUG] Server returned selected account: {...account_id: "DOT93136231"...}
   Using existing selected account: DOT93136231 demo
   ```
7. **Check UI:** Badge should show "Demo · USD"
8. **Wait 5 seconds:** Should NOT switch back to Real

**Pass Criteria:**
- ✅ Console shows clicked account ID
- ✅ After reload, server returns same account ID
- ✅ UI shows Demo account
- ✅ Stays on Demo (doesn't flicker back)

### Test 2: Switch Demo → Real

Same steps as above, but switch from Demo to Real.

**Pass Criteria:**
- ✅ Switches to Real
- ✅ Stays on Real
- ✅ No flicker back to Demo

### Test 3: Refresh Page

1. **Current:** On Demo account
2. **Action:** Press F5
3. **Expected:** Console shows:
   ```
   [DEBUG] Server returned selected account: {..."DOT93136231"...}
   Using existing selected account: DOT93136231 demo
   ```
4. **Result:** Still on Demo account

---

## 🔍 Diagnosis Guide

### Scenario A: Flicker Still Happens

**Symptoms:**
- Click Demo
- Shows Demo briefly
- Switches back to Real after 2-4 seconds

**Diagnosis Steps:**

1. **Check console for:**
   ```
   Cache too old, skipping cached data display
   ```
   If you DON'T see this, cache blocking might not be working.

2. **Check if localStorage was cleared:**
   - Open DevTools → Application → Local Storage
   - Should be EMPTY after account switch
   - If you see `deriv_app_data`, cache wasn't cleared

3. **Check server response:**
   ```
   [DEBUG] Server returned selected account: {..."account_id": "ROT91837061"...}
   ```
   If this doesn't match what you clicked, **BACKEND IS THE PROBLEM**.

### Scenario B: Selection Not Persisting

**Symptoms:**
- Click Demo
- Page reloads
- Back to Real immediately

**This is a BACKEND issue!**

**Proof:**
```
[AccountSelector] User clicked account: DOT93136231  ← Frontend working
Account selection response: {status: "success"}     ← Backend says OK
[DEBUG] Server returned selected account: {..."ROT91837061"...}  ← BUT RETURNS WRONG ACCOUNT!
```

**Backend endpoints to check:**

1. **POST /accounts/select** - Is it saving to session/database?
2. **GET /accounts/selected** - Is it reading from correct session?
3. **Session management** - Is session persisting across requests?

### Scenario C: Works But Shows Stale Data

**Symptoms:**
- Click Demo
- Console shows correct account
- UI shows old balance or account info

**Check:**
- Cache age: `Loading cached data (age: X seconds)`
- If X > 10, cache should be skipped
- Look for: `Cache too old, skipping cached data display`

---

## 🛠️ Backend Investigation

If the console shows the frontend is working correctly but the account still doesn't persist, **the issue is in the backend**.

### Check Backend Code

**File:** `app/session_service.py` or similar

**Questions:**
1. Is `POST /accounts/select` actually saving to session/database?
2. Is `GET /accounts/selected` reading from the correct session?
3. Is session ID consistent between requests?
4. Is there a race condition in session storage?

**Test directly:**
```bash
# Select Demo account
curl -X POST https://deriv-oauth-app.onrender.com/accounts/select \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"account_id": "DOT93136231"}'

# Check what was saved
curl https://deriv-oauth-app.onrender.com/accounts/selected \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

If this returns the WRONG account, the backend is not saving properly.

---

## 📝 Summary

**Frontend fixes applied:**
- ✅ Clear cache before reload
- ✅ Skip showing stale cached data
- ✅ Force hard reload to bypass browser cache
- ✅ Added comprehensive debug logging

**What to report:**

If still not working, **copy the ENTIRE console output** when you:
1. Click to switch accounts
2. Page reloads
3. Account switches back

Focus on these lines:
```
[AccountSelector] User clicked account: XXXXX
[DEBUG] Server returned selected account: {...}
Using existing selected account: XXXXX demo/real
```

If clicked account ≠ server returned account → **BACKEND ISSUE**

---

## 🎯 Expected Result

**After this fix:**
- ✅ No visual flicker (cache cleared)
- ✅ Hard reload forces fresh data
- ✅ Debug logs show exactly what's happening
- ✅ If still broken, we know it's the backend

**Clear next steps based on console output!**
