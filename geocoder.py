"""
Moduł pobierania współrzędnych geograficznych miast.
"""
import time
import unicodedata
from typing import List, Optional, Tuple
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
        self.retry_attempts = 3

    @staticmethod
    def _normalize_key(value: str) -> str:
        """Lowercase string stripped of accents for alias lookups."""
        value = unicodedata.normalize("NFKD", value.strip().lower())
        return "".join(char for char in value if not unicodedata.combining(char))

    def _build_query_candidates(self, city_name: str) -> List[str]:
        base = city_name.strip()
        if not base:
            return []

        candidates = []
        seen = set()

        def add_candidate(query: str) -> None:
            query_clean = query.strip()
            if not query_clean:
                return
            if query_clean in seen:
                return
            seen.add(query_clean)
            candidates.append(query_clean)

        add_candidate(base)

        ascii_variant = unicodedata.normalize("NFKD", base)
        ascii_variant = "".join(c for c in ascii_variant if not unicodedata.combining(c))
        if ascii_variant != base:
            add_candidate(ascii_variant)

        if "," not in base:
            add_candidate(f"{base}, Europe")

        return candidates

    def _geocode_query(self, query: str) -> Optional[Tuple[float, float]]:
        for attempt in range(1, self.retry_attempts + 1):
            try:
                time.sleep(self.rate_limit_delay)
                location = self.geolocator.geocode(
                    query,
                    timeout=10,
                    language="pl",
                )
                if location:
                    return (location.latitude, location.longitude)
                # Jeśli nic nie znaleziono, nie ma sensu ponawiać tego samego zapytania
                break
            except (GeocoderTimedOut, GeocoderServiceError) as exc:
                if attempt == self.retry_attempts:
                    print(f"Błąd podczas pobierania współrzędnych dla '{query}': {exc}")
                continue
            except Exception as exc:
                if attempt == self.retry_attempts:
                    print(f"Nieoczekiwany błąd dla '{query}': {exc}")
                continue
        return None

    def get_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """
        Pobiera współrzędne dla nazwy miasta.

        Args:
            city_name: Nazwa miasta

        Returns:
            Tuple (latitude, longitude) lub None jeśli nie znaleziono
        """
        for query in self._build_query_candidates(city_name):
            coords = self._geocode_query(query)
            if coords:
                return coords
        print(f"Nie udało się pobrać współrzędnych dla '{city_name}'.")
        return None
