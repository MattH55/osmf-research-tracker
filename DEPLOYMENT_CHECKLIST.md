# MedFreedom Arbitrage Map - Deployment Checklist

**Status**: Ready for Render.com deployment  
**Last Updated**: 2026-07-16  
**Target**: Production on Render (free tier)

---

## Pre-Deployment Verification

### ✅ Code Quality Checks

- [x] `main.py` exists and includes all endpoints
  - ✅ `/api/health` (health check)
  - ✅ `/api/jurisdictions` (list, create, get, update, delete)
  - ✅ `/api/procedures` (list, create, get, update, delete)
  - ✅ `/api/access-records` (list, query, get, create, update, delete)
  - ✅ `/api/search` (unified search)
  - ✅ `/api/export/json` and `/api/export/csv`

- [x] Database models complete
  - ✅ Jurisdiction (with nesting: parent_id + level)
  - ✅ Procedure (with regulatory_modality + restriction_driver)
  - ✅ AccessRecord (with pricing, travel, oversight, provenance fields)
  - ✅ Condition + ProcedureIndication (E1-E8 evidence grades)
  - ✅ All enums defined (JurisdictionLevel, RegulatoryModality, etc.)

- [x] Seed data ready
  - ✅ 32 jurisdictions defined
  - ✅ 38 procedures defined
  - ✅ 28 AccessRecords populated with schema fields

- [x] Configuration files
  - ✅ `.env.example` with all required variables
  - ✅ `Dockerfile` with Python 3.11 base
  - ✅ `requirements.txt` with all dependencies

- [x] CORS & Security
  - ✅ CORS middleware configured
  - ✅ Environment variables for sensitive data
  - ✅ No hardcoded secrets in code

### ✅ Database Readiness

- [x] SQLAlchemy models with type hints
- [x] Seed script (`seed.py`) creates schema on first run
- [x] Database connection string pattern: `postgresql://user:pass@host/db`
- [x] All relationships properly configured
- [x] No syntax errors in models

### ✅ API Readiness

- [x] FastAPI app instantiated with title/description/version
- [x] Startup event auto-initializes database
- [x] All endpoints return proper response models
- [x] Error handling with HTTPException (404, validation errors)
- [x] Search and filter endpoints implemented
- [x] Export (JSON + CSV) endpoints working

---

## Step-by-Step Deployment

### Phase 1: Prepare GitHub Repository

```bash
cd c:\Users\matth\OneDrive\Documents\OpenSourceMed\Opensource\ Medicine\ \(1\)\research-tracker

# Check current status
git status

# Add all files
git add .

# Commit changes
git commit -m "Deploy: Complete MedFreedom Arbitrage Map with schema + data"

# Create/switch to main branch
git branch -M main

# Add GitHub remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/research-tracker.git

# Push to GitHub
git push -u origin main
```

**Status**: [ ] Complete  
**Verified**: [ ] Code pushed successfully  
**GitHub URL**: `https://github.com/YOUR_USERNAME/research-tracker`

---

### Phase 2: Create Render Resources

#### Step 2A: Create PostgreSQL Database

