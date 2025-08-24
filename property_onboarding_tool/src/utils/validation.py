import re
import validators
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
import json

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class PropertyDataValidator:
    """Validator for property extraction data"""
    
    # Predefined dropdown values for features (from the requirements)
    ALLOWED_FEATURE_TYPES = {
        "Air Conditioner & Heating", "Balcony or Patios", "Barbeque & Grill", "Business Center", 
        "Cafe & Restaurant", "Fan", "Cinema Room", "Clubhouse", "Courtyard", "Disability Access", 
        "Fireplace", "Tile Flooring", "Wooden Flooring", "Carpet Flooring", "Food & Meals", 
        "Garbage Disposal", "Gas Stove", "Gym & Fitness", "Prayer Room", "Internet Access", 
        "Wifi", "Jogging", "Kitchen with Appliance", "Laundry Facility", "Library & Study Area", 
        "Lounge", "Maintenance", "Medical Facility", "Microwave", "Parking", "Electronic Payments", 
        "Pet Friendly", "Playground", "Snow Removal", "Social Events", "Spa & Salon", "Sport Golf", 
        "Room Storage", "Swimming Pool", "Television", "Sports", "Pets Not Allowed", "Blinds", 
        "Telephone", "Breakfast Bar", "Home Linen", "Industry Accreditation & Awards", 
        "Common Social Area", "Unfurnished Accommodations", "Mattress", "Games Area", 
        "Household Supplies", "Sundeck", "Vending Machine", "Bean Bag", "Terrace", "Noticeboard", 
        "Property Rules", "Content Insurance", "Ironing Facility", "Flatmate", "Alarm Clock", 
        "Classroom", "Den", "Newly Refurbished", "Fire Extinguisher", "Coffee Machine", 
        "Basic Essentials", "Parcel Collection", "Location Benefit", "Dining Area", 
        "Locker & Safes", "Shuttle & Cab Service", "Shops", "Electric Vehicle Charging Station", 
        "Double Occupancy", "Guarantor Requirement", "Reception & Staff", "Common Service", 
        "Fully Furnished", "Fridge", "Accommodation Features", "Bathroom", "Others"
    }
    
    # Guarantor requirement options
    GUARANTOR_OPTIONS = {
        "No guarantor required",
        "International and local guarantors allowed", 
        "Local guarantor only (third party guarantor service not allowed)",
        "Local guarantor only (third party guarantor service allowed)",
        "Information unavailable"
    }
    
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, Optional[str]]:
        """Validate URL format and accessibility"""
        if not url or not isinstance(url, str):
            return False, "URL must be a non-empty string"
        
        url = url.strip()
        
        # More lenient URL validation
        try:
            parsed = urlparse(url)
            
            # Basic checks
            if not parsed.scheme in ['http', 'https']:
                return False, "URL must use HTTP or HTTPS protocol"
            
            if not parsed.netloc:
                return False, "URL must have a valid domain"
            
            # Check if domain looks reasonable (at least has a dot)
            if '.' not in parsed.netloc:
                return False, "URL must have a valid domain with at least one dot"
            
            return True, None
            
        except Exception as e:
            return False, f"URL parsing error: {str(e)}"
    
    @staticmethod
    def validate_basic_info(data: Dict[str, Any]) -> List[str]:
        """Validate basic info data structure"""
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Basic info data must be a dictionary")
            return errors
        
        # Check required fields
        required_fields = ['name', 'guarantor_required', 'source', 'source_link']
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif not data[field] or not isinstance(data[field], str):
                errors.append(f"Field '{field}' must be a non-empty string")
        
        # Validate guarantor requirement
        if 'guarantor_required' in data:
            if data['guarantor_required'] not in PropertyDataValidator.GUARANTOR_OPTIONS:
                errors.append(f"Invalid guarantor requirement: {data['guarantor_required']}")
        
        # Validate source link
        if 'source_link' in data and data['source_link']:
            is_valid, error = PropertyDataValidator.validate_url(data['source_link'])
            if not is_valid:
                errors.append(f"Invalid source link: {error}")
        
        return errors
    
    @staticmethod
    def validate_location(data: Dict[str, Any]) -> List[str]:
        """Validate location data structure"""
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Location data must be a dictionary")
            return errors
        
        # Check location name
        if 'location_name' in data and data['location_name']:
            if not isinstance(data['location_name'], str):
                errors.append("Location name must be a string")
        
        # Validate coordinates
        if 'latitude' in data and data['latitude']:
            try:
                lat = float(data['latitude'])
                if not -90 <= lat <= 90:
                    errors.append("Latitude must be between -90 and 90")
            except (ValueError, TypeError):
                errors.append("Latitude must be a valid number")
        
        if 'longitude' in data and data['longitude']:
            try:
                lng = float(data['longitude'])
                if not -180 <= lng <= 180:
                    errors.append("Longitude must be between -180 and 180")
            except (ValueError, TypeError):
                errors.append("Longitude must be a valid number")
        
        # Validate region format
        if 'region' in data and data['region']:
            if not isinstance(data['region'], str):
                errors.append("Region must be a string")
        
        return errors
    
    @staticmethod
    def validate_features(features: List[Dict[str, Any]]) -> List[str]:
        """Validate features list"""
        errors = []
        
        if not isinstance(features, list):
            errors.append("Features must be a list")
            return errors
        
        for i, feature in enumerate(features):
            if not isinstance(feature, dict):
                errors.append(f"Feature {i} must be a dictionary")
                continue
            
            # Check required fields
            if 'type' not in feature:
                errors.append(f"Feature {i} missing 'type' field")
            elif feature['type'] not in PropertyDataValidator.ALLOWED_FEATURE_TYPES:
                errors.append(f"Feature {i} has invalid type: {feature['type']}")
            
            if 'name' not in feature:
                errors.append(f"Feature {i} missing 'name' field")
            elif not isinstance(feature['name'], str) or not feature['name'].strip():
                errors.append(f"Feature {i} 'name' must be a non-empty string")
        
        return errors
    
    @staticmethod
    def validate_pricing(pricing: Dict[str, Any]) -> List[str]:
        """Validate pricing data"""
        errors = []
        
        if not isinstance(pricing, dict):
            errors.append("Pricing data must be a dictionary")
            return errors
        
        # Validate numeric fields
        numeric_fields = ['Price', 'Min Price', 'Max Price', 'Deposit', 'Min Deposit Amount', 'Max Deposit Amount']
        for field in numeric_fields:
            if field in pricing and pricing[field]:
                # Allow string representation of numbers
                if isinstance(pricing[field], str):
                    # Remove currency symbols and whitespace
                    cleaned = re.sub(r'[£$€¥,\s]', '', pricing[field])
                    try:
                        float(cleaned)
                    except ValueError:
                        errors.append(f"Pricing field '{field}' must be a valid number")
                elif not isinstance(pricing[field], (int, float)):
                    errors.append(f"Pricing field '{field}' must be a number")
        
        # Validate currency
        if 'Price Currency' in pricing and pricing['Price Currency']:
            if not isinstance(pricing['Price Currency'], str):
                errors.append("Price Currency must be a string")
        
        return errors
    
    @staticmethod
    def validate_json_structure(data: Any, schema_name: str) -> List[str]:
        """Validate JSON structure against expected format"""
        errors = []
        
        try:
            if isinstance(data, str):
                data = json.loads(data)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON format for {schema_name}: {str(e)}")
            return errors
        
        if not isinstance(data, dict):
            errors.append(f"{schema_name} must be a JSON object")
            return errors
        
        return errors
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        if not email or not isinstance(email, str):
            return False
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email.strip()))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format"""
        if not phone or not isinstance(phone, str):
            return False
        
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
        
        # Check if it's all digits and reasonable length
        return cleaned.isdigit() and 7 <= len(cleaned) <= 15
    
    @staticmethod
    def validate_date_format(date_str: str) -> bool:
        """Validate date string format"""
        if not date_str or not isinstance(date_str, str):
            return False
        
        # Common date formats
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
            r'^\d{2}/\d{2}/\d{4}$',  # MM/DD/YYYY
            r'^\d{2}-\d{2}-\d{4}$',  # MM-DD-YYYY
            r'^\d{1,2}\s+\w+\s+\d{4}$',  # D Month YYYY
        ]
        
        return any(re.match(pattern, date_str.strip()) for pattern in date_patterns)
    
    @staticmethod
    def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
        """Sanitize text input"""
        if not text or not isinstance(text, str):
            return ""
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', text.strip())
        
        # Remove potentially harmful characters
        sanitized = re.sub(r'[<>"\']', '', sanitized)
        
        # Truncate if necessary
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length].strip()
        
        return sanitized
    
    @staticmethod
    def validate_complete_extraction(data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate complete extraction data"""
        validation_results = {
            'basic_info': [],
            'location': [],
            'features': [],
            'property_rules': [],
            'safety_and_security': [],
            'description': [],
            'configurations': [],
            'general': []
        }
        
        if not isinstance(data, dict):
            validation_results['general'].append("Extraction data must be a dictionary")
            return validation_results
        
        # Validate basic info
        if 'basic_info' in data:
            validation_results['basic_info'] = PropertyDataValidator.validate_basic_info(data['basic_info'])
        
        # Validate location
        if 'location' in data:
            validation_results['location'] = PropertyDataValidator.validate_location(data['location'])
        
        # Validate features
        if 'features' in data:
            validation_results['features'] = PropertyDataValidator.validate_features(data['features'])
        
        # Validate property rules
        if 'property_rules' in data:
            validation_results['property_rules'] = PropertyDataValidator.validate_features(data['property_rules'])
        
        # Validate safety and security
        if 'safety_and_security' in data:
            validation_results['safety_and_security'] = PropertyDataValidator.validate_features(data['safety_and_security'])
        
        return validation_results

def validate_extraction_job_data(job_data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
    """Validate extraction job data and return validation results"""
    validator = PropertyDataValidator()
    validation_results = validator.validate_complete_extraction(job_data)
    
    # Check if there are any errors
    has_errors = any(errors for errors in validation_results.values())
    
    return not has_errors, validation_results

