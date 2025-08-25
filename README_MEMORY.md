# Property Onboarding Tool - In-Memory Version

A comprehensive AI-powered property data extraction tool that processes student accommodation listings using GPT-4o and web browsing capabilities. This version uses **in-memory storage** instead of a database for simplified deployment and testing.

## 🚀 Features

### Core Functionality
- **Multi-Node Extraction**: 4 specialized extraction nodes for comprehensive data coverage
- **GPT-4o Integration**: Advanced AI-powered data extraction with web browsing
- **Real-time Progress Tracking**: Live monitoring with detailed progress updates
- **In-Memory Storage**: No database required - all data stored in memory
- **Modern UI**: React-based interface with real-time updates
- **Parallel Processing**: Configurable execution strategies (Parallel, Sequential, Hybrid)

### Extraction Capabilities
- **Node 1**: Basic Info, Location, Features, Rules, Safety
- **Node 2**: Property Description (Detailed)
- **Node 3**: Room Configurations, Pricing, Offers, Availability
- **Node 4**: Tenancy-Level Room Configs with Contracts & Pricing

### Advanced Features
- **Competitor Analysis**: Automatic competitor property discovery
- **Data Validation**: Comprehensive quality scoring and validation
- **Export Options**: JSON download and clipboard copy
- **Progress Monitoring**: Real-time event tracking and progress updates
- **Error Handling**: Robust retry mechanisms and error recovery

## 📋 Requirements

### System Requirements
- Python 3.11+
- Node.js 18+
- npm or pnpm

### API Keys (Optional for Testing)
- OpenAI API Key (for GPT-4o) - Uses mock responses if not provided
- Perplexity API Key (for competitor analysis) - Uses mock responses if not provided

## 🛠️ Installation & Setup

### 1. Extract the Project
```bash
unzip property-onboarding-tool-memory.zip
cd property-onboarding-tool-memory
```

### 2. Backend Setup
```bash
cd property_onboarding_tool

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Set environment variables for API keys
export OPENAI_API_KEY="your-openai-api-key"
export PERPLEXITY_API_KEY="your-perplexity-api-key"
```

### 3. Frontend Setup
```bash
cd ../property-onboarding-ui

# Install dependencies
npm install
# or
pnpm install
```

## 🚀 Running the Application

### Start Backend (Terminal 1)
```bash
cd property_onboarding_tool
source venv/bin/activate
python run_memory.py
```

The backend will start on `http://localhost:5000`

### Start Frontend (Terminal 2)
```bash
cd property-onboarding-ui
npm run dev
# or
pnpm dev
```

The frontend will start on `http://localhost:5173` (or next available port)

### Access the Application
Open your browser and navigate to the frontend URL (displayed in terminal)

## 🎯 Usage

### Basic Usage
1. **Enter Property URL**: Input a student accommodation property URL
2. **Select Priority**: Choose from Low, Normal, High, or Urgent
3. **Choose Strategy**: Select Parallel (fastest), Sequential (reliable), or Hybrid (balanced)
4. **Submit**: Click "Submit for Extraction" to start processing
5. **Monitor Progress**: Watch real-time progress updates
6. **View Results**: Review extracted JSON data with verification interface

### Sample URLs for Testing
```
https://www.unite-students.com/student-accommodation/london/stratford-one
https://www.iq-student.com/student-accommodation/london/iq-shoreditch
https://www.freshstudentliving.co.uk/student-accommodation/london/chapter-kings-cross
```

### API Endpoints
- `POST /api/extraction/submit` - Submit new extraction job
- `GET /api/extraction/jobs` - List all jobs
- `GET /api/extraction/jobs/{id}` - Get job details
- `GET /api/extraction/jobs/{id}/status` - Get job status
- `GET /api/extraction/jobs/{id}/results` - Get extraction results
- `GET /api/extraction/jobs/{id}/progress` - Get detailed progress
- `GET /api/health` - System health check

## 🏗️ Architecture

