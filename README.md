# Property Onboarding Tool

A comprehensive AI-powered property data extraction system that extracts structured data from student accommodation listings using GPT-4o and advanced orchestration.

## 🚀 Features

### Core Capabilities
- **Multi-Node Extraction**: 4 specialized extraction nodes for comprehensive data coverage
- **GPT-4o Integration**: Advanced AI-powered web browsing and data extraction
- **Parallel Processing**: Intelligent orchestration with parallel, sequential, and hybrid execution strategies
- **Real-time Monitoring**: Live progress tracking with detailed event timelines
- **JSON Verification**: Interactive UI for result verification and export

### Extraction Nodes
1. **Node 1 - Basic Info & Location**: Property details, location, features, rules, safety
2. **Node 2 - Description**: Detailed property descriptions and amenities
3. **Node 3 - Room Configurations**: Room types, pricing, offers, availability
4. **Node 4 - Tenancy Information**: Contracts, pricing, tenancy-level configurations

### Advanced Features
- **Competitor Analysis**: Automatic discovery and analysis of similar properties
- **Data Validation**: Comprehensive validation and quality scoring
- **Retry Logic**: Intelligent retry mechanisms with exponential backoff
- **Export Capabilities**: Multiple export formats (JSON, CSV, Airtable-ready)
- **Progress Tracking**: Real-time progress monitoring with event logging

## 🏗️ Architecture

### Backend (Flask)
- **API Layer**: RESTful API with comprehensive endpoints
- **Orchestration Engine**: Async job queue with priority scheduling
- **Data Processing**: Advanced data merging and validation
- **Progress Tracking**: Real-time progress monitoring system
- **Database**: SQLite with SQLAlchemy ORM

### Frontend (React)
- **Modern UI**: Clean, responsive interface built with React and Tailwind CSS
- **Real-time Updates**: Live progress monitoring and status updates
- **JSON Viewer**: Interactive JSON display with syntax highlighting
- **Export Tools**: Copy-to-clipboard and download functionality

## 📦 Installation

### Prerequisites
- Python 3.11+
- Node.js 20+
- npm/pnpm

### Backend Setup
```bash
cd property_onboarding_tool
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend Setup
```bash
cd property-onboarding-ui
npm install
# or
pnpm install
```

### Environment Configuration
Create a `.env` file in the backend directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
PERPLEXITY_API_KEY=your_perplexity_api_key_here  # Optional
DATABASE_URL=sqlite:///property_extraction.db
SECRET_KEY=your_secret_key_here
```

## 🚀 Usage

### Starting the Backend
```bash
cd property_onboarding_tool
source venv/bin/activate
python src/main.py
```
Backend will be available at `http://localhost:5000`

### Starting the Frontend
```bash
cd property-onboarding-ui
npm run dev
# or
pnpm dev
```
Frontend will be available at `http://localhost:3000`

### API Endpoints

#### Job Management
- `POST /api/extraction/submit` - Submit new extraction job
- `GET /api/extraction/jobs` - List all jobs
- `GET /api/extraction/jobs/{id}` - Get job details
- `GET /api/extraction/jobs/{id}/status` - Get job status
- `GET /api/extraction/jobs/{id}/progress` - Get detailed progress
- `GET /api/extraction/jobs/{id}/events` - Get progress events
- `POST /api/extraction/jobs/{id}/cancel` - Cancel job
- `POST /api/extraction/jobs/{id}/retry` - Retry failed job

#### System Monitoring
- `GET /api/extraction/stats` - System statistics
- `GET /api/extraction/queue/status` - Queue status
- `GET /api/health` - Health check

### Sample Usage

#### Submit a Job
```bash
curl -X POST http://localhost:5000/api/extraction/submit \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.unite-students.com/student-accommodation/london/stratford-one",
    "priority": "normal",
    "strategy": "parallel"
  }'
```

#### Check Progress
```bash
curl http://localhost:5000/api/extraction/jobs/1/progress
```

## 🎯 Execution Strategies

### Parallel (Default)
- All extraction nodes run simultaneously
- Fastest execution time
- Best for most use cases

### Sequential
- Nodes run one after another
- Most reliable for complex pages
- Slower but more stable

### Hybrid
- Dependencies run sequentially
- Independent nodes run in parallel
- Balanced approach

## 📊 Data Output Schema

### Basic Info Node
```json
{
  "basic_info": {
    "name": "Property Name",
    "guarantor_required": true,
    "deposit_amount": 500
  },
  "location": {
    "location_name": "London, Stratford",
    "region": "East London",
    "coordinates": {...}
  },
  "features": [...],
  "rules": [...],
  "safety": [...]
}
```

### Configuration Node
```json
{
  "configurations": [
    {
      "room_type": "Studio",
      "price_per_week": 350,
      "availability": "Available",
      "features": [...]
    }
  ]
}
```

## 🔧 Configuration

### Backend Configuration
Edit `src/utils/config.py` for:
- API timeouts
- Retry attempts
- Queue settings
- Database configuration

### Frontend Configuration
Edit environment variables in `.env.local`:
```env
VITE_API_BASE_URL=http://localhost:5000
```

## 📈 Monitoring & Logging

### Progress Tracking
- Real-time progress updates
- Event-driven architecture
- Detailed execution metrics
- Error tracking and reporting

### Logging
- Structured logging with job IDs
- Multiple log levels
- File and console output
- Performance metrics

## 🧪 Testing

### Sample URLs
The system includes sample URLs for testing:
- Unite Students properties
- IQ Student accommodation
- Fresh Student Living properties

### Mock Mode
For testing without API keys, the system includes mock clients that simulate extraction results.

## 🚀 Deployment

### Production Considerations
- Use a production WSGI server (Gunicorn, uWSGI)
- Configure proper database (PostgreSQL recommended)
- Set up Redis for job queue (optional)
- Configure proper logging
- Set up monitoring and alerting

### Docker Support
Docker configurations are included for easy deployment.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the documentation
- Review the API endpoints
- Examine the sample code
- Check the logs for error details

## 🔮 Future Enhancements

- Additional extraction nodes
- More data sources
- Advanced analytics
- Batch processing
- API rate limiting
- User authentication
- Data persistence options
- Advanced export formats

---

**Property Onboarding Tool v1.0.0** - Powered by GPT-4o and modern web technologies




cd property_onboarding_tool
python3 -m venv venv
source venv/bin/activate  
pip install -r requirements.txt
python run_memory.py

# Property-Onboarding-Tool
