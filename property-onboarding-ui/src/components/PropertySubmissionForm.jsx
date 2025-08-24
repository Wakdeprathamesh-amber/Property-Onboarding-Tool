import { useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Loader2, Send, AlertCircle } from 'lucide-react'

const PropertySubmissionForm = ({ onSubmit, isSubmitting, onCompare }) => {
  const [url, setUrl] = useState('')
  const [competitorUrl, setCompetitorUrl] = useState('')
  const [priority, setPriority] = useState('normal')
  const [strategy, setStrategy] = useState('parallel')
  const [error, setError] = useState('')

  const validateUrl = (url) => {
    try {
      new URL(url)
      return true
    } catch {
      return false
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')

    if (!url.trim()) {
      setError('Please enter a property URL')
      return
    }

    if (!validateUrl(url)) {
      setError('Please enter a valid URL')
      return
    }

    // If competitor URL is provided, run compare flow directly
    if (competitorUrl && onCompare) {
      onCompare({ property_url: url.trim(), competitor_url: competitorUrl.trim() })
      return
    }

    onSubmit({
      property_url: url.trim(),
      priority,
      execution_strategy: strategy
    })
  }

  const handleCompare = async (e) => {
    e.preventDefault()
    setError('')
    if (!url.trim() || !competitorUrl.trim()) {
      setError('Please enter both property and competitor URLs')
      return
    }
    if (!validateUrl(url) || !validateUrl(competitorUrl)) {
      setError('Please enter valid URLs')
      return
    }
    if (onCompare) {
      onCompare({ property_url: url.trim(), competitor_url: competitorUrl.trim() })
    }
  }

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Send className="h-5 w-5" />
          Submit Property for Extraction
        </CardTitle>
        <CardDescription>
          Enter a student accommodation property URL to extract structured data using AI
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="url">Property URL</Label>
            <Input
              id="url"
              type="url"
              placeholder="https://example.com/property-listing"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isSubmitting}
              className="w-full"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="competitor">Competitor URL (optional)</Label>
            <Input
              id="competitor"
              type="url"
              placeholder="https://competitor.com/property"
              value={competitorUrl}
              onChange={(e) => setCompetitorUrl(e.target.value)}
              disabled={isSubmitting}
              className="w-full"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="priority">Priority</Label>
              <Select value={priority} onValueChange={setPriority} disabled={isSubmitting}>
                <SelectTrigger>
                  <SelectValue placeholder="Select priority" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="strategy">Execution Strategy</Label>
              <Select value={strategy} onValueChange={setStrategy} disabled={isSubmitting}>
                <SelectTrigger>
                  <SelectValue placeholder="Select strategy" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="parallel">Parallel (Fastest)</SelectItem>
                  <SelectItem value="sequential">Sequential (Reliable)</SelectItem>
                  <SelectItem value="hybrid">Hybrid (Balanced)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Submit for Extraction
                </>
              )}
            </Button>
            <Button 
              type="button"
              variant="secondary"
              className="w-full"
              onClick={handleCompare}
              disabled={isSubmitting}
            >
              Compare Both Links
            </Button>
          </div>
        </form>

        <div className="mt-6 p-4 bg-muted rounded-lg">
          <h4 className="font-medium mb-2">Execution Strategies:</h4>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li><strong>Parallel:</strong> All extraction nodes run simultaneously (fastest)</li>
            <li><strong>Sequential:</strong> Nodes run one after another (most reliable)</li>
            <li><strong>Hybrid:</strong> Dependencies run sequentially, independents in parallel</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}

export default PropertySubmissionForm

