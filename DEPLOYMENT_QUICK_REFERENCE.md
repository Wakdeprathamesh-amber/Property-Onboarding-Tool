# 🚀 Render Deployment - Quick Reference

**Essential steps and commands for quick deployment**

---

## 📋 **Quick Deployment Steps**

### **1. Backend API (Web Service)**
- **Type**: Web Service
- **Runtime**: Python 3
- **Root Directory**: `property_onboarding_tool`
- **Build Command**: `pip install -r requirements_production.txt`
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 src.main_memory:create_app()`
- **Health Check**: `/api/health`

### **2. Frontend (Static Site)**
- **Type**: Static Site
- **Root Directory**: `property-onboarding-ui`
- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`
- **Environment Variable**: `VITE_API_BASE_URL=https://your-backend-url.onrender.com`

---

## 🔑 **Required Environment Variables**

### **Backend (Required)**
```bash
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_secret_key_here
DEBUG=false
HOST=0.0.0.0
PORT=10000
```

### **Frontend (Required)**
```bash
VITE_API_BASE_URL=https://your-backend-url.onrender.com
```

---

## 🚀 **Deployment Commands**

### **Manual Deployment**
1. **Backend**: Create Web Service → Connect GitHub → Configure → Deploy
2. **Frontend**: Create Static Site → Connect GitHub → Configure → Deploy

### **Automated Deployment (Blueprint)**
1. Push `render.yaml` to GitHub
2. Create Blueprint in Render
3. Select repository
4. Deploy both services automatically

---

## 🔍 **Quick Testing**

### **Health Check**
```bash
curl https://your-backend-url.onrender.com/api/health
```

### **Frontend Test**
1. Open frontend URL
2. Submit test property URL
3. Check browser console for API calls

---

## 📚 **Full Documentation**
See `RENDER_DEPLOYMENT_GUIDE.md` for complete step-by-step instructions.

---

**🎯 Goal**: Deploy both services and connect them for full functionality!
