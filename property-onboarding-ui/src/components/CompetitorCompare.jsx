import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'

export default function CompetitorCompare() {
  const [propertyUrl, setPropertyUrl] = useState('')
  const [competitorUrl, setCompetitorUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const handleCompare = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const resp = await fetch('http://localhost:5000/api/competitors/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ property_url: propertyUrl, competitor_url: competitorUrl })
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error || 'Comparison failed')
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="max-w-3xl mx-auto">
        <CardHeader>
          <CardTitle>Competitor Comparison</CardTitle>
          <CardDescription>Compare our extraction against a competitor page using the same pipeline.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted-foreground">Property URL</label>
              <Input value={propertyUrl} onChange={(e) => setPropertyUrl(e.target.value)} placeholder="https://..." />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Competitor URL</label>
              <Input value={competitorUrl} onChange={(e) => setCompetitorUrl(e.target.value)} placeholder="https://..." />
            </div>
          </div>
          <Button disabled={loading || !propertyUrl || !competitorUrl} onClick={handleCompare}>
            {loading ? 'Comparing...' : 'Compare'}
          </Button>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle>Our JSON</CardTitle>
              <CardDescription>Extracted and merged</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <pre className="bg-muted p-2 rounded overflow-auto max-h-[400px] text-xs">
                {JSON.stringify(result.our?.merged_data ?? result.our, null, 2)}
              </pre>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Competitor JSON</CardTitle>
              <CardDescription>Extracted and merged</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted p-2 rounded overflow-auto max-h-[400px] text-xs">
                {JSON.stringify(result.competitor?.merged_data ?? result.competitor, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}


