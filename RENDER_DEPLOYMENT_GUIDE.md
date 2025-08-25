# 🚀 Render Deployment Guide - Property Onboarding Tool

**Complete step-by-step guide to deploy the Property Onboarding Tool on Render**

---

## 📋 **Prerequisites**

- ✅ GitHub repository connected
- ✅ Render account (free tier available)
- ✅ OpenAI API key
- ✅ Basic understanding of web deployment

---

## 🔧 **Step 1: Backend API Deployment (Flask)**

### **1.1 Create New Web Service**

1. **Go to Render Dashboard**: https://dashboard.render.com/
2. **Click "New +"** → **"Web Service"**
3. **Connect GitHub Repository**:
   - Select your repository: `Wakdeprathamesh-amber/Property-Onboarding-Tool`
   - Click **"Connect"**

### **1.2 Configure Web Service**

#### **Basic Settings**
- **Name**: `property-onboarding-api` (or your preferred name)
- **Region**: Choose closest to your users (e.g., `Oregon (US West)` for US)
- **Branch**: `main`
- **Root Directory**: `property_onboarding_tool` ⚠️ **IMPORTANT!**

#### **Build & Deploy Settings**
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements_super_minimal.txt` ⚠️ **UPDATED!**
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 src.main_memory:create_app()`

**⚠️ IMPORTANT**: Use `requirements_super_minimal.txt` to avoid Python 3.13 compatibility issues with lxml and other packages.

#### **Environment Variables**
Click **"Environment"** tab and add these variables:

```bash
# Required Variables
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_secret_key_here
DEBUG=false
HOST=0.0.0.0
PORT=10000

# Optional Variables
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=5
EXTRACTION_TIMEOUT_SECONDS=300
PARALLEL_NODE_EXECUTION=true
ENABLE_COMPETITOR_ANALYSIS=true
MAX_COMPETITOR_SEARCHES=3
MAX_CONCURRENT_NODES=4
MAX_CONCURRENT_JOBS=2
REQUEST_TIMEOUT=30
CRAWL_DELAY_MS=500
```

#### **Advanced Settings**
- **Auto-Deploy**: ✅ Enable (recommended)
- **Health Check Path**: `/api/health`
- **Health Check Timeout**: `300` seconds

### **1.3 Deploy Backend**

1. **Click "Create Web Service"**
2. **Wait for build to complete** (5-10 minutes)
3. **Note the URL** (e.g., `https://property-onboarding-api.onrender.com`)

---

## 🎨 **Step 2: Frontend Deployment (React)**

### **2.1 Create New Static Site**

1. **Go to Render Dashboard**
2. **Click "New +"** → **"Static Site"**
3. **Connect GitHub Repository**:
   - Select your repository: `Wakdeprathamesh-amber/Property-Onboarding-Tool`
   - Click **"Connect"**

### **2.2 Configure Static Site**

#### **Basic Settings**
- **Name**: `property-onboarding-ui` (or your preferred name)
- **Region**: Same as backend (e.g., `Oregon (US West)`)
- **Branch**: `main`
- **Root Directory**: `property-onboarding-ui` ⚠️ **IMPORTANT!**

#### **Build & Deploy Settings**
- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`

#### **Environment Variables**
```bash
VITE_API_BASE_URL=https://your-backend-url.onrender.com
```

**Replace `your-backend-url` with your actual backend URL from Step 1.**

#### **Advanced Settings**
- **Auto-Deploy**: ✅ Enable (recommended)

### **2.3 Deploy Frontend**

1. **Click "Create Static Site"**
2. **Wait for build to complete** (3-5 minutes)
3. **Note the URL** (e.g., `https://property-onboarding-ui.onrender.com`)

---

## 🔄 **Step 3: Update Frontend API Configuration**

### **3.1 Update API Base URL**

After both services are deployed, update the frontend environment variable:

1. **Go to Frontend Service** in Render Dashboard
2. **Click "Environment"** tab
3. **Update `VITE_API_BASE_URL`** with your backend URL
4. **Redeploy** the frontend

### **3.2 Test the Connection**

1. **Open your frontend URL**
2. **Try submitting a property URL**
3. **Check browser console for API calls**
4. **Verify data extraction works**

---

## 🚀 **Step 4: Automated Deployment (Optional)**

### **4.1 Using render.yaml**

If you want to deploy both services at once:

1. **Push the `render.yaml` file to GitHub**
2. **Go to Render Dashboard**
3. **Click "New +"** → **"Blueprint"**
4. **Select your repository**
5. **Render will automatically create both services**