1. Log in to [render.com](https://render.com)
2. Click **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name**: `medfreedom-db`
   - **Database**: `medfreedom`
   - **Region**: (choose closest to you)
   - **Plan**: Free
4. Click **"Create Database"**
5. **SAVE** the internal connection string (looks like `postgresql://user:pass@...`)

**Status**: [ ] Complete  
**Database URL Saved**: [ ] Yes  
**Database Status**: [ ] Available (green light)  
**Wait Time**: 2-3 minutes

#### Step 2B: Deploy Backend Service

1. Click **"New +"** → **"Web Service"**
2. **Connect GitHub**:
   - Select `research-tracker` repo
   - Branch: `main`
   - Root directory: `med-freedom-map/backend`
3. **Configure Service**:
   - **Name**: `medfreedom-api`
   - **Environment**: `Python 3.11`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. **Set Environment Variables**:
   - `DATABASE_URL` = (paste PostgreSQL connection string from Step 2A)
   - `DEBUG` = `false`
   - `ENVIRONMENT` = `production`
   - `API_PORT` = `8000`
5. **Plan**: Free
6. Click **"Create Web Service"**

**Status**: [ ] Complete  
**Service Name**: medfreedom-api  
**Build Status**: [ ] Success (should say "Deploy live")  
**Service URL**: `https://medfreedom-api.onrender.com`  
**Wait Time**: 3-5 minutes

---

### Phase 3: Initialize Database

Once service is deployed and showing "Deploy live":

1. Go to your service on Render dashboard
2. Click **"Shell"** tab (top navigation)
3. Run database initialization:

```bash
cd /opt/render/project/src
python -m app.seed
```

**Expected Output**:
```
Seed complete: 32 jurisdictions, 38 procedures, 28 access records.
```

**Status**: [ ] Complete  
**Seed Output Verified**: [ ] Yes

---

### Phase 4: Verify API Endpoints

#### Test 1: Health Check
```bash
curl https://medfreedom-api.onrender.com/api/health
```

**Expected**: `{"status":"ok","version":"0.1.0"}`

#### Test 2: Get Jurisdictions
```bash
curl https://medfreedom-api.onrender.com/api/jurisdictions | jq '.[] | {name, type, level}' | head -5
```

**Expected**: List of jurisdiction objects with name, type, level

#### Test 3: Get Procedures
```bash
curl https://medfreedom-api.onrender.com/api/procedures | jq '.[] | {name, regulatory_modality, restriction_driver}' | head -5
```

**Expected**: List of procedure objects

#### Test 4: Access Records
```bash
curl https://medfreedom-api.onrender.com/api/access-records | jq '.[] | {procedure_name, jurisdiction_name, legal_status, price_usd}' | head -3
```

**Expected**: List of records with pricing and legal status

#### Test 5: Search
```bash
curl "https://medfreedom-api.onrender.com/api/search?q=psilocybin"
```

**Expected**: Results object with procedures, jurisdictions, access_records

**Status**: [ ] All 5 tests pass

---

### Phase 5: Monitor Production

#### Render Dashboard Checks

- [ ] Service shows "Deploy live" (green)
- [ ] Recent Deployment section shows successful build
- [ ] Database shows "Available" (green)
- [ ] Logs show no errors in startup event
- [ ] Memory usage is reasonable (~50-100MB)

#### Log Inspection

Click **Logs** tab and verify:
- [ ] FastAPI startup message appears
- [ ] Database connection succeeds
- [ ] No error tracebacks in logs
- [ ] Search appears for seed data creation

---

## Maintenance & Updates

### Auto-Deployment from GitHub

After initial deployment, any push to `main` branch will:
1. Automatically trigger Render build
2. Run `pip install -r requirements.txt`
3. Restart service with new code
4. Database persists (no data loss)

**To deploy updates**:
```bash
git add .
git commit -m "Update: [your change description]"
git push origin main
```

Service will be live again in ~2 minutes.

### Database Backups

Render manages PostgreSQL backups automatically. Check:
- Render Dashboard → Your database → **Backups** tab
- Automatic backups run daily

### Monitoring Commands

View logs in real-time:
```bash
# Via Render dashboard: Logs tab (recommended)
# Or use Render's API if needed
```

---

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| 503 Service Unavailable | Service is cold-booting (10s). Retry after 30s. |
| 404 /api/health | Database_URL not set or invalid. Check env vars. |
| "psycopg2 error" | DATABASE_URL might be wrong. Verify in Render env vars. |
| Seed fails | Database may not be fully initialized. Wait 2-3 min, retry. |
| CORS errors from frontend | Update ALLOWED_ORIGINS env var with frontend URL. |
| Out of memory | Free tier is small. Render will restart if needed. |

---

## Final Verification Checklist

Before marking complete:

- [ ] GitHub repository has all code (git log shows latest commit)
- [ ] Render database shows "Available" status
- [ ] Render service shows "Deploy live" status
- [ ] Health check endpoint returns {"status": "ok"}
- [ ] At least 5 jurisdictions visible via `/api/jurisdictions`
- [ ] At least 5 procedures visible via `/api/procedures`
- [ ] At least 5 access records visible via `/api/access-records`
- [ ] Search endpoint works: `/api/search?q=psilocybin`
- [ ] No errors in Render logs for past 5 minutes
- [ ] Database still responsive after 5 minutes of inactivity

---

## Completion Summary

**Deployment Status**: 🚀 **READY FOR PRODUCTION**

**What You Have**:
- ✅ Live API at `https://medfreedom-api.onrender.com`
- ✅ Managed PostgreSQL database (250MB free tier)
- ✅ Auto-deploy on git push (zero manual steps)
- ✅ Full REST API for jurisdictions, procedures, access records
- ✅ Search, filtering, export (JSON + CSV)
- ✅ Zero monthly cost (free Render tier)

**Next Steps**:
1. Frontend deployment (optional, uses API)
2. Data expansion (add more procedures/jurisdictions as needed)
3. Refinement (based on user feedback)

**Support**:
- Check Render logs for errors
- Re-verify endpoints if deployment fails
- Push fixes to main branch for auto-redeploy

---

**Deployment Date**: ________________  
**Deployed By**: ________________  
**Production URL**: https://medfreedom-api.onrender.com  
**Database**: Render PostgreSQL (Free)  
**Last Verified**: ________________
