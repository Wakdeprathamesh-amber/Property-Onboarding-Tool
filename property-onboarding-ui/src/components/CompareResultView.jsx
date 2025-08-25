import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { apiUrl, fetchJson } from '@/lib/api.js'

export default function CompareResultView({ initialResult }) {
  const [propUrl, setPropUrl] = useState(initialResult?.property_url || '')
  const [compUrl, setCompUrl] = useState(initialResult?.competitor_url || '')
  const [result, setResult] = useState(initialResult || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const formatJson = (obj) => JSON.stringify(obj || {}, null, 2)

  // Helpers for readable comparison
  const getMerged = (side) => side?.merged_data || {}
  const getFeatures = (side) => {
    const merged = getMerged(side)
    let features = []
    
    // Check multiple possible locations for features
    if (Array.isArray(merged?.features)) {
      features = merged.features
    } else if (merged?.description?.features && typeof merged.description.features === 'string') {
      // Handle string features (split by commas, semicolons, etc.)
      features = merged.description.features.split(/[,;]/).map(f => f.trim()).filter(Boolean)
    } else if (merged?.description?.features && Array.isArray(merged.description.features)) {
      features = merged.description.features
    }
    
    // Also check configurations for features
    const configs = getConfigs(side)
    configs.forEach(config => {
      if (Array.isArray(config.features)) {
        features.push(...config.features)
      } else if (Array.isArray(config.Features)) {
        features.push(...config.Features)
      }
    })
    
    // Deduplicate and format features
    const uniqueFeatures = [...new Set(features)]
    return uniqueFeatures.map((f) => {
      if (typeof f === 'string') return f
      if (f && typeof f === 'object') {
        return f.name || f.feature || f.Type || f.Description || f.Description || JSON.stringify(f)
      }
      return String(f)
    }).filter(Boolean)
  }
  const getLocation = (side) => {
    const merged = getMerged(side)
    let location = {}
    
    // Check multiple possible locations for location data
    if (merged?.location && typeof merged.location === 'object') {
      location = merged.location
    } else if (merged?.tenancy_data?.property_level && typeof merged.tenancy_data.property_level === 'object') {
      // Fallback to tenancy_data.property_level for location
      const propLevel = merged.tenancy_data.property_level
      location = {
        location_name: propLevel.location_name || propLevel.name || '',
        address: propLevel.address || '',
        city: propLevel.city || propLevel.region || '',
        region: propLevel.region || propLevel.city || '',
        country: propLevel.country || 'UK',
        latitude: propLevel.latitude || '',
        longitude: propLevel.longitude || ''
      }
    }
    
    // Ensure all required fields exist
    return {
      location_name: location.location_name || '',
      address: location.address || '',
      city: location.city || '',
      region: location.region || '',
      country: location.country || '',
      latitude: location.latitude || '',
      longitude: location.longitude || ''
    }
  }
  const getFaqs = (side) => {
    const desc = getMerged(side)?.description || {}
    const faqs = Array.isArray(desc?.faqs) ? desc.faqs : []
    return faqs.map((f) => ({
      question: f?.question || '',
      answer: f?.answer || ''
    })).filter((f) => f.question || f.answer)
  }
  const getDescription = (side) => (getMerged(side)?.description || {})
  const getDescField = (side, key) => {
    const d = getDescription(side)
    return d && typeof d === 'object' ? (d[key] || '') : ''
  }
  const getPayments = (side) => {
    const d = getDescription(side)
    return (d && typeof d === 'object' && typeof d.payments === 'object') ? d.payments : {}
  }
  const getCancellation = (side) => {
    const d = getDescription(side)
    return (d && typeof d === 'object' && typeof d.cancellation_policy === 'object') ? d.cancellation_policy : {}
  }
  const getConfigs = (side) => {
    const merged = getMerged(side)
    let configs = []
    
    // Check both direct configurations and tenancy_data.configurations
    if (Array.isArray(merged?.configurations)) {
      configs.push(...merged.configurations)
    }
    
    if (Array.isArray(merged?.tenancy_data?.configurations)) {
      configs.push(...merged.tenancy_data.configurations)
    }
    
    // If we have both, prefer tenancy_data.configurations as they're usually more detailed
    // but also include unique configurations from the root level
    if (Array.isArray(merged?.tenancy_data?.configurations) && Array.isArray(merged?.configurations)) {
      const tenancyNames = new Set(merged.tenancy_data.configurations.map(c => getConfigName(c)))
      const uniqueRootConfigs = merged.configurations.filter(c => !tenancyNames.has(getConfigName(c)))
      configs = [...merged.tenancy_data.configurations, ...uniqueRootConfigs]
    }
    
    return configs
  }
  // Enhanced field access helpers with multiple path checks
  const getConfigName = (cfg) => {
    if (!cfg) return ''
    return cfg.name || 
           cfg.room_type || 
           (cfg.Basic && cfg.Basic.Name) || 
           '(Unnamed)'
  }
  
  const normalizeName = (s) => (s ? String(s).trim().toLowerCase() : '')
  
  const priceFromConfig = (cfg) => {
    if (!cfg) return ''
    
    // Try multiple price fields in order of preference
    const price = cfg.base_price || 
                  cfg.Price || 
                  (cfg.Pricing && cfg.Pricing.Price) || 
                  cfg.min_price || 
                  cfg.max_price ||
                  cfg.price ||
                  ''
    
    // If we have a price, format it properly
    if (price) {
      // Remove currency symbols and clean up
      const cleanPrice = String(price).replace(/[£$€]/g, '').trim()
      return cleanPrice
    }
    
    return ''
  }
  
  const getTenancies = (cfg) => {
    if (!cfg) return []
    
    // Try multiple tenancy fields in order of preference
    const tenancies = Array.isArray(cfg.tenancy_options) ? cfg.tenancy_options : 
                      Array.isArray(cfg.tenancies) ? cfg.tenancies :
                      Array.isArray(cfg.tenancy) ? cfg.tenancy :
                      []
    
    // If no tenancies found, try to create a basic tenancy from configuration data
    if (tenancies.length === 0 && cfg) {
      const basicTenancy = {}
      
      // Try to extract duration
      if (cfg.tenancy_length) basicTenancy.tenancy_length = cfg.tenancy_length
      else if (cfg.Lease && cfg.Lease['Lease Duration']) basicTenancy.tenancy_length = cfg.Lease['Lease Duration']
      else if (cfg['Lease Duration'] && cfg['Lease Duration']['Lease Duration']) basicTenancy.tenancy_length = cfg['Lease Duration']['Lease Duration']
      
      // Try to extract price
      if (cfg.base_price) basicTenancy.price = cfg.base_price
      else if (cfg.Price) basicTenancy.price = cfg.Price
      else if (cfg.Pricing && cfg.Pricing.Price) basicTenancy.price = cfg.Pricing.Price
      
      // Try to extract dates
      if (cfg.available_from) basicTenancy.start_date = cfg.available_from
      else if (cfg.Availability && cfg.Availability['Available From']) basicTenancy.start_date = cfg.Availability['Available From']
      
      // If we have at least some data, return it
      if (basicTenancy.tenancy_length || basicTenancy.price) {
        basicTenancy.availability_status = cfg.status || cfg.availability_status || 'Available'
        return [basicTenancy]
      }
    }
    
    return tenancies
  }
  
  const getConfigFeatures = (cfg) => {
    if (!cfg) return []
    if (Array.isArray(cfg.features)) return cfg.features
    
    // Try to extract features from Features array if it exists
    if (Array.isArray(cfg.Features)) {
      return cfg.Features.map(f => {
        if (typeof f === 'string') return f
        if (f && typeof f === 'object') {
          return f.Description || f.name || f.Type || JSON.stringify(f)
        }
        return String(f)
      })
    }
    
    return []
  }
  const normalizeDurationKey = (t) => {
    if (!t || typeof t !== 'object') return ''
    if (t.duration_months) return `${t.duration_months}m`
    const d = t.duration || t.tenancy_length || ''
    const match = String(d).match(/(\d+)\s*(month|months|m)/i)
    return match ? `${match[1]}m` : String(d)
  }
  const priceFromTenancy = (t) => t?.price || t?.amount || ''

  // Render helpers to keep JSX simple
  const renderConfigTable = () => {
    if (!result) return null
    
    const left = getConfigs(result.our)
    const right = getConfigs(result.competitor)
    
    // Use normalized names for better matching
    const mapL = new Map(left.map((c) => [normalizeName(getConfigName(c)), c]))
    const mapR = new Map(right.map((c) => [normalizeName(getConfigName(c)), c]))
    const names = Array.from(new Set([...mapL.keys(), ...mapR.keys()])).filter(Boolean).sort()

    if (!names.length) {
      return (
        <table className="w-full text-sm">
          <tbody>
            <tr>
              <td className="p-2 text-center text-muted-foreground">No configurations found</td>
            </tr>
          </tbody>
        </table>
      )
    }

    // Calculate data quality scores
    const getQualityScore = (cfg) => {
      if (!cfg) return 0
      let score = 0
      if (cfg.name || cfg.Basic?.Name) score += 0.2
      if (priceFromConfig(cfg)) score += 0.2
      if (getTenancies(cfg).length > 0) score += 0.3
      if (getConfigFeatures(cfg).length > 0) score += 0.2
      if (cfg.status || cfg.availability_status) score += 0.1
      return score
    }

    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted">
            <th className="text-left p-2">Configuration</th>
            <th className="text-left p-2">Our Price</th>
            <th className="text-left p-2">Their Price</th>
            <th className="text-left p-2">Our Tenancies</th>
            <th className="text-left p-2">Their Tenancies</th>
            <th className="text-left p-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const L = mapL.get(n)
            const R = mapR.get(n)
            
            // Get tenancy counts using enhanced accessor
            const lTen = getTenancies(L).length
            const rTen = getTenancies(R).length
            
            // Get prices using enhanced accessor
            const lPrice = priceFromConfig(L)
            const rPrice = priceFromConfig(R)
            
            // Calculate price difference if both exist
            const diff = (lPrice && rPrice && String(lPrice) !== String(rPrice))
            let priceDiff = null
            if (lPrice && rPrice) {
              const lNum = parseFloat(lPrice)
              const rNum = parseFloat(rPrice)
              if (!isNaN(lNum) && !isNaN(rNum) && lNum !== 0) {
                const diffPct = Math.round((rNum - lNum) / lNum * 100)
                priceDiff = diffPct
              }
            }
            
            // Determine source indicators
            const onlyInOurs = L && !R
            const onlyInTheirs = !L && R
            
            // Get quality scores
            const lQuality = getQualityScore(L)
            const rQuality = getQualityScore(R)
            
            return (
              <tr key={n} className={`border-b last:border-0 ${onlyInOurs ? 'bg-blue-50' : onlyInTheirs ? 'bg-green-50' : ''}`}>
                <td className="p-2 font-medium">
                  {getConfigName(L) || getConfigName(R)}
                  {onlyInOurs && <Badge variant="outline" className="ml-2 text-xs">Only in ours</Badge>}
                  {onlyInTheirs && <Badge variant="outline" className="ml-2 text-xs">Only in theirs</Badge>}
                </td>
                <td className="p-2">
                  {lPrice ? lPrice : <span className="text-muted-foreground">—</span>}
                  {lQuality < 0.5 && lPrice && <Badge variant="secondary" className="ml-1 text-xs">Limited data</Badge>}
                </td>
                <td className="p-2">
                  {rPrice ? (
                    <>
                      {rPrice}
                      {priceDiff !== null && (
                        <Badge 
                          variant={priceDiff < 0 ? "success" : priceDiff > 0 ? "destructive" : "outline"} 
                          className="ml-1 text-xs"
                        >
                          {priceDiff > 0 ? `+${priceDiff}%` : `${priceDiff}%`}
                        </Badge>
                      )}
                    </>
                  ) : <span className="text-muted-foreground">—</span>}
                  {rQuality < 0.5 && rPrice && <Badge variant="secondary" className="ml-1 text-xs">Limited data</Badge>}
                </td>
                <td className="p-2">{lTen > 0 ? lTen : <span className="text-muted-foreground">—</span>}</td>
                <td className="p-2">{rTen > 0 ? rTen : <span className="text-muted-foreground">—</span>}</td>
                <td className="p-2">
                  {L?.status || L?.availability_status || R?.status || R?.availability_status || <span className="text-muted-foreground">—</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    )
  }

  const renderTenancySections = () => {
    if (!result) return null
    
    const left = getConfigs(result.our)
    const right = getConfigs(result.competitor)
    
    // Use enhanced accessor functions for better matching
    const mapL = new Map(left.map((c) => [normalizeName(getConfigName(c)), c]))
    const mapR = new Map(right.map((c) => [normalizeName(getConfigName(c)), c]))
    const names = Array.from(new Set([...mapL.keys(), ...mapR.keys()])).filter(Boolean).sort()
    
    if (!names.length) {
      return <div className="text-sm text-muted-foreground">No configurations with tenancies</div>
    }

    const toNum = (k) => (k && typeof k === 'string' && k.endsWith('m') ? parseInt(k) : 9999)

    return (
      <div className="space-y-4">
        {names.map((n) => {
          const L = mapL.get(n)
          const R = mapR.get(n)
          
          // Use enhanced tenancy accessor
          const lT = getTenancies(L)
          const rT = getTenancies(R)
          
          // Skip if no tenancies on either side
          if (lT.length === 0 && rT.length === 0) return null
          
          const mapLT = new Map(lT.map((t) => [normalizeDurationKey(t), t]))
          const mapRT = new Map(rT.map((t) => [normalizeDurationKey(t), t]))
          const durs = Array.from(new Set([...mapLT.keys(), ...mapRT.keys()])).filter(Boolean).sort((a,b) => toNum(a) - toNum(b))
          
          // Determine source indicators
          const onlyInOurs = L && !R
          const onlyInTheirs = !L && R
          
          return (
            <div key={`ten-${n}`} className={`border rounded ${onlyInOurs ? 'border-blue-200' : onlyInTheirs ? 'border-green-200' : ''}`}>
              <div className={`p-2 text-sm font-medium ${onlyInOurs ? 'bg-blue-50' : onlyInTheirs ? 'bg-green-50' : 'bg-muted'}`}>
                {getConfigName(L) || getConfigName(R)}
                {onlyInOurs && <Badge variant="outline" className="ml-2 text-xs">Only in ours</Badge>}
                {onlyInTheirs && <Badge variant="outline" className="ml-2 text-xs">Only in theirs</Badge>}
              </div>
              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-muted">
                      <th className="text-left p-2">Duration</th>
                      <th className="text-left p-2">Our Price</th>
                      <th className="text-left p-2">Their Price</th>
                      <th className="text-left p-2">Start Date</th>
                      <th className="text-left p-2">End Date</th>
                      <th className="text-left p-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {durs.length ? durs.map((k) => {
                      const lt = mapLT.get(k)
                      const rt = mapRT.get(k)
                      const lp = priceFromTenancy(lt)
                      const rp = priceFromTenancy(rt)
                      const showK = (k && typeof k === 'string' && k.endsWith('m')) ? `${parseInt(k)} months` : k
                      
                      // Calculate price difference
                      let priceDiff = null
                      if (lp && rp) {
                        const lNum = parseFloat(lp)
                        const rNum = parseFloat(rp)
                        if (!isNaN(lNum) && !isNaN(rNum) && lNum !== 0) {
                          const diffPct = Math.round((rNum - lNum) / lNum * 100)
                          priceDiff = diffPct
                        }
                      }
                      
                      // Determine if this duration exists in only one source
                      const onlyInOursTenancy = lt && !rt
                      const onlyInTheirsTenancy = !lt && rt
                      
                      return (
                        <tr 
                          key={`row-${n}-${k}`} 
                          className={`border-b last:border-0 ${onlyInOursTenancy ? 'bg-blue-50' : onlyInTheirsTenancy ? 'bg-green-50' : ''}`}
                        >
                          <td className="p-2 whitespace-nowrap">
                            {showK}
                            {onlyInOursTenancy && <Badge variant="outline" className="ml-1 text-xs">Only in ours</Badge>}
                            {onlyInTheirsTenancy && <Badge variant="outline" className="ml-1 text-xs">Only in theirs</Badge>}
                          </td>
                          <td className="p-2">{lp || <span className="text-muted-foreground">—</span>}</td>
                          <td className="p-2">
                            {rp ? (
                              <>
                                {rp}
                                {priceDiff !== null && (
                                  <Badge 
                                    variant={priceDiff < 0 ? "success" : priceDiff > 0 ? "destructive" : "outline"} 
                                    className="ml-1 text-xs"
                                  >
                                    {priceDiff > 0 ? `+${priceDiff}%` : `${priceDiff}%`}
                                  </Badge>
                                )}
                              </>
                            ) : <span className="text-muted-foreground">—</span>}
                          </td>
                          <td className="p-2">{lt?.start_date || rt?.start_date || <span className="text-muted-foreground">—</span>}</td>
                          <td className="p-2">{lt?.end_date || rt?.end_date || <span className="text-muted-foreground">—</span>}</td>
                          <td className="p-2">{lt?.availability_status || rt?.availability_status || <span className="text-muted-foreground">—</span>}</td>
                        </tr>
                      )
                    }) : (
                      <tr>
                        <td colSpan={6} className="p-2 text-center text-muted-foreground">No tenancy options</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )
        }).filter(Boolean)}
      </div>
    )
  }

  const handleCompare = async () => {
    if (!propUrl || !compUrl) {
      setError('Please provide both property and competitor URLs')
      return
    }

    setLoading(true)
    setError('')

    try {
      const data = await fetchJson(apiUrl('/api/competitors/compare'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          property_url: propUrl,
          competitor_url: compUrl,
        }),
      })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleExportCSV = async () => {
    if (!propUrl || !compUrl) {
      setError('Please provide both property and competitor URLs')
      return
    }

    try {
      const response = await fetch(apiUrl('/api/competitors/compare/export/csv'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          property_url: propUrl,
          competitor_url: compUrl,
        }),
      })

      // Get the filename from the response headers
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = 'competitor_comparison.csv'
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

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Compare Two Links</CardTitle>
          <CardDescription>Extract and view both JSON outputs side by side</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-1">
              <label className="text-xs text-muted-foreground">Property URL</label>
              <Input value={propUrl} onChange={(e) => setPropUrl(e.target.value)} placeholder="https://..." />
            </div>
            <div className="md:col-span-1">
              <label className="text-xs text-muted-foreground">Competitor URL</label>
              <Input value={compUrl} onChange={(e) => setCompUrl(e.target.value)} placeholder="https://..." />
            </div>
            <div className="md:col-span-1 flex items-end gap-2">
              <Button disabled={loading || !propUrl || !compUrl} onClick={handleCompare}>
                {loading ? 'Comparing...' : 'Compare'}
              </Button>
              <Button 
                variant="outline" 
                disabled={loading || !propUrl || !compUrl || !result} 
                onClick={handleExportCSV}
              >
                Export CSV
              </Button>
            </div>
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-6">
          {/* Readable, side-by-side comparison */}
          <Card>
            <CardHeader>
              <CardTitle>Readable Comparison</CardTitle>
              <CardDescription>Aligned, parallel sections for quick visual comparison</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {/* Data Quality Summary */}
                <div className="font-medium mb-2">Data Quality Summary</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                  <div className="p-3 border rounded">
                    <div className="mb-1">
                      <span>Property Source: {result.our?.merged_data?.basic_info?.source || result.our?.merged_data?.tenancy_data?.property_level?.source || result.our?.merged_data?.basic_info?.source_link || "Unknown"}</span>
                    </div>
                    <div className="text-muted-foreground">
                      {(() => {
                        const cfgs = getConfigs(result.our)
                        const tenCount = cfgs.reduce((acc, c) => acc + getTenancies(c).length, 0)
                        return `${cfgs.length} configurations, ${tenCount} tenancy options`
                      })()}
                    </div>
                  </div>
                  <div className="p-3 border rounded">
                    <div className="mb-1">
                      <span>Competitor Source: {result.competitor?.merged_data?.basic_info?.source || result.competitor?.merged_data?.tenancy_data?.property_level?.source || result.competitor?.merged_data?.basic_info?.source_link || "Unknown"}</span>
                    </div>
                    <div className="text-muted-foreground">
                      {(() => {
                        const cfgs = getConfigs(result.competitor)
                        const tenCount = cfgs.reduce((acc, c) => acc + getTenancies(c).length, 0)
                        return `${cfgs.length} configurations, ${tenCount} tenancy options`
                      })()}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center">
                    <div className="w-3 h-3 rounded-full bg-blue-100 border border-blue-300 mr-1"></div>
                    <span>Only in Property</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-3 h-3 rounded-full bg-green-100 border border-green-300 mr-1"></div>
                    <span>Only in Competitor</span>
                  </div>
                  <div className="flex items-center">
                    <Badge variant="destructive" className="text-xs">+10%</Badge>
                    <span className="ml-1">Price higher in competitor</span>
                  </div>
                  <div className="flex items-center">
                    <Badge variant="success" className="text-xs">-10%</Badge>
                    <span className="ml-1">Price lower in competitor</span>
                  </div>
                </div>
            </CardContent>
            <CardContent className="space-y-6">
              {/* Features */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Features</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border rounded p-3">
                    <div className="text-sm font-medium mb-2">Property</div>
                    <ul className="list-disc pl-5 space-y-1 text-sm">
                      {getFeatures(result.our).length ? getFeatures(result.our).map((f, idx) => (
                        <li key={`fL-${idx}`}>{f}</li>
                      )) : <li className="text-muted-foreground">No features found</li>}
                    </ul>
                  </div>
                  <div className="border rounded p-3">
                    <div className="text-sm font-medium mb-2">Competitor</div>
                    <ul className="list-disc pl-5 space-y-1 text-sm">
                      {getFeatures(result.competitor).length ? getFeatures(result.competitor).map((f, idx) => (
                        <li key={`fR-${idx}`}>{f}</li>
                      )) : <li className="text-muted-foreground">No features found</li>}
                    </ul>
                  </div>
                </div>
              </div>

              {/* Location */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Location</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {['Property', 'Competitor'].map((label, i) => {
                    const side = i === 0 ? result.our : result.competitor
                    const loc = getLocation(side)
                    const fields = ['location_name','address','city','region','country','latitude','longitude']
                    return (
                      <div className="border rounded p-3" key={`loc-${label}`}>
                        <div className="text-sm font-medium mb-2">{label}</div>
                        <table className="w-full text-sm">
                          <tbody>
                            {fields.map((k) => (
                              <tr key={k} className="border-b last:border-0">
                                <td className="py-1 pr-3 text-muted-foreground whitespace-nowrap">{k.replace(/_/g,' ')}</td>
                                <td className="py-1 break-all">{loc?.[k] || <span className="text-muted-foreground">—</span>}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* FAQs */}
              <div className="space-y-3">
                <div className="text-base font-semibold">FAQs</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => (
                    <div className="border rounded p-3" key={`faq-${label}`}>
                      <div className="text-sm font-medium mb-2">{label}</div>
                      <div className="space-y-3">
                        {getFaqs(side).length ? getFaqs(side).map((f, idx) => (
                          <div key={`faq-${label}-${idx}`} className="text-sm">
                            <div className="font-medium">Q: {f.question || <span className="text-muted-foreground">—</span>}</div>
                            <div className="text-muted-foreground">A: {f.answer || <span className="text-muted-foreground">—</span>}</div>
                          </div>
                        )) : <div className="text-sm text-muted-foreground">No FAQs found</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Node 2: About */}
              <div className="space-y-3">
                <div className="text-base font-semibold">About</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => (
                    <div className="border rounded p-3 text-sm" key={`about-${label}`}>
                      <div className="text-sm font-medium mb-2">{label}</div>
                      <div className="text-muted-foreground whitespace-pre-wrap break-words">{getDescField(side, 'about') || <span className="text-muted-foreground">—</span>}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Node 2: Commute & Distance */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Commute & Distance</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => (
                    <div className="border rounded p-3 text-sm" key={`commute-${label}`}>
                      <div className="text-sm font-medium mb-2">{label}</div>
                      <div className="space-y-2 text-muted-foreground">
                        <div><span className="font-medium">Commute: </span>{getDescField(side, 'commute') || <span className="text-muted-foreground">—</span>}</div>
                        <div><span className="font-medium">Distance: </span>{getDescField(side, 'distance') || <span className="text-muted-foreground">—</span>}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Node 2: Location & What's Hot */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Location & What's Hot</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => (
                    <div className="border rounded p-3 text-sm" key={`hot-${label}`}>
                      <div className="text-sm font-medium mb-2">{label}</div>
                      <div className="text-muted-foreground whitespace-pre-wrap break-words">{getDescField(side, 'location_and_whats_hot') || <span className="text-muted-foreground">—</span>}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Node 2: Payments */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Payments</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => {
                    const p = getPayments(side)
                    const rows = [
                      ['booking_deposit','Booking Deposit'],
                      ['security_deposit','Security Deposit'],
                      ['mode_of_payment','Mode of Payment'],
                      ['payment_installment_plan','Installments'],
                      ['additional_fees','Additional Fees'],
                      ['platform_fee','Platform Fee'],
                      ['fully_refundable_holding_fee','Holding Fee']
                    ]
                    return (
                      <div className="border rounded p-3" key={`pay-${label}`}>
                        <div className="text-sm font-medium mb-2">{label}</div>
                        <table className="w-full text-sm">
                          <tbody>
                            {rows.map(([k, label2]) => (
                              <tr key={k} className="border-b last:border-0">
                                <td className="py-1 pr-3 text-muted-foreground whitespace-nowrap">{label2}</td>
                                <td className="py-1 break-all">{p?.[k] || <span className="text-muted-foreground">—</span>}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Node 2: Cancellation Policy */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Cancellation Policy</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => {
                    const c = getCancellation(side)
                    const rows = [
                      ['cooling_off_period','Cooling Off Period'],
                      ['no_place_no_pay','No Place No Pay'],
                      ['no_visa_no_pay','No Visa No Pay'],
                      ['deferring_studies','Deferring Studies'],
                      ['delayed_arrivals_or_travel_restrictions','Delayed Arrivals/Restrictions'],
                      ['early_termination_by_student','Early Termination (Student)'],
                      ['extenuating_circumstances','Extenuating Circumstances'],
                      ['university_intake_delayed','University Intake Delayed'],
                      ['replacement_tenant_found','Replacement Tenant'],
                      ['no_questions_asked','No Questions Asked'],
                      ['other_policies','Other Policies'],
                      ['university_course_cancellation_or_modification','Course Cancel/Modify']
                    ]
                    return (
                      <div className="border rounded p-3" key={`cancel-${label}`}>
                        <div className="text-sm font-medium mb-2">{label}</div>
                        <table className="w-full text-sm">
                          <tbody>
                            {rows.map(([k, label2]) => (
                              <tr key={k} className="border-b last:border-0">
                                <td className="py-1 pr-3 text-muted-foreground whitespace-nowrap">{label2}</td>
                                <td className="py-1 break-all">{c?.[k] || <span className="text-muted-foreground">—</span>}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Node 2: Pet Policy & Contact */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Pet Policy & Contact</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => (
                    <div className="border rounded p-3" key={`pet-${label}`}>
                      <div className="text-sm font-medium mb-2">{label}</div>
                      <div className="space-y-2 text-sm">
                        <div><span className="font-medium">Pet Policy: </span>{getDescField(side, 'pet_policy') || <span className="text-muted-foreground">—</span>}</div>
                        <div><span className="font-medium">Email: </span>{getDescField(side, 'email') || <span className="text-muted-foreground">—</span>}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Node 2: Highlights */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Highlights</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => {
                    const hl = Array.isArray(getDescField(side, 'highlights')) ? getDescField(side, 'highlights') : []
                    return (
                      <div className="border rounded p-3" key={`high-${label}`}>
                        <div className="text-sm font-medium mb-2">{label}</div>
                        {hl.length ? (
                          <ul className="list-disc pl-5 space-y-1 text-sm">
                            {hl.map((h, i) => <li key={`h-${label}-${i}`}>{h}</li>)}
                          </ul>
                        ) : <div className="text-sm text-muted-foreground">No highlights found</div>}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Node 2: Commute POIs */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Commute POIs</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[{label:'Property', side: result.our}, {label:'Competitor', side: result.competitor}].map(({label, side}) => {
                    const pois = Array.isArray(getDescField(side, 'commute_pois')) ? getDescField(side, 'commute_pois') : []
                    return (
                      <div className="border rounded p-3" key={`poi-${label}`}>
                        <div className="text-sm font-medium mb-2">{label}</div>
                        {pois.length ? (
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-muted">
                                <th className="text-left p-2">POI</th>
                                <th className="text-left p-2">Distance</th>
                                <th className="text-left p-2">Time</th>
                                <th className="text-left p-2">Transport</th>
                              </tr>
                            </thead>
                            <tbody>
                              {pois.map((p, i) => (
                                <tr key={`p-${label}-${i}`} className="border-b last:border-0">
                                  <td className="p-2">{p?.poi_name || <span className="text-muted-foreground">—</span>}</td>
                                  <td className="p-2">{p?.distance || <span className="text-muted-foreground">—</span>}</td>
                                  <td className="p-2">{p?.time || <span className="text-muted-foreground">—</span>}</td>
                                  <td className="p-2">{p?.transport || <span className="text-muted-foreground">—</span>}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : <div className="text-sm text-muted-foreground">No POIs found</div>}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Configurations summary */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Configurations</div>
                <div className="overflow-auto">
                  {renderConfigTable()}
                </div>
              </div>

              {/* Tenancy comparison per configuration */}
              <div className="space-y-3">
                <div className="text-base font-semibold">Tenancies (per configuration)</div>
                {renderTenancySections()}
              </div>
            </CardContent>
          </Card>

          {/* Raw JSON side-by-side (kept as reference) */}
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
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.our?.merged_data)}</pre>
                </TabsContent>
                <TabsContent value="node1">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.our?.node_results?.node1_basic_info)}</pre>
                </TabsContent>
                <TabsContent value="node2">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.our?.node_results?.node2_description)}</pre>
                </TabsContent>
                <TabsContent value="node3">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.our?.node_results?.node3_configuration)}</pre>
                </TabsContent>
                <TabsContent value="node4">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.our?.node_results?.node4_tenancy)}</pre>
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
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.competitor?.merged_data)}</pre>
                </TabsContent>
                <TabsContent value="node1">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.competitor?.node_results?.node1_basic_info)}</pre>
                </TabsContent>
                <TabsContent value="node2">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.competitor?.node_results?.node2_description)}</pre>
                </TabsContent>
                <TabsContent value="node3">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.competitor?.node_results?.node3_configuration)}</pre>
                </TabsContent>
                <TabsContent value="node4">
                  <pre className="p-3 overflow-auto max-h-[480px] text-xs">{formatJson(result.competitor?.node_results?.node4_tenancy)}</pre>
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}