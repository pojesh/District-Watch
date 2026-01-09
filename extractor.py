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
        """Fallback HTML parsing"""
        theaters = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            for theater_config in self.target_theaters:
                for keyword in theater_config.keywords:
                    elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
                    
                    if elements:
                        time_pattern = r'\b(\d{1,2}:\d{2}\s*(?:AM|PM))\b'
                        
                        for element in elements:
                            context = str(element.parent) if element.parent else ""
                            times = re.findall(time_pattern, context, re.IGNORECASE)
                            
                            if times:
                                showtimes = [ShowTime(time=t, available=True) for t in times]
                                theaters.append(Theater(
                                    name=theater_config.name,
                                    showtimes=showtimes,
                                    priority=theater_config.priority
                                ))
                                logger.debug(f"HTML fallback: found {len(times)} times for {theater_config.name}")
                                break
        
        except Exception as e:
            logger.error(f"HTML extraction error: {e}")
        
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
