import re
import time
from urllib.parse import urljoin, urlparse, urlunparse
from typing import List, Dict, Set, Tuple, Any

import requests
from bs4 import BeautifulSoup


DEFAULT_USER_AGENT = "PropertyOnboardingBot/1.0 (+https://example.com)"


def _is_same_domain(base_url: str, target_url: str) -> bool:
    try:
        b = urlparse(base_url)
        t = urlparse(target_url)
        return (t.netloc or b.netloc) == b.netloc
    except Exception:
        return False


def _is_allowed_domain(base_url: str, target_url: str, extra_allowed: List[str] | None) -> bool:
    """Return True if target is same-domain as base OR its host matches any in extra_allowed.
    Matching for extras is suffix-based to allow subdomains, e.g., help.example.com for example.com
    """
    if _is_same_domain(base_url, target_url):
        return True
    if not extra_allowed:
        return False
    try:
        host = (urlparse(target_url).netloc or '').lower()
        for pattern in extra_allowed:
            p = (pattern or '').strip().lower()
            if not p:
                continue
            if host == p or host.endswith('.' + p):
                return True
    except Exception:
        return False
    return False


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract structured data if available (JSON-LD, microdata)
    structured_data = ""
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            structured_data += "\n\n[STRUCTURED DATA]\n" + script.string + "\n[END STRUCTURED DATA]\n\n"
        except Exception:
            pass
    
    # Extract map coordinates from JavaScript (high priority for Node 1)
    map_coordinates = ""
    for script in soup.find_all("script"):
        if script.string:
            script_content = script.string
            # Look for common map initializers
            map_patterns = [
                # Google Maps
                r'google\.maps\.LatLng\(([-\d.]+),\s*([-\d.]+)\)',
                r'center:\s*\{lat:\s*([-\d.]+),\s*lng:\s*([-\d.]+)\}',
                r'position:\s*\{lat:\s*([-\d.]+),\s*lng:\s*([-\d.]+)\}',
                # Mapbox
                r'center:\s*\[([-\d.]+),\s*([-\d.]+)\]',
                r'coordinates:\s*\[([-\d.]+),\s*([-\d.]+)\]',
                # Leaflet
                r'setView\(\[([-\d.]+),\s*([-\d.]+)\]',
                # Generic coordinate patterns
                r'lat(?:itude)?["\']?\s*:\s*([-\d.]+)[,;]\s*lng|long(?:itude)?["\']?\s*:\s*([-\d.]+)',
                r'["\']lat["\']\s*:\s*([-\d.]+)[,;]\s*["\']lng["\']\s*:\s*([-\d.]+)',
            ]
            
            for pattern in map_patterns:
                matches = re.findall(pattern, script_content, re.IGNORECASE)
                for match in matches:
                    if len(match) >= 2:
                        lat, lng = match[0], match[1]
                        # Validate coordinates
                        try:
                            lat_f, lng_f = float(lat), float(lng)
                            if -90 <= lat_f <= 90 and -180 <= lng_f <= 180:
                                map_coordinates += f"\n\n[MAP COORDINATES]\nLatitude: {lat}\nLongitude: {lng}\n[END MAP COORDINATES]\n\n"
                                break  # Found valid coordinates, move to next script
                        except ValueError:
                            continue
    
    # Extract location data from HTML meta tags and data attributes
    location_meta = ""
    
    # Open Graph and standard meta tags
    meta_tags = [
        ('og:latitude', 'latitude'),
        ('og:longitude', 'longitude'),
        ('geo.position', 'position'),
        ('geo.region', 'region'),
        ('geo.placename', 'placename'),
        ('geo.country', 'country'),
        ('og:locality', 'locality'),
        ('og:region', 'region'),
        ('og:country-name', 'country'),
        ('og:street-address', 'street_address'),
        ('og:postal-code', 'postal_code'),
    ]
    
    for meta_name, field_name in meta_tags:
        meta_elem = soup.find('meta', {'property': meta_name}) or soup.find('meta', {'name': meta_name})
        if meta_elem and meta_elem.get('content'):
            location_meta += f"{field_name}: {meta_elem['content']}\n"
    
    # Data attributes for coordinates
    for elem in soup.find_all(attrs={'data-lat': True, 'data-lng': True}):
        lat = elem.get('data-lat')
        lng = elem.get('data-lng')
        if lat and lng:
            try:
                lat_f, lng_f = float(lat), float(lng)
                if -90 <= lat_f <= 90 and -180 <= lng_f <= 180:
                    location_meta += f"data_latitude: {lat}\ndata_longitude: {lng}\n"
            except ValueError:
                pass
    
    # Extract address information from structured elements
    address_info = ""
    address_selectors = [
        'address', '[itemtype*="PostalAddress"]', '[itemtype*="Place"]',
        '.address', '.location', '.property-address', '.contact-address'
    ]
    
    for selector in address_selectors:
        for elem in soup.select(selector):
            if elem.get_text(strip=True):
                address_info += f"\n[ADDRESS INFO]\n{elem.get_text(' ', strip=True)}\n[END ADDRESS INFO]\n"
    
    # Extract property type and classification information
    property_info = ""
    
    # Look for property type in meta tags and structured data
    property_type_selectors = [
        'meta[property="og:type"]',
        'meta[name="property-type"]',
        'meta[name="accommodation-type"]',
        '[data-property-type]',
        '[data-accommodation-type]'
    ]
    
    for selector in property_type_selectors:
        for elem in soup.select(selector):
            if elem.get('content') or elem.get('data-property-type') or elem.get('data-accommodation-type'):
                value = elem.get('content') or elem.get('data-property-type') or elem.get('data-accommodation-type')
                if value:
                    property_info += f"\n[PROPERTY TYPE]\n{value}\n[END PROPERTY TYPE]\n"
                    break
    
    # Look for property type in text patterns
    property_type_patterns = [
        r'student\s+accommodation',
        r'residential\s+(?:accommodation|property)',
        r'purpose\s+built\s+student\s+residence',
        r'student\s+residence',
        r'student\s+housing',
        r'student\s+apartments',
        r'student\s+flats'
    ]
    
    for pattern in property_type_patterns:
        if re.search(pattern, text.lower()):
            property_info += f"\n[PROPERTY TYPE]\nStudent Accommodation\n[END PROPERTY TYPE]\n"
            break
    
    # Extract contact information
    contact_info = ""
    
    # Phone number patterns (UK and international)
    phone_patterns = [
        r'\+44\s*\d{1,4}\s*\d{1,4}\s*\d{1,4}',
        r'\(0\)\d{1,4}\s*\d{1,4}\s*\d{1,4}',
        r'0\d{1,4}\s*\d{1,4}\s*\d{1,4}',
        r'07\d{3}\s*\d{3}\s*\d{3}',
        r'01\d{3}\s*\d{3}\s*\d{3}',
        r'02\d{3}\s*\d{3}\s*\d{3}'
    ]
    
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            contact_info += f"\n[CONTACT INFO]\nPhone: {match}\n[END CONTACT INFO]\n"
            break  # Only add first phone number found
    
    # Look for contact sections
    contact_selectors = [
        '.contact', '.contact-info', '.contact-details', '.get-in-touch',
        '.phone', '.telephone', '.call-us', '.contact-us'
    ]
    
    for selector in contact_selectors:
        for elem in soup.select(selector):
            if elem.get_text(strip=True):
                contact_info += f"\n[CONTACT INFO]\n{elem.get_text(' ', strip=True)}\n[END CONTACT INFO]\n"
                break

    # Heading-aware section extraction
    heading_sections = ""
    try:
        headings = soup.find_all(['h1','h2','h3','h4'])
        for idx, h in enumerate(headings):
            title = h.get_text(" ", strip=True)
            if not title:
                continue
            content_parts = []
            for sib in h.next_siblings:
                if getattr(sib, 'name', None) in ['h1','h2','h3','h4']:
                    break
                # Skip scripts/styles
                if getattr(sib, 'name', None) in ['script','style','noscript']:
                    continue
                txt = sib.get_text(" ", strip=True) if getattr(sib, 'get_text', None) else str(sib).strip()
                if txt:
                    content_parts.append(txt)
            section_text = " ".join(content_parts)
            if len(section_text) > 80:
                heading_sections += f"\n[HEADING_SECTION title=\"{title}\"]\n{section_text}\n[END HEADING_SECTION]\n"
    except Exception:
        pass

    # Enhanced multi-tab/accordion/widget content extraction
    widget_sections = _extract_widget_sections(soup)
    
    # Enhanced JavaScript and hidden content extraction
    js_content = _extract_javascript_content(soup)
    
    # Enhanced structured data extraction
    enhanced_structured_data = _extract_structured_data(soup)
    
    # Extract structured data from tables (high priority for pricing, features, etc.)
    table_data = ""
    for table in soup.find_all('table'):
        try:
            table_text = ""
            rows = table.find_all(['tr'])
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    row_data = []
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if cell_text:
                            row_data.append(cell_text)
                    if row_data:
                        table_text += " | ".join(row_data) + "\n"
            
            if table_text.strip():
                # Try to identify table type based on content
                table_type = "general"
                if any(word in table_text.lower() for word in ['price', 'cost', 'rent', 'fee', 'deposit']):
                    table_type = "pricing"
                elif any(word in table_text.lower() for word in ['feature', 'amenity', 'facility', 'included']):
                    table_type = "features"
                elif any(word in table_text.lower() for word in ['date', 'start', 'end', 'duration', 'term']):
                    table_type = "tenancy"
                
                table_data += f"\n[TABLE: {table_type.upper()}]\n{table_text.strip()}\n[END TABLE]\n"
        except Exception:
            continue
    
    # Extract structured data from lists (features, amenities, rules, etc.)
    list_data = ""
    list_selectors = [
        'ul', 'ol', 'dl'
    ]
    
    for selector in list_selectors:
        for elem in soup.select(selector):
            try:
                if selector in ['ul', 'ol']:
                    items = elem.find_all('li')
                    if items:
                        list_text = ""
                        for item in items:
                            item_text = item.get_text(strip=True)
                            if item_text:
                                list_text += f"• {item_text}\n"
                        
                        if list_text.strip():
                            # Identify list type
                            list_type = "general"
                            parent_text = elem.get_text(strip=True).lower()
                            if any(word in parent_text for word in ['feature', 'amenity', 'facility', 'included']):
                                list_type = "features"
                            elif any(word in parent_text for word in ['rule', 'policy', 'term', 'condition']):
                                list_type = "rules"
                            elif any(word in parent_text for word in ['contact', 'phone', 'email', 'address']):
                                list_type = "contact"
                            
                            list_data += f"\n[LIST: {list_type.upper()}]\n{list_text.strip()}\n[END LIST]\n"
                
                elif selector == 'dl':
                    # Definition lists often contain key-value pairs
                    terms = elem.find_all('dt')
                    definitions = elem.find_all('dd')
                    
                    if terms and definitions:
                        dl_text = ""
                        for i, term in enumerate(terms):
                            if i < len(definitions):
                                term_text = term.get_text(strip=True)
                                def_text = definitions[i].get_text(strip=True)
                                if term_text and def_text:
                                    dl_text += f"{term_text}: {def_text}\n"
                        
                        if dl_text.strip():
                            list_data += f"\n[DEFINITION LIST]\n{dl_text.strip()}\n[END DEFINITION LIST]\n"
            except Exception:
                continue
    
    # Extract data attributes and custom properties (often contain structured data)
    data_attributes = ""
    data_selectors = [
        '[data-*]', '[itemprop]', '[itemtype]', '[itemscope]'
    ]
    
    for selector in data_selectors:
        for elem in soup.select(selector):
            try:
                # Extract data attributes
                data_attrs = {}
                for attr, value in elem.attrs.items():
                    if attr.startswith('data-') and value:
                        data_attrs[attr] = value
                
                # Extract microdata
                if elem.get('itemprop'):
                    data_attrs['itemprop'] = elem.get('itemprop')
                if elem.get('itemtype'):
                    data_attrs['itemtype'] = elem.get('itemtype')
                
                if data_attrs:
                    attr_text = ""
                    for attr, value in data_attrs.items():
                        attr_text += f"{attr}: {value}\n"
                    
                    if attr_text.strip():
                        data_attributes += f"\n[DATA ATTRIBUTES]\n{attr_text.strip()}\n[END DATA ATTRIBUTES]\n"
            except Exception:
                continue
    
    # Extract footer content (often contains contact info, policies, etc.)
    footer_content = ""
    footer_selectors = [
        'footer', '.footer', '#footer', '[role="contentinfo"]'
    ]
    
    for selector in footer_selectors:
        for elem in soup.select(selector):
            try:
                footer_text = elem.get_text(' ', strip=True)
                if footer_text and len(footer_text) > 50:  # Only substantial footer content
                    footer_content += f"\n[FOOTER CONTENT]\n{footer_text}\n[END FOOTER CONTENT]\n"
            except Exception:
                continue
    
    # Prioritize important content sections
    important_content = ""
    priority_sections = [
        "main", "article", "section", "div.content", "div.main", "div.description", 
        "div.property", "div.room", "div.pricing", "div.tenancy", 
        "div.details", "div.features", "div.amenities"
    ]
    
    for selector in priority_sections:
        try:
            elements = soup.select(selector)
            for elem in elements:
                if len(elem.get_text(strip=True)) > 100:  # Only substantial sections
                    important_content += "\n\n[SECTION: " + selector + "]\n"
                    important_content += elem.get_text(" ", strip=True) + "\n[END SECTION]\n\n"
        except Exception:
            pass
    
    # Remove non-content elements
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "video", "iframe", "header", "nav"]):
        tag.decompose()
    
    # Get all text
    text = soup.get_text(" ", strip=True)
    
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    
    # Combine all extracted data with priority order
    combined = (
        structured_data +           # Highest priority: structured data
        enhanced_structured_data +  # High priority: enhanced structured data
        map_coordinates +           # High priority: map coordinates
        location_meta +             # High priority: meta tags
        address_info +              # Medium priority: address elements
        property_info +             # Medium priority: property type
        contact_info +              # Medium priority: contact info
        heading_sections +          # Medium priority: heading sections
        widget_sections +           # Medium priority: widgets/accordions/tabs
        js_content +                # High priority: JavaScript/hidden content
        table_data +                # High priority: table data
        list_data +                 # High priority: list data
        data_attributes +           # High priority: data attributes
        footer_content +            # High priority: footer content
        important_content +         # Medium priority: important sections
        text                        # Lower priority: general page text
    )
    
    return combined[:120000]  # Increased cap to 120k chars per page


