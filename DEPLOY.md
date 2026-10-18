# Deployment Instructions

## Step 1: Push to GitHub

Replace `YOUR_USERNAME` with your GitHub username:

```bash
cd C:\Users\abere\Desktop\DERIV
git remote add origin https://github.com/YOUR_USERNAME/deriv-oauth-app.git
git branch -M main
git push -u origin main
```

If prompted for credentials, use a Personal Access Token (not password).

## Step 2: Deploy to Render

1. Go to https://render.com and sign up (free tier)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select the `deriv-oauth-app` repository
5. Configure settings:
   - **Name**: `deriv-oauth-app` (or choose your own)
   - **Environment**: Python 3
   - **Branch**: main
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
   - **Instance Type**: Free

## Step 3: Add Environment Variables

In Render dashboard, add these environment variables:

| Key | Value |
|-----|-------|
| `CLIENT_ID` | `33x4yt1oLTBWGsLUTHRWo` |
| `SECRET_KEY` | `3cd8b8e361007ebc7eb0a354c6628d296b32274e6146736abccfd7654a83ddef` |
| `REDIRECT_URI` | `https://YOUR-APP-NAME.onrender.com/callback` |
| `FLASK_ENV` | `production` |
| `FLASK_DEBUG` | `False` |
| `MOCK_OAUTH` | `False` |

**Important**: After deployment, Render will give you a URL like `https://deriv-oauth-app-xxxx.onrender.com`

Update the `REDIRECT_URI` environment variable with your actual Render URL.

## Step 4: Update Deriv Dashboard

1. Go to your Deriv developer dashboard: https://app.deriv.com/account/api-token
2. Find your application (ID: `33x4yt1oLTBWGsLUTHRWo`)
3. Update the **Redirect URI** to: `https://your-actual-render-url.onrender.com/callback`
4. Save changes

## Step 5: Test Your Deployment

Visit: `https://your-actual-render-url.onrender.com/login`

You should now see the Deriv login page without the "Access Denied" error!

## Troubleshooting

- **502 Bad Gateway**: Wait 2-3 minutes for initial deployment
- **Environment variables not loaded**: Check Render dashboard → Environment tab
- **Still getting Access Denied**: Verify redirect URI matches exactly in both Render and Deriv dashboard
