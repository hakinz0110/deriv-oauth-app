# Railway.app Setup (No Credit Card Required)

## Why Railway?
- ✅ No credit card needed
- ✅ $5 free credit/month
- ✅ No spin-down (always fast)
- ✅ Fixed permanent URL
- ✅ Deploy from GitHub

## Setup Steps

### Step 1: Sign Up
1. Go to: https://railway.app
2. Click **"Login"** or **"Start a New Project"**
3. Sign in with **GitHub** (no credit card required)

### Step 2: Create New Project
1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose **"hakinz0110/deriv-oauth-app"**
4. Click **"Deploy Now"**

### Step 3: Add Environment Variables
In the Railway dashboard:
1. Click on your deployed service
2. Go to **"Variables"** tab
3. Click **"New Variable"** and add these:

```
CLIENT_ID = 33x4yt1oLTBWGsLUTHRWo
SECRET_KEY = 3cd8b8e361007ebc7eb0a354c6628d296b32274e6146736abccfd7654a83ddef
FLASK_ENV = production
FLASK_DEBUG = False
MOCK_OAUTH = False
OAUTH_SCOPES = trade account_manage
PORT = 8080
```

**REDIRECT_URI** - We'll set this after getting the URL

### Step 4: Generate Domain
1. Go to **"Settings"** tab
2. Scroll to **"Domains"** section
3. Click **"Generate Domain"**
4. You'll get a URL like: `https://deriv-oauth-app-production.up.railway.app`

### Step 5: Update REDIRECT_URI
1. Go back to **"Variables"** tab
2. Add:
```
REDIRECT_URI = https://your-railway-url.up.railway.app/callback
```
3. Railway will auto-redeploy

### Step 6: Update Deriv Dashboard
1. Go to: https://app.deriv.com/account/api-token
2. Add redirect URI: `https://your-railway-url.up.railway.app/callback`
3. Save

### Step 7: Test
Visit: `https://your-railway-url.up.railway.app/login`

## Monitoring
- View logs in Railway dashboard
- Check usage (should be well under $5/month)
- No automatic shutdowns!

## Cost
- **Free tier**: $5 credit/month
- **Your app**: ~$2-3/month usage
- **Result**: FREE ✅

## Advantages Over Render
- ✅ No spin-down delays
- ✅ Faster response times
- ✅ Same permanent URL
- ✅ Better free tier