def _extract_widget_sections(soup: BeautifulSoup) -> str:
    """Extract content from interactive widgets, tabs, accordions, and expandable sections"""
    widget_sections = ""
    
    # Enhanced tab detection and extraction
    tab_content = _extract_tab_content(soup)
    if tab_content:
        widget_sections += f"\n[TAB CONTENT]\n{tab_content}\n[END TAB CONTENT]\n"
    
    # Enhanced accordion detection and extraction
    accordion_content = _extract_accordion_content(soup)
    if accordion_content:
        widget_sections += f"\n[ACCORDION CONTENT]\n{accordion_content}\n[END ACCORDION CONTENT]\n"
    
    # Enhanced expandable/collapsible sections
    expandable_content = _extract_expandable_content(soup)
    if expandable_content:
        widget_sections += f"\n[EXPANDABLE CONTENT]\n{expandable_content}\n[END EXPANDABLE CONTENT]\n"
    
    # Enhanced modal/popup content detection
    modal_content = _extract_modal_content(soup)
    if modal_content:
        widget_sections += f"\n[MODAL CONTENT]\n{modal_content}\n[END MODAL CONTENT]\n"
    
    # Enhanced carousel/slider content
    carousel_content = _extract_carousel_content(soup)
    if carousel_content:
        widget_sections += f"\n[CAROUSEL CONTENT]\n{carousel_content}\n[END CAROUSEL CONTENT]\n"
    
    return widget_sections


def _extract_tab_content(soup: BeautifulSoup) -> str:
    """Extract content from all tab interfaces with comprehensive pattern matching"""
    tab_content = ""
    
    # Comprehensive tab detection patterns
    tab_selectors = [
        # Standard tab patterns
        '[role="tablist"]', '[role="tab"]', '[role="tabpanel"]',
        '.tabs', '.tab', '.tab-content', '.tab-panel', '.tab-container',
        '.nav-tabs', '.nav-item', '.nav-link', '.tab-pane',
        
        # Bootstrap and common frameworks
        '.nav', '.nav-pills', '.nav-tabs', '.tab-content',
        '.tabbable', '.tabbable-pane', '.tabbable-content',
        
        # Custom tab implementations
        '[data-tab]', '[data-target]', '[data-toggle="tab"]',
        '.js-tab', '.js-tabs', '.tab-wrapper', '.tab-group',
        
        # Property-specific tab patterns
        '.room-tabs', '.pricing-tabs', '.tenancy-tabs', '.amenity-tabs',
        '.property-tabs', '.accommodation-tabs', '.booking-tabs',
        
        # Generic interactive elements that might be tabs
        '.interactive', '.content-tabs', '.section-tabs', '.info-tabs'
    ]
    
    # Find all potential tab containers
    tab_containers = []
    for selector in tab_selectors:
        tab_containers.extend(soup.select(selector))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_containers = []
    for container in tab_containers:
        container_id = container.get('id', '') or container.get('class', [])
        if str(container_id) not in seen:
            seen.add(str(container_id))
            unique_containers.append(container)
    
    for container in unique_containers:
        try:
            # Extract tab headers/labels
            tab_headers = []
            header_selectors = [
                '[role="tab"]', '.tab', '.nav-link', '.nav-item',
                '[data-toggle="tab"]', '[data-target]', '[data-tab]',
                '.tab-header', '.tab-title', '.tab-label', '.tab-name'
            ]
            
            for header_sel in header_selectors:
                headers = container.select(header_sel)
                for header in headers:
                    header_text = header.get_text(strip=True)
                    if header_text and header_text not in tab_headers:
                        tab_headers.append(header_text)
            
            # Extract tab content/panels
            tab_panels = []
            panel_selectors = [
                '[role="tabpanel"]', '.tab-content', '.tab-panel', '.tab-pane',
                '.tab-body', '.tab-content-area', '.tab-inner'
            ]
            
            for panel_sel in panel_selectors:
                panels = container.select(panel_sel)
                for panel in panels:
                    panel_text = panel.get_text(strip=True)
                    if panel_text and panel_text not in tab_panels:
                        tab_panels.append(panel_text)
            
            # If we found both headers and content, structure them
            if tab_headers and tab_panels:
                tab_content += f"\n[TAB GROUP: {len(tab_headers)} tabs]\n"
                for i, (header, panel) in enumerate(zip(tab_headers, tab_panels)):
                    tab_content += f"TAB {i+1}: {header}\n{panel}\n---\n"
                tab_content += "[END TAB GROUP]\n"
            
            # If we only found headers, try to extract from parent/sibling elements
            elif tab_headers:
                tab_content += f"\n[TAB HEADERS: {len(tab_headers)} tabs]\n"
                for i, header in enumerate(tab_headers):
                    tab_content += f"TAB {i+1}: {header}\n"
                
                # Try to find content in parent or sibling elements
                parent = container.parent
                if parent:
                    parent_text = parent.get_text(strip=True)
                    if parent_text:
                        tab_content += f"PARENT CONTENT: {parent_text[:500]}...\n"
                
                tab_content += "[END TAB HEADERS]\n"
                
        except Exception as e:
            continue
    
    return tab_content


def _extract_accordion_content(soup: BeautifulSoup) -> str:
    """Extract content from accordion interfaces with comprehensive pattern matching"""
    accordion_content = ""
    
    # Comprehensive accordion detection patterns
    accordion_selectors = [
        # Standard accordion patterns
        '.accordion', '.accordion-item', '.accordion-header', '.accordion-content',
        '.accordion-title', '.accordion-body', '.accordion-collapse',
        
        # Bootstrap accordion
        '.accordion', '.accordion-item', '.accordion-header', '.accordion-button',
        '.accordion-collapse', '.accordion-body',
        
        # Custom accordion implementations
        '.Accordion', '.Accordion_item', '.Accordion__header', '.Accordion__content',
        '.Accordion__heading', '.Accordion__content__inner',
        
        # FAQ accordion patterns
        '.faq-accordion', '.faq-accordion-item', '.faq-item', '.FAQ_item',
        '.faq-question', '.faq-answer', '.FAQ_question', '.FAQ_answer',
        
        # Property-specific accordion patterns
        '.room-accordion', '.pricing-accordion', '.amenity-accordion',
        '.tenancy-accordion', '.policy-accordion', '.feature-accordion',
        
        # Generic expandable patterns
        '.expandable', '.collapsible', '.toggle', '.Toggle',
        '.expand-trigger', '.collapse-trigger', '.toggle-trigger'
    ]
    
    # Find all potential accordion containers
    accordion_containers = []
    for selector in accordion_selectors:
        accordion_containers.extend(soup.select(selector))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_containers = []
    for container in accordion_containers:
        container_id = container.get('id', '') or container.get('class', [])
        if str(container_id) not in seen:
            seen.add(str(container_id))
            unique_containers.append(container)
    
    for container in unique_containers:
        try:
            # Extract accordion headers/titles
            headers = []
            header_selectors = [
                '.accordion-header', '.accordion-title', '.accordion-button',
                '.Accordion__header', '.Accordion__heading', '.accordion-heading',
                '.faq-question', '.FAQ_question', '.expand-trigger', '.toggle-trigger',
                'h3', 'h4', 'h5', 'h6', '.title', '.heading', '.label'
            ]
            
            for header_sel in header_selectors:
                header_elements = container.select(header_sel)
                for header in header_elements:
                    header_text = header.get_text(strip=True)
                    if header_text and header_text not in headers:
                        headers.append(header_text)
            
            # Extract accordion content/body
            contents = []
            content_selectors = [
                '.accordion-content', '.accordion-body', '.accordion-collapse',
                '.Accordion__content', '.Accordion__content__inner',
                '.faq-answer', '.FAQ_answer', '.expand-content', '.toggle-content',
                '.content', '.body', '.panel', '.section'
            ]
            
            for content_sel in content_selectors:
                content_elements = container.select(content_sel)
                for content in content_elements:
                    content_text = content.get_text(strip=True)
                    if content_text and content_text not in contents:
                        contents.append(content_text)
            
            # If we found both headers and content, structure them
            if headers and contents:
                accordion_content += f"\n[ACCORDION GROUP: {len(headers)} items]\n"
                for i, (header, content) in enumerate(zip(headers, contents)):
                    accordion_content += f"ITEM {i+1}: {header}\n{content}\n---\n"
                accordion_content += "[END ACCORDION GROUP]\n"
            
            # If we only found headers, try to extract from parent/sibling elements
            elif headers:
                accordion_content += f"\n[ACCORDION HEADERS: {len(headers)} items]\n"
                for i, header in enumerate(headers):
                    accordion_content += f"ITEM {i+1}: {header}\n"
                
                # Try to find content in parent or sibling elements
                parent = container.parent
                if parent:
                    parent_text = parent.get_text(strip=True)
                    if parent_text:
                        accordion_content += f"PARENT CONTENT: {parent_text[:500]}...\n"
                
                accordion_content += "[END ACCORDION HEADERS]\n"
                
        except Exception as e:
            continue
    
    return accordion_content


def _extract_expandable_content(soup: BeautifulSoup) -> str:
    """Extract content from expandable/collapsible sections"""
    expandable_content = ""
    
    # Comprehensive expandable section detection
    expandable_selectors = [
        # Standard expandable patterns
        '.expandable', '.collapsible', '.toggle', '.Toggle',
        '.expand-trigger', '.collapse-trigger', '.toggle-trigger',
        
        # Bootstrap collapse
        '.collapse', '.Collapse', '.collapsing',
        
        # Custom expandable implementations
        '.expand-section', '.collapsible-section', '.toggle-section',
        '.expandable-content', '.collapsible-content', '.toggle-content',
        
        # Property-specific expandable patterns
        '.room-details', '.pricing-details', '.amenity-details',
        '.tenancy-details', '.policy-details', '.feature-details',
        
        # Generic interactive elements
        '.interactive', '.clickable', '.expandable', '.collapsible',
        '[data-toggle="collapse"]', '[data-target]', '[data-expand]'
    ]
    
    # Find all potential expandable containers
    expandable_containers = []
    for selector in expandable_selectors:
        expandable_containers.extend(soup.select(selector))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_containers = []
    for container in expandable_containers:
        container_id = container.get('id', '') or container.get('class', [])
        if str(container_id) not in seen:
            seen.add(str(container_id))
            unique_containers.append(container)
    
    for container in unique_containers:
        try:
            # Extract trigger/button text
            trigger_text = ""
            trigger_selectors = [
                '.expand-trigger', '.collapse-trigger', '.toggle-trigger',
                '.expand-button', '.collapse-button', '.toggle-button',
                'button', '.btn', '.button', '[role="button"]'
            ]
            
            for trigger_sel in trigger_selectors:
                triggers = container.select(trigger_sel)
                for trigger in triggers:
                    trigger_text = trigger.get_text(strip=True)
                    if trigger_text:
                        break
                if trigger_text:
                    break
            
            # Extract expandable content
            content_text = container.get_text(strip=True)
            
            if trigger_text and content_text:
                expandable_content += f"\n[EXPANDABLE SECTION: {trigger_text}]\n{content_text}\n[END EXPANDABLE SECTION]\n"
            elif content_text:
                expandable_content += f"\n[EXPANDABLE CONTENT]\n{content_text}\n[END EXPANDABLE CONTENT]\n"
                
        except Exception as e:
            continue
    
    return expandable_content


def _extract_modal_content(soup: BeautifulSoup) -> str:
    """Extract content from modal/popup dialogs"""
    modal_content = ""
    
    # Comprehensive modal detection patterns
    modal_selectors = [
        # Standard modal patterns
        '.modal', '.Modal', '.modal-dialog', '.modal-content',
        '.modal-header', '.modal-body', '.modal-footer',
        
        # Bootstrap modal
        '.modal', '.modal-dialog', '.modal-content',
        
        # Custom modal implementations
        '.popup', '.Popup', '.dialog', '.Dialog',
        '.overlay', '.Overlay', '.lightbox', '.Lightbox',
        
        # Property-specific modal patterns
        '.room-modal', '.pricing-modal', '.amenity-modal',
        '.tenancy-modal', '.policy-modal', '.booking-modal',
        
        # Generic popup patterns
        '.popup-content', '.popup-body', '.popup-text',
        '[data-modal]', '[data-popup]', '[data-dialog]'
    ]
    
    # Find all potential modal containers
    modal_containers = []
    for selector in modal_selectors:
        modal_containers.extend(soup.select(selector))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_containers = []
    for container in modal_containers:
        container_id = container.get('id', '') or container.get('class', [])
        if str(container_id) not in seen:
            seen.add(str(container_id))
            unique_containers.append(container)
    
    for container in unique_containers:
        try:
            # Extract modal title/header
            title_text = ""
            title_selectors = [
                '.modal-title', '.modal-header', '.popup-title',
                '.popup-header', '.dialog-title', '.dialog-header',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6', '.title', '.heading'
            ]
            
            for title_sel in title_selectors:
                titles = container.select(title_sel)
                for title in titles:
                    title_text = title.get_text(strip=True)
                    if title_text:
                        break
                if title_text:
                    break
            
            # Extract modal content
            content_text = container.get_text(strip=True)
            
            if title_text and content_text:
                modal_content += f"\n[MODAL: {title_text}]\n{content_text}\n[END MODAL]\n"
            elif content_text:
                modal_content += f"\n[MODAL CONTENT]\n{content_text}\n[END MODAL CONTENT]\n"
                
        except Exception as e:
            continue
    
    return modal_content


