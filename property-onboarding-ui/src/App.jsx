import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { 
  Building2, 
  ArrowLeft, 
  AlertCircle, 
  CheckCircle,
  Activity,
  Database,
  Zap
} from 'lucide-react'
import PropertySubmissionForm from './components/PropertySubmissionForm.jsx'
import ProgressMonitor from './components/ProgressMonitor.jsx'
import JsonViewer from './components/JsonViewer.jsx'
import CompareResultView from './components/CompareResultView.jsx'
import './App.css'

function App() {
  const [currentView, setCurrentView] = useState('submit') // 'submit', 'progress', 'results', 'compare'
  const [currentJobId, setCurrentJobId] = useState(null)
  const [comparePayload, setComparePayload] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const handleSubmitProperty = async (formData) => {
    setIsSubmitting(true)
    setSubmitError('')

    try {
      const response = await fetch('http://localhost:5000/api/extraction/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to submit property')
      }

      setCurrentJobId(data.job_id)
      setCurrentView('progress')
    } catch (error) {
      setSubmitError(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCompareLinks = async ({ property_url, competitor_url }) => {
    setIsSubmitting(true)
    setSubmitError('')
    try {
      const resp = await fetch('http://localhost:5000/api/competitors/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ property_url, competitor_url })
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error || 'Comparison failed')
      setComparePayload(data)
      setCurrentView('compare')
    } catch (e) {
      setSubmitError(e.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleViewResults = (jobId) => {
    setCurrentJobId(jobId)
    setCurrentView('results')
  }

  const handleBackToSubmit = () => {
    setCurrentView('submit')
    setCurrentJobId(null)
    setSubmitError('')
  }

  const handleBackToProgress = () => {
    setCurrentView('progress')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary rounded-lg">
                <Building2 className="h-6 w-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Property Onboarding Tool</h1>
                <p className="text-sm text-muted-foreground">
                  AI-powered property data extraction and verification
                </p>
              </div>
            </div>
            
            {currentView !== 'submit' && (
              <Button 
                variant="outline" 
                onClick={currentView === 'results' ? handleBackToProgress : handleBackToSubmit}
                className="flex items-center gap-2"
              >
                <ArrowLeft className="h-4 w-4" />
                {currentView === 'results' ? 'Back to Progress' : 'New Extraction'}
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {currentView === 'submit' && (
          <div className="space-y-8">
            {/* Hero Section */}
            <div className="text-center space-y-4 py-8">
              <h2 className="text-3xl font-bold tracking-tight">
                Extract Structured Data from Property Listings
              </h2>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                Submit a student accommodation URL and our AI system will extract comprehensive 
                structured data including property details, room configurations, pricing, and tenancy information.
              </p>
              
              <div className="flex justify-center gap-6 pt-4">
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span>GPT-4o Powered</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Zap className="h-4 w-4 text-yellow-500" />
                  <span>Parallel Processing</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Database className="h-4 w-4 text-blue-500" />
                  <span>Structured Output</span>
                </div>
              </div>
            </div>

            {/* Features Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Multi-Node Extraction</CardTitle>
                  <CardDescription>
                    4 specialized extraction nodes for comprehensive data coverage
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div>• Basic Info & Location</div>
                    <div>• Property Description</div>
                    <div>• Room Configurations</div>
                    <div>• Tenancy Information</div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Intelligent Processing</CardTitle>
                  <CardDescription>
                    Advanced orchestration with retry logic and quality scoring
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div>• Parallel execution</div>
                    <div>• Automatic retries</div>
                    <div>• Data validation</div>
                    <div>• Confidence scoring</div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Real-time Monitoring</CardTitle>
                  <CardDescription>
                    Live progress tracking and detailed result verification
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div>• Progress tracking</div>
                    <div>• Event timeline</div>
                    <div>• JSON verification</div>
                    <div>• Export capabilities</div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Submission Form */}
            <PropertySubmissionForm 
              onSubmit={handleSubmitProperty} 
              onCompare={handleCompareLinks}
              isSubmitting={isSubmitting}
            />

            {submitError && (
              <Alert variant="destructive" className="max-w-2xl mx-auto">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{submitError}</AlertDescription>
              </Alert>
            )}

            {/* Sample URLs */}
            <Card className="max-w-2xl mx-auto">
              <CardHeader>
                <CardTitle className="text-lg">Sample URLs for Testing</CardTitle>
                <CardDescription>
                  Try these example property URLs to see the extraction in action
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="p-2 bg-muted rounded font-mono text-xs">
                    https://www.unite-students.com/student-accommodation/london/stratford-one
                  </div>
                  <div className="p-2 bg-muted rounded font-mono text-xs">
                    https://www.iq-student.com/student-accommodation/london/iq-shoreditch
                  </div>
                  <div className="p-2 bg-muted rounded font-mono text-xs">
                    https://www.freshstudentliving.co.uk/student-accommodation/london/chapter-kings-cross
                  </div>
                </div>
              </CardContent>
            </Card>

            {null}
          </div>
        )}

        {currentView === 'progress' && currentJobId && (
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold">Extraction in Progress</h2>
              <p className="text-muted-foreground">
                Monitoring real-time progress for Job ID: {currentJobId}
              </p>
            </div>
            <ProgressMonitor 
              jobId={currentJobId} 
              onViewResults={handleViewResults}
            />
          </div>
        )}

        {currentView === 'results' && currentJobId && (
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold">Extraction Results</h2>
              <p className="text-muted-foreground">
                Verify and export the extracted structured data
              </p>
            </div>
            <JsonViewer jobId={currentJobId} />
          </div>
        )}

        {currentView === 'compare' && comparePayload && (
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold">Compare Results</h2>
              <p className="text-muted-foreground">Side-by-side JSON outputs using the same schema</p>
            </div>
            <CompareResultView initialResult={comparePayload} />
          </div>
        )}

        {null}
      </main>

      {/* Footer */}
      <footer className="border-t bg-white/80 backdrop-blur-sm mt-16">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div>
              Property Onboarding Tool v1.0.0 - Powered by GPT-4o
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="flex items-center gap-1">
                <Activity className="h-3 w-3" />
                System Active
              </Badge>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App

