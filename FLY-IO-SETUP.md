# Fly.io Setup Instructions

## Step 1: Install Fly CLI

### Option A: Direct Download (Recommended for Windows)
1. Go to: https://fly.io/docs/flyctl/install/
2. Download the Windows installer
3. Run the installer
4. Restart your terminal/PowerShell

### Option B: PowerShell Install
```powershell
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

### Verify Installation
```bash
flyctl version
```

## Step 2: Sign Up for Fly.io

```bash
flyctl auth signup
```

Or sign up at: https://fly.io/app/sign-up

**Note:** You'll need to add a credit card for verification, but the free tier ($5/month credit) covers your usage.

## Step 3: Login

```bash
flyctl auth login
```

## Step 4: Launch Your App

```bash
cd C:\Users\abere\Desktop\DERIV
flyctl launch
```

**Answer the prompts:**
- Choose app name: `deriv-oauth-app` (or let it auto-generate)
- Choose region: Select closest to you
- Create PostgreSQL database? **No**
- Create Redis database? **No**
- Deploy now? **No** (we need to set secrets first)

## Step 5: Set Environment Variables (Secrets)

```bash
flyctl secrets set CLIENT_ID=33x4yt1oLTBWGsLUTHRWo
flyctl secrets set SECRET_KEY=3cd8b8e361007ebc7eb0a354c6628d296b32274e6146736abccfd7654a83ddef
flyctl secrets set REDIRECT_URI=https://deriv-oauth-app.fly.dev/callback
flyctl secrets set FLASK_ENV=production
flyctl secrets set FLASK_DEBUG=False
flyctl secrets set MOCK_OAUTH=False
flyctl secrets set OAUTH_SCOPES="trade account_manage"
```

**Note:** Replace `deriv-oauth-app` with your actual app name if different.

## Step 6: Deploy

```bash
flyctl deploy
```

Wait 2-3 minutes for deployment to complete.

## Step 7: Get Your URL

```bash
flyctl info
```

Your URL will be: `https://your-app-name.fly.dev`

Or visit: `https://fly.io/dashboard` to see your apps.

## Step 8: Update Deriv Dashboard

1. Go to: https://app.deriv.com/account/api-token
2. Find your app (ID: 33x4yt1oLTBWGsLUTHRWo)
3. Add new redirect URI: `https://your-app-name.fly.dev/callback`
4. Save changes

## Step 9: Test

Visit: `https://your-app-name.fly.dev/login`

You should see the Deriv login page!

## Useful Commands

```bash
# View logs
flyctl logs

# View app status
flyctl status

# Open app in browser
flyctl open

# SSH into your app
flyctl ssh console

# Scale to 0 machines (stop app, save resources)
flyctl scale count 0

# Scale to 1 machine (restart app)
flyctl scale count 1

# Deploy new version
flyctl deploy

# View secrets
flyctl secrets list
```

## Free Tier Details

Fly.io Free Tier includes:
- Up to 3 shared-cpu-1x 256MB VMs
- 160GB outbound data transfer
- Effectively free for development/staging

Your app will be more responsive than Render (no spin-down delay).

## Troubleshooting

### Error: "could not find App"
Make sure you're in the correct directory:
```bash
cd C:\Users\abere\Desktop\DERIV
```

### Error: "region not specified"
Add to fly.toml:
```toml
primary_region = "iad"  # or your preferred region
```

### Check deployment status
```bash
flyctl status
flyctl logs
```

## Git Workflow

After setup, deploy new changes:

```bash
# Make changes to your code
git add .
git commit -m "Your changes"

# Deploy to Fly.io
flyctl deploy

# Or push to GitHub and deploy
git push origin main
flyctl deploy
```

## Cost

With free tier:
- **First 3 VMs**: Free (up to 256MB each)
- **Your usage**: 1 VM = FREE ✅
- **No credit card charges** unless you exceed free tier
