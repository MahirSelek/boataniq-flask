# 🚀 Flask App Deployment Guide

This guide will help you deploy your Flask app to a cloud platform with secure credential handling.

## 🔒 Security First

**NEVER commit your credentials file to GitHub!** The `.gitignore` file is configured to exclude all `.json` files.

---

## Option 1: Render (Recommended - Easiest)

### Step 1: Prepare Your Repository

1. **Initialize Git (if not already done):**
   ```bash
   cd /Users/mahirselek/Desktop/DSPhD/MS/denizmen-scraping
   git init
   git add .
   git commit -m "Initial commit: Flask app ready for deployment"
   ```

2. **Create GitHub Repository:**
   - Go to https://github.com/new
   - Create a **public** repository
   - Push your code:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/boataniq-flask.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Render

1. **Sign up/Login:**
   - Go to https://render.com
   - Sign up with GitHub

2. **Create New Web Service:**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select your repository: `YOUR_USERNAME/boataniq-flask`

3. **Configure Settings:**
   - **Name:** `boataniq-app` (or any name)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Plan:** Free (or paid if you need more resources)

4. **Add Environment Variables:**
   - Go to "Environment" tab
   - Add these variables:
   
   **GCP_CREDENTIALS_JSON** (IMPORTANT):
   - Open your JSON file: `static-chiller-472906-f3-4ee4a099f2f1.json`
   - Copy the ENTIRE JSON content
   - Paste it as a single-line string in the environment variable
   - Make sure to escape quotes properly or use the JSON as-is
   
   **Optional:**
   - `SECRET_KEY`: Generate a random secret key for Flask sessions
   - `GEMINI_API_KEY`: (if you want fallback)

5. **Deploy:**
   - Click "Create Web Service"
   - Wait 5-10 minutes for deployment
   - Your app will be live at: `https://boataniq-app.onrender.com` (or your custom domain)

---

## Option 2: Railway

### Step 1: Prepare Repository (same as Render)

### Step 2: Deploy on Railway

1. **Sign up:** https://railway.app (use GitHub login)

2. **Create New Project:**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Configure:**
   - Railway auto-detects Python
   - Add `gunicorn` to requirements.txt if not present:
   ```bash
   echo "gunicorn>=21.2.0" >> requirements.txt
   ```

4. **Add Environment Variables:**
   - Go to "Variables" tab
   - Add `GCP_CREDENTIALS_JSON` with your full JSON credentials (as single-line string)
   - Add `PORT` (Railway sets this automatically, but you can add it)

5. **Deploy:**
   - Railway auto-deploys on push
   - Get your URL from the dashboard

---

## Option 3: Google Cloud Run (Since you have GCP)

### Step 1: Install Google Cloud SDK

```bash
# macOS
brew install google-cloud-sdk

# Or download from: https://cloud.google.com/sdk/docs/install
```

### Step 2: Authenticate

```bash
gcloud auth login
gcloud config set project static-chiller-472906-f3
```

### Step 3: Create Dockerfile

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

COPY . .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
```

### Step 4: Deploy

```bash
# Build and deploy
gcloud run deploy boataniq-app \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_CREDENTIALS_JSON="$(cat static-chiller-472906-f3-4ee4a099f2f1.json | jq -c .)"
```

---

## Option 4: Fly.io

### Step 1: Install Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
```

### Step 2: Login

```bash
fly auth login
```

### Step 3: Create fly.toml

```bash
fly launch
```

### Step 4: Set Secrets

```bash
fly secrets set GCP_CREDENTIALS_JSON="$(cat static-chiller-472906-f3-4ee4a099f2f1.json)"
```

### Step 5: Deploy

```bash
fly deploy
```

---

## 📝 Converting JSON to Environment Variable

Your JSON file needs to be converted to a single-line string for environment variables:

### Method 1: Using Python

```python
import json

with open('static-chiller-472906-f3-4ee4a099f2f1.json', 'r') as f:
    data = json.load(f)
    json_string = json.dumps(data)
    print(json_string)  # Copy this entire output
```

### Method 2: Using jq (if installed)

```bash
cat static-chiller-472906-f3-4ee4a099f2f1.json | jq -c .
```

### Method 3: Manual

1. Open your JSON file
2. Copy all content
3. Remove all newlines (make it one line)
4. Paste in environment variable

**Important:** Make sure all quotes are properly escaped or the platform handles JSON strings correctly.

---

## ✅ Verification Checklist

Before deploying:

- [ ] `.gitignore` includes `*.json`
- [ ] No credentials file is in Git
- [ ] `app.py` uses environment variables
- [ ] `requirements.txt` includes `gunicorn`
- [ ] `Procfile` exists (for Heroku/Render)
- [ ] Environment variables are set in deployment platform
- [ ] Test locally with environment variables

---

## 🧪 Test Locally with Environment Variables

Before deploying, test locally:

```bash
# Set environment variable
export GCP_CREDENTIALS_JSON='{"type":"service_account",...}'  # Your full JSON as one line

# Run app
python app.py
```

---

## 🔗 After Deployment

Once deployed, you'll get a public URL like:
- Render: `https://your-app.onrender.com`
- Railway: `https://your-app.up.railway.app`
- Cloud Run: `https://your-app-xxxxx.run.app`
- Fly.io: `https://your-app.fly.dev`

**Share this URL with anyone!** Your credentials are secure in environment variables.

---

## 🆘 Troubleshooting

### "Credentials not found"
- Check environment variable name is exactly `GCP_CREDENTIALS_JSON`
- Verify JSON is valid (use JSON validator)
- Make sure JSON is a single line or properly formatted

### "Module not found"
- Check `requirements.txt` has all dependencies
- Verify build completed successfully
- Check build logs in deployment platform

### "Port binding error"
- Make sure app uses `$PORT` environment variable
- Check `Procfile` or start command uses `$PORT`

---

## 📚 Recommended: Render

**I recommend Render** because:
- ✅ Free tier available
- ✅ Easy setup
- ✅ Automatic deployments from GitHub
- ✅ Good documentation
- ✅ No credit card required for free tier

---

**🎉 Good luck with your deployment!**
