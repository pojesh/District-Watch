"""
Configuration management for DistrictWatch
Supports dynamic multi-movie, multi-theatre configuration
"""

import os
import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class TheaterConfig:
    """Theater configuration with priority"""
    name: str
    priority: int = 1  # 1 = highest priority
    keywords: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.keywords:
            self.keywords = [self.name.lower()]
    
    def to_dict(self) -> dict:
        return {"name": self.name, "priority": self.priority, "keywords": self.keywords}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TheaterConfig':
        return cls(**data)
    
    @classmethod
    def parse_string(cls, theater_str: str) -> 'TheaterConfig':
        """Parse theater from string format: NAME:PRIORITY:keyword1,keyword2"""
        parts = theater_str.split(":")
        name = parts[0].strip()
        priority = int(parts[1]) if len(parts) > 1 else 1
        keywords = [k.strip().lower() for k in parts[2].split(",")] if len(parts) > 2 else [name.lower()]
        return cls(name=name, priority=priority, keywords=keywords)


@dataclass
class MovieConfig:
    """Individual movie configuration"""
    movie_id: str
    movie_url: str
    movie_name: str
    city: str = "Chennai"
    target_theaters: List[TheaterConfig] = field(default_factory=list)
    check_interval: int = 120
    enabled: bool = True
    added_at: str = ""
    
    def to_dict(self) -> dict:
        return {
            "movie_id": self.movie_id,
            "movie_url": self.movie_url,
            "movie_name": self.movie_name,
            "city": self.city,
            "target_theaters": [t.to_dict() for t in self.target_theaters],
            "check_interval": self.check_interval,
            "enabled": self.enabled,
            "added_at": self.added_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MovieConfig':
        theaters = [TheaterConfig.from_dict(t) for t in data.get("target_theaters", [])]
        return cls(
            movie_id=data["movie_id"],
            movie_url=data["movie_url"],
            movie_name=data["movie_name"],
            city=data.get("city", "Chennai"),
            target_theaters=theaters,
            check_interval=data.get("check_interval", 120),
            enabled=data.get("enabled", True),
            added_at=data.get("added_at", "")
        )


@dataclass
class AppConfig:
    """Main application configuration"""
    
    # Default theaters for new movies
    default_theaters: List[TheaterConfig] = field(default_factory=list)
    
    # Active movies
    movies: Dict[str, MovieConfig] = field(default_factory=dict)
    
    # Timing
    check_interval: int = 120
    min_interval: int = 30
    max_interval: int = 300
    
    # Telegram
    telegram_token: str = ""
    telegram_chat_id: str = ""
    
    # Browser
    headless: bool = True
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    request_timeout: int = 60000
    
    # Reliability
    max_retries: int = 3
    retry_delay: int = 5
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300
    
    # Paths
    log_level: str = "INFO"
    log_file: str = "logs/district-watch.log"
    db_path: str = "data/state.db"
    movies_file: str = "data/movies.json"
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Load configuration from environment"""
        
        # Parse default theaters
        theaters_str = os.getenv("DEFAULT_THEATERS", "")
        default_theaters = []
        if theaters_str:
            for theater_def in theaters_str.split(";"):
                if theater_def.strip():
                    default_theaters.append(TheaterConfig.parse_string(theater_def))
        
        # Telegram credentials
        telegram_token = os.getenv("TELEGRAM_TOKEN", "")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        if not telegram_token or not telegram_chat_id:
            raise ValueError(
                "TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are required.\n"
                "Get token from @BotFather and chat ID from @userinfobot on Telegram."
            )
        
        config = cls(
            default_theaters=default_theaters,
            check_interval=int(os.getenv("CHECK_INTERVAL", "120")),
            min_interval=int(os.getenv("MIN_INTERVAL", "30")),
            max_interval=int(os.getenv("MAX_INTERVAL", "300")),
            telegram_token=telegram_token,
            telegram_chat_id=telegram_chat_id,
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay=int(os.getenv("RETRY_DELAY", "5")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "60000")),
            circuit_breaker_threshold=int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5")),
            circuit_breaker_timeout=int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "logs/district-watch.log"),
            db_path=os.getenv("DB_PATH", "data/state.db"),
            movies_file=os.getenv("MOVIES_FILE", "data/movies.json")
        )
        
        # Load saved movies
        config.load_movies()
        
        # Add initial movie from env if no movies configured
        initial_url = os.getenv("MOVIE_URL")
        if initial_url and not config.movies:
            config.add_movie(
                url=initial_url,
                name=os.getenv("MOVIE_NAME", "Movie"),
                city=os.getenv("CITY", "Chennai")
            )
        
        return config
    
    def load_movies(self) -> None:
        """Load movies from JSON file"""
        if not os.path.exists(self.movies_file):
            return
        
        try:
            with open(self.movies_file, 'r') as f:
                data = json.load(f)
                self.movies = {
                    movie_id: MovieConfig.from_dict(movie_data)
                    for movie_id, movie_data in data.items()
                }
        except Exception as e:
            print(f"Warning: Could not load movies config: {e}")
    
    def save_movies(self) -> None:
        """Save movies to JSON file"""
        try:
            Path(self.movies_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.movies_file, 'w') as f:
                data = {mid: m.to_dict() for mid, m in self.movies.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save movies config: {e}")
    
    def _generate_movie_id(self, name: str, city: str) -> str:
        """Generate unique movie ID"""
        base = f"{name.lower().replace(' ', '_')}_{city.lower()}"
        base = re.sub(r'[^a-z0-9_]', '', base)
        
        # Ensure uniqueness
        if base not in self.movies:
            return base
        
        counter = 2
        while f"{base}_{counter}" in self.movies:
            counter += 1
        return f"{base}_{counter}"
    
    def add_movie(
        self,
        url: str,
        name: str,
        city: str = "Chennai",
        theaters: Optional[List[TheaterConfig]] = None
    ) -> str:
        """Add a new movie to monitor"""
        movie_id = self._generate_movie_id(name, city)
        
        # Use default theaters if not specified
        if theaters is None:
            theaters = [TheaterConfig(t.name, t.priority, t.keywords.copy()) 
                       for t in self.default_theaters]
        
        movie = MovieConfig(
            movie_id=movie_id,
            movie_url=url,
            movie_name=name,
            city=city,
            target_theaters=theaters,
            check_interval=self.check_interval,
            enabled=True,
            added_at=datetime.now().isoformat()
        )
        
        self.movies[movie_id] = movie
        self.save_movies()
        return movie_id
    
    def remove_movie(self, movie_id: str) -> bool:
        """Remove a movie"""
        if movie_id in self.movies:
            del self.movies[movie_id]
            self.save_movies()
            return True
        return False
    
    def enable_movie(self, movie_id: str) -> bool:
        """Enable movie monitoring"""
        if movie_id in self.movies:
            self.movies[movie_id].enabled = True
            self.save_movies()
            return True
        return False
    
    def disable_movie(self, movie_id: str) -> bool:
        """Disable movie monitoring"""
        if movie_id in self.movies:
            self.movies[movie_id].enabled = False
            self.save_movies()
            return True
        return False
    
    def get_movie(self, movie_id: str) -> Optional[MovieConfig]:
        """Get movie by ID"""
        return self.movies.get(movie_id)
    
    def get_active_movies(self) -> List[MovieConfig]:
        """Get all enabled movies"""
        return [m for m in self.movies.values() if m.enabled]
    
    def list_movies(self) -> List[Dict]:
        """Get summary of all movies"""
        return [
            {
                "id": mid,
                "name": m.movie_name,
                "city": m.city,
                "enabled": m.enabled,
                "theaters": len(m.target_theaters)
            }
            for mid, m in self.movies.items()
        ]
    
    def update_movie_theaters(self, movie_id: str, theaters: List[TheaterConfig]) -> bool:
        """Update theaters for a specific movie"""
        if movie_id in self.movies:
            self.movies[movie_id].target_theaters = theaters
            self.save_movies()
            return True
        return False
    
    def add_theater_to_movie(self, movie_id: str, theater: TheaterConfig) -> bool:
        """Add a theater to a movie"""
        if movie_id in self.movies:
            # Check if already exists
            existing = [t.name.lower() for t in self.movies[movie_id].target_theaters]
            if theater.name.lower() not in existing:
                self.movies[movie_id].target_theaters.append(theater)
                self.save_movies()
                return True
        return False
    
    def remove_theater_from_movie(self, movie_id: str, theater_name: str) -> bool:
        """Remove a theater from a movie"""
        if movie_id in self.movies:
            theaters = self.movies[movie_id].target_theaters
            original_count = len(theaters)
            self.movies[movie_id].target_theaters = [
                t for t in theaters if t.name.lower() != theater_name.lower()
            ]
            if len(self.movies[movie_id].target_theaters) < original_count:
                self.save_movies()
                return True
        return False
    
    def validate(self) -> None:
        """Validate configuration"""
        if self.check_interval < self.min_interval:
            raise ValueError(f"check_interval must be >= {self.min_interval}")
        if self.check_interval > self.max_interval:
            raise ValueError(f"check_interval must be <= {self.max_interval}")
        if self.max_retries < 1:
            raise ValueError("max_retries must be >= 1")
