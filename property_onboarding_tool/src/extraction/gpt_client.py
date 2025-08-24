import openai
import json
import time
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from src.utils.config import get_config
from src.utils.logging_config import get_logger
from src.extraction.scraper import crawl_site, build_context

@dataclass
class ExtractionResult:
    """Result of an extraction operation"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    confidence_score: Optional[float]
    execution_time: float
    raw_response: Optional[str]
    error_category: Optional[str] = None

class GPTExtractionClient:
    """Client for GPT-4o based property data extraction with browsing capabilities"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(
            api_key=self.config.api.openai_api_key,
            base_url=self.config.api.openai_api_base
        )
        
        # Extraction node prompts (from requirements)
        self.node_prompts = {
            'node1_basic_info': self._get_node1_prompt(),
            'node2_description': self._get_node2_prompt(),
            'node3_configuration': self._get_node3_prompt(),
            'node4_tenancy': self._get_node4_prompt()
        }
    
    def extract_property_data(self, url: str, node_name: str, job_id: int) -> ExtractionResult:
        """Extract property data using GPT-4o with browsing for a specific node"""
        start_time = time.time()
        
        try:
            self.logger.log_node_start(job_id, node_name)
            
            # Get the appropriate prompt for this node
            if node_name not in self.node_prompts:
                raise ValueError(f"Unknown node name: {node_name}")
            
            prompt = self.node_prompts[node_name]
            
            # Build crawl context (same-domain, shallow)
            try:
                # Enhanced Node-specific crawl patterns for maximum coverage
                if node_name == "node3_configuration":
                    allow_patterns = [
                        # Core room/accommodation types
                        r"room|rooms|studio|ensuite|en-suite|apartment|flat|accommodation|unit|suite|residence",
                        r"bedroom|bathroom|kitchen|living|dining|study|workspace|common\s*area",
                        
                        # Pricing and financial information
                        r"price|pricing|cost|fee|rent|deposit|rate|tariff|amount|charge|payment",
                        r"weekly|monthly|per\s*week|per\s*month|pw|pm|total|from|starting\s*at",
                        r"discount|offer|deal|promotion|early\s*bird|limited\s*time|special\s*rate",
                        
                        # Physical specifications
                        r"detail|specification|floor|area|size|dimension|sqm|sqft|square\s*meter|square\s*foot",
                        r"bedroom\s*count|bathroom\s*count|occupancy|single|double|twin|triple|quad",
                        r"floor\s*plan|layout|diagram|map|view|gallery|photo|image|virtual\s*tour",
                        
                        # Features and amenities
                        r"feature|amenity|facility|furniture|equipped|included|provided|available",
                        r"wifi|internet|utilities|bills|heating|cooling|air\s*conditioning",
                        r"furnished|unfurnished|partially\s*furnished|fully\s*furnished",
                        
                        # Availability and booking
                        r"availability|available|book|apply|reserve|check|enquire|contact",
                        r"move\s*in|start\s*date|semester|academic\s*year|term|session",
                        r"waitlist|sold\s*out|limited|exclusive|premium|standard|basic",
                        
                        # Room configuration variations
                        r"configuration|option|type|variant|style|category|tier|level",
                        r"premium|deluxe|standard|basic|economy|budget|luxury|executive",
                        r"city\s*view|garden\s*view|street\s*view|quiet|noisy|corner|end\s*unit",
                        
                        # Building and location details
                        r"building|block|tower|wing|section|floor|level|elevator|lift",
                        r"nearby|distance|walking|transport|bus|train|metro|underground",
                        r"university|campus|college|school|institution|academic"
                    ]
                elif node_name == "node4_tenancy":
                    allow_patterns = [
                        # Core tenancy and contract terms
                        r"tenancy|contract|lease|term|duration|agreement|booking|reservation",
                        r"rental|renting|letting|accommodation|housing|lodging|residence",
                        
                        # Contract duration and timing
                        r"week|weeks|month|months|year|years|semester|term|academic\s*year",
                        r"start|end|date|move|arrival|departure|check\s*in|check\s*out",
                        r"flexible|fixed|rolling|monthly|weekly|short\s*term|long\s*term",
                        
                        # Pricing and payment details
                        r"price|pricing|cost|fee|rent|deposit|rate|tariff|amount|charge",
                        r"weekly|monthly|per\s*week|per\s*month|pw|pm|total|from|starting\s*at",
                        r"payment|installment|instalment|schedule|plan|method|frequency",
                        r"advance|upfront|first\s*month|last\s*month|security\s*deposit|holding\s*fee",
                        
                        # Availability and booking process
                        r"availability|available|book|apply|reserve|check|enquire|contact",
                        r"waitlist|sold\s*out|limited|exclusive|premium|standard|basic",
                        r"booking\s*form|application|enquiry|reservation|confirmation",
                        
                        # Tenancy requirements and conditions
                        r"guarantor|guarantee|reference|requirement|condition|criteria|eligibility",
                        r"student|academic|university|college|institution|enrollment|registration",
                        r"visa|passport|id|document|proof|verification|background\s*check",
                        
                        # Cancellation and modification policies
                        r"cancellation|refund|modification|change|transfer|swap|exchange",
                        r"policy|terms|conditions|rules|regulations|agreement|contract",
                        r"cooling\s*off|grace\s*period|notice|termination|early\s*exit|break\s*clause",
                        
                        # Special offers and incentives
                        r"offer|deal|promotion|discount|incentive|bonus|free|included",
                        r"no\s*fee|waived|reduced|special|limited\s*time|early\s*bird|referral",
                        r"package|bundle|combo|deal|savings|value|premium|exclusive",
                        
                        # Room-specific tenancy options
                        r"room\s*option|accommodation\s*type|tenancy\s*variant|contract\s*option",
                        r"studio\s*tenancy|ensuite\s*tenancy|apartment\s*tenancy|shared\s*tenancy",
                        r"individual|shared|dual|twin|triple|quad|group|collective"
                    ]
                elif node_name == "node2_description":
                    allow_patterns = [
                        r"about|overview|description|summary|property|why|highlights",
                        r"amenity|feature|facility|service|benefit",
                        r"contact|map|location|address|direction|transport|commute|distance|nearby|what's hot|whats hot",
                        r"faq|question|answer|info|information",
                        r"payment|payments|pay|deposit|security\s+deposit|booking\s+deposit|holding\s+fee|installment|instalment|mode\s+of\s+payment|platform\s+fee|additional\s+fees",
                        r"policy|policies|house\s+rules|rules|terms|conditions|cancellation|no\s+visa\s+no\s+pay|no\s+place\s+no\s+pay|refund|deferring|delayed\s+arrivals|extenuating|replacement\s+tenant|intake\s+delayed|pet\s+policy|pets"
                    ]
                else:  # node1_basic_info
                    allow_patterns = [
                        r"about|overview|description|summary|property",
                        r"amenity|feature|facility|service|benefit",
                        r"contact|map|location|address|direction|transport",
                        r"faq|question|answer|info|information"
                    ]
                
                # Enhanced crawling parameters for Node 3 and 4
                if node_name in ["node3_configuration", "node4_tenancy"]:
                    # Deeper crawling for configuration and tenancy data
                    follow_depth = 3  # Increased from 1 for better coverage
                    max_links_per_page = 20  # Increased from 8 for comprehensive coverage
                    max_total_pages = 50  # Increased from 20 for maximum data extraction
                    context_cap = 150000  # Increased context for detailed extraction
                else:
                    # Standard parameters for other nodes
                    follow_depth = 2 if node_name in ['node1_basic_info','node2_description'] else 1
                    max_links_per_page = 14 if node_name in ['node1_basic_info','node2_description'] else 8
                    max_total_pages = 36 if node_name in ['node1_basic_info','node2_description'] else 20
                    context_cap = 120000
                
                # Allow limited external domains for policy/faq/support pages
                external_allow = [
                    'wearehomesforstudents.com',
                    'kxweb.wearehomesforstudents.com',
                    'essentialstudentliving.com',
                ] if node_name in ['node1_basic_info','node2_description'] else None

                pages = crawl_site(
                    url,
                    follow_depth=follow_depth,
                    max_links_per_page=max_links_per_page,
                    max_total_pages=max_total_pages,
                    request_timeout=30,  # Increased from 12 to 30 seconds
                    crawl_delay_ms=500,  # Increased from 350 to 500ms
                    allow_patterns=allow_patterns,
                    allow_external_domains=external_allow,
                )
                
                # Build context with intelligent prioritization
                context_text = build_context(pages, max_chars=context_cap)
                
                # Extract and highlight key information for better GPT focus
                highlighted_context = self._highlight_key_information(context_text, node_name)
                # Derive hints from context for Node 1 (coordinates, metadata)
                node1_hints = {}
                if node_name == 'node1_basic_info':
                    try:
                        node1_hints = self._derive_node1_hints_from_pages(pages)
                    except Exception:
                        node1_hints = {}
            except Exception:
                context_text = ""

            # Create the extraction request with strict JSON and enhanced context
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional property data extraction assistant with expertise in student accommodation listings. Your task is to extract structured JSON data with maximum accuracy and completeness. Follow the schema exactly and prioritize factual information from the provided context."
                },
                {
                    "role": "user",
                    "content": f"""Primary URL: {url}

{prompt}

IMPORTANT EXTRACTION INSTRUCTIONS:
1. Extract ALL relevant details from the provided context, especially from HIGHLIGHTED sections.
2. For room configurations, extract EVERY DISTINCT configuration with its unique attributes.
3. For tenancy options, extract ALL available contract lengths and their specific pricing.
4. Do not hallucinate; if a field is not present, use empty string, 0, false, or empty array as appropriate.
5. Return only valid JSON matching the specified schema.
6. Keep string fields concise but complete - include all meaningful information.
7. If information appears contradictory, prioritize the most specific/detailed source.
8. For room configurations, extract ALL configurations (up to 20) with complete details.

CONTEXT FROM CRAWLED PAGES (same domain, prioritized by relevance):
{highlighted_context}

ADDITIONAL HINTS (if present):
{json.dumps(node1_hints) if node_name == 'node1_basic_info' else ''}
"""
                }
            ]
            
            def _call_and_parse(msgs):
                api_start = time.time()
                resp = self.client.chat.completions.create(
                model=self.config.api.openai_model,
                    messages=msgs,
                max_tokens=self.config.api.max_tokens,
                temperature=self.config.api.temperature,
                    response_format={"type": "json_object"}
                )
                dur = time.time() - api_start
                self.logger.log_api_call(job_id, node_name, "OpenAI GPT-4o", dur, True)
                raw = resp.choices[0].message.content
                data = self._parse_json_response(raw)
                return raw, data

            # Primary attempt
            try:
                raw_response, extracted_data = _call_and_parse(messages)
            except Exception as primary_err:
                # Retry with reduced context and stricter guidance, especially for node3
                if node_name == 'node3_configuration' and context_text:
                    reduced_context = context_text[:30000]
                    retry_messages = [
                        {"role": "system", "content": "You are a strict JSON extraction assistant. Return only compact JSON."},
                        {"role": "user", "content": f"""Primary URL: {url}

{prompt}

Instructions:
- Strictly output compact JSON.
- Limit configurations to 12 items.
- Keep strings short.

Context (reduced):
{reduced_context}
"""}
                    ]
                    raw_response, extracted_data = _call_and_parse(retry_messages)
                else:
                    raise primary_err
            
            # Post-process Node 2: enrich FAQs and Policies from context markers if sparse
            if node_name == 'node2_description':
                try:
                    extracted_data = self._postprocess_node2_enrich(extracted_data, highlighted_context)
                    # If still sparse, perform a selective second-pass crawl focused on FAQs/Policies/Payments/Commute
                    if self._is_node2_sparse(extracted_data):
                        try:
                            selective_patterns = [
                                r"faq|question|answer|help|support|information|info|guide",
                                r"policy|policies|terms|conditions|cancellation|refund",
                                r"payment|payments|deposit|fee|installment|instalment|mode|platform|holding",
                                r"commute|distance|transport|nearby|what's\s*hot|whats\s*hot|location",
                                r"pet|pets|contact|email|phone|call",
                            ]
                            external_allow = [
                                'wearehomesforstudents.com',
                                'kxweb.wearehomesforstudents.com',
                                'essentialstudentliving.com',
                            ]
                            pages2 = crawl_site(
                                url,
                                follow_depth=2,
                                max_links_per_page=14,
                                max_total_pages=36,
                                request_timeout=30,  # Increased from 12 to 30 seconds
                                crawl_delay_ms=500,  # Increased from 350 to 500ms
                                allow_patterns=selective_patterns,
                                allow_external_domains=external_allow,
                            )
                            context2 = build_context(pages2, max_chars=60000)
                            highlighted_context2 = self._highlight_key_information(context2, node_name)
                            # Re-run deterministic enrichment with extra context appended
                            combined_ctx = (highlighted_context or '') + "\n\n" + (highlighted_context2 or '')
                            extracted_data = self._postprocess_node2_enrich(extracted_data, combined_ctx)
                        except Exception:
                            pass
                except Exception:
                    pass
            
            # Post-process Node 3 and Node 4
            if node_name == 'node3_configuration':
                try:
                    extracted_data = self._postprocess_node3_add_config_id(extracted_data)
                except Exception:
                    pass
            if node_name == 'node4_tenancy':
                try:
                    extracted_data = self._postprocess_node4_normalize_tenancies(extracted_data)
                except Exception:
                    pass

            # Calculate confidence score based on data completeness
            confidence_score = self._calculate_confidence_score(extracted_data, node_name)
            
            execution_time = time.time() - start_time
            
            self.logger.log_node_complete(job_id, node_name, execution_time, confidence_score)
            
            return ExtractionResult(
                success=True,
                data=extracted_data,
                error=None,
                confidence_score=confidence_score,
                execution_time=execution_time,
                raw_response=raw_response
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # Categorize errors for better handling
            if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                error_category = 'timeout'
            elif 'connection' in error_msg.lower() or 'network' in error_msg.lower():
                error_category = 'connection'
            elif 'rate limit' in error_msg.lower() or 'too many requests' in error_msg.lower():
                error_category = 'rate_limit'
            else:
                error_category = 'unknown'
            
            self.logger.log_node_failed(job_id, node_name, error_msg, duration=execution_time)
            
            return ExtractionResult(
                success=False,
                data=None,
                error=error_msg,
                confidence_score=0.0,
                execution_time=execution_time,
                raw_response=None,
                error_category=error_category
            )
    
    async def extract_basic_info(self, url: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract basic property information and location data"""
        result = self.extract_property_data(url, 'node1_basic_info', 0)  # job_id 0 for context calls
        if result.success:
            return result.data
        else:
            raise Exception(f"Failed to extract basic info: {result.error}")
    
    async def extract_description(self, url: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract property description and features"""
        result = self.extract_property_data(url, 'node2_description', 0)  # job_id 0 for context calls
        if result.success:
            return result.data
        else:
            raise Exception(f"Failed to extract description: {result.error}")
    
    async def extract_room_configurations(self, url: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract room configurations and pricing"""
        result = self.extract_property_data(url, 'node3_configuration', 0)  # job_id 0 for context calls
        if result.success:
            return result.data
        else:
            raise Exception(f"Failed to extract room configurations: {result.error}")
    
    async def extract_tenancy_information(self, url: str, context_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract tenancy information and policies"""
        result = self.extract_property_data(url, 'node4_tenancy', 0)  # job_id 0 for context calls
        if result.success:
            return result.data
        else:
            raise Exception(f"Failed to extract tenancy information: {result.error}")
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from GPT-4o"""
        try:
            # Try to find JSON in the response
            response = response.strip()
            
            # Look for JSON block markers
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end].strip()
            
            # Try to parse as JSON
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            # If direct parsing fails, try to extract JSON from text
            import re
            json_pattern = r'\{.*\}'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
            
            raise ValueError(f"Could not parse JSON from response: {str(e)}")
    
    def _calculate_confidence_score(self, data: Dict[str, Any], node_name: str) -> float:
        """Calculate confidence score based on data completeness and quality"""
        if not data:
            return 0.0
        
        # Define expected fields for each node with importance weights
        expected_fields = {
            'node1_basic_info': [
                ('basic_info.name', 1.0), 
                ('basic_info.guarantor_required', 0.8),
                ('basic_info.property_type', 0.6),
                ('basic_info.contact.phone', 0.5),
                ('location.location_name', 1.0), 
                ('location.latitude', 0.9),
                ('location.longitude', 0.9),
                ('location.address', 0.7),
                ('location.city', 0.8),
                ('location.region', 0.8),
                ('location.country', 0.7),
                ('location.postcode', 0.6),
                ('features', 0.7), 
                ('property_rules', 0.5), 
                ('safety_and_security', 0.5)
            ],
            'node2_description': [
                ('description.about', 1.0), ('description.features', 0.8), 
                ('description.commute', 0.6), ('description.faqs', 0.7)
            ],
            'node3_configuration': [
                ('configurations', 1.0)
            ],
            'node4_tenancy': [
                ('property_level', 0.3), ('configurations', 1.0)
            ]
        }
        
        if node_name not in expected_fields:
            return 0.5  # Default score for unknown nodes
        
        # Check presence of fields with nested path support
        weighted_score = 0.0
        total_weight = 0.0
        
        for field_path, weight in expected_fields[node_name]:
            total_weight += weight
            
            # Handle nested paths like 'basic_info.name'
            parts = field_path.split('.')
            current = data
            found = True
            
            for part in parts:
                if isinstance(current, dict) and part in current and current[part]:
                    current = current[part]
                else:
                    found = False
                    break
                    
            # Special handling for arrays - check if non-empty
            if found and isinstance(current, list):
                found = len(current) > 0
                
            if found:
                weighted_score += weight
        
        base_score = weighted_score / total_weight if total_weight > 0 else 0
        
        # Node-specific quality checks
        quality_bonus = 0.0
        
        if node_name == 'node1_basic_info':
            # Bonus for location data completeness (up to 15%)
            location_fields = ['latitude', 'longitude', 'address', 'city', 'region', 'country', 'postcode']
            location_completeness = 0.0
            for field in location_fields:
                if data.get('location', {}).get(field):
                    location_completeness += 1.0
            location_completeness = location_completeness / len(location_fields)
            location_bonus = location_completeness * 0.15
            
            # Bonus for guarantor information (up to 5%)
            guarantor_bonus = 0.0
            if data.get('basic_info', {}).get('guarantor_required') and data['basic_info']['guarantor_required'] != "Information unavailable":
                guarantor_bonus = 0.05
            
            # Bonus for property type information (up to 3%)
            property_type_bonus = 0.0
            if data.get('basic_info', {}).get('property_type'):
                property_type_bonus = 0.03
            
            # Bonus for contact information (up to 2%)
            contact_bonus = 0.0
            if data.get('basic_info', {}).get('contact', {}).get('phone'):
                contact_bonus = 0.02
            
            # Bonus for features richness (up to 5%)
            features_bonus = 0.0
            if data.get('features') and isinstance(data['features'], list):
                features_bonus = min(0.05, len(data['features']) * 0.01)
            
            quality_bonus = location_bonus + guarantor_bonus + property_type_bonus + contact_bonus + features_bonus
            
        elif node_name == 'node3_configuration' and 'configurations' in data:
            configs = data['configurations']
            if isinstance(configs, list) and configs:
                # Bonus for number of configurations (up to 10% for 5+ configs)
                config_count_bonus = min(0.1, len(configs) * 0.02)
                
                # Bonus for configuration detail richness
                detail_richness = 0.0
                for cfg in configs:
                    if not isinstance(cfg, dict):
                        continue
                        
                    # Check for important configuration details
                    detail_score = 0.0
                    if cfg.get('Basic', {}).get('Name'):
                        detail_score += 0.2
                    if cfg.get('Pricing', {}).get('Price'):
                        detail_score += 0.2
                    if cfg.get('Area', {}).get('Area'):
                        detail_score += 0.1
                    if cfg.get('Configuration', {}).get('Types'):
                        detail_score += 0.1
                    if cfg.get('Features') and isinstance(cfg.get('Features'), list):
                        detail_score += 0.1 * min(1.0, len(cfg.get('Features')) / 3)
                        
                    detail_richness += detail_score / len(configs)
                    
                quality_bonus = config_count_bonus + (detail_richness * 0.1)  # Up to 20% bonus
                
        elif node_name == 'node4_tenancy' and 'configurations' in data:
            configs = data['configurations']
            if isinstance(configs, list) and configs:
                # Bonus for tenancy options richness
                tenancy_richness = 0.0
                for cfg in configs:
                    if not isinstance(cfg, dict):
                        continue
                        
                    tenancy_options = cfg.get('tenancy_options', [])
                    if isinstance(tenancy_options, list) and tenancy_options:
                        # Bonus for number of tenancy options per config
                        option_count = min(1.0, len(tenancy_options) / 3)  # Max bonus at 3+ options
                        
                        # Bonus for tenancy option details
                        detail_score = 0.0
                        for opt in tenancy_options:
                            if not isinstance(opt, dict):
                                continue
                                
                            if opt.get('tenancy_length') and opt.get('price'):
                                detail_score += 0.5
                            if opt.get('start_date') and opt.get('end_date'):
                                detail_score += 0.3
                            if opt.get('availability_status'):
                                detail_score += 0.2
                                
                        detail_score = detail_score / (len(tenancy_options) or 1)
                        tenancy_richness += (option_count * 0.5) + (detail_score * 0.5)
                        
                quality_bonus = min(0.2, tenancy_richness / len(configs))  # Up to 20% bonus
        
        # General data richness bonus
        total_values = self._count_non_empty_values(data)
        richness_bonus = min(0.1, total_values * 0.005)  # Up to 10% bonus, reduced coefficient
        
        final_score = base_score + quality_bonus + richness_bonus
        return min(1.0, final_score)  # Clamp between 0 and 1

    # -----------------------------
    # Node 3 + Node 4 Postprocessing
    # -----------------------------
    def _generate_configuration_id(self, config: Dict[str, Any]) -> str:
        """Generate a stable slug ID for a configuration using name and key attributes.
        Falls back gracefully when fields are missing.
        """
        import re as _re

        def _norm(s: str) -> str:
            s = (s or '').lower().strip()
            s = _re.sub(r"[^a-z0-9\s\-_/]", "", s)
            s = s.replace("/", "-")
            s = _re.sub(r"\s+", "-", s)
            s = _re.sub(r"-+", "-", s)
            return s.strip('-')

        # Try multiple possible name fields
        name = None
        for path in [
            ['Basic', 'Name'],
            ['Description', 'Name'],
            ['name'],
            ['room_type']
        ]:
            cur = config
            ok = True
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and isinstance(cur, (str, int, float)):
                name = str(cur)
                break

        name_part = _norm(name or "config")

        # Area range
        min_area = None
        max_area = None
        for path in [['Area', 'Min Area'], ['Area', 'Area']]:
            cur = config
            ok = True
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and cur:
                try:
                    # extract first number
                    import re as _re2
                    m = _re2.search(r"(\d+\.?\d*)", str(cur))
                    if m:
                        if min_area is None:
                            min_area = m.group(1)
                except Exception:
                    pass
        for path in [['Area', 'Max Area']]:
            cur = config
            ok = True
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and cur:
                try:
                    import re as _re3
                    m = _re3.search(r"(\d+\.?\d*)", str(cur))
                    if m:
                        max_area = m.group(1)
                except Exception:
                    pass

        area_part = None
        if min_area and max_area and min_area != max_area:
            area_part = f"{min_area}-{max_area}sqm"
        elif min_area:
            area_part = f"{min_area}sqm"

        # Unit type / types
        unit_type = None
        for path in [['Configuration', 'Unit Type'], ['Configuration', 'Types']]:
            cur = config
            ok = True
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and cur:
                if isinstance(cur, list):
                    unit_type = ",".join([str(x) for x in cur if x])
                else:
                    unit_type = str(cur)
                break
        unit_part = _norm(unit_type or "")

        # Dual occupancy / occupancy hints
        dual_occ = None
        cur = config.get('Configuration', {}) if isinstance(config, dict) else {}
        if isinstance(cur, dict) and 'Dual Occupancy' in cur and cur['Dual Occupancy']:
            val = str(cur['Dual Occupancy']).lower()
            if val in {'yes', 'true'}:
                dual_occ = 'dual'
        occ_part = dual_occ or ''

        parts = [p for p in [name_part, unit_part, area_part, occ_part] if p]
        slug = "-".join(parts) if parts else name_part or "config"
        return slug[:120]

    def _postprocess_node3_add_config_id(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return data
        configs = data.get('configurations')
        if isinstance(configs, list):
            for cfg in configs:
                if isinstance(cfg, dict) and 'configuration_id' not in cfg:
                    try:
                        cfg['configuration_id'] = self._generate_configuration_id(cfg)
                    except Exception:
                        pass
        return data

    def _normalize_tenancy_length_to_weeks(self, value: str) -> Optional[int]:
        if not value:
            return None
        import re as _re
        s = str(value).lower().strip()
        # direct weeks like "44 weeks", "51 w"
        m = _re.search(r"(\d+(?:\.\d+)?)\s*(w|week|weeks)\b", s)
        if m:
            try:
                return int(round(float(m.group(1))))
            except Exception:
                return None
        # months → weeks (~4.33 weeks per month)
        m = _re.search(r"(\d+(?:\.\d+)?)\s*(m|mo|month|months)\b", s)
        if m:
            try:
                months = float(m.group(1))
                return int(round(months * 4.33))
            except Exception:
                return None
        # semester/term common values
        if 'semester' in s or 'term' in s:
            # if number present like "1 semester" assume ~20 weeks; otherwise 20
            m = _re.search(r"(\d+)", s)
            n = int(m.group(1)) if m else 1
            return 20 * n
        if 'year' in s or 'yr' in s:
            m = _re.search(r"(\d+)", s)
            n = int(m.group(1)) if m else 1
            return int(round(n * 52))
        return None

    def _parse_currency_amount(self, price_str: str) -> Dict[str, Any]:
        """Parse a price string into currency and numeric amount (best-effort)."""
        result = {'currency': '', 'amount': None}
        if not price_str:
            return result
        import re as _re
        s = str(price_str).strip()
        # currency symbol or code
        mcur = _re.search(r"([£$€]|AUD|NZD|USD|GBP|EUR)", s, _re.IGNORECASE)
        if mcur:
            result['currency'] = mcur.group(1).upper() if len(mcur.group(1)) > 1 else mcur.group(1)
        # amount (first number with optional decimals and commas)
        mamt = _re.search(r"(\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+\.\d+|\d+)", s)
        if mamt:
            try:
                result['amount'] = float(mamt.group(1).replace(',', '').replace(' ', ''))
            except Exception:
                pass
        return result

    def _infer_price_type(self, price_str: str) -> str:
        s = (price_str or '').lower()
        if 'per week' in s or '/week' in s or 'pw' in s or 'weekly' in s:
            return 'per_week'
        if 'per month' in s or '/month' in s or 'pm' in s or 'monthly' in s:
            return 'per_month'
        if 'total' in s or 'for' in s:
            return 'total'
        return ''

    def _postprocess_node4_normalize_tenancies(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return data

        def _process_config(cfg: Dict[str, Any]) -> None:
            # Attach configuration_id if missing
            if 'configuration_id' not in cfg:
                try:
                    cfg['configuration_id'] = self._generate_configuration_id(cfg)
                except Exception:
                    pass

            options = cfg.get('tenancy_options') if isinstance(cfg, dict) else None
            if not isinstance(options, list):
                return
            for opt in options:
                if not isinstance(opt, dict):
                    continue
                # retain original
                length_raw = opt.get('tenancy_length') or opt.get('duration') or ''
                weeks = self._normalize_tenancy_length_to_weeks(length_raw)
                if weeks is not None:
                    opt['tenancy_length_weeks'] = weeks

                price_raw = opt.get('price') or opt.get('price_per_week') or opt.get('total_price') or ''
                parsed = self._parse_currency_amount(price_raw)
                price_type = (opt.get('price_type') or self._infer_price_type(price_raw)).lower()
                currency = parsed.get('currency') or ''
                amount = parsed.get('amount')

                # Compute both price_per_week and price_total when possible
                if amount is not None:
                    if price_type == 'per_week':
                        opt['price_per_week'] = amount
                        if weeks:
                            opt['price_total'] = round(amount * weeks, 2)
                    elif price_type == 'per_month':
                        # per-month → per-week ~ month/4.33
                        pw = amount / 4.33
                        opt['price_per_week'] = round(pw, 2)
                        if weeks:
                            opt['price_total'] = round(pw * weeks, 2)
                    elif price_type == 'total':
                        opt['price_total'] = amount
                        if weeks and weeks > 0:
                            opt['price_per_week'] = round(amount / weeks, 2)
                    else:
                        # Unknown type: if weeks present and looks like weekly phrasing, assume pw
                        if 'pw' in (price_raw or '').lower():
                            opt['price_per_week'] = amount
                            if weeks:
                                opt['price_total'] = round(amount * weeks, 2)
                        else:
                            # leave as-is but try not to lose info
                            opt.setdefault('price_per_week', amount)
                if currency:
                    opt['currency'] = currency

        # Process configurations array if present
        if isinstance(data.get('configurations'), list):
            for cfg in data['configurations']:
                if isinstance(cfg, dict):
                    _process_config(cfg)

        # Some responses may store tenancies at top-level 'tenancies'
        if isinstance(data.get('tenancies'), list):
            for t in data['tenancies']:
                if isinstance(t, dict):
                    # wrap into a pseudo-config for normalization
                    _process_config({'tenancy_options': [t]})

        return data
    def _postprocess_node2_enrich(self, data: Dict[str, Any], context_text: str) -> Dict[str, Any]:
        """Enrich Node 2 description with FAQs and normalized policy fields from context markers.
        This is a deterministic fallback when the model fails to extract from widgets/lists.
        """
        if not isinstance(data, dict):
            return data
        desc = data.get('description')
        if not isinstance(desc, dict):
            desc = {}
            data['description'] = desc

        # Ensure structures exist
        faqs: List[Dict[str, str]] = desc.get('faqs') if isinstance(desc.get('faqs'), list) else []
        cancellation: Dict[str, str] = desc.get('cancellation_policy') if isinstance(desc.get('cancellation_policy'), dict) else {}
        if 'faqs' not in desc:
            desc['faqs'] = faqs
        if 'cancellation_policy' not in desc:
            desc['cancellation_policy'] = cancellation

        # Helper: extract blocks between markers
        def _extract_blocks(marker: str, end_marker: str) -> List[str]:
            import re as _re
            blocks: List[str] = []
            try:
                pattern = _re.compile(_re.escape(marker) + r"[\s\S]*?" + _re.escape(end_marker))
                for m in pattern.finditer(context_text or ""):
                    block = m.group(0)
                    # strip wrapper lines
                    try:
                        start_idx = block.find('\n')
                        end_idx = block.rfind('\n')
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            blocks.append(block[start_idx+1:end_idx].strip())
                        else:
                            blocks.append(block)
                    except Exception:
                        blocks.append(block)
            except Exception:
                pass
            return blocks

        # Extract FAQs from widget sections when missing/sparse
        try:
            if len(faqs) < 2:
                widget_faq_blocks = []
                # Match [WIDGET_SECTION type="faq" ...] ... [END WIDGET_SECTION]
                import re as _re
                faq_open_pattern = _re.compile(r"\[WIDGET_SECTION[^\]]*type=\"faq\"[^\]]*\]\s*", _re.IGNORECASE)
                end_tag = "[END WIDGET_SECTION]"
                text = context_text or ""
                for m in faq_open_pattern.finditer(text):
                    start = m.end()
                    end = text.find(end_tag, start)
                    if end != -1:
                        widget_faq_blocks.append(text[start:end].strip())

                parsed_qas: List[Dict[str, str]] = []
                for block in widget_faq_blocks:
                    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
                    current_q: Optional[str] = None
                    current_a: Optional[str] = None
                    for ln in lines:
                        if ln.lower().startswith('q:'):
                            # flush previous pair
                            if current_q and current_a:
                                parsed_qas.append({"question": current_q, "answer": current_a})
                            current_q = ln[2:].strip(" :\t")
                            current_a = None
                        elif ln.lower().startswith('a:'):
                            current_a = ln[2:].strip(" :\t")
                        elif ln.endswith('?') and not current_q:
                            current_q = ln.strip()
                        elif current_q and not current_a:
                            # accumulate answer lines until next Q or end
                            current_a = (current_a + " " if current_a else "") + ln
                    if current_q and current_a:
                        parsed_qas.append({"question": current_q, "answer": current_a})

                # Also parse [DEFINITION LIST] entries with question-like terms
                def_blocks = _extract_blocks('[DEFINITION LIST]', '[END DEFINITION LIST]')
                for block in def_blocks:
                    for ln in block.splitlines():
                        if ':' in ln:
                            k, v = ln.split(':', 1)
                            if k.strip().endswith('?') and v.strip():
                                parsed_qas.append({"question": k.strip(), "answer": v.strip()})

                # Deduplicate and merge into desc.faqs
                seen = set()
                for qa in parsed_qas:
                    q = qa.get('question', '')
                    a = qa.get('answer', '')
                    if not (q or a):
                        continue
                    key = (q.lower(), a.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    faqs.append({"question": q, "answer": a})
        except Exception:
            pass

        # Normalize / fill cancellation_policy from policy widgets and headings
        try:
            # Aggregate policy-like text
            policy_texts: List[str] = []
            policy_texts.extend(_extract_blocks('[FOOTER CONTENT]', '[END FOOTER CONTENT]'))
            policy_texts.extend(_extract_blocks('[HEADING_SECTION title="', '[END HEADING_SECTION]'))  # may include many sections
            # Include only sections whose title suggests policy terms
            filtered_policy_texts: List[str] = []
            for t in policy_texts:
                tl = t.lower()
                if any(w in tl for w in ['policy', 'policies', 'term', 'rule', 'cancellation', 'refund']):
                    filtered_policy_texts.append(t)
            # Add policy widget sections
            import re as _re
            pol_open_pattern = _re.compile(r"\[WIDGET_SECTION[^\]]*type=\"policy\"[^\]]*\]\s*", _re.IGNORECASE)
            end_tag = "[END WIDGET_SECTION]"
            text = context_text or ""
            for m in pol_open_pattern.finditer(text):
                start = m.end()
                end = text.find(end_tag, start)
                if end != -1:
                    filtered_policy_texts.append(text[start:end].strip())

            # Synonym patterns
            synonym_patterns: List[Tuple[str, str]] = [
                (r'cooling\s*off', 'cooling_off_period'),
                (r'no\s*visa\s*no\s*pay|visa\s*(rejected|refused)', 'no_visa_no_pay'),
                (r'no\s*place\s*no\s*pay', 'no_place_no_pay'),
                (r'course\s*(cancel|change|modif)', 'university_course_cancellation_or_modification'),
                (r'early\s*(termination|release|surrender)', 'early_termination_by_student'),
                (r'delayed\s*arrivals|travel\s*restriction|quarantine', 'delayed_arrivals_or_travel_restrictions'),
                (r'replacement\s*tenant|re[- ]?let|reassign', 'replacement_tenant_found'),
                (r'defer|deferral|postpone', 'deferring_studies'),
                (r'intake\s*delayed|semester\s*delayed|term\s*delayed', 'university_intake_delayed'),
                (r'no\s*questions\s*asked', 'no_questions_asked'),
                (r'extenuating\s*circumstances|exceptional\s*circumstances|medical\s*reason', 'extenuating_circumstances'),
            ]

            combined = "\n\n".join(filtered_policy_texts)
            for pattern, key in synonym_patterns:
                try:
                    import re as _re
                    if cancellation.get(key):
                        continue
                    m = _re.search(pattern, combined, flags=_re.IGNORECASE)
                    if m:
                        # capture a nearby sentence as value
                        span_start = max(0, m.start() - 120)
                        span_end = min(len(combined), m.end() + 240)
                        snippet = combined[span_start:span_end]
                        # Trim to sentence boundaries if possible
                        # Simple heuristic: cut at nearest period
                        left_cut = snippet.find('.')
                        right_cut = snippet.rfind('.')
                        value = snippet.strip()
                        if len(value) > 800:
                            value = value[:800] + '...'
                        cancellation[key] = value
                except Exception:
                    continue
            # Ensure keys exist
            for k in ['cooling_off_period','no_visa_no_pay','no_place_no_pay','university_course_cancellation_or_modification','early_termination_by_student','delayed_arrivals_or_travel_restrictions','replacement_tenant_found','deferring_studies','university_intake_delayed','no_questions_asked','extenuating_circumstances','other_policies']:
                if k not in cancellation:
                    cancellation[k] = cancellation.get(k, '')
        except Exception:
            pass

        return data

    def _is_node2_sparse(self, data: Dict[str, Any]) -> bool:
        """Heuristic to decide if Node 2 description is underfilled and warrants a second crawl pass."""
        try:
            desc = data.get('description', {}) if isinstance(data, dict) else {}
            score = 0
            if desc.get('about'): score += 1
            if desc.get('features'): score += 1
            if desc.get('faqs') and isinstance(desc.get('faqs'), list) and len(desc['faqs']) >= 2: score += 1
            if desc.get('payments') and any(desc.get('payments', {}).get(k) for k in ['booking_deposit','security_deposit','payment_installment_plan','mode_of_payment']): score += 1
            if desc.get('cancellation_policy') and any(desc.get('cancellation_policy', {}).get(k) for k in ['cooling_off_period','no_visa_no_pay','no_place_no_pay']): score += 1
            if desc.get('commute') or desc.get('distance') or (desc.get('commute_pois') and len(desc.get('commute_pois') or []) >= 1): score += 1
            return score <= 2
        except Exception:
            return False
    
    def _count_non_empty_values(self, data: Any) -> int:
        """Count non-empty values in nested data structure"""
        if isinstance(data, dict):
            count = 0
            for value in data.values():
                count += self._count_non_empty_values(value)
            return count
        elif isinstance(data, list):
            count = 0
            for item in data:
                count += self._count_non_empty_values(item)
            return count
        elif data and str(data).strip():
            return 1
        else:
            return 0
            
    def _derive_node1_hints_from_pages(self, pages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Derive helpful hints for Node 1 from crawled pages' text.
        Extracts lat/lng, candidate name, amenity features, guarantor info, and best source link.
        Pages contain cleaned text and may include markers like [STRUCTURED DATA], [MAP COORDINATES], etc.
        """
        hints: Dict[str, Any] = {
            "derived_location": {},
            "derived_basic_info": {},
            "derived_features": [],
            "derived_guarantor": {},
            "best_source_link": pages[0]["url"] if pages else ""
        }

        # Regex patterns for coordinates
        latlng_patterns = [
            r"lat(?:itude)?\s*[:=]?\s*([\-\d\.]{2,})\s*[,;\s]+lng|long(?:itude)?\s*[:=]?\s*([\-\d\.]{2,})",
            r"\b([-\d\.]{2,}),\s*([-\d\.]{2,})\b",  # generic pair
        ]

        # Try to parse JSON-LD blocks from [STRUCTURED DATA] markers in text
        def _extract_jsonld_blocks(text: str) -> List[Dict[str, Any]]:
            blocks: List[Dict[str, Any]] = []
            try:
                # Find segments between markers
                parts = re.split(r"\[STRUCTURED DATA\]", text)
                for part in parts[1:]:
                    end_idx = part.find("[END STRUCTURED DATA]")
                    if end_idx > 0:
                        payload = part[:end_idx].strip()
                        # Some sites include multiple JSON objects; try to parse best-effort
                        try:
                            data = json.loads(payload)
                            blocks.append(data)
                        except Exception:
                            # Attempt to locate first {...} JSON object
                            m = re.search(r"\{[\s\S]*\}", payload)
                            if m:
                                try:
                                    data = json.loads(m.group(0))
                                    blocks.append(data)
                                except Exception:
                                    pass
            except Exception:
                pass
            return blocks

        # Extract map coordinates from [MAP COORDINATES] markers
        def _extract_map_coordinates(text: str) -> Tuple[Optional[str], Optional[str]]:
            lat, lng = None, None
            try:
                parts = re.split(r"\[MAP COORDINATES\]", text)
                for part in parts[1:]:
                    end_idx = part.find("[END MAP COORDINATES]")
                    if end_idx > 0:
                        coord_text = part[:end_idx].strip()
                        lat_match = re.search(r"Latitude:\s*([-\d\.]+)", coord_text)
                        lng_match = re.search(r"Longitude:\s*([-\d\.]+)", coord_text)
                        if lat_match and lng_match:
                            lat = lat_match.group(1)
                            lng = lng_match.group(1)
                            # Validate coordinates
                            try:
                                lat_f, lng_f = float(lat), float(lng)
                                if -90 <= lat_f <= 90 and -180 <= lng_f <= 180:
                                    return lat, lng
                            except ValueError:
                                pass
            except Exception:
                pass
            return None, None

        # Extract address info from [ADDRESS INFO] markers
        def _extract_address_info(text: str) -> Dict[str, str]:
            address_data = {}
            try:
                parts = re.split(r"\[ADDRESS INFO\]", text)
                for part in parts[1:]:
                    end_idx = part.find("[END ADDRESS INFO]")
                    if end_idx > 0:
                        address_text = part[:end_idx].strip()
                        # Try to parse address components
                        # Look for postcode pattern (UK: A1A 1AA, US: 12345 or 12345-6789)
                        postcode_match = re.search(r'\b[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2}\b', address_text, re.IGNORECASE)
                        if postcode_match:
                            address_data['postcode'] = postcode_match.group(0)
                        
                        # Look for city/region patterns
                        city_patterns = [
                            r'\b(?:in|at|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
                            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*(?:West\s+)?(?:Yorkshire|England|UK|United\s+Kingdom)\b'
                        ]
                        for pattern in city_patterns:
                            city_match = re.search(pattern, address_text, re.IGNORECASE)
                            if city_match:
                                address_data['city'] = city_match.group(1).strip()
                                break
                        
                        # Look for street address
                        street_match = re.search(r'\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|Road|Avenue|Lane|Drive|Close|Way)\b', address_text, re.IGNORECASE)
                        if street_match:
                            address_data['street'] = street_match.group(0)
            except Exception:
                pass
            return address_data

        # Extract property type information
        def _extract_property_type(text: str) -> Dict[str, str]:
            property_data = {}
            try:
                parts = re.split(r"\[PROPERTY TYPE\]", text)
                for part in parts[1:]:
                    end_idx = part.find("[END PROPERTY TYPE]")
                    if end_idx > 0:
                        type_text = part[:end_idx].strip()
                        if type_text:
                            property_data['property_type'] = type_text
                            break
            except Exception:
                pass
            return property_data

        # Extract contact information
        def _extract_contact_info(text: str) -> Dict[str, str]:
            contact_data = {}
            try:
                parts = re.split(r"\[CONTACT INFO\]", text)
                for part in parts[1:]:
                    end_idx = part.find("[END CONTACT INFO]")
                    if end_idx > 0:
                        contact_text = part[:end_idx].strip()
                        # Extract phone number
                        phone_match = re.search(r'Phone:\s*([+\d\s\(\)\-]+)', contact_text)
                        if phone_match:
                            contact_data['phone'] = phone_match.group(1).strip()
                        # Extract other contact info
                        elif contact_text and not contact_data.get('phone'):
                            contact_data['contact_details'] = contact_text
                        break
            except Exception:
                pass
            return contact_data

        # Extract structured data from tables
        def _extract_table_data(text: str) -> Dict[str, List[str]]:
            table_data = {}
            try:
                parts = re.split(r"\[TABLE:", text)
                for part in parts[1:]:
                    end_idx = part.find("[END TABLE]")
                    if end_idx > 0:
                        table_content = part[:end_idx].strip()
                        # Extract table type from first line
                        lines = table_content.split('\n')
                        if lines:
                            table_type = lines[0].strip()
                            table_rows = lines[1:] if len(lines) > 1 else []
                            
                            if table_type not in table_data:
                                table_data[table_type] = []
                            
                            for row in table_rows:
                                if row.strip():
                                    table_data[table_type].append(row.strip())
            except Exception:
                pass
            return table_data

        # Extract structured data from lists
        def _extract_list_data(text: str) -> Dict[str, List[str]]:
            list_data = {}
            try:
                parts = re.split(r"\[LIST:", text)
                for part in parts[1:]:
                    end_idx = part.find("[END LIST]")
                    if end_idx > 0:
                        list_content = part[:end_idx].strip()
                        # Extract list type from first line
                        lines = list_content.split('\n')
                        if lines:
                            list_type = lines[0].strip()
                            list_items = lines[1:] if len(lines) > 1 else []
                            
                            if list_type not in list_data:
                                list_data[list_type] = []
                            
                            for item in list_items:
                                if item.strip() and item.startswith('•'):
                                    list_data[list_type].append(item.strip()[1:].strip())
            except Exception:
                pass
            return list_data

        # Extract definition list data
        def _extract_definition_list_data(text: str) -> Dict[str, str]:
            definition_data = {}
            try:
                parts = re.split(r"\[DEFINITION LIST\]", text)
                for part in parts[1:]:
                    end_idx = part.find("[END DEFINITION LIST]")
                    if end_idx > 0:
                        dl_content = part[:end_idx].strip()
                        lines = dl_content.split('\n')
                        for line in lines:
                            if ':' in line:
                                parts = line.split(':', 1)
                                if len(parts) == 2:
                                    key = parts[0].strip()
                                    value = parts[1].strip()
                                    if key and value:
                                        definition_data[key] = value
            except Exception:
                pass
            return definition_data

        # Extract footer content
        def _extract_footer_data(text: str) -> Dict[str, str]:
            footer_data = {}
            try:
                parts = re.split(r"\[FOOTER CONTENT\]", text)
                for part in parts[1:]:
                    end_idx = part.find("[END FOOTER CONTENT]")
                    if end_idx > 0:
                        footer_content = part[:end_idx].strip()
                        if footer_content:
                            footer_data['footer_text'] = footer_content
                            
                            # Try to extract specific info from footer
                            # Phone numbers
                            phone_match = re.search(r'(\+44\s*\d{1,4}\s*\d{1,4}\s*\d{1,4}|\(0\)\d{1,4}\s*\d{1,4}\s*\d{1,4}|0\d{1,4}\s*\d{1,4}\s*\d{1,4})', footer_content)
                            if phone_match:
                                footer_data['footer_phone'] = phone_match.group(1)
                            
                            # Email addresses
                            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', footer_content)
                            if email_match:
                                footer_data['footer_email'] = email_match.group(1)
                            
                            # Address information
                            address_match = re.search(r'(\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|Road|Avenue|Lane|Drive|Close|Way))', footer_content, re.IGNORECASE)
                            if address_match:
                                footer_data['footer_address'] = address_match.group(1)
            except Exception:
                pass
            return footer_data

        # Extract guarantor requirements
        def _extract_guarantor_info(text: str) -> Dict[str, str]:
            guarantor_data = {}
            text_lower = text.lower()
            
            # Look for guarantor-related patterns
            guarantor_patterns = [
                (r'guarantor\s+(?:is\s+)?(?:required|needed|mandatory)', 'guarantor_required'),
                (r'(?:no|not\s+required)\s+guarantor', 'no_guarantor'),
                (r'guarantor\s+(?:not\s+)?(?:required|needed)', 'guarantor_optional'),
                (r'international\s+guarantor', 'international_guarantor'),
                (r'local\s+guarantor\s+only', 'local_guarantor_only'),
                (r'third\s+party\s+guarantor\s+service', 'third_party_guarantor'),
                (r'parent.*signature.*required', 'parent_signature_required'),
                (r'co.?signer', 'co_signer_required'),
            ]
            
            for pattern, key in guarantor_patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    guarantor_data[key] = 'true'
                    break
            
            # If no specific pattern found, look for general guarantor mentions
            if not guarantor_data and 'guarantor' in text_lower:
                guarantor_data['guarantor_mentioned'] = 'true'
            
            return guarantor_data

        candidate_names: List[str] = []
        lat: Optional[str] = None
        lng: Optional[str] = None
        features_accum: List[Dict[str, str]] = []
        address_components: Dict[str, str] = {}
        property_type_info: Dict[str, str] = {}
        contact_info: Dict[str, str] = {}
        table_info: Dict[str, List[str]] = {}
        list_info: Dict[str, List[str]] = {}
        definition_info: Dict[str, str] = {}
        footer_info: Dict[str, str] = {}
        guarantor_info: Dict[str, str] = {}

        for p in pages:
            text = p.get("text", "") or ""
            
            # Extract map coordinates from new markers
            map_lat, map_lng = _extract_map_coordinates(text)
            if map_lat and map_lng and not (lat and lng):
                lat, lng = map_lat, map_lng
            
            # Extract address information
            page_address = _extract_address_info(text)
            for key, value in page_address.items():
                if key not in address_components:
                    address_components[key] = value
            
            # Extract property type information
            page_property_type = _extract_property_type(text)
            for key, value in page_property_type.items():
                if key not in property_type_info:
                    property_type_info[key] = value
            
            # Extract contact information
            page_contact_info = _extract_contact_info(text)
            for key, value in page_contact_info.items():
                if key not in contact_info:
                    contact_info[key] = value
            
            # Extract structured data from tables
            page_table_data = _extract_table_data(text)
            for key, value in page_table_data.items():
                if key not in table_info:
                    table_info[key] = []
                table_info[key].extend(value)
            
            # Extract structured data from lists
            page_list_data = _extract_list_data(text)
            for key, value in page_list_data.items():
                if key not in list_info:
                    list_info[key] = []
                list_info[key].extend(value)
            
            # Extract definition list data
            page_definition_data = _extract_definition_list_data(text)
            for key, value in page_definition_data.items():
                if key not in definition_info:
                    definition_info[key] = value
            
            # Extract footer data
            page_footer_data = _extract_footer_data(text)
            for key, value in page_footer_data.items():
                if key not in footer_info:
                    footer_info[key] = value
            
            # Extract guarantor information
            page_guarantor = _extract_guarantor_info(text)
            for key, value in page_guarantor.items():
                if key not in guarantor_info:
                    guarantor_info[key] = value
            
            # JSON-LD extraction (existing logic)
            for block in _extract_jsonld_blocks(text):
                try:
                    if isinstance(block, list):
                        for item in block:
                            if isinstance(item, dict):
                                n = item.get("name") or item.get("@name")
                                if n:
                                    candidate_names.append(str(n))
                                geo = item.get("geo") or {}
                                lat_v = geo.get("latitude")
                                lng_v = geo.get("longitude")
                                if lat_v and lng_v and not (lat and lng):
                                    lat, lng = str(lat_v), str(lng_v)
                                # Features
                                amen = item.get("amenityFeature") or []
                                if isinstance(amen, list):
                                    for a in amen:
                                        nm = a.get("name") if isinstance(a, dict) else None
                                        if nm:
                                            features_accum.append({"type": "Amenities", "name": str(nm)})
                    elif isinstance(block, dict):
                        n = block.get("name") or block.get("@name")
                        if n:
                            candidate_names.append(str(n))
                        geo = block.get("geo") or {}
                        lat_v = geo.get("latitude")
                        lng_v = geo.get("longitude")
                        if lat_v and lng_v and not (lat and lng):
                            lat, lng = str(lat_v), str(lng_v)
                        amen = block.get("amenityFeature") or []
                        if isinstance(amen, list):
                            for a in amen:
                                nm = a.get("name") if isinstance(a, dict) else None
                                if nm:
                                    features_accum.append({"type": "Amenities", "name": str(nm)})
                except Exception:
                    continue

            # Fallback lat/lng from free text (avoid false positives)
            if not (lat and lng):
                for pat in latlng_patterns:
                    m = re.search(pat, text, flags=re.IGNORECASE)
                    if m and len(m.groups()) >= 2:
                        g1, g2 = m.group(1), m.group(2)
                        # Simple sanity check for lat/lng ranges
                        try:
                            g1f = float(g1)
                            g2f = float(g2)
                            if -90 <= g1f <= 90 and -180 <= g2f <= 180:
                                lat, lng = g1, g2
                                break
                        except Exception:
                            continue

        # Set derived hints
        if candidate_names:
            # Choose the longest meaningful name
            best_name = max(candidate_names, key=lambda s: len(s))
            hints["derived_basic_info"]["name"] = best_name.strip()
        
        if lat and lng:
            hints["derived_location"]["latitude"] = lat
            hints["derived_location"]["longitude"] = lng
        
        if address_components:
            hints["derived_location"].update(address_components)
        
        if property_type_info:
            hints["derived_basic_info"].update(property_type_info)
        
        if contact_info:
            hints["derived_basic_info"]["contact"] = contact_info
        
        if table_info:
            hints["derived_structured_data"] = {"tables": table_info}
        
        if list_info:
            if "derived_structured_data" not in hints:
                hints["derived_structured_data"] = {}
            hints["derived_structured_data"]["lists"] = list_info
        
        if definition_info:
            if "derived_structured_data" not in hints:
                hints["derived_structured_data"] = {}
            hints["derived_structured_data"]["definitions"] = definition_info
        
        if footer_info:
            hints["derived_footer"] = footer_info
        
        if features_accum:
            hints["derived_features"] = features_accum[:50]
        
        if guarantor_info:
            hints["derived_guarantor"] = guarantor_info

        return hints

    def _highlight_key_information(self, context_text: str, node_name: str) -> str:
        """Highlight key information in context text based on node type"""
        if not context_text:
            return ""
            
        # Define node-specific highlight patterns
        highlight_patterns = {
            'node1_basic_info': [
                r'property\s+name', r'address', r'location', r'guarantor', 
                r'feature', r'amenity', r'facility', r'rule', r'security'
            ],
            'node2_description': [
                r'about', r'description', r'overview', r'feature', 
                r'commute', r'location', r'payment', r'deposit', r'security\s+deposit', r'booking\s+deposit', r'holding\s+fee', r'installment|instalment', r'mode\s+of\s+payment', r'platform\s+fee', r'additional\s+fees',
                r'policy', r'policies', r'house\s+rules', r'rules', r'cancellation', r'no\s+visa\s+no\s+pay', r'no\s+place\s+no\s+pay', r'refund', r'deferring', r'delayed\s+arrivals', r'extenuating', r'replacement\s+tenant', r'intake\s+delayed', r'pet\s+policy|pets', r'faq'
            ],
            'node3_configuration': [
                r'room', r'studio', r'apartment', r'flat', r'accommodation',
                r'price', r'cost', r'fee', r'rent', r'area', r'size', r'floor',
                r'bedroom', r'bathroom', r'ensuite', r'en-suite', r'kitchen',
                r'furniture', r'equipped', r'feature', r'amenity'
            ],
            'node4_tenancy': [
                r'tenancy', r'contract', r'lease', r'term', r'duration',
                r'week', r'month', r'year', r'availability', r'available',
                r'start', r'end', r'date', r'price', r'cost', r'deposit'
            ]
        }
        
        patterns = highlight_patterns.get(node_name, [])
        if not patterns:
            return context_text
            
        # Split context into sections by source markers
        sections = re.split(r'(===\s+[^=]+\s+===)', context_text)
        highlighted_sections = []
        
        for i in range(0, len(sections), 2):
            header = sections[i] if i == 0 else sections[i-1]
            content = sections[i] if i == 0 else sections[i]
            
            # Apply highlighting to content
            for pattern in patterns:
                try:
                    content = re.sub(
                        f'({pattern}[\\w\\s\\-.,;:()]+)', 
                        r'[IMPORTANT] \1 [/IMPORTANT]', 
                        content, 
                        flags=re.IGNORECASE
                    )
                except Exception:
                    continue
            
            highlighted_sections.append(header if i > 0 else '')
            highlighted_sections.append(content)
        
        return ''.join(highlighted_sections)
    
    def _get_node1_prompt(self) -> str:
        """Get prompt for Node 1: Basic Info, Location, Features, Rules, Safety"""
        return """You are a professional property data extraction assistant. Your task is to extract structured, authentic, and complete data from the provided student accommodation listing webpage and all linked content on that page.

📌 Scope of Extraction:
Parse the following sources:
- The main webpage content.
- All internal links, buttons, tabs, and expandable sections within the page that may contain additional content (e.g., amenities, policies, features, location).
- Content loaded asynchronously via JavaScript, including dynamically rendered HTML elements.
- Ensure everything is extracted as if rendered in a headless browser (with scrolling, clicking, expanding done).

🧠 Your Objective:
Return the extracted information in the following structured JSON format:
{
  "basic_info": {
    "name": "",
    "guarantor_required": "",
    "source": "",
    "source_link": "",
    "property_type": "",
    "contact": {
      "phone": "",
      "contact_details": ""
    }
  },
  "location": {
    "location_name": "",
    "address": "",
    "city": "",
    "region": "",
    "country": "",
    "latitude": "",
    "longitude": "",
    "postcode": ""
  },
  "features": [
    {
      "type": "",
      "name": ""
    }
  ],
  "property_rules": [
    {
      "type": "",
      "name": ""
    }
  ],
  "safety_and_security": [
    {
      "type": "",
      "name": ""
    }
  ]
}

🔍 Field-Level Details
🟠 Basic Info
- name: Full property name including city (e.g., "iQ Broderick House, Birmingham")
- guarantor_required: Choose one from:
  * No guarantor required
  * International and local guarantors allowed
  * Local guarantor only (third party guarantor service not allowed)
  * Local guarantor only (third party guarantor service allowed)
  * Information unavailable
- source: Brand or operator name (e.g., "IQ Student Accommodation")
- source_link: The original URL you are extracting from
- property_type: Type of accommodation (e.g., "Student Accommodation", "Student Residence", "Purpose Built Student Residence")
- contact: Contact information including phone and other details

🟢 Location (ENHANCED - Extract ALL available fields)
- location_name: Full name or address as mentioned
- address: Complete street address if available
- city: City name (e.g., "Leeds", "Birmingham")
- region: State/County/Region (e.g., "West Yorkshire", "England")
- country: Country name (e.g., "United Kingdom", "UK")
- latitude: Extract from map, metadata, or page scripts (decimal format)
- longitude: Extract from map, metadata, or page scripts (decimal format)
- postcode: Postal/ZIP code if available

🟡 Features
Each item must contain:
- type: Must match one from predefined dropdown (see below)
- name: Amenity or label as shown on the page

🔵 Property Rules
Same structure as features.

🔴 Safety and Security
If the feature doesn't match any dropdown value, use:
{
  "type": "Others",
  "name": "CCTV / Smart Entry / etc."
}

📎 Allowed Dropdown Values for type
Air Conditioner & Heating, Balcony or Patios, Barbeque & Grill, Business Center, Cafe & Restaurant, Fan, Cinema Room, Clubhouse, Courtyard, Disability Access, Fireplace, Tile Flooring, Wooden Flooring, Carpet Flooring, Food & Meals, Garbage Disposal, Gas Stove, Gym & Fitness, Prayer Room, Internet Access, Wifi, Jogging, Kitchen with Appliance, Laundry Facility, Library & Study Area, Lounge, Maintenance, Medical Facility, Microwave, Parking, Electronic Payments, Pet Friendly, Playground, Snow Removal, Social Events, Spa & Salon, Sport Golf, Room Storage, Swimming Pool, Television, Sports, Pets Not Allowed, Blinds, Telephone, Breakfast Bar, Home Linen, Industry Accreditation & Awards, Common Social Area, Unfurnished Accommodations, Mattress, Games Area, Household Supplies, Sundeck, Vending Machine, Bean Bag, Terrace, Noticeboard, Property Rules, Content Insurance, Ironing Facility, Flatmate, Alarm Clock, Classroom, Den, Newly Refurbished, Fire Extinguisher, Coffee Machine, Basic Essentials, Parcel Collection, Location Benefit, Dining Area, Locker & Safes, Shuttle & Cab Service, Shops, Electric Vehicle Charging Station, Double Occupancy, Guarantor Requirement, Reception & Staff, Common Service, Fully Furnished, Fridge, Accommodation Features, Bathroom, Others

⚠️ Extraction Rules
❌ Do not guess values
❌ Do not hallucinate information
✅ Only extract what is explicitly available
✅ Match dropdown values exactly
✅ Leave missing data as empty string or "Information unavailable"
✅ PRIORITIZE extracting coordinates and address information from any available source
✅ Look for guarantor requirements in terms, FAQ, and application sections
✅ Extract property type from meta tags, structured data, and page content
✅ Look for contact information including phone numbers in contact sections"""
    
    def _get_node2_prompt(self) -> str:
        """Get prompt for Node 2: Description Section (Detailed)"""
        return """You are an expert data extraction agent for student accommodation platforms.
Your task is to extract the entire description section, with all available sub-sections and nested tags, from a given student accommodation webpage.
Return your output in strictly valid JSON format, as specified below.
Maintain:
- Original phrasing and language wherever possible
- Full detail for all sections (do not truncate or paraphrase)
- Empty string ("") or omit keys only if the data is truly not present

📦 JSON Output Format
{
  "description": {
    "about": "",
    "features": "",
    "highlights": [""],
    "commute": "",
    "location_and_whats_hot": "",
    "distance": "",
    "commute_pois": [
      { "poi_name": "", "distance": "", "time": "", "transport": "" }
    ],
    "payments": {
      "booking_deposit": "",
      "security_deposit": "",
      "payment_installment_plan": "",
      "mode_of_payment": "",
      "guarantor_requirement": "",
      "fully_refundable_holding_fee": "",
      "platform_fee": "",
      "additional_fees": ""
    },
    "cancellation_policy": {
      "cooling_off_period": "",
      "no_visa_no_pay": "",
      "no_place_no_pay": "",
      "university_course_cancellation_or_modification": "",
      "early_termination_by_student": "",
      "delayed_arrivals_or_travel_restrictions": "",
      "replacement_tenant_found": "",
      "deferring_studies": "",
      "university_intake_delayed": "",
      "no_questions_asked": "",
      "extenuating_circumstances": "",
      "other_policies": ""
    },
    "pet_policy": "",
    "faqs": [
      {
        "question": "",
        "answer": ""
      }
    ],
    "booking_disclaimer": "",
    "email": ""
  }
}

✅ Parsing Guidelines
- Section Headings (Smart Mapping): Prefer content grouped under headings (About, Features, Payments, Policies, FAQs, Commute). Use heading boundaries when present. Map by title synonyms:
  - About/Overview/Summary/Why this property → description.about
  - Features/Amenities/Facilities/Inclusions → description.features
  - Location/What's Hot/Nearby/Neighborhood/Area → description.location_and_whats_hot
  - Distance/Commute/Transport/Travel → description.commute, description.distance, description.commute_pois
  - Payments/Fees/Deposit/Charges/Installments/Instalments → description.payments (split into booking_deposit, security_deposit, installments, mode_of_payment, platform_fee, additional_fees, holding_fee)
  - Policies/Terms/House Rules/Cancellation → description.cancellation_policy (map to specific keys using synonyms below)
  - Pet Policy/Pets → description.pet_policy
- Markers: Utilize content from markers produced by the scraper, including:
  - [HEADING_SECTION title="..."] ... [END HEADING_SECTION]
  - [WIDGET_SECTION type="..." selector="..."] ... [END WIDGET_SECTION]
  - [LIST: TYPE] ... [END LIST], [TABLE: TYPE] ... [END TABLE], [DEFINITION LIST] ... [END DEFINITION LIST]
  - [INLINE JSON] ... [END INLINE JSON], [API RESPONSE url="..."] ... [END API RESPONSE]
  - [FOOTER CONTENT] for contact/policy/links if relevant
- Commute POIs: When POIs/distances/times/transport are listed (tables, lists, widgets), populate commute_pois[] alongside the free-text commute.
- Payments & Policies: Normalize different phrasings into the keys shown; if multiple values, include the most complete text.
- Formatting: Keep full paragraphs intact with line breaks (\n) preserved if present on the source page.
- Missing Data: If a sub-section does not exist, use an empty string "" or skip that key.

SMART SECTION MAPPING DETAILS
- Use [HEADING_SECTION] titles to infer the target field. Example: title contains "Payment" → description.payments; title contains "Policy" → description.cancellation_policy; title contains "FAQ" → description.faqs.
- If [WIDGET_SECTION type="faq"] contains lines like "Q: ...\nA: ...", split into {question, answer} objects and append to description.faqs.
- If [WIDGET_SECTION type="policy"] contains cancellation/terms language, assign to description.cancellation_policy using the synonyms below.
- For [TABLE: PRICING] or [LIST: FEATURES], merge structured items into description.features when they describe amenities; otherwise map to payments when they are fees.

POLICY FIELD SYNONYMS (map to description.cancellation_policy keys):
- cooling_off_period: cooling off, change of mind window, free cancellation window
- no_visa_no_pay: no visa no pay, visa refused, visa rejection
- no_place_no_pay: no place no pay, university place not confirmed, CAS refused
- university_course_cancellation_or_modification: course cancelled, course changed, course modification
- early_termination_by_student: early termination, breaking contract, early release, surrender tenancy
- delayed_arrivals_or_travel_restrictions: delayed arrival, travel restriction, quarantine, covid
- replacement_tenant_found: replacement tenant, substitute tenant, relet, reassign
- deferring_studies: defer, deferral, postpone studies
- university_intake_delayed: intake delayed, semester delayed, term delayed
- no_questions_asked: no questions asked cancellation, unconditional cancellation
- extenuating_circumstances: extenuating circumstances, exceptional circumstances, medical reasons
- other_policies: any remaining relevant policy text not mapped above
"""
    
    def _get_node3_prompt(self) -> str:
        """Get prompt for Node 3: Room Configurations, Pricing, Offers, Availability"""
        return """You are a highly accurate data extraction agent trained to onboard detailed configuration-level data for student housing properties.

📌 Objective:
From the given property webpage content (including hidden sections, JS-loaded content, linked tabs, or accordions), extract all configurations (room types/units) offered under this property.
Return structured JSON for each configuration, following the format below.

📦 JSON Output Format
Return an array named configurations where each object includes:
{
  "configurations": [
    {
      "Basic": {
        "Name": "",
        "Status": ""
      },
      "Source Details": {
        "Source": "",
        "Source Id": "",
        "Source Link": ""
      },
      "Pricing": {
        "Price": "",
        "Min Price": "",
        "Max Price": "",
        "Deposit": "",
        "Min Deposit Amount": "",
        "Max Deposit Amount": ""
      },
      "Meta": {
        "Price Duration": "",
        "Price Currency": "",
        "Advance Rent Multiplier Value": ""
      },
      "Area": {
        "Area": "",
        "Min Area": "",
        "Max Area": "",
        "Area Unit": ""
      },
      "Floor Details": {
        "Floor": "",
        "Facing": ""
      },
      "Configuration": {
        "Types": [],
        "Dual Occupancy": "",
        "Unit Type": "",
        "Bedroom Count": "",
        "Min Bedroom Count": "",
        "Max Bedroom Count": "",
        "Bathroom Count": "",
        "Min Bathroom Count": "",
        "Max Bathroom Count": "",
        "Unit Count": ""
      },
      "Lease Duration": {
        "Lease Duration": "",
        "Min Lease Duration": "",
        "Max Lease Duration": "",
        "Lease Duration Unit": ""
      },
      "Availability": {
        "Available Units": "",
        "Available From": ""
      },
      "Payments and Forms": {
        "Jotform Form Id": "",
        "Accept Payments": "",
        "Payment Type to Collect": "",
        "Terms and Conditions Doc URL": "",
        "Login URL": "",
        "Property is Non-Commissionable for Locals": "",
        "Enable Payment Before Bookform": ""
      },
      "Description": {
        "Name": "",
        "Type": "",
        "Numeric Value": "",
        "Description": "",
        "Safe to Save": ""
      },
      "Features": [
        {
          "Type": "",
          "Section Name": "",
          "Description": ""
        }
      ]
    }
  ]
}

🧠 Instructions
- Scrape every configuration/unit listed on the page and its linked inner pages or tabs if required.
- Normalize missing fields with "null" or "" where data is not mentioned.
- Use dropdown values where applicable (e.g., Configuration Types, Dual Occupancy, etc.).
- If ranges (e.g., price or area) are given, separate them as Min and Max.
- Ensure all numeric values are extracted as strings for safety and compatibility.
❌ Do not hallucinate. ✅ Return only what's explicitly or clearly stated in the source content.
If a property has no configurations or content is missing, return: "configurations": []"""
    
    def _get_node4_prompt(self) -> str:
        """Get prompt for Node 4: Tenancy-Level Room Configs with Contracts & Pricing"""
        return """You are a property onboarding assistant tasked with extracting the most detailed, accurate, and structured tenancy-level data for student accommodation listings from a given webpage and all its links.
Your job now goes beyond property-level details, and you must also extract all configuration (tenancy) level data, including room types, tenancy durations, prices, availability, and any special terms.

📌 DATA SOURCES TO CONSIDER:
You must extract and consolidate data from:
- The main webpage
- All tabs, pop-ups, expandable sections, and linked subpages
- Content that loads dynamically via JavaScript or user interactions
- Any JSON embedded in <script> tags or API responses if visible
- All room cards, booking flows, or floor plan sections on the site

📦 JSON OUTPUT FORMAT
{
  "property_level": {
    "name": "",
    "guarantor_required": "",
    "source": "",
    "source_link": "",
    "location_name": "",
    "latitude": "",
    "longitude": "",
    "region": ""
  },
  "configurations": [
    {
      "name": "",
      "status": "",
      "source": "",
      "source_id": "",
      "source_link": "",
      "base_price": "",
      "min_price": "",
      "max_price": "",
      "tenancy_options": [
        {
          "tenancy_length": "",
          "price": "",
          "availability_status": "",
          "price_type": "",
          "start_date": "",
          "end_date": ""
        }
      ],
      "room_type": "",
      "bathroom_type": "",
      "kitchen_type": "",
      "occupancy": "",
      "floor_area": "",
      "features": ["..."],
      "offers": ["..."],
      "availability_note": ""
    }
  ]
}

📚 FIELD EXPLANATIONS:
- All property-level data fields mirror those from Node 1
- Each room configuration includes room-specific tenancy options
- Each tenancy_option is a separate contract offering

⚠️ RULES:
❌ Do not merge configs that differ in any detail
❌ Do not hallucinate or guess
✅ Extract data as rendered on full UI and booking flow
✅ Simulate browser interactions if needed (scroll, expand, click)
✅ Extract deeply nested data (scripts, React/Angular sections, JSON blobs)"""

# Alternative implementation for environments without browsing capability
class MockGPTExtractionClient(GPTExtractionClient):
    """Mock client for testing without actual GPT-4o browsing"""
    
    def extract_property_data(self, url: str, node_name: str, job_id: int) -> ExtractionResult:
        """Mock extraction that returns sample data"""
        start_time = time.time()
        
        try:
            self.logger.log_node_start(job_id, node_name)
            
            # Simulate processing time
            time.sleep(2)
            
            # Return mock data based on node type
            mock_data = self._get_mock_data(node_name, url)
            
            execution_time = time.time() - start_time
            confidence_score = 0.85  # Mock confidence score
            
            self.logger.log_node_complete(job_id, node_name, execution_time, confidence_score)
            
            return ExtractionResult(
                success=True,
                data=mock_data,
                error=None,
                confidence_score=confidence_score,
                execution_time=execution_time,
                raw_response=json.dumps(mock_data, indent=2)
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # Categorize errors for better handling
            if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                error_category = 'timeout'
            elif 'connection' in error_msg.lower() or 'network' in error_msg.lower():
                error_category = 'connection'
            elif 'rate limit' in error_msg.lower() or 'too many requests' in error_msg.lower():
                error_category = 'rate_limit'
            else:
                error_category = 'unknown'
            
            self.logger.log_node_failed(job_id, node_name, error_msg, duration=execution_time)
            
            return ExtractionResult(
                success=False,
                data=None,
                error=error_msg,
                confidence_score=0.0,
                execution_time=execution_time,
                raw_response=None,
                error_category=error_category
            )
    
    def _get_mock_data(self, node_name: str, url: str) -> Dict[str, Any]:
        """Generate mock data for testing"""
        if node_name == 'node1_basic_info':
            return {
                "basic_info": {
                    "name": "Sample Student Accommodation",
                    "guarantor_required": "International and local guarantors allowed",
                    "source": "Sample Provider",
                    "source_link": url,
                    "property_type": "Student Residence",
                    "contact": {
                        "phone": "0123 456 7890",
                        "contact_details": "info@sampleaccommodation.com"
                    }
                },
                "location": {
                    "location_name": "Sample Location, City",
                    "latitude": "51.5074",
                    "longitude": "-0.1278",
                    "region": "City, State, Country"
                },
                "features": [
                    {"type": "Wifi", "name": "High-speed WiFi"},
                    {"type": "Gym & Fitness", "name": "24/7 Fitness Center"},
                    {"type": "Laundry Facility", "name": "On-site Laundry"}
                ],
                "property_rules": [
                    {"type": "Property Rules", "name": "No smoking policy"},
                    {"type": "Property Rules", "name": "Quiet hours 10PM-8AM"}
                ],
                "safety_and_security": [
                    {"type": "Others", "name": "24/7 CCTV monitoring"},
                    {"type": "Others", "name": "Secure key card access"}
                ]
            }
        elif node_name == 'node2_description':
            return {
                "description": {
                    "about": "Modern student accommodation in the heart of the city...",
                    "features": "Premium amenities including gym, study areas, and social spaces...",
                    "commute": "5 minutes walk to university campus...",
                    "location_and_whats_hot": "Located in vibrant student district...",
                    "distance": "University: 0.3 miles, City center: 0.8 miles",
                    "payments": {
                        "booking_deposit": "£200 refundable deposit",
                        "security_deposit": "£500 security deposit",
                        "payment_installment_plan": "Monthly payments available",
                        "mode_of_payment": "Bank transfer, credit card",
                        "guarantor_requirement": "UK guarantor or international guarantor service",
                        "fully_refundable_holding_fee": "£100 holding fee",
                        "platform_fee": "No platform fee",
                        "additional_fees": "Utilities included"
                    },
                    "cancellation_policy": {
                        "cooling_off_period": "14 days cooling off period",
                        "no_visa_no_pay": "Full refund if visa rejected",
                        "no_place_no_pay": "Full refund if university place not confirmed",
                        "university_course_cancellation_or_modification": "Flexible cancellation for course changes",
                        "early_termination_by_student": "30 days notice required",
                        "delayed_arrivals_or_travel_restrictions": "Flexible arrival dates",
                        "replacement_tenant_found": "Early termination if replacement found",
                        "deferring_studies": "Option to defer booking",
                        "university_intake_delayed": "Flexible start dates",
                        "no_questions_asked": "Not applicable",
                        "extenuating_circumstances": "Case by case basis",
                        "other_policies": "Standard terms and conditions apply"
                    },
                    "pet_policy": "No pets allowed",
                    "faqs": [
                        {
                            "question": "What is included in the rent?",
                            "answer": "Rent includes utilities, WiFi, and access to all facilities"
                        },
                        {
                            "question": "Is there parking available?",
                            "answer": "Limited parking spaces available for additional fee"
                        }
                    ],
                    "booking_disclaimer": "Prices subject to availability and terms apply",
                    "email": "info@sampleaccommodation.com"
                }
            }
        elif node_name == 'node3_configuration':
            return {
                "configurations": [
                    {
                        "Basic": {
                            "Name": "Standard Studio",
                            "Status": "Available"
                        },
                        "Source Details": {
                            "Source": "Sample Provider",
                            "Source Id": "STD001",
                            "Source Link": url
                        },
                        "Pricing": {
                            "Price": "£150",
                            "Min Price": "£140",
                            "Max Price": "£160",
                            "Deposit": "£500",
                            "Min Deposit Amount": "£500",
                            "Max Deposit Amount": "£500"
                        },
                        "Meta": {
                            "Price Duration": "per week",
                            "Price Currency": "GBP",
                            "Advance Rent Multiplier Value": "4"
                        },
                        "Area": {
                            "Area": "18",
                            "Min Area": "16",
                            "Max Area": "20",
                            "Area Unit": "sqm"
                        },
                        "Floor Details": {
                            "Floor": "Various",
                            "Facing": "Mixed"
                        },
                        "Configuration": {
                            "Types": ["Studio"],
                            "Dual Occupancy": "No",
                            "Unit Type": "Studio",
                            "Bedroom Count": "0",
                            "Min Bedroom Count": "0",
                            "Max Bedroom Count": "0",
                            "Bathroom Count": "1",
                            "Min Bathroom Count": "1",
                            "Max Bathroom Count": "1",
                            "Unit Count": "50"
                        },
                        "Lease Duration": {
                            "Lease Duration": "44",
                            "Min Lease Duration": "44",
                            "Max Lease Duration": "51",
                            "Lease Duration Unit": "weeks"
                        },
                        "Availability": {
                            "Available Units": "15",
                            "Available From": "2024-09-01"
                        },
                        "Payments and Forms": {
                            "Jotform Form Id": "",
                            "Accept Payments": "Yes",
                            "Payment Type to Collect": "Deposit",
                            "Terms and Conditions Doc URL": "",
                            "Login URL": "",
                            "Property is Non-Commissionable for Locals": "No",
                            "Enable Payment Before Bookform": "Yes"
                        },
                        "Description": {
                            "Name": "Standard Studio",
                            "Type": "Studio",
                            "Numeric Value": "18",
                            "Description": "Modern studio with kitchenette and en-suite bathroom",
                            "Safe to Save": "Yes"
                        },
                        "Features": [
                            {
                                "Type": "Kitchen with Appliance",
                                "Section Name": "Room Features",
                                "Description": "Fully equipped kitchenette"
                            },
                            {
                                "Type": "Bathroom",
                                "Section Name": "Room Features", 
                                "Description": "Private en-suite bathroom"
                            }
                        ]
                    }
                ]
            }
        elif node_name == 'node4_tenancy':
            return {
                "property_level": {
                    "name": "Sample Student Accommodation",
                    "guarantor_required": "International and local guarantors allowed",
                    "source": "Sample Provider",
                    "source_link": url,
                    "location_name": "Sample Location, City",
                    "latitude": "51.5074",
                    "longitude": "-0.1278",
                    "region": "City, State, Country"
                },
                "configurations": [
                    {
                        "name": "Standard Studio",
                        "status": "Available",
                        "source": "Sample Provider",
                        "source_id": "STD001",
                        "source_link": url,
                        "base_price": "£150",
                        "min_price": "£140",
                        "max_price": "£160",
                        "tenancy_options": [
                            {
                                "tenancy_length": "44 weeks",
                                "price": "£150",
                                "availability_status": "Available",
                                "price_type": "per week",
                                "start_date": "2024-09-01",
                                "end_date": "2025-06-30"
                            },
                            {
                                "tenancy_length": "51 weeks",
                                "price": "£145",
                                "availability_status": "Available",
                                "price_type": "per week",
                                "start_date": "2024-09-01",
                                "end_date": "2025-08-31"
                            }
                        ],
                        "room_type": "Studio",
                        "bathroom_type": "En-suite",
                        "kitchen_type": "Kitchenette",
                        "occupancy": "Single",
                        "floor_area": "18 sqm",
                        "features": ["WiFi", "Utilities included", "24/7 security"],
                        "offers": ["Early bird discount", "No admin fees"],
                        "availability_note": "Limited availability - book early"
                    }
                ]
            }
        else:
            return {"error": f"Unknown node: {node_name}"}

def get_extraction_client() -> GPTExtractionClient:
    """Get the appropriate extraction client based on configuration"""
    config = get_config()
    
    # Check if we have a valid OpenAI API key
    if config.api.openai_api_key and config.api.openai_api_key.strip():
        return GPTExtractionClient()
    else:
        # Return mock client for testing
        return MockGPTExtractionClient()

