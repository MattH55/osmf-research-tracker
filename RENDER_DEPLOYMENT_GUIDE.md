# Deploying MedFreedom Arbitrage Map to Render

**Free deployment on Render.com** — No credit card required, no charges.

---

## Prerequisites

- ✅ Render.com account (created)
- ✅ GitHub account with repo access
- ✅ Project fully populated (28 AccessRecords ✅)

---

## Architecture

```
GitHub Repository
    ↓
Render (detects push → auto-deploy)
    ├── Backend API (Python/FastAPI) 
    │   └── Port 8000
    └── PostgreSQL Database
        └── Managed by Render
```

---

## Step 1: Push Code to GitHub

```bash
cd /path/to/research-tracker

# Initialize git if needed
git init

# Add remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/research-tracker.git

# Stage all changes
git add .

# Commit
git commit -m "Deploy: Complete MedFreedom Arbitrage Map with schema + data"

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Step 2: Create PostgreSQL Database on Render

1. Log in to [render.com](https://render.com)
2. Click **"New +"** → **"PostgreSQL"**
3. Enter database name: `medfreedom-db`
4. Choose **Free** plan
5. Click **"Create Database"**
6. **Copy the internal connection string** (you'll need it in Step 3)
   - It looks like: `postgresql://user:password@...`

**Wait 2-3 minutes** for database to be ready.

---

## Step 3: Deploy Backend Service

1. Click **"New +"** → **"Web Service"**
2. **Connect your GitHub repo**
   - Select: `research-tracker`
   - Branch: `main`
   - Root directory: `med-freedom-map/backend`
3. **Configure**:
   - Name: `medfreedom-api`
   - Environment: `Python 3.11`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. **Set Environment Variables**:
   - `DATABASE_URL` = (paste PostgreSQL connection string from Step 2)
   - `DEBUG` = `false`
   - `ENVIRONMENT` = `production`
5. Choose **Free** plan
6. Click **"Create Web Service"**

**Wait 3-5 minutes** for build and deployment.

---

## Step 4: Initialize Database

Once the service is deployed:

1. Go to your service page on Render
2. Click **"Shell"** tab (top right)
3. Run these commands:

```bash
python -m app.seed
```

This will:
- Create all tables
- Seed 32 jurisdictions
- Seed 38 procedures  
- Seed 28 AccessRecords with complete schema

**Output should say**: `Seed complete: 32 jurisdictions, 38 procedures, 28 access records.`

---

## Step 5: Test the API

Once seeded successfully:

1. Get your service URL from Render (something like `https://medfreedom-api.onrender.com`)
2. Test the API:

```bash
curl https://medfreedom-api.onrender.com/health
```

You should get: `{"status":"ok"}`

Try a sample query:
```bash
curl https://medfreedom-api.onrender.com/procedures
```

---

## Step 6: Connect Frontend (Optional)

If you're deploying the Next.js frontend:

1. Deploy frontend to Vercel or Render
2. Update backend environment variable:
   - `ALLOWED_ORIGINS` = `["https://your-frontend-url.vercel.app"]`
3. Frontend can now call: `https://medfreedom-api.onrender.com/api/...`

---

## Monitoring

### View Logs
- Render dashboard → Your service → **Logs** tab
- Real-time output of your API

### Database Status
- Render dashboard → Your database → **Connection** tab
- Database stats and usage

### Performance
- Free tier: Goes to sleep after 15 minutes of inactivity
- First request after sleep: ~10 seconds cold start
- But: **Zero cost**

---

## Environment Variables Reference

| Variable | Example | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql://...` | From Render Postgres |
| `DEBUG` | `false` | Set to false in production |
| `ENVIRONMENT` | `production` | Signals prod mode |
| `ALLOWED_ORIGINS` | `["https://example.com"]` | CORS whitelist |

---

## Troubleshooting

### "Module not found" errors
- Check `requirements.txt` is in `med-freedom-map/backend/`
- Check build command uses correct directory

### Database connection fails
- Verify `DATABASE_URL` environment variable is set
- Check Postgres database is "Available" (green status)
- Wait 2-3 minutes for database to fully initialize

### API returns 503
- Service may be starting (cold boot)
- Check logs for errors
- Free tier goes to sleep — wait 30 seconds and retry

### Seeding fails
- Check logs for specific error
- Verify database is writable
- Try again (sometimes transient)

---

## Updating the API

After initial deployment, any push to `main` branch will:
1. Automatically trigger a rebuild
2. Restart the service
3. New version live in ~2 minutes

No manual steps needed — Render watches your repo.

---

## Cost

**Total cost: $0/month**

- Backend: Free tier
- Database: Free tier (250MB storage, plenty for your data)
- No hidden charges, no credit card needed

---

## Support

If something goes wrong:
1. Check Render logs (Dashboard → Service → Logs)
2. Common issues are usually build/env-variable related
3. Push a fix to main branch → automatic redeploy

---

## Next Steps

1. ✅ Push code to GitHub
2. ✅ Create PostgreSQL on Render
3. ✅ Deploy backend service
4. ✅ Run database seed
5. ✅ Test API endpoint
6. ✅ (Optional) Deploy frontend

You'll have a live, zero-cost API for the MedFreedom Arbitrage Map!

---

**Your API URL**: `https://medfreedom-api.onrender.com`  
**Database**: Managed PostgreSQL on Render  
**Cost**: **$0/month** (free tier)

Questions? Check your service logs on Render dashboard.
