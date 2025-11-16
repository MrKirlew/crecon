"""
Location Service - Geofencing and Location Management
Handles location detection, geofencing, and distance calculations
"""
import math
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth
    Returns distance in meters
    """
    R = 6371000  # Earth radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


class Location:
    """Location model"""
    def __init__(
        self,
        id: str,
        name: str,
        latitude: float,
        longitude: float,
        radius_meters: float = 100.0,
        description: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.radius_meters = radius_meters
        self.description = description
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def is_within_radius(self, lat: float, lon: float) -> bool:
        """Check if given coordinates are within this location's radius"""
        distance = haversine_distance(self.latitude, self.longitude, lat, lon)
        return distance <= self.radius_meters
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_meters": self.radius_meters,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class LocationService:
    """Service for managing locations and geofencing"""
    
    def __init__(self):
        # In-memory storage (replace with database in production)
        self.locations: Dict[str, Location] = {}
        logger.info("LocationService initialized")
    
    def create_location(
        self,
        name: str,
        latitude: float,
        longitude: float,
        radius_meters: float = 100.0,
        description: Optional[str] = None
    ) -> Location:
        """Create a new location"""
        location_id = str(uuid4())
        location = Location(
            id=location_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            description=description
        )
        self.locations[location_id] = location
        logger.info(f"Created location: {name} ({location_id})")
        return location
    
    def get_location(self, location_id: str) -> Optional[Location]:
        """Get location by ID"""
        return self.locations.get(location_id)
    
    def list_locations(self) -> List[Location]:
        """List all locations"""
        return list(self.locations.values())
    
    def update_location(
        self,
        location_id: str,
        name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: Optional[float] = None,
        description: Optional[str] = None
    ) -> Optional[Location]:
        """Update a location"""
        location = self.locations.get(location_id)
        if not location:
            return None
        
        if name is not None:
            location.name = name
        if latitude is not None:
            location.latitude = latitude
        if longitude is not None:
            location.longitude = longitude
        if radius_meters is not None:
            location.radius_meters = radius_meters
        if description is not None:
            location.description = description
        
        location.updated_at = datetime.utcnow()
        logger.info(f"Updated location: {location_id}")
        return location
    
    def delete_location(self, location_id: str) -> bool:
        """Delete a location"""
        if location_id in self.locations:
            del self.locations[location_id]
            logger.info(f"Deleted location: {location_id}")
            return True
        return False
    
    def find_nearby_locations(self, lat: float, lon: float) -> List[Location]:
        """Find all locations within which the given coordinates fall"""
        nearby = []
        for location in self.locations.values():
            if location.is_within_radius(lat, lon):
                nearby.append(location)
        return nearby
    
    def get_location_by_coordinates(
        self,
        lat: float,
        lon: float,
        radius_meters: Optional[float] = None
    ) -> Optional[Location]:
        """Get the first location that contains the given coordinates"""
        nearby = self.find_nearby_locations(lat, lon)
        if nearby:
            # If radius specified, filter by it
            if radius_meters is not None:
                nearby = [loc for loc in nearby if loc.radius_meters <= radius_meters]
            return nearby[0] if nearby else None
        return None

