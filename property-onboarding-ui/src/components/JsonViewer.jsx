import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Input } from '@/components/ui/input.jsx'
import { 
  Copy, 
  Download, 
  CheckCircle, 
  AlertCircle, 
  FileJson, 
  Database,
  Building,
  MapPin,
  Star,
  Clock
} from 'lucide-react'
import { apiUrl } from '@/lib/api.js'

const JsonViewer = ({ jobId }) => {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [propUrl, setPropUrl] = useState('')
  const [compUrl, setCompUrl] = useState('')
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState('')
  const [compareResult, setCompareResult] = useState(null)

  useEffect(() => {
    const fetchResults = async () => {
      try {
        const response = await fetch(apiUrl(`/api/extraction/jobs/${jobId}`))
        if (!response.ok) {
          throw new Error('Failed to fetch results')
        }
        const data = await response.json()
        setResults(data)
        setError('')
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchResults()
  }, [jobId])

  const copyToClipboard = async (data) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const downloadJson = (data, filename) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleCompare = async () => {
    setCompareLoading(true)
    setCompareError('')
    setCompareResult(null)
    try {
      const resp = await fetch(apiUrl('/api/competitors/compare'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ property_url: propUrl || results?.url, competitor_url: compUrl })
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error || 'Comparison failed')
      setCompareResult(data)
    } catch (e) {
      setCompareError(e.message)
    } finally {
      setCompareLoading(false)
    }
  }

  const formatJson = (obj) => {
    return JSON.stringify(obj, null, 2)
  }

  const getNodeDisplayName = (nodeName) => {
    const names = {
      'node1_basic_info': 'Basic Info & Location',
      'node2_description': 'Description & Details',
      'node3_configuration': 'Room Configurations',
      'node4_tenancy': 'Tenancy Information'
    }
    return names[nodeName] || nodeName
  }

  const renderPropertySummary = (mergedData) => {
    if (!mergedData) return null

    const basicInfo = mergedData.basic_info || {}
    const location = mergedData.location || {}
    const features = mergedData.features || []
    const configurations = mergedData.configurations || []

    return (
      <div className="space-y-6">
        {/* Property Overview */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building className="h-5 w-5" />
              Property Overview
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {basicInfo.name && (
              <div>
                <h3 className="font-semibold text-lg">{basicInfo.name}</h3>
              </div>
            )}
            
            {location.location_name && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <MapPin className="h-4 w-4" />
                <span>{location.location_name}</span>
                {location.region && <span>• {location.region}</span>}
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {basicInfo.guarantor_required !== undefined && (
                <div className="text-center p-3 border rounded-lg">
                  <div className="font-medium">Guarantor</div>
                  <div className="text-sm text-muted-foreground">
                    {basicInfo.guarantor_required ? 'Required' : 'Not Required'}
                  </div>
                </div>
              )}
              
              {features.length > 0 && (
                <div className="text-center p-3 border rounded-lg">
                  <div className="font-medium">{features.length}</div>
                  <div className="text-sm text-muted-foreground">Features</div>
                </div>
              )}
              
              {configurations.length > 0 && (
                <div className="text-center p-3 border rounded-lg">
                  <div className="font-medium">{configurations.length}</div>
                  <div className="text-sm text-muted-foreground">Room Types</div>
                </div>
              )}

              {results?.accuracy_score && (
                <div className="text-center p-3 border rounded-lg">
                  <div className="font-medium flex items-center justify-center gap-1">
                    <Star className="h-4 w-4 text-yellow-500" />
                    {(results.accuracy_score * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-muted-foreground">Accuracy</div>
                </div>
              )}
            </div>

            {features.length > 0 && (
              <div>
                <h4 className="font-medium mb-2">Key Features</h4>
                <div className="flex flex-wrap gap-2">
                  {features.slice(0, 10).map((feature, index) => (
                    <Badge key={index} variant="secondary">
                      {feature.name || feature}
                    </Badge>
                  ))}
                  {features.length > 10 && (
                    <Badge variant="outline">+{features.length - 10} more</Badge>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Extraction Metadata */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Extraction Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="font-medium">Status</div>
                <Badge className={results?.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                  {results?.status}
                </Badge>
              </div>
              
              {results?.extraction_duration && (
                <div>
                  <div className="font-medium">Duration</div>
                  <div className="text-sm text-muted-foreground">
                    {results.extraction_duration.toFixed(1)}s
                  </div>
                </div>
              )}
              
              {results?.completed_at && (
                <div>
                  <div className="font-medium">Completed</div>
                  <div className="text-sm text-muted-foreground">
                    {new Date(results.completed_at).toLocaleString()}
                  </div>
                </div>
              )}

              <div>
                <div className="font-medium">Source</div>
                <div className="text-sm text-muted-foreground truncate">
                  <a 
                    href={results?.url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="hover:underline"
                  >
                    {results?.url}
                  </a>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (loading) {
    return (
      <Card className="w-full max-w-6xl mx-auto">
        <CardContent className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mr-2"></div>
          Loading results...
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="w-full max-w-6xl mx-auto">
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileJson className="h-5 w-5" />
              Extraction Results - Job {jobId}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(results)}
              >
                {copied ? <CheckCircle className="h-4 w-4 mr-2" /> : <Copy className="h-4 w-4 mr-2" />}
                {copied ? 'Copied!' : 'Copy All'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => downloadJson(results, `property-extraction-${jobId}.json`)}
              >
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
            </div>
          </CardTitle>
          <CardDescription>
            Structured data extracted from the property listing
          </CardDescription>
        </CardHeader>
      </Card>

      <Tabs defaultValue="summary" className="w-full">
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-7">
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="merged">Merged Data</TabsTrigger>
          <TabsTrigger value="node1">Basic Info</TabsTrigger>
          <TabsTrigger value="node2">Description</TabsTrigger>
          <TabsTrigger value="node3">Configurations</TabsTrigger>
          <TabsTrigger value="node4">Tenancy</TabsTrigger>
          <TabsTrigger value="compare">Compare</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          {renderPropertySummary(results?.merged_data)}
        </TabsContent>

        <TabsContent value="merged" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  Merged Data
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(results?.merged_data)}
                  >
                    <Copy className="h-4 w-4 mr-2" />
                    Copy
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => downloadJson(results?.merged_data, `merged-data-${jobId}.json`)}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </Button>
                </div>
              </CardTitle>
              <CardDescription>
                Final merged and processed data from all extraction nodes
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted p-4 rounded-lg overflow-auto text-sm max-h-96">
                {formatJson(results?.merged_data)}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="compare" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Competitor Comparison</CardTitle>
              <CardDescription>Provide two URLs to see both JSON outputs side by side</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="md:col-span-1">
                  <label className="text-xs text-muted-foreground">Property URL (defaults to job URL)</label>
                  <Input value={propUrl} onChange={(e) => setPropUrl(e.target.value)} placeholder={results?.url || 'https://...'} />
                </div>
                <div className="md:col-span-1">
                  <label className="text-xs text-muted-foreground">Competitor URL</label>
                  <Input value={compUrl} onChange={(e) => setCompUrl(e.target.value)} placeholder="https://..." />
                </div>
                <div className="md:col-span-1 flex items-end">
                  <Button disabled={compareLoading || !compUrl} onClick={handleCompare}>
                    {compareLoading ? 'Comparing...' : 'Compare'}
                  </Button>
                </div>
              </div>
              {compareError && (
                <Alert variant="destructive">
                  <AlertDescription>{compareError}</AlertDescription>
                </Alert>
              )}
              {compareResult && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left: Our data */}
                  <div className="border rounded">
                    <div className="p-2 text-sm font-medium bg-muted">Our JSON</div>
                    <Tabs defaultValue="merged" className="w-full">
                      <TabsList className="grid w-full grid-cols-5">
                        <TabsTrigger value="merged">Merged</TabsTrigger>
                        <TabsTrigger value="node1">Node 1</TabsTrigger>
                        <TabsTrigger value="node2">Node 2</TabsTrigger>
                        <TabsTrigger value="node3">Node 3</TabsTrigger>
                        <TabsTrigger value="node4">Node 4</TabsTrigger>
                      </TabsList>
                      <TabsContent value="merged">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.our?.merged_data)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node1">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.our?.node_results?.node1_basic_info)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node2">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.our?.node_results?.node2_description)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node3">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.our?.node_results?.node3_configuration)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node4">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.our?.node_results?.node4_tenancy)}
                        </pre>
                      </TabsContent>
                    </Tabs>
                  </div>

                  {/* Right: Competitor data */}
                  <div className="border rounded">
                    <div className="p-2 text-sm font-medium bg-muted">Competitor JSON</div>
                    <Tabs defaultValue="merged" className="w-full">
                      <TabsList className="grid w-full grid-cols-5">
                        <TabsTrigger value="merged">Merged</TabsTrigger>
                        <TabsTrigger value="node1">Node 1</TabsTrigger>
                        <TabsTrigger value="node2">Node 2</TabsTrigger>
                        <TabsTrigger value="node3">Node 3</TabsTrigger>
                        <TabsTrigger value="node4">Node 4</TabsTrigger>
                      </TabsList>
                      <TabsContent value="merged">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.competitor?.merged_data)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node1">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.competitor?.node_results?.node1_basic_info)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node2">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.competitor?.node_results?.node2_description)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node3">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.competitor?.node_results?.node3_configuration)}
                        </pre>
                      </TabsContent>
                      <TabsContent value="node4">
                        <pre className="p-3 overflow-auto max-h-[480px] text-xs">
                          {formatJson(compareResult.competitor?.node_results?.node4_tenancy)}
                        </pre>
                      </TabsContent>
                    </Tabs>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {['node1_basic_info', 'node2_description', 'node3_configuration', 'node4_tenancy'].map((nodeKey, index) => (
          <TabsContent key={nodeKey} value={`node${index + 1}`} className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileJson className="h-5 w-5" />
                    {getNodeDisplayName(nodeKey)}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copyToClipboard(results?.node_results?.[nodeKey]?.data)}
                    >
                      <Copy className="h-4 w-4 mr-2" />
                      Copy
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => downloadJson(results?.node_results?.[nodeKey]?.data, `${nodeKey}-${jobId}.json`)}
                    >
                      <Download className="h-4 w-4 mr-2" />
                      Download
                    </Button>
                  </div>
                </CardTitle>
                <CardDescription>
                  Raw data extracted by {getNodeDisplayName(nodeKey)} node
                </CardDescription>
              </CardHeader>
              <CardContent>
                {results?.node_results?.[nodeKey] ? (
                  <div className="space-y-4">
                    {/* Node Statistics */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-muted rounded-lg">
                      <div className="text-center">
                        <div className="font-medium">Status</div>
                        <Badge className={results.node_results[nodeKey].status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                          {results.node_results[nodeKey].status}
                        </Badge>
                      </div>
                      {results.node_results[nodeKey].confidence_score && (
                        <div className="text-center">
                          <div className="font-medium">Confidence</div>
                          <div className="text-sm text-muted-foreground">
                            {(results.node_results[nodeKey].confidence_score * 100).toFixed(1)}%
                          </div>
                        </div>
                      )}
                      {results.node_results[nodeKey].execution_duration && (
                        <div className="text-center">
                          <div className="font-medium">Duration</div>
                          <div className="text-sm text-muted-foreground">
                            {results.node_results[nodeKey].execution_duration.toFixed(1)}s
                          </div>
                        </div>
                      )}
                      {results.node_results[nodeKey].data_completeness && (
                        <div className="text-center">
                          <div className="font-medium">Completeness</div>
                          <div className="text-sm text-muted-foreground">
                            {(results.node_results[nodeKey].data_completeness * 100).toFixed(1)}%
                          </div>
                        </div>
                      )}
                    </div>

                    {/* JSON Data */}
                    <pre className="bg-muted p-4 rounded-lg overflow-auto text-sm max-h-96">
                      {formatJson(results.node_results[nodeKey].data)}
                    </pre>
                  </div>
                ) : (
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      No data available for this node
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>

      {/* Competitor Analysis */}
      {results?.competitor_analyses && results.competitor_analyses.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Competitor Analysis</CardTitle>
            <CardDescription>
              Similar properties found during analysis
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {results.competitor_analyses.map((competitor, index) => (
                <div key={index} className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium">{competitor.competitor_name}</h4>
                    <Badge variant="outline">
                      {(competitor.similarity_score * 100).toFixed(1)}% similar
                    </Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <a 
                      href={competitor.competitor_url} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {competitor.competitor_url}
                    </a>
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

export default JsonViewer

