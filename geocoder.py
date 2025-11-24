"""
Moduł pobierania współrzędnych geograficznych miast.
"""
import time
from typing import Tuple, Optional
import ssl

import certifi
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


class Geocoder:
    """Pobiera współrzędne geograficzne dla nazw miast używając Nominatim API."""
    
    def __init__(self, user_agent: str = "route_mapper_app"):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.geolocator = Nominatim(user_agent=user_agent, ssl_context=ssl_context)
        self.rate_limit_delay = 1.0  # Opóźnienie między zapytaniami (Nominatim wymaga)
    
    def get_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """
        Pobiera współrzędne dla nazwy miasta.
        
        Args:
            city_name: Nazwa miasta
            
        Returns:
            Tuple (latitude, longitude) lub None jeśli nie znaleziono
        """
        try:
            time.sleep(self.rate_limit_delay)  # Szanujemy rate limit API
            location = self.geolocator.geocode(city_name, timeout=10)
            
            if location:
                return (location.latitude, location.longitude)
            else:
                return None
                
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Błąd podczas pobierania współrzędnych dla '{city_name}': {e}")
            return None
        except Exception as e:
            print(f"Nieoczekiwany błąd dla '{city_name}': {e}")
            return None


