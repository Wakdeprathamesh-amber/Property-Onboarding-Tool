import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from src.utils.logging_config import get_logger
from src.utils.validation import PropertyDataValidator

@dataclass
class ValidationResult:
    """Result of data validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    completeness_score: float
    # Optional field-level completeness/confidence breakdown
    field_scores: Optional[Dict[str, float]] = None

@dataclass
class MergeResult:
    """Result of data merging operation"""
    success: bool
    merged_data: Optional[Dict[str, Any]]
    conflicts_found: int
    conflicts_resolved: int
    errors: List[str]
    quality_score: float

class PropertyDataProcessor:
    """Processor for property extraction data validation, transformation, and merging"""
    
    def __init__(self):
        self.logger = get_logger()
        self.validator = PropertyDataValidator()
    
    def validate_node_data(self, data: Dict[str, Any], node_name: str, job_id: int) -> ValidationResult:
        """Validate data from a specific extraction node"""
        try:
            self.logger.debug(f"Validating data for {node_name}", job_id=job_id, node_name=node_name)
            
            errors = []
            warnings = []
            
            # Basic structure validation
            if not isinstance(data, dict):
                errors.append("Data must be a dictionary")
                return ValidationResult(False, errors, warnings, 0.0)
            
            # Node-specific validation
            if node_name == 'node1_basic_info':
                errors.extend(self._validate_node1_data(data))
            elif node_name == 'node2_description':
                errors.extend(self._validate_node2_data(data))
            elif node_name == 'node3_configuration':
                errors.extend(self._validate_node3_data(data))
            elif node_name == 'node4_tenancy':
                errors.extend(self._validate_node4_data(data))
            else:
                warnings.append(f"Unknown node type: {node_name}")
            
            # Calculate completeness score and field scores
            completeness_score, field_scores = self._calculate_completeness_with_fields(data)
            
            is_valid = len(errors) == 0
            
            if not is_valid:
                self.logger.warning(f"Validation failed for {node_name}: {len(errors)} errors", 
                                  job_id=job_id, node_name=node_name)
            
            return ValidationResult(is_valid, errors, warnings, completeness_score, field_scores)
            
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self.logger.error(error_msg, job_id=job_id, node_name=node_name, exc_info=True)
            return ValidationResult(False, [error_msg], [], 0.0)
    
    def merge_node_data(self, node_data: Dict[str, Dict[str, Any]], job_id: int) -> MergeResult:
        """Merge data from all extraction nodes into final structure"""
        try:
            self.logger.info("Starting data merge process", job_id=job_id)
            
            merged_data = {}
            conflicts_found = 0
            conflicts_resolved = 0
            errors = []
            
            # Initialize merged structure
            merged_data = {
                "basic_info": {},
                "location": {},
                "features": [],
                "property_rules": [],
                "safety_and_security": [],
                "description": {},
                "configurations": [],
                "tenancy_data": {}
            }
            
            # Merge Node 1 data (basic info, location, features, rules, safety)
            if 'node1_basic_info' in node_data:
                node1_data = node_data['node1_basic_info']
                if isinstance(node1_data, dict):
                    merged_data["basic_info"] = node1_data.get("basic_info", {})
                    merged_data["location"] = node1_data.get("location", {})
                    merged_data["features"] = node1_data.get("features", []) or []
                    merged_data["property_rules"] = node1_data.get("property_rules", []) or []
                    merged_data["safety_and_security"] = node1_data.get("safety_and_security", []) or []
            
            # Merge Node 2 data (description)
            if 'node2_description' in node_data:
                node2_data = node_data['node2_description']
                if isinstance(node2_data, dict):
                    merged_data["description"] = node2_data.get("description", {}) or {}
            
            # Merge Node 3 data (configurations)
            if 'node3_configuration' in node_data:
                node3_data = node_data['node3_configuration']
                if isinstance(node3_data, dict):
                    merged_data["configurations"] = node3_data.get("configurations", []) or []
            
            # Merge Node 4 data (tenancy details)
            if 'node4_tenancy' in node_data:
                node4_data = node_data['node4_tenancy']
                if isinstance(node4_data, dict):
                    merged_data["tenancy_data"] = node4_data or {}
                    
                    # Resolve conflicts between Node 1 and Node 4 basic info
                    if "property_level" in node4_data:
                        conflicts_found_count, resolved_count = self._resolve_basic_info_conflicts(
                            merged_data["basic_info"], 
                            node4_data["property_level"]
                        )
                        conflicts_found += conflicts_found_count
                        conflicts_resolved += resolved_count

                    # Map Node 4 tenancy options to Node 3 configurations by configuration_id or name
                    try:
                        n4_configs = node4_data.get("configurations", []) if isinstance(node4_data, dict) else []
                        if isinstance(n4_configs, list) and isinstance(merged_data.get("configurations"), list):
                            # Build lookup maps for Node 3 configurations
                            cfg_by_id = {}
                            cfg_by_name = {}

                            def norm_name(s: str) -> str:
                                if not s:
                                    return ""
                                s = str(s).lower().strip()
                                import re as _re
                                s = _re.sub(r"[^a-z0-9]+", "-", s)
                                return s.strip('-')

                            for cfg in merged_data["configurations"]:
                                if not isinstance(cfg, dict):
                                    continue
                                cfg_id = cfg.get("configuration_id")
                                if cfg_id:
                                    cfg_by_id[str(cfg_id)] = cfg
                                # derive name candidates
                                name_candidates = []
                                try:
                                    name_candidates.append(cfg.get("Basic", {}).get("Name"))
                                except Exception:
                                    pass
                                if cfg.get("name"):
                                    name_candidates.append(cfg.get("name"))
                                try:
                                    name_candidates.append(cfg.get("Description", {}).get("Name"))
                                except Exception:
                                    pass
                                for nm in name_candidates:
                                    if nm:
                                        cfg_by_name[norm_name(nm)] = cfg

                            # Attach tenancies
                            for n4 in n4_configs:
                                if not isinstance(n4, dict):
                                    continue
                                target = None
                                # Prefer configuration_id match
                                n4_id = n4.get("configuration_id")
                                if n4_id and str(n4_id) in cfg_by_id:
                                    target = cfg_by_id[str(n4_id)]
                                else:
                                    # Match by normalized name
                                    n4_name = n4.get("name")
                                    if not n4_name:
                                        # try nested names
                                        try:
                                            n4_name = n4.get("Basic", {}).get("Name")
                                        except Exception:
                                            pass
                                    key = norm_name(n4_name) if n4_name else ""
                                    if key and key in cfg_by_name:
                                        target = cfg_by_name[key]

                                if not target:
                                    continue

                                # Get tenancy options from Node 4 structure
                                tenancies = None
                                if isinstance(n4.get("tenancy_options"), list):
                                    tenancies = n4.get("tenancy_options")
                                elif isinstance(n4.get("tenancies"), list):
                                    tenancies = n4.get("tenancies")
                                if not isinstance(tenancies, list):
                                    continue

                                # Ensure target has tenancy_options list
                                if not isinstance(target.get("tenancy_options"), list):
                                    target["tenancy_options"] = []
                                # Extend and deduplicate
                                existing = target["tenancy_options"]
                                seen = set()
                                def tenancy_key(t: Dict[str, Any]) -> str:
                                    tlw = t.get("tenancy_length_weeks")
                                    tl = t.get("tenancy_length")
                                    base = str(tlw) if tlw is not None else str(tl or "")
                                    price = t.get("price_per_week") or t.get("price") or ""
                                    return f"{base}|{price}"

                                for t in existing:
                                    if isinstance(t, dict):
                                        seen.add(tenancy_key(t))
                                for t in tenancies:
                                    if not isinstance(t, dict):
                                        continue
                                    key = tenancy_key(t)
                                    if key in seen:
                                        continue
                                    seen.add(key)
                                    existing.append(t)

                            # Recompute base min/max price per configuration from tenancy options
                            for cfg in merged_data["configurations"]:
                                if not isinstance(cfg, dict):
                                    continue
                                ten_opts = cfg.get("tenancy_options")
                                if not isinstance(ten_opts, list) or not ten_opts:
                                    continue
                                prices = []
                                for t in ten_opts:
                                    if not isinstance(t, dict):
                                        continue
                                    val = t.get("price_per_week")
                                    try:
                                        if val is not None:
                                            prices.append(float(val))
                                    except Exception:
                                        continue
                                if prices:
                                    min_p = min(prices)
                                    max_p = max(prices)
                                    # Write back to Node 3 Pricing section if available
                                    pr = cfg.get("Pricing") if isinstance(cfg.get("Pricing"), dict) else None
                                    if pr is None:
                                        pr = {}
                                        cfg["Pricing"] = pr
                                    pr["Min Price"] = str(min_p)
                                    pr["Max Price"] = str(max_p)
                    except Exception:
                        pass
            
            # Augment features with additional sources for better inclusion
            try:
                merged_data["features"] = self._augment_features(merged_data)
            except Exception:
                pass
            
            # Fill missing location fields from Node 4 property_level if available
            try:
                merged_data["location"] = self._augment_location(merged_data)
            except Exception:
                pass
            
            # Post-processing and cleanup
            merged_data = self._clean_merged_data(merged_data)
            
            # Calculate quality score
            quality_score = self._calculate_merge_quality_score(merged_data, node_data)
            
            self.logger.log_data_merge(job_id, conflicts_found, conflicts_resolved)
            
            return MergeResult(
                success=True,
                merged_data=merged_data,
                conflicts_found=conflicts_found,
                conflicts_resolved=conflicts_resolved,
                errors=errors,
                quality_score=quality_score
            )
            
        except Exception as e:
            error_msg = f"Data merge failed: {str(e)}"
            self.logger.error(error_msg, job_id=job_id, exc_info=True)
            
            return MergeResult(
                success=False,
                merged_data=None,
                conflicts_found=0,
                conflicts_resolved=0,
                errors=[error_msg],
                quality_score=0.0
            )
    
    def transform_for_export(self, merged_data: Dict[str, Any], export_format: str = "standard") -> Dict[str, Any]:
        """Transform merged data for export to external systems"""
        try:
            if export_format == "standard":
                return self._transform_to_standard_format(merged_data)
            elif export_format == "airtable":
                return self._transform_to_airtable_format(merged_data)
            elif export_format == "crm":
                return self._transform_to_crm_format(merged_data)
            else:
                return merged_data
                
        except Exception as e:
            self.logger.error(f"Export transformation failed: {str(e)}", exc_info=True)
            return merged_data
    
    def _validate_node1_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate Node 1 specific data structure"""
        errors = []
        
        # Validate basic_info
        if 'basic_info' in data:
            basic_info_errors = self.validator.validate_basic_info(data['basic_info'])
            errors.extend([f"basic_info.{error}" for error in basic_info_errors])
        
        # Validate location
        if 'location' in data:
            location_errors = self.validator.validate_location(data['location'])
            errors.extend([f"location.{error}" for error in location_errors])
        
        # Validate features
        if 'features' in data:
            feature_errors = self.validator.validate_features(data['features'])
            errors.extend([f"features.{error}" for error in feature_errors])
        
        # Validate property rules
        if 'property_rules' in data:
            rules_errors = self.validator.validate_features(data['property_rules'])
            errors.extend([f"property_rules.{error}" for error in rules_errors])
        
        # Validate safety and security
        if 'safety_and_security' in data:
            safety_errors = self.validator.validate_features(data['safety_and_security'])
            errors.extend([f"safety_and_security.{error}" for error in safety_errors])
        
        return errors
    
    def _validate_node2_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate Node 2 specific data structure"""
        errors = []
        
        if 'description' not in data:
            errors.append("Missing 'description' section")
            return errors
        
        description = data['description']
        if not isinstance(description, dict):
            errors.append("Description must be a dictionary")
            return errors
        
        # Validate email format if present
        if 'email' in description and description['email']:
            if not self.validator.validate_email(description['email']):
                errors.append("Invalid email format")
        
        # Validate FAQs structure
        if 'faqs' in description and description['faqs']:
            if not isinstance(description['faqs'], list):
                errors.append("FAQs must be a list")
            else:
                for i, faq in enumerate(description['faqs']):
                    if not isinstance(faq, dict):
                        errors.append(f"FAQ {i} must be a dictionary")
                    elif 'question' not in faq or 'answer' not in faq:
                        errors.append(f"FAQ {i} must have 'question' and 'answer' fields")
        
        return errors
    
    def _validate_node3_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate Node 3 specific data structure"""
        errors = []
        
        if 'configurations' not in data:
            errors.append("Missing 'configurations' section")
            return errors
        
        configurations = data['configurations']
        if not isinstance(configurations, list):
            errors.append("Configurations must be a list")
            return errors
        
        for i, config in enumerate(configurations):
            if not isinstance(config, dict):
                errors.append(f"Configuration {i} must be a dictionary")
                continue
            
            # Validate required sections
            required_sections = ['Basic', 'Source Details', 'Pricing']
            for section in required_sections:
                if section not in config:
                    errors.append(f"Configuration {i} missing '{section}' section")
        
        return errors
    
    def _validate_node4_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate Node 4 specific data structure"""
        errors = []
        
        # Validate property level data
        if 'property_level' in data:
            property_level = data['property_level']
            if not isinstance(property_level, dict):
                errors.append("Property level data must be a dictionary")
        
        # Validate configurations
        if 'configurations' in data:
            configurations = data['configurations']
            if not isinstance(configurations, list):
                errors.append("Configurations must be a list")
            else:
                for i, config in enumerate(configurations):
                    if not isinstance(config, dict):
                        errors.append(f"Configuration {i} must be a dictionary")
                        continue
                    
                    # Validate tenancy options
                    if 'tenancy_options' in config:
                        tenancy_options = config['tenancy_options']
                        if not isinstance(tenancy_options, list):
                            errors.append(f"Configuration {i} tenancy_options must be a list")
                        else:
                            for j, opt in enumerate(tenancy_options):
                                if not isinstance(opt, dict):
                                    errors.append(f"Configuration {i} tenancy_options[{j}] must be a dictionary")
                                    continue
                                # If standardized fields are present, check their types
                                if 'tenancy_length_weeks' in opt and not isinstance(opt['tenancy_length_weeks'], int):
                                    errors.append(f"Configuration {i} tenancy_options[{j}].tenancy_length_weeks must be int")
                                for k in ['price_per_week', 'price_total']:
                                    if k in opt and not isinstance(opt[k], (int, float)):
                                        errors.append(f"Configuration {i} tenancy_options[{j}].{k} must be number")
        
        return errors
    
    def _calculate_completeness_with_fields(self, data: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """Calculate overall completeness and per-field presence ratio map."""
        try:
            totals: Dict[str, int] = {}
            filled: Dict[str, int] = {}

            def count(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        field_path = f"{path}.{key}" if path else key
                        totals[field_path] = totals.get(field_path, 0) + 1
                        if value is not None and str(value).strip() != "":
                            filled[field_path] = filled.get(field_path, 0) + 1
                        if isinstance(value, (dict, list)):
                            count(value, field_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        field_path = f"{path}[{i}]" if path else f"[{i}]"
                        if isinstance(item, (dict, list)):
                            count(item, field_path)
                        else:
                            totals[field_path] = totals.get(field_path, 0) + 1
                            if item is not None and str(item).strip() != "":
                                filled[field_path] = filled.get(field_path, 0) + 1

            count(data)

            overall_total = sum(totals.values())
            overall_filled = sum(filled.values())
            overall = (overall_filled / overall_total) if overall_total > 0 else 0.0
            # Build normalized per-field scores (0/1 presence)
            field_scores = {k: (1.0 if k in filled else 0.0) for k in totals.keys()}
            return overall, field_scores
        except Exception:
            return 0.0, {}
    
    def _resolve_basic_info_conflicts(self, node1_basic_info: Dict[str, Any], 
                                    node4_property_level: Dict[str, Any]) -> Tuple[int, int]:
        """Resolve conflicts between Node 1 and Node 4 basic info"""
        conflicts_found = 0
        conflicts_resolved = 0
        
        # Compare and resolve conflicts for common fields
        common_fields = ['name', 'guarantor_required', 'source', 'source_link']
        
        for field in common_fields:
            node1_value = node1_basic_info.get(field, "")
            node4_value = node4_property_level.get(field, "")
            
            if node1_value and node4_value and node1_value != node4_value:
                conflicts_found += 1
                
                # Resolution strategy: prefer Node 1 data (more specific extraction)
                # but use Node 4 if Node 1 is empty
                if not node1_value.strip():
                    node1_basic_info[field] = node4_value
                    conflicts_resolved += 1
                else:
                    conflicts_resolved += 1  # Keep Node 1 value
        
        return conflicts_found, conflicts_resolved
    
    def _clean_merged_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and normalize merged data"""
        try:
            # Normalize configuration names and sort arrays for stable comparisons
            def normalize_name(name: Any) -> str:
                return str(name).strip().lower() if name is not None else ""

            if isinstance(data, dict):
                cfgs = data.get('configurations')
                if isinstance(cfgs, list):
                    for cfg in cfgs:
                        if isinstance(cfg, dict):
                            n = cfg.get('name') or cfg.get('Basic', {}).get('Configuration Name')
                            if n:
                                cfg['name'] = str(n).strip()
                            # Sort tenancies by normalized duration if present
                            tens = cfg.get('tenancies')
                            if isinstance(tens, list):
                                try:
                                    cfg['tenancies'] = sorted(
                                        tens,
                                        key=lambda t: (t.get('duration_months') or 0, str(t.get('duration') or ''))
                                    )
                                except Exception:
                                    pass
                    try:
                        data['configurations'] = sorted(cfgs, key=lambda c: normalize_name(c.get('name')))
                    except Exception:
                        pass
            # Remove empty strings and null values
            def clean_dict(obj):
                if isinstance(obj, dict):
                    cleaned = {}
                    for key, value in obj.items():
                        if value is not None and value != "":
                            cleaned_value = clean_dict(value)
                            if cleaned_value is not None and cleaned_value != "":
                                cleaned[key] = cleaned_value
                    return cleaned if cleaned else None
                elif isinstance(obj, list):
                    cleaned = []
                    for item in obj:
                        cleaned_item = clean_dict(item)
                        if cleaned_item is not None:
                            cleaned.append(cleaned_item)
                    return cleaned if cleaned else None
                else:
                    return obj if obj and str(obj).strip() else None
            
            return clean_dict(data) or {}
            
        except Exception as e:
            self.logger.error(f"Data cleaning failed: {str(e)}", exc_info=True)
            return data
    
    def _calculate_merge_quality_score(self, merged_data: Dict[str, Any], 
                                     node_data: Dict[str, Dict[str, Any]]) -> float:
        """Calculate overall quality score for merged data"""
        try:
            scores = []
            
            # Data completeness score
            completeness, _ = self._calculate_completeness_with_fields(merged_data)
            scores.append(('completeness', completeness, 0.4))
            
            # Node coverage score (how many nodes contributed data)
            contributing_nodes = sum(1 for node, data in node_data.items() if data)
            coverage = contributing_nodes / 4.0  # 4 total nodes
            scores.append(('coverage', coverage, 0.3))
            
            # Data consistency score (fewer conflicts = higher score)
            consistency = 0.9  # Default high consistency score
            scores.append(('consistency', consistency, 0.3))
            
            # Calculate weighted average
            total_weight = sum(weight for _, _, weight in scores)
            weighted_sum = sum(score * weight for _, score, weight in scores)
            
            return weighted_sum / total_weight if total_weight > 0 else 0.0
            
        except Exception:
            return 0.5  # Default moderate score
    
    def _transform_to_standard_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform to standard export format"""
        return data  # Already in standard format
    
    def _transform_to_airtable_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform to Airtable-compatible format"""
        try:
            # Flatten nested structures for Airtable
            flattened = {}
            
            # Basic info
            if 'basic_info' in data:
                for key, value in data['basic_info'].items():
                    flattened[f"basic_{key}"] = value
            
            # Location
            if 'location' in data:
                for key, value in data['location'].items():
                    flattened[f"location_{key}"] = value
            
            # Features as comma-separated string
            if 'features' in data:
                feature_names = [f.get('name', '') for f in data['features'] if f.get('name')]
                flattened['features'] = ', '.join(feature_names)
            
            # Description fields
            if 'description' in data:
                for key, value in data['description'].items():
                    if key != 'faqs':  # Skip complex nested structures
                        flattened[f"desc_{key}"] = value
            
            return flattened
            
        except Exception as e:
            self.logger.error(f"Airtable transformation failed: {str(e)}", exc_info=True)
            return data
    
    def _transform_to_crm_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform to CRM-compatible format"""
        try:
            # Create CRM-friendly structure
            crm_data = {
                'property_name': data.get('basic_info', {}).get('name', ''),
                'property_source': data.get('basic_info', {}).get('source', ''),
                'property_url': data.get('basic_info', {}).get('source_link', ''),
                'location': data.get('location', {}).get('location_name', ''),
                'region': data.get('location', {}).get('region', ''),
                'coordinates': {
                    'lat': data.get('location', {}).get('latitude', ''),
                    'lng': data.get('location', {}).get('longitude', '')
                },
                'guarantor_required': data.get('basic_info', {}).get('guarantor_required', ''),
                'contact_email': data.get('description', {}).get('email', ''),
                'description': data.get('description', {}).get('about', ''),
                'features_count': len(data.get('features', [])),
                'configurations_count': len(data.get('configurations', [])),
                'last_updated': None  # Will be set by the system
            }
            
            return crm_data
            
        except Exception as e:
            self.logger.error(f"CRM transformation failed: {str(e)}", exc_info=True)
            return data

    def _augment_features(self, merged: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Combine features from Node 1, description, and configurations. Deduplicate by name."""
        combined: List[Dict[str, Any]] = []
        seen: set[str] = set()
        
        def push(name: str, ftype: str = ""):
            key = (name or "").strip().lower()
            if not key or key in seen:
                return
            seen.add(key)
            item = {"name": name}
            if ftype:
                item["type"] = ftype
            combined.append(item)
        
        # From Node 1 features
        for f in merged.get("features", []) or []:
            if isinstance(f, dict):
                nm = f.get("name") or f.get("Description") or f.get("feature") or ""
                tp = f.get("type") or f.get("Type") or ""
                if nm:
                    push(str(nm), str(tp))
            elif isinstance(f, str):
                push(f)
        
        # From Node 2 description.features
        desc = merged.get("description", {}) or {}
        desc_feats = desc.get("features")
        if isinstance(desc_feats, str):
            parts = [p.strip() for p in desc_feats.replace("\n", ",").split(",") if p.strip()]
            for p in parts:
                push(p)
        elif isinstance(desc_feats, list):
            for f in desc_feats:
                if isinstance(f, str):
                    push(f)
                elif isinstance(f, dict):
                    nm = f.get("name") or f.get("Description") or f.get("feature") or ""
                    if nm:
                        push(str(nm))
        
        # From configurations (Node 3 / Node 4)
        for cfg in merged.get("configurations", []) or []:
            if not isinstance(cfg, dict):
                continue
            # features (flat) or Features (array of dicts)
            if isinstance(cfg.get("features"), list):
                for f in cfg["features"]:
                    if isinstance(f, str):
                        push(f)
                    elif isinstance(f, dict):
                        nm = f.get("name") or f.get("Description") or f.get("feature") or ""
                        if nm:
                            push(str(nm))
            if isinstance(cfg.get("Features"), list):
                for f in cfg["Features"]:
                    if isinstance(f, str):
                        push(f)
                    elif isinstance(f, dict):
                        nm = f.get("name") or f.get("Description") or f.get("feature") or ""
                        tp = f.get("Type") or f.get("type") or ""
                        if nm:
                            push(str(nm), str(tp))
        
        return combined

    def _augment_location(self, merged: Dict[str, Any]) -> Dict[str, Any]:
        """Fill missing location fields from tenancy_data.property_level where sensible."""
        loc = merged.get("location", {}) or {}
        prop_level = merged.get("tenancy_data", {}).get("property_level", {}) or {}
        
        def choose(a, b):
            return a if (a is not None and str(a).strip() != "") else b
        
        return {
            "location_name": choose(loc.get("location_name"), prop_level.get("location_name") or prop_level.get("name")),
            "address": choose(loc.get("address"), prop_level.get("address")),
            "city": choose(loc.get("city"), prop_level.get("city") or prop_level.get("region")),
            "region": choose(loc.get("region"), prop_level.get("region")),
            "country": choose(loc.get("country"), prop_level.get("country")),
            "latitude": choose(loc.get("latitude"), prop_level.get("latitude")),
            "longitude": choose(loc.get("longitude"), prop_level.get("longitude")),
        }

def get_data_processor() -> PropertyDataProcessor:
    """Get the data processor instance"""
    return PropertyDataProcessor()