### In-Memory Storage
- **No Database Required**: All data stored in memory using Python data structures
- **Thread-Safe Operations**: Concurrent access handled with proper locking
- **Job Queue Management**: Priority-based job scheduling in memory
- **Progress Tracking**: Real-time event and progress monitoring

### Backend Components
- **Flask API**: RESTful API with CORS support
- **Async Orchestration**: Parallel node execution with dependency management
- **GPT-4o Client**: AI-powered extraction with web browsing
- **Data Processing**: Validation, merging, and quality scoring
- **Memory Store**: Thread-safe in-memory data management

### Frontend Components
- **React Application**: Modern UI with Tailwind CSS
- **Real-time Updates**: Live progress monitoring
- **JSON Viewer**: Interactive result display with export options
- **Form Validation**: Input validation and error handling

## 🔧 Configuration

### Environment Variables
```bash
# API Configuration
OPENAI_API_KEY=your-openai-api-key
PERPLEXITY_API_KEY=your-perplexity-api-key

# Application Configuration
FLASK_ENV=development
FLASK_DEBUG=true
```

### Execution Strategies
- **Parallel**: All nodes run simultaneously (fastest, ~30-60 seconds)
- **Sequential**: Nodes run one after another (most reliable, ~2-4 minutes)
- **Hybrid**: Dependencies sequential, independents parallel (balanced, ~1-2 minutes)

## 📊 System Monitoring

### Health Check
```bash
curl http://localhost:5000/api/health
```

### Queue Statistics
```bash
curl http://localhost:5000/api/extraction/stats
```

### Job Management
```bash
# List all jobs
curl http://localhost:5000/api/extraction/jobs

# Get specific job
curl http://localhost:5000/api/extraction/jobs/{job_id}

# Cancel job
curl -X POST http://localhost:5000/api/extraction/jobs/{job_id}/cancel
```

## 🐛 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Kill processes on port 5000
   lsof -ti:5000 | xargs kill -9
   
   # Kill processes on port 5173
   lsof -ti:5173 | xargs kill -9
   ```

2. **Module Import Errors**
   ```bash
   # Clear Python cache
   find . -name "*.pyc" -delete
   find . -name "__pycache__" -type d -exec rm -rf {} +
   ```

3. **Frontend Build Issues**
   ```bash
   # Clear npm cache
   npm cache clean --force
   rm -rf node_modules package-lock.json
   npm install
   ```

### Memory Limitations
- **Data Persistence**: Data is lost when the application restarts
- **Memory Usage**: Large jobs may consume significant memory
- **Concurrent Jobs**: Limited by available system memory

## 🔒 Security Notes

- **Development Mode**: This is configured for development/testing
- **API Keys**: Store securely and never commit to version control
- **CORS**: Currently allows all origins for development
- **Input Validation**: Basic URL and parameter validation implemented

## 📈 Performance

### Expected Performance
- **Parallel Execution**: 30-60 seconds per property
- **Sequential Execution**: 2-4 minutes per property
- **Concurrent Jobs**: Up to 3 simultaneous extractions
- **Memory Usage**: ~50-100MB per active job

### Optimization Tips
- Use Parallel strategy for speed
- Use Sequential strategy for reliability
- Monitor memory usage with multiple concurrent jobs
- Restart application periodically to clear memory

## 🤝 Support

### Getting Help
1. Check the troubleshooting section above
2. Review the console logs for error messages
3. Verify API keys are correctly set
4. Ensure all dependencies are installed

### Development
- Backend logs: Check terminal running `run_memory.py`
- Frontend logs: Check browser developer console
- API testing: Use curl or Postman for API endpoints

## 📝 Notes

### Differences from Database Version
- **No Persistence**: Data is lost on restart
- **Simplified Setup**: No database configuration required
- **Memory Constraints**: Limited by available system memory
- **Development Focus**: Optimized for testing and development

### Production Considerations
- For production use, consider the database version
- Implement proper logging and monitoring
- Add authentication and authorization
- Configure proper CORS policies
- Use production WSGI server (gunicorn, uwsgi)

---

**Property Onboarding Tool v1.0.0 - In-Memory Edition**  
*Powered by GPT-4o and built with Flask + React*

