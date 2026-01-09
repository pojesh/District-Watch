"""
Change detection using content hashing
"""

import hashlib
import json
import logging
from typing import List, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detect changes in theater availability"""
    
    def __init__(self, state_manager, movie_id: str = "default"):
        self.state = state_manager
        self.movie_id = movie_id
        self._hash_key = f"hash_{movie_id}"
        self._theaters_key = f"theaters_{movie_id}"
    
    def compute_hash(self, theaters: List) -> str:
        """Compute hash of theater data"""
        sorted_theaters = sorted(theaters, key=lambda t: (t.priority, t.name))
        
        data = []
        for theater in sorted_theaters:
            theater_data = {
                "name": theater.name,
                "showtimes": [
                    {"time": st.time, "available": st.available, "format": st.format}
                    for st in sorted(theater.showtimes, key=lambda x: x.time)
                ]
            }
            data.append(theater_data)
        
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def is_new_availability(self, theaters: List) -> bool:
        """Check if this is new availability"""
        if not theaters:
            return False
        
        current_hash = self.compute_hash(theaters)
        last_hash = self.state.get_value(self._hash_key)
        
        is_new = current_hash != last_hash
        
        if is_new:
            logger.info(f"New availability detected for {self.movie_id}")
            self.state.set_value(self._hash_key, current_hash)
            self.state.set_value(f"last_change_{self.movie_id}", datetime.now().isoformat())
        
        return is_new
    
    def get_new_theaters(self, theaters: List) -> List:
        """Get newly appearing theaters"""
        current_names = {t.name for t in theaters}
        
        last_names_str = self.state.get_value(self._theaters_key, "[]")
        try:
            last_names = set(json.loads(last_names_str))
        except:
            last_names = set()
        
        new_names = current_names - last_names
        
        if new_names:
            logger.info(f"New theaters: {new_names}")
            self.state.set_value(self._theaters_key, json.dumps(list(current_names)))
            return [t for t in theaters if t.name in new_names]
        
        # Update theater list
        if current_names != last_names:
            self.state.set_value(self._theaters_key, json.dumps(list(current_names)))
        
        return []
    
    def should_alert(self, theaters: List, force: bool = False) -> bool:
        """Determine if alert should be sent"""
        if force:
            return True
        
        if not theaters:
            return False
        
        is_new = self.is_new_availability(theaters)
        new_theaters = self.get_new_theaters(theaters)
        
        return is_new or len(new_theaters) > 0
    
    def format_summary(self, theaters: List) -> str:
        """Create human-readable summary"""
        if not theaters:
            return "No theaters available"
        
        sorted_theaters = sorted(theaters, key=lambda t: (t.priority, t.name))
        
        lines = []
        for theater in sorted_theaters:
            stars = "⭐" * theater.priority
            lines.append(f"{stars} *{theater.name}*")
            
            if theater.location:
                lines.append(f"   📍 {theater.location}")
            
            available = [st.time for st in theater.showtimes if st.available]
            if available:
                times = ", ".join(available[:6])
                if len(available) > 6:
                    times += f" +{len(available) - 6} more"
                lines.append(f"   🎬 {times}")
            
            lines.append("")
        
        return "\n".join(lines)
