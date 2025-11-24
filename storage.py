"""
Moduł przechowywania trasy - zarządza listą miast.
"""
import json
import os
from typing import List, Dict


class StorageManager:
    """Zarządza przechowywaniem trasy w pliku JSON."""
    
    def __init__(self, storage_file: str = "route.json"):
        self.storage_file = storage_file
        self.route: List[Dict] = []
        self.load_route()
    
    def load_route(self) -> None:
        """Wczytuje trasę z pliku, jeśli istnieje."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    self.route = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.route = []
        else:
            self.route = []
    
    def save_route(self) -> None:
        """Zapisuje trasę do pliku."""
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(self.route, f, ensure_ascii=False, indent=2)
    
    def add_city(self, city_name: str, latitude: float = None, longitude: float = None) -> None:
        """Dodaje miasto do trasy."""
        city_data = {
            "name": city_name,
            "latitude": latitude,
            "longitude": longitude
        }
        self.route.append(city_data)
        self.save_route()
    
    def update_city_coordinates(self, index: int, latitude: float, longitude: float) -> None:
        """Aktualizuje współrzędne miasta o podanym indeksie."""
        if 0 <= index < len(self.route):
            self.route[index]["latitude"] = latitude
            self.route[index]["longitude"] = longitude
            self.save_route()
    
    def get_route(self) -> List[Dict]:
        """Zwraca aktualną trasę."""
        return self.route.copy()
    
    def clear_route(self) -> None:
        """Czyści trasę."""
        self.route = []
        self.save_route()
    
    def get_cities_list(self) -> List[str]:
        """Zwraca listę nazw miast."""
        return [city["name"] for city in self.route]