### **4.2 Manual Deployment**

If you prefer manual deployment, follow Steps 1-3 above.

---

## 🔍 **Step 5: Testing & Verification**

### **5.1 Health Check**

- **Backend**: Visit `/api/health` endpoint
- **Expected Response**: `{"status": "healthy"}`

### **5.2 API Endpoints Test**

Test these endpoints:
- `POST /api/extraction/submit`
- `GET /api/extraction/jobs/{job_id}/status`
- `GET /api/extraction/jobs/{job_id}/results`
- `POST /api/competitors/compare`

### **5.3 Frontend Functionality**

- ✅ Property submission form
- ✅ Progress monitoring
- ✅ Results display
- ✅ Competitor comparison
- ✅ CSV export functionality

---

## 🛠️ **Step 6: Troubleshooting**

### **Common Issues**

#### **Build Failures**
- **Check requirements.txt** - ensure all dependencies are listed
- **Verify Python version** - Render supports Python 3.7+
- **Check build logs** - look for specific error messages

#### **Cryptography Compatibility Issue** ⚠️ **COMMON ON PYTHON 3.13**
**Error**: `ERROR: No matching distribution found for cryptography==41.0.8`

**Solution**: Use `requirements_super_minimal.txt` instead of `requirements.txt`
- **Build Command**: `pip install -r requirements_super_minimal.txt`
- **Alternative**: Use `requirements_minimal.txt` for minimal dependencies
- **Why**: Python 3.13 requires newer versions of cryptography package

#### **LXML Compatibility Issue** ⚠️ **COMMON ON PYTHON 3.13**
**Error**: `ERROR: Failed building wheel for lxml`

**Solution**: Use `requirements_super_minimal.txt` which excludes lxml
- **Build Command**: `pip install -r requirements_super_minimal.txt`
- **Why**: lxml package is not compatible with Python 3.13 on Render
- **Alternative**: BeautifulSoup uses built-in `html.parser` instead

#### **Runtime Errors**
- **Environment variables** - ensure all required vars are set
- **Port configuration** - use `$PORT` environment variable
- **Dependencies** - check if all packages are installed

#### **Frontend Issues**
- **API connection** - verify `VITE_API_BASE_URL` is correct
- **Build output** - ensure `dist/` directory is created
- **CORS errors** - check backend CORS configuration

### **Debug Commands**

```bash
# Check backend logs
# Go to Render Dashboard → Backend Service → Logs

# Check frontend build
# Go to Render Dashboard → Frontend Service → Build Logs

# Test API locally
curl -X GET https://your-backend-url.onrender.com/api/health
```

---

## 📊 **Step 7: Monitoring & Maintenance**

### **7.1 Performance Monitoring**

- **Response times** - monitor API performance
- **Error rates** - check for failed requests
- **Resource usage** - monitor memory and CPU

### **7.2 Regular Updates**

- **Dependencies** - update packages regularly
- **Security patches** - apply security updates
- **Feature updates** - deploy new features

### **7.3 Backup & Recovery**

- **Database backups** - if using persistent storage
- **Configuration backups** - save environment variables
- **Code backups** - GitHub serves as backup

---

## 🎯 **Step 8: Production Checklist**

### **Before Going Live**

- ✅ Backend API deployed and responding
- ✅ Frontend UI deployed and accessible
- ✅ API endpoints tested and working
- ✅ Environment variables configured
- ✅ CORS properly configured
- ✅ Health checks passing
- ✅ Error handling implemented
- ✅ Logging configured
- ✅ Performance tested
- ✅ Security reviewed

### **Post-Deployment**

- ✅ Monitor application performance
- ✅ Set up alerts for errors
- ✅ Document deployment process
- ✅ Train team on new system
- ✅ Plan scaling strategy

---

## 🔗 **Useful Links**

- **Render Dashboard**: https://dashboard.render.com/
- **Render Documentation**: https://render.com/docs
- **GitHub Repository**: https://github.com/Wakdeprathamesh-amber/Property-Onboarding-Tool
- **Project Specification**: See `PROJECT_SPECIFICATION.md`

---

## 📞 **Support**

If you encounter issues:

1. **Check Render logs** first
2. **Review this deployment guide**
3. **Check project documentation**
4. **Review GitHub issues**
5. **Contact development team**

---

**🎉 Congratulations! Your Property Onboarding Tool is now deployed on Render!**

**Next Steps**: Test the application, configure monitoring, and start using it in production.