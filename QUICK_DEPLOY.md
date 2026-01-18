# ⚡ Quick Deploy Guide - Flask App

## 🎯 Fastest Way: Render (5 minutes)

### Step 1: Get Your Credentials String

```bash
python convert_credentials_for_deployment.py
```

Copy the output (the long JSON string).

### Step 2: Push to GitHub

```bash
git add .
git commit -m "Ready for deployment"
git push
```

### Step 3: Deploy on Render

1. Go to https://render.com
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your repository
5. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
6. **Environment Variables:**
   - Click "Environment" tab
   - Add: `GCP_CREDENTIALS_JSON` = (paste the JSON string from Step 1)
7. Click "Create Web Service"
8. Wait 5-10 minutes
9. **Done!** Get your URL from the dashboard

---

## 🔒 Security

✅ Your credentials file is protected by `.gitignore`
✅ Credentials are stored as environment variables (secure)
✅ Never committed to Git

---

## 📋 Files Created

- `Procfile` - For deployment platforms
- `runtime.txt` - Python version
- `.gitignore` - Protects credentials
- `FLASK_DEPLOYMENT_GUIDE.md` - Full guide
- `convert_credentials_for_deployment.py` - Helper script

---

## ✅ That's It!

Your app will be live at: `https://your-app.onrender.com`

Share this URL - it's public and secure! 🎉
