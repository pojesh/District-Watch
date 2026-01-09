"""
Data extraction from District.in pages
"""

import json
import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ShowTime:
    """Showtime information"""
    time: str
    available: bool
    format: str = ""


@dataclass
class Theater:
    """Theater with showtimes"""
    name: str
    location: str = ""
    showtimes: List[ShowTime] = None
    priority: int = 1
    
    def __post_init__(self):
        if self.showtimes is None:
            self.showtimes = []


class DataExtractor:
    """Extract booking information from page data"""
    
    def __init__(self, target_theaters: List):
        """
        Args:
            target_theaters: List of TheaterConfig objects
        """
        self.target_theaters = target_theaters
        self.theater_keywords = self._build_keyword_map()
    
    def _build_keyword_map(self) -> Dict[str, Dict]:
        """Build keyword to theater mapping"""
        keyword_map = {}
        for theater in self.target_theaters:
            for keyword in theater.keywords:
                keyword_map[keyword.lower()] = {
                    "name": theater.name,
                    "priority": theater.priority
                }
        return keyword_map
    
    def _match_theater(self, theater_name: str) -> Optional[Dict]:
        """Match theater name against keywords"""
        name_lower = theater_name.lower()
        
        for keyword, config in self.theater_keywords.items():
            if keyword in name_lower:
                return config
        
        return None
    
    def extract_from_json(self, json_str: str) -> List[Theater]:
        """Extract from __NEXT_DATA__ JSON"""
        theaters = []
        
        try:
            data = json.loads(json_str)
            page_props = data.get("props", {}).get("pageProps", {})
            
            # Try multiple paths for venue data
            venues = None
            for path in [
                ["initialState", "movie", "venues"],
                ["movie", "venues"],
                ["venues"],
                ["initialState", "shows"],
                ["shows"],
                ["initialData", "venues"],
                ["data", "venues"]
            ]:
                temp = page_props
                for key in path:
                    temp = temp.get(key, {})
                    if not temp:
                        break
                if temp and isinstance(temp, (list, dict)):
                    venues = temp
                    break
            
            if not venues:
                logger.debug("No venue data in JSON")
                return theaters
            
            venue_list = venues if isinstance(venues, list) else venues.values()
            
            for venue in venue_list:
                theater_name = venue.get("name", "") or venue.get("venueName", "")
                
                # Check if target theater
                theater_config = self._match_theater(theater_name)
                if not theater_config:
                    continue
                
                # Get location
                location = venue.get("location", {})
                location_str = ""
                if isinstance(location, dict):
                    location_str = location.get("address", "") or location.get("area", "")
                elif isinstance(location, str):
                    location_str = location
                
                # Extract showtimes
                shows = venue.get("shows", []) or venue.get("showtimes", [])
                showtimes = []
                
                for show in shows:
                    time = show.get("time", "") or show.get("showTime", "") or show.get("startTime", "")
                    available = show.get("available", False) or show.get("isAvailable", False) or show.get("bookingAllowed", False)
                    format_type = show.get("format", "") or show.get("experienceType", "") or show.get("screen", "")
                    
                    if time:
                        showtimes.append(ShowTime(
                            time=time,
                            available=available,
                            format=format_type
                        ))
                
                if showtimes:
                    theaters.append(Theater(
                        name=theater_config["name"],
                        location=location_str,
                        showtimes=showtimes,
                        priority=theater_config["priority"]
                    ))
                    logger.debug(f"Found {len(showtimes)} shows at {theater_config['name']}")
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Extraction error: {e}")
        
        return theaters
    
    def extract_from_html(self, html: str) -> List[Theater]:
        """Parse HTML for theater listings (District.in specific)"""
        theaters = []
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Find all theater listing elements
            theater_elements = soup.find_all('li', class_=re.compile(r'MovieSessionsListing_movieSessions'))
            
            logger.debug(f"Found {len(theater_elements)} theater elements in HTML")
            
            for element in theater_elements:
                # Get theater name - look for link with theater href pattern
                theater_name = ""
                
                # Find all links and get the one with theater name
                for link in element.find_all('a'):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # Theater detail links typically have this pattern
                    if '/movies/' in href and '-in-' in href and text:
                        theater_name = text
                        break
                
                if not theater_name:
                    continue
                
                # Check if this matches our target theaters
                theater_config = self._match_theater(theater_name)
                if not theater_config:
                    continue
                
                logger.info(f"Found matching theater: {theater_name}")
                
                # Get showtimes from timeblock elements
                showtimes = []
                timeblocks = element.find_all('li', class_=re.compile(r'MovieSessionsListing_timeblock'))
                
                for block in timeblocks:
                    # Get time div with color indicator
                    time_div = block.find('div', class_=re.compile(r'.*Col.*MovieSessionsListing_time'))
                    if not time_div:
                        time_div = block.find('div', class_=re.compile(r'MovieSessionsListing_time'))
                    
                    if not time_div:
                        continue
                    
                    # Get time text (first text node)
                    time_text = time_div.get_text(separator=' ', strip=True)
                    
                    # Parse time - typically first part before any format info
                    time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM))', time_text, re.IGNORECASE)
                    if not time_match:
                        continue
                    
                    show_time = time_match.group(1).strip()
                    
                    # Determine availability by color class
                    # greenCol = Available, yellowCol = Filling fast, redCol = Almost full (all available)
                    # greyCol = Sold out (not available)
                    div_classes = time_div.get('class', [])
                    class_str = ' '.join(div_classes) if isinstance(div_classes, list) else str(div_classes)
                    
                    is_available = 'greyCol' not in class_str
                    
                    # Get format (screen name) if any
                    format_span = time_div.find('span', class_=re.compile(r'MovieSessionsListing_timeblock__frmt'))
                    format_type = format_span.get_text(strip=True) if format_span else ""
                    
                    showtimes.append(ShowTime(
                        time=show_time,
                        available=is_available,
                        format=format_type
                    ))
                
                if showtimes:
                    available_count = sum(1 for st in showtimes if st.available)
                    logger.info(f"{theater_config['name']}: {available_count}/{len(showtimes)} shows available")
                    
                    theaters.append(Theater(
                        name=theater_config["name"],
                        location=theater_name,  # Use full name as location
                        showtimes=showtimes,
                        priority=theater_config["priority"]
                    ))
        
        except Exception as e:
            logger.error(f"HTML extraction error: {e}", exc_info=True)
        
        return theaters
    
    def process_page_data(self, page_result: Dict) -> Dict:
        """Main processing function"""
        result = {
            "success": False,
            "theaters": [],
            "error": None
        }
        
        if not page_result.get("success"):
            result["error"] = page_result.get("error", "Page fetch failed")
            return result
        
        # Try JSON first
        if page_result.get("content"):
            theaters = self.extract_from_json(page_result["content"])
            if theaters:
                result["success"] = True
                result["theaters"] = theaters
                return result
        
        # Fallback to HTML
        if page_result.get("html"):
            logger.debug("Falling back to HTML parsing")
            theaters = self.extract_from_html(page_result["html"])
            if theaters:
                result["success"] = True
                result["theaters"] = theaters
                return result
        
        result["error"] = "No theater data found"
        return result