def _extract_carousel_content(soup: BeautifulSoup) -> str:
    """Extract content from carousel/slider interfaces"""
    carousel_content = ""
    
    # Comprehensive carousel detection patterns
    carousel_selectors = [
        # Standard carousel patterns
        '.carousel', '.Carousel', '.carousel-inner', '.carousel-item',
        '.carousel-caption', '.carousel-control', '.carousel-indicators',
        
        # Bootstrap carousel
        '.carousel', '.carousel-inner', '.carousel-item',
        
        # Custom carousel implementations
        '.slider', '.Slider', '.slideshow', '.Slideshow',
        '.slide', '.Slide', '.slide-content', '.slide-text',
        
        # Property-specific carousel patterns
        '.room-carousel', '.pricing-carousel', '.amenity-carousel',
        '.tenancy-carousel', '.photo-carousel', '.gallery-carousel',
        
        # Generic slider patterns
        '.slider-content', '.slide-content', '.carousel-content',
        '[data-carousel]', '[data-slider]', '[data-slideshow]'
    ]
    
    # Find all potential carousel containers
    carousel_containers = []
    for selector in carousel_selectors:
        carousel_containers.extend(soup.select(selector))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_containers = []
    for container in carousel_containers:
        container_id = container.get('id', '') or container.get('class', [])
        if str(container_id) not in seen:
            seen.add(str(container_id))
            unique_containers.append(container)
    
    for container in unique_containers:
        try:
            # Extract carousel items/slides
            items = []
            item_selectors = [
                '.carousel-item', '.slide', '.Slide', '.slide-content',
                '.carousel-slide', '.slider-item', '.slideshow-item'
            ]
            
            for item_sel in item_selectors:
                item_elements = container.select(item_sel)
                for item in item_elements:
                    item_text = item.get_text(strip=True)
                    if item_text and item_text not in items:
                        items.append(item_text)
            
            # Extract carousel captions/descriptions
            captions = []
            caption_selectors = [
                '.carousel-caption', '.slide-caption', '.slide-description',
                '.carousel-text', '.slide-text', '.carousel-description'
            ]
            
            for caption_sel in caption_selectors:
                caption_elements = container.select(caption_sel)
                for caption in caption_elements:
                    caption_text = caption.get_text(strip=True)
                    if caption_text and caption_text not in captions:
                        captions.append(caption_text)
            
            # If we found items, structure them
            if items:
                carousel_content += f"\n[CAROUSEL: {len(items)} items]\n"
                for i, item in enumerate(items):
                    carousel_content += f"ITEM {i+1}: {item}\n"
                    # Try to match with captions
                    if i < len(captions):
                        carousel_content += f"CAPTION: {captions[i]}\n"
                    carousel_content += "---\n"
                carousel_content += "[END CAROUSEL]\n"
            
            # If we only found captions
            elif captions:
                carousel_content += f"\n[CAROUSEL CAPTIONS: {len(captions)} items]\n"
                for i, caption in enumerate(captions):
                    carousel_content += f"CAPTION {i+1}: {caption}\n"
                carousel_content += "[END CAROUSEL CAPTIONS]\n"
                
        except Exception as e:
            continue
    
    return carousel_content


def _extract_javascript_content(soup: BeautifulSoup) -> str:
    """Extract content from JavaScript-loaded or hidden elements that might contain important data"""
    js_content = ""
    
    # Look for hidden elements that might contain data
    hidden_selectors = [
        '[style*="display: none"]', '[style*="display:none"]', '[style*="visibility: hidden"]',
        '[hidden]', '[aria-hidden="true"]', '.hidden', '.d-none', '.invisible',
        '[data-hidden="true"]', '[data-visible="false"]', '.js-hidden', '.js-hidden-content'
    ]
    
    for selector in hidden_selectors:
        try:
            elements = soup.select(selector)
            for elem in elements:
                elem_text = elem.get_text(strip=True)
                if elem_text and len(elem_text) > 20:  # Only substantial content
                    js_content += f"\n[HIDDEN CONTENT: {selector}]\n{elem_text}\n[END HIDDEN CONTENT]\n"
        except Exception:
            continue
    
    # Look for data attributes that might contain content
    data_selectors = [
        '[data-content]', '[data-text]', '[data-description]', '[data-info]',
        '[data-details]', '[data-features]', '[data-amenities]', '[data-pricing]',
        '[data-tenancy]', '[data-rooms]', '[data-configuration]'
    ]
    
    for selector in data_selectors:
        try:
            elements = soup.select(selector)
            for elem in elements:
                # Get the data attribute value
                data_attr = None
                for attr in ['data-content', 'data-text', 'data-description', 'data-info', 
                           'data-details', 'data-features', 'data-amenities', 'data-pricing',
                           'data-tenancy', 'data-rooms', 'data-configuration']:
                    if elem.has_attr(attr):
                        data_attr = elem.get(attr)
                        break
                
                if data_attr:
                    js_content += f"\n[DATA ATTRIBUTE: {selector}]\n{data_attr}\n[END DATA ATTRIBUTE]\n"
                
                # Also get the element text if it exists
                elem_text = elem.get_text(strip=True)
                if elem_text and len(elem_text) > 20:
                    js_content += f"\n[DATA ELEMENT TEXT: {selector}]\n{elem_text}\n[END DATA ELEMENT TEXT]\n"
        except Exception:
            continue
    
    # Look for script tags that might contain JSON data
    script_selectors = [
        'script[type="application/json"]', 'script[type="application/ld+json"]',
        'script[data-config]', 'script[data-content]', 'script[data-property]'
    ]
    
    for selector in script_selectors:
        try:
            scripts = soup.select(selector)
            for script in scripts:
                if script.string:
                    script_content = script.string.strip()
                    if script_content and len(script_content) > 50:  # Only substantial JSON
                        # Truncate very long JSON for readability
                        if len(script_content) > 2000:
                            script_content = script_content[:2000] + "..."
                        js_content += f"\n[JAVASCRIPT JSON: {selector}]\n{script_content}\n[END JAVASCRIPT JSON]\n"
        except Exception:
            continue
    
    # Look for elements with aria-label or title attributes that might contain descriptions
    aria_selectors = [
        '[aria-label]', '[title]', '[alt]', '[data-tooltip]', '[data-title]'
    ]
    
    for selector in aria_selectors:
        try:
            elements = soup.select(selector)
            for elem in elements:
                aria_text = ""
                for attr in ['aria-label', 'title', 'alt', 'data-tooltip', 'data-title']:
                    if elem.has_attr(attr):
                        aria_text = elem.get(attr)
                        if aria_text and len(aria_text) > 10:  # Only substantial descriptions
                            js_content += f"\n[ARIA CONTENT: {attr}]\n{aria_text}\n[END ARIA CONTENT]\n"
                        break
        except Exception:
            continue
    
    return js_content


