import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  Loader2, 
  Eye, 
  RefreshCw,
  AlertCircle,
  Activity
} from 'lucide-react'
import { apiUrl, fetchJson } from '@/lib/api.js'

const ProgressMonitor = ({ jobId, onViewResults }) => {
  const [progress, setProgress] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchProgress = async () => {
    try {
      const data = await fetchJson(apiUrl(`/api/extraction/jobs/${jobId}/progress`))
      setProgress(data)
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  const fetchEvents = async () => {
    try {
      const data = await fetchJson(apiUrl(`/api/extraction/jobs/${jobId}/events?limit=10`))
      setEvents(data.events || [])
    } catch (err) {
      console.error('Failed to fetch events:', err)
    }
  }

  const handleExportCSV = async () => {
    try {
      const response = await fetch(apiUrl(`/api/extraction/jobs/${jobId}/export/csv`))
      
      if (!response.ok) {
        const raw = await response.text().catch(() => '')
        const message = raw || `Failed to export CSV (HTTP ${response.status})`
        console.error('CSV export failed', { url: apiUrl(`/api/extraction/jobs/${jobId}/export/csv`), status: response.status, raw })
        throw new Error(message)
      }

      // Get the filename from the response headers
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = `property_extraction_${jobId}.csv`
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename=(.+)/)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }

      // Create blob and download
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError(`Export failed: ${err.message}`)
    }
  }

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      await Promise.all([fetchProgress(), fetchEvents()])
      setLoading(false)
    }

    fetchData()

    // Poll for updates every 2 seconds if job is in progress
    const interval = setInterval(() => {
      if (progress?.status === 'in_progress' || progress?.status === 'pending') {
        fetchData()
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [jobId, progress?.status])

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'in_progress':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <Activity className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'in_progress':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString()
  }

  if (loading) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          Loading progress...
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button 
            onClick={() => window.location.reload()} 
            className="mt-4"
            variant="outline"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Main Progress Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {getStatusIcon(progress?.status)}
              Job Progress - ID: {jobId}
            </div>
            <Badge className={getStatusColor(progress?.status)}>
              {progress?.status?.toUpperCase()}
            </Badge>
          </CardTitle>
          <CardDescription>
            Current Phase: {progress?.current_phase?.replace('_', ' ')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Overall Progress */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Overall Progress</span>
              <span>{progress?.overall_progress || 0}%</span>
            </div>
            <Progress value={progress?.overall_progress || 0} className="w-full" />
          </div>

          {/* Node Progress */}
          <div className="space-y-4">
            <h4 className="font-medium">Extraction Nodes</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {progress?.node_details && Object.entries(progress.node_details).map(([nodeName, nodeData]) => (
                <div key={nodeName} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">
                      {nodeName.replace('node', 'Node ').replace('_', ' ')}
                    </span>
                    <div className="flex items-center gap-2">
                      {getStatusIcon(nodeData.status)}
                      <Badge variant="outline" className="text-xs">
                        {nodeData.status}
                      </Badge>
                    </div>
                  </div>
                  <Progress value={nodeData.progress || 0} className="w-full h-2" />
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>{nodeData.progress || 0}%</span>
                    {nodeData.execution_time && (
                      <span>{nodeData.execution_time.toFixed(1)}s</span>
                    )}
                  </div>
                  {nodeData.confidence_score && (
                    <div className="text-xs text-muted-foreground mt-1">
                      Confidence: {(nodeData.confidence_score * 100).toFixed(1)}%
                    </div>
                  )}
                  {nodeData.error && (
                    <div className="text-xs text-red-500 mt-1">
                      Error: {nodeData.error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Statistics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {progress?.nodes_completed || 0}
              </div>
              <div className="text-sm text-muted-foreground">Completed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {progress?.nodes_failed || 0}
              </div>
              <div className="text-sm text-muted-foreground">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {progress?.execution_time ? `${progress.execution_time.toFixed(1)}s` : '-'}
              </div>
              <div className="text-sm text-muted-foreground">Duration</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {progress?.accuracy_score ? `${(progress.accuracy_score * 100).toFixed(1)}%` : '-'}
              </div>
              <div className="text-sm text-muted-foreground">Accuracy</div>
            </div>
          </div>

          {/* Action Buttons */}
          {progress?.status === 'completed' && (
            <div className="flex gap-2 pt-4">
              <Button onClick={() => onViewResults(jobId)} className="flex-1">
                <Eye className="h-4 w-4 mr-2" />
                View Results
              </Button>
              <Button 
                variant="outline" 
                onClick={handleExportCSV}
                className="flex-1"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </div>
          )}

          {progress?.error_message && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{progress.error_message}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Events Timeline */}
      {events.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Events</CardTitle>
            <CardDescription>Latest progress updates</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {events.slice(0, 5).map((event, index) => (
                <div key={index} className="flex items-start gap-3 p-3 border rounded-lg">
                  <div className="flex-shrink-0 mt-0.5">
                    {event.event_type.includes('completed') ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : event.event_type.includes('failed') ? (
                      <XCircle className="h-4 w-4 text-red-500" />
                    ) : event.event_type.includes('started') ? (
                      <Loader2 className="h-4 w-4 text-blue-500" />
                    ) : (
                      <Activity className="h-4 w-4 text-gray-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{event.message}</div>
                    {event.node_name && (
                      <div className="text-xs text-muted-foreground">
                        Node: {event.node_name}
                      </div>
                    )}
                    <div className="text-xs text-muted-foreground">
                      {formatTimestamp(event.timestamp)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default ProgressMonitor