def _extract_structured_data(soup: BeautifulSoup) -> str:
    """Extract structured data from meta tags, schema.org markup, and other structured formats"""
    structured_data = ""
    
    # Extract meta tags that might contain property information
    meta_selectors = [
        'meta[name="description"]', 'meta[name="keywords"]', 'meta[property="og:description"]',
        'meta[property="og:title"]', 'meta[property="og:type"]', 'meta[name="author"]',
        'meta[name="robots"]', 'meta[name="viewport"]', 'meta[charset]'
    ]
    
    for selector in meta_selectors:
        try:
            metas = soup.select(selector)
            for meta in metas:
                content = meta.get('content', '') or meta.get('charset', '')
                if content and len(content) > 5:
                    name = meta.get('name', '') or meta.get('property', '') or meta.get('charset', '')
                    structured_data += f"\n[META: {name}]\n{content}\n[END META]\n"
        except Exception:
            continue
    
    # Extract schema.org structured data
    schema_selectors = [
        '[itemtype*="schema.org"]', '[itemtype*="schema.org/Place"]', 
        '[itemtype*="schema.org/Residence"]', '[itemtype*="schema.org/Apartment"]',
        '[itemtype*="schema.org/Product"]', '[itemtype*="schema.org/Offer"]'
    ]
    
    for selector in schema_selectors:
        try:
            schema_elements = soup.select(selector)
            for elem in schema_elements:
                # Extract itemtype
                itemtype = elem.get('itemtype', '')
                if itemtype:
                    structured_data += f"\n[SCHEMA: {itemtype}]\n"
                    
                    # Extract itemprops
                    itemprops = elem.find_all(attrs={'itemprop': True})
                    for prop in itemprops:
                        prop_name = prop.get('itemprop', '')
                        prop_content = prop.get('content', '') or prop.get_text(strip=True)
                        if prop_content:
                            structured_data += f"{prop_name}: {prop_content}\n"
                    
                    structured_data += "[END SCHEMA]\n"
        except Exception:
            continue
    
    # Extract Open Graph and Twitter Card data
    og_selectors = [
        'meta[property^="og:"]', 'meta[property^="twitter:"]', 'meta[name^="twitter:"]'
    ]
    
    for selector in og_selectors:
        try:
            og_elements = soup.select(selector)
            for elem in og_elements:
                property_name = elem.get('property', '') or elem.get('name', '')
                content = elem.get('content', '')
                if property_name and content:
                    structured_data += f"\n[OPEN GRAPH: {property_name}]\n{content}\n[END OPEN GRAPH]\n"
        except Exception:
            continue
    
    return structured_data


def _fetch(url: str, timeout: int, headers: Dict[str, str]) -> str:
    """Fetch URL content with retry logic and better error handling"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            raise Exception(f"Timeout after {max_retries} attempts for {url}")
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise Exception(f"Connection error after {max_retries} attempts for {url}")
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise Exception(f"Request failed after {max_retries} attempts for {url}: {str(e)}")
    
    raise Exception(f"Failed to fetch {url} after {max_retries} attempts")


_CACHE: Dict[str, str] = {}


def _normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        # drop fragment and query for stability
        normalized = parsed._replace(query="", fragment="")
        s = urlunparse(normalized)
        if s.endswith('/'):
            s = s[:-1]
        return s.lower()
    except Exception:
        return url


def _score_link(url: str, anchor_text: str, allow_patterns: List[str]) -> int:
    score = 0
    path = urlparse(url).path.lower()
    anchor_lower = anchor_text.lower() if anchor_text else ''
    
    # Enhanced scoring for Node 3 (Configuration) and Node 4 (Tenancy) priority
    configuration_keywords = {
        # High priority room configuration keywords
        'room': 8, 'studio': 8, 'apartment': 8, 'flat': 8, 'accommodation': 8,
        'ensuite': 9, 'en-suite': 9, 'bedroom': 8, 'bathroom': 7, 'kitchen': 6,
        'configuration': 10, 'config': 9, 'option': 8, 'variant': 8, 'type': 7,
        'detail': 8, 'specification': 8, 'spec': 7, 'info': 6, 'information': 6,
        'floor\\s*plan': 9, 'layout': 8, 'diagram': 7, 'gallery': 6, 'photo': 5,
        'premium': 7, 'deluxe': 7, 'standard': 6, 'basic': 5, 'economy': 5
    }
    
    tenancy_keywords = {
        # High priority tenancy and contract keywords
        'tenancy': 10, 'contract': 10, 'lease': 10, 'term': 9, 'duration': 9,
        'agreement': 8, 'booking': 8, 'reservation': 8, 'availability': 7,
        'price': 9, 'pricing': 9, 'cost': 8, 'fee': 8, 'rent': 9, 'deposit': 8,
        'weekly': 8, 'monthly': 7, 'per\\s*week': 8, 'per\\s*month': 7, 'pw': 8, 'pm': 7,
        'start': 7, 'end': 7, 'date': 6, 'move': 6, 'arrival': 6, 'departure': 6,
        'semester': 8, 'academic\\s*year': 8, 'term': 7, 'session': 6,
        'guarantor': 8, 'guarantee': 7, 'reference': 6, 'requirement': 6,
        'cancellation': 7, 'refund': 7, 'modification': 6, 'transfer': 6,
        'offer': 6, 'deal': 6, 'promotion': 6, 'discount': 6, 'incentive': 6
    }
    
    # Score based on configuration keywords (Node 3 priority)
    for keyword, keyword_score in configuration_keywords.items():
        if re.search(rf'\b{keyword}\b', path, re.IGNORECASE):
            score += keyword_score
        if anchor_text and re.search(rf'\b{keyword}\b', anchor_lower, re.IGNORECASE):
            score += keyword_score // 2  # Anchor text gets half the score
    
    # Score based on tenancy keywords (Node 4 priority)
    for keyword, keyword_score in tenancy_keywords.items():
        if re.search(rf'\b{keyword}\b', path, re.IGNORECASE):
            score += keyword_score
        if anchor_text and re.search(rf'\b{keyword}\b', anchor_lower, re.IGNORECASE):
            score += keyword_score // 2  # Anchor text gets half the score
    
    # Apply pattern-based scoring from allow_patterns
    for pat in allow_patterns:
        try:
            if re.search(pat, url, re.IGNORECASE):
                score += 4  # Increased from 3
            if anchor_text and re.search(pat, anchor_text, re.IGNORECASE):
                score += 3  # Increased from 2
        except Exception:
            continue
    
    # Enhanced path-based scoring
    path_segments = [p for p in path.split('/') if p]
    if 1 <= len(path_segments) <= 3:  # Optimal depth for detail pages
        score += 4  # Increased from 3
    elif len(path_segments) > 3:
        score -= min(len(path_segments) - 3, 4)  # Increased penalty for very deep paths
    
    # Bonus for likely configuration detail pages
    if any(kw in path for kw in ['room', 'studio', 'apartment', 'ensuite']) and any(kw in path for kw in ['detail', 'info', 'spec', 'configuration']):
        score += 8  # Increased from 5
    
    # Bonus for likely tenancy/pricing pages
    if any(kw in path for kw in ['price', 'cost', 'fee', 'rent']) and any(kw in path for kw in ['tenancy', 'contract', 'lease', 'booking']):
        score += 8  # Increased from 5
    
    # Bonus for semester/academic year specific pages
    if any(kw in path for kw in ['semester', 'academic', 'term']) and any(kw in path for kw in ['tenancy', 'contract', 'booking', 'availability']):
        score += 6
    
    # Bonus for room type variations
    if any(kw in path for kw in ['premium', 'deluxe', 'standard', 'basic', 'economy']) and any(kw in path for kw in ['room', 'studio', 'apartment']):
        score += 6
    
    # Bonus for pricing variations
    if any(kw in path for kw in ['weekly', 'monthly', 'pw', 'pm']) and any(kw in path for kw in ['price', 'cost', 'rent', 'fee']):
        score += 6
        
    return score


def crawl_site(
    main_url: str,
    follow_depth: int = 1,
    max_links_per_page: int = 8,
    max_total_pages: int = 20,
    request_timeout: int = 30,  # Increased from 10 to 30 seconds
    crawl_delay_ms: int = 500,  # Increased from 300 to 500ms
    allow_patterns: List[str] | None = None,
    allow_external_domains: List[str] | None = None,
) -> List[Dict[str, str]]:
    """Crawl same-domain pages up to a small depth and return list of {url, text}."""
    if allow_patterns is None:
        allow_patterns = [
            # Core accommodation types
            r"room", r"rooms", r"config", r"configuration", r"option", r"variant", r"type",
            r"studio", r"flat", r"apartment", r"ensuite", r"en-suite", r"accommodation", r"unit", r"suite",
            
            # Pricing and financial
            r"pricing", r"prices", r"price", r"cost", r"fee", r"rent", r"deposit", r"rate", r"tariff",
            r"weekly", r"monthly", r"per\s*week", r"per\s*month", r"pw", r"pm", r"total", r"from",
            
            # Tenancy and contracts
            r"tenancy", r"contract", r"lease", r"term", r"duration", r"agreement", r"booking", r"availability",
            r"start", r"end", r"date", r"move", r"arrival", r"departure", r"semester", r"academic\s*year",
            
            # Physical specifications
            r"detail", r"specification", r"floor", r"area", r"size", r"dimension", r"sqm", r"sqft",
            r"bedroom", r"bathroom", r"kitchen", r"occupancy", r"single", r"double", r"twin", r"triple",
            
            # Features and amenities
            r"amenity", r"feature", r"facility", r"furniture", r"equipped", r"included", r"provided",
            r"wifi", r"internet", r"utilities", r"bills", r"heating", r"cooling", r"air\s*conditioning",
            
            # Availability and booking
            r"available", r"book", r"apply", r"reserve", r"check", r"enquire", r"contact",
            r"waitlist", r"sold\s*out", r"limited", r"exclusive", r"premium", r"standard", r"basic",
            
            # Building and location
            r"building", r"block", r"tower", r"wing", r"section", r"floor", r"level", r"elevator",
            r"nearby", r"distance", r"walking", r"transport", r"bus", r"train", r"metro", r"underground",
            
            # Policies and information
            r"policy", r"policies", r"rule", r"condition", r"requirement", r"faq", r"question", r"answer",
            r"terms", r"conditions", r"cancellation", r"refund", r"modification", r"transfer", r"swap"
        ]

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    seen: Set[str] = set()
    queue: List[tuple[str, int]] = [(main_url, 0)]
    pages: List[Dict[str, str]] = []

    def _extract_api_urls(html: str, base_url: str) -> List[str]:
        urls: Set[str] = set()
        try:
            # Find absolute/relative URLs in scripts
            for m in re.findall(r"https?://[^\'\"\s<>]+", html):
                urls.add(m)
            # JSON-looking endpoints inside quotes
            for m in re.findall(r"[\'\"](/[^\'\"\s<>]+)[\'\"]", html):
                try:
                    urls.add(urljoin(base_url, m))
                except Exception:
                    continue
        except Exception:
            pass
        filtered: List[str] = []
        for u in urls:
            try:
                if not _is_same_domain(base_url, u):
                    continue
                l = u.lower()
                if any(x in l for x in ["/api/", ".json", "?format=json", "&_format=json", "/wp-json/"]):
                    filtered.append(u)
            except Exception:
                continue
        # Deduplicate and limit per page
        uniq = []
        seen_local = set()
        for u in filtered:
            nu = _normalize_url(u)
            if nu in seen_local:
                continue
            seen_local.add(nu)
            uniq.append(u)
            if len(uniq) >= 5:
                break
        return uniq

    while queue and len(pages) < max_total_pages:
        url, depth = queue.pop(0)
        norm_url = _normalize_url(url)
        if norm_url in seen:
            continue
        seen.add(norm_url)
        try:
            if norm_url in _CACHE:
                html = _CACHE[norm_url]
            else:
                html = _fetch(url, request_timeout, headers)
                # naive cache with simple cap
                if len(_CACHE) < 200:
                    _CACHE[norm_url] = html

            extra_blocks = ""
            # Include inline JSON scripts (application/json)
            try:
                soup_local = BeautifulSoup(html, "html.parser")
                for js in soup_local.find_all("script", {"type": "application/json"}):
                    if js.string and len(js.string) > 2:
                        payload = js.string.strip()
                        if len(payload) > 2000:
                            payload = payload[:2000] + "..."
                        extra_blocks += f"\n[INLINE JSON]\n{payload}\n[END INLINE JSON]\n"
            except Exception:
                pass
            # Fetch referenced JSON/API endpoints
            try:
                api_urls = _extract_api_urls(html, url)
                for api_url in api_urls:
                    try:
                        resp = requests.get(api_url, timeout=request_timeout, headers=headers)
                        if resp.status_code == 200 and resp.text:
                            body = resp.text
                            if len(body) > 4000:
                                body = body[:4000] + "..."
                            extra_blocks += f"\n[API RESPONSE url=\"{api_url}\"]\n{body}\n[END API RESPONSE]\n"
                    except Exception:
                        continue
            except Exception:
                pass

            text = _clean_text(html)
            if extra_blocks:
                text = extra_blocks + "\n" + text
            if text:
                # Append page link inventory to help discovery
                try:
                    soup_links = BeautifulSoup(html, "html.parser")
                    links = []
                    for a in soup_links.find_all("a", href=True):
                        target = urljoin(url, a["href"])
                        if _is_same_domain(main_url, target):
                            links.append(_normalize_url(target))
                    if links:
                        unique_links = []
                        seen_link = set()
                        for l in links:
                            if l in seen_link:
                                continue
                            seen_link.add(l)
                            unique_links.append(l)
                            if len(unique_links) >= 50:
                                break
                        text = f"[PAGE LINKS]\n" + "\n".join(unique_links) + "\n[END PAGE LINKS]\n\n" + text
                except Exception:
                    pass
                pages.append({"url": norm_url, "text": text})

            if depth < follow_depth:
                soup = BeautifulSoup(html, "html.parser")
                scored: List[Tuple[int, str]] = []
                for a in soup.find_all("a", href=True):
                    target = urljoin(url, a["href"])
                    if not _is_allowed_domain(main_url, target, allow_external_domains):
                        continue
                    anchor = a.get_text(strip=True) or ""
                    # Allow following if URL OR anchor text matches allowed patterns
                    if not any(
                        re.search(pat, target, re.IGNORECASE) or (anchor and re.search(pat, anchor, re.IGNORECASE))
                        for pat in allow_patterns
                    ):
                        continue
                    score = _score_link(target, anchor, allow_patterns)
                    scored.append((score, _normalize_url(target)))
                # sort by score desc and unique
                scored.sort(key=lambda x: x[0], reverse=True)
                unique_targets = []
                seen_targets = set()
                for _, t in scored:
                    if t in seen_targets:
                        continue
                    seen_targets.add(t)
                    unique_targets.append(t)
                    if len(unique_targets) >= max_links_per_page:
                        break
                for nxt in unique_targets:
                    if nxt not in seen:
                        queue.append((nxt, depth + 1))
            # politeness delay
            if crawl_delay_ms:
                time.sleep(crawl_delay_ms / 1000.0)
        except Exception:
            # ignore fetch errors silently for robustness
            continue

    return pages


def build_context(pages: List[Dict[str, str]], max_chars: int = 120000) -> str:
    """Build a concatenated context string from crawled pages, capped by size."""
    # First pass: extract and categorize content from pages
    categorized_pages = []
    for p in pages:
        url = p['url']
        text = p['text']
        
        # Enhanced categorization for Node 3 and 4 priority
        category = "general"
        
        # Configuration-related pages (Node 3 priority)
        if any(kw in url.lower() for kw in ["room", "studio", "apartment", "flat", "accommodation", "ensuite", "en-suite"]):
            if any(kw in url.lower() for kw in ["detail", "info", "spec", "configuration", "option", "variant"]):
                category = "room_config_detail"
            else:
                category = "room_config"
        elif any(kw in url.lower() for kw in ["configuration", "config", "option", "variant", "type", "style"]):
            category = "room_config"
        elif any(kw in url.lower() for kw in ["floor\\s*plan", "layout", "diagram", "gallery", "photo", "view"]):
            category = "room_visual"
        
        # Tenancy and pricing pages (Node 4 priority)
        elif any(kw in url.lower() for kw in ["tenancy", "contract", "lease", "term", "duration", "agreement"]):
            if any(kw in url.lower() for kw in ["price", "cost", "fee", "rent", "deposit", "rate"]):
                category = "tenancy_pricing"
            else:
                category = "tenancy"
        elif any(kw in url.lower() for kw in ["price", "pricing", "cost", "fee", "rent", "deposit"]):
            if any(kw in url.lower() for kw in ["weekly", "monthly", "pw", "pm", "per\\s*week", "per\\s*month"]):
                category = "tenancy_pricing"
            else:
                category = "pricing"
        elif any(kw in url.lower() for kw in ["booking", "reservation", "availability", "apply", "enquire"]):
            category = "tenancy"
        
        # Semester and academic year specific
        elif any(kw in url.lower() for kw in ["semester", "academic\\s*year", "term", "session"]):
            if any(kw in url.lower() for kw in ["tenancy", "contract", "booking", "availability"]):
                category = "tenancy_academic"
            else:
                category = "academic"
        
        # Features and amenities
        elif any(kw in url.lower() for kw in ["feature", "amenity", "facility", "furniture", "equipped"]):
            category = "features"
        
        # Policies and information
        elif any(kw in url.lower() for kw in ["faq", "policy", "policies", "rule", "condition", "requirement"]):
            category = "policies"
        
        categorized_pages.append({"url": url, "text": text, "category": category})
    
    # Enhanced priority system for Node 3 and 4
    category_priority = {
        # Highest priority for configuration and tenancy
        "room_config_detail": 1,      # Detailed room configuration pages
        "tenancy_pricing": 2,         # Tenancy with pricing information
        "tenancy_academic": 3,        # Academic year specific tenancy
        "room_config": 4,             # General room configuration
        "tenancy": 5,                 # General tenancy information
        "pricing": 6,                 # General pricing information
        "room_visual": 7,             # Floor plans, photos, layouts
        "academic": 8,                # Academic information
        "features": 9,                # Features and amenities
        "policies": 10,               # Policies and rules
        "general": 99                 # Everything else
    }
    categorized_pages.sort(key=lambda x: category_priority.get(x["category"], 99))
    
    # Build context with priority to important categories
    parts: List[str] = []
    used = 0
    
    # Add main page first
    main_page = next((p for p in categorized_pages if p["url"] == pages[0]["url"]), None)
    if main_page:
        header = f"\n\n=== MAIN PAGE: {main_page['url']} ===\n"
        chunk = header + main_page["text"][: max(0, max_chars // 4)]  # Allocate up to 1/4 for main page
        parts.append(chunk)
        used += len(chunk)
        categorized_pages.remove(main_page)
    
    # Enhanced allocation for Node 3 and 4 priority categories
    for p in categorized_pages:
        if used >= max_chars:
            break
            
        header = f"\n\n=== {p['category'].upper()}: {p['url']} ===\n"
        
        # Enhanced allocation strategy for configuration and tenancy
        category_allocation = {
            "room_config_detail": max_chars // 5,      # Maximum allocation for detailed configs
            "tenancy_pricing": max_chars // 5,         # Maximum allocation for tenancy with pricing
            "tenancy_academic": max_chars // 6,        # High allocation for academic tenancy
            "room_config": max_chars // 6,             # High allocation for room configs
            "tenancy": max_chars // 7,                 # Good allocation for tenancy
            "pricing": max_chars // 7,                 # Good allocation for pricing
            "room_visual": max_chars // 8,             # Moderate for visual content
            "academic": max_chars // 9,                # Moderate for academic info
            "features": max_chars // 10,               # Lower for features
            "policies": max_chars // 12,               # Lower for policies
            "general": max_chars // 15                 # Lowest for general content
        }
        
        allocation = category_allocation.get(p["category"], max_chars // 10)
        chunk = header + p["text"][: max(0, min(allocation, max_chars - used - len(header)))]
        if not chunk:
            continue
        parts.append(chunk)
        used += len(chunk)
    
    return "".join(parts)


