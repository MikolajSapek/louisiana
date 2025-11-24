# Aplikacja do zarządzania trasą i generowania mapy

Minimalistyczna aplikacja CLI do dodawania miejsc (miast) i generowania mapy z połączeniami między nimi.

## Instalacja

1. Zainstaluj wymagane pakiety:
```bash
pip install -r requirements.txt
```

## Użycie

### Wersja web (Flask)
```bash
# 1. Zainstaluj zależności
pip install -r requirements.txt

# 2. Uruchom serwer (z auto-reloadem podczas developmentu)
flask --app app.py run --reload
# alternatywnie:
# python app.py

# 3. Otwórz w przeglądarce
# http://localhost:5000/
```
Formularz zbiera miasta i ustawienia wyglądu, wysyła je do API (`/api/generate`)
i zwraca gotowy plakat (PNG). Wszystko działa lokalnie, bez webhooków ani usług zewnętrznych.

### Dodawanie miasta do trasy
```bash
python main.py add "Barcelona"
python main.py add "Madryt"
python main.py add "Paryż"
```

### Generowanie mapy
```bash
# Wyświetlenie mapy
python main.py map

# Zapisanie mapy do pliku
python main.py map --output mapa.png

# Z niestandardowym tłem i czcionką podpisów
python main.py map --background "#f0f0f0" --font "Helvetica"

# Z niestandardowym kolorem podpisów (np. jasny na ciemnym tle)
python main.py map --font-color "#ffffff"

# Z innym stylem linii i punktów
python main.py map --line-style dotted --line-color "#ffd966" --point-style star --point-color "#ffffff"

# Z granicami państw w tle
python main.py map --borders

# W formacie A3 przy 300 DPI (automatyczna orientacja)
python main.py map --paper A3 --dpi 300 --output plakat_a3.png

# Z tytułem, podpisami i inną czcionką napisów
python main.py map --title "Nasza droga" --footer-left "Wiosna 2025" --footer-right "Trasa: Warszawa → Lizbona" --text-font "Futura"
```

### Interaktywny kreator (bez pamiętania parametrów)
```bash
python main.py interactive
```
Kreator poprosi o kolejne miasta, kolor tła, czcionkę, kolor podpisów,
granice państw oraz format/DPI plakatu, a następnie wygeneruje mapę.

### Zdefiniowanie całej trasy jedną komendą i zapis mapy do pliku
```bash
# Nadpisuje trasę, dodaje miasta w kolejności i zapisuje mapę do route_map.png
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona

# Z własną nazwą pliku
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona --output trasa.png

# Z własnym tłem i czcionką podpisów
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona --background "#f7f3ea" --font "Helvetica"

# Z jasnym podpisem na ciemnym tle
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona --background "#0a3dbb" --font-color "#ffffff"

# Z granicami państw w tle
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona --borders

# W formacie A3 przy 300 DPI (automatyczna orientacja)
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona --paper A3 --dpi 300 --output trasa_a3.png

# Z własnym stylem linii/punktów
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona --line-style dot --point-style square --point-size 80

# Z tytułem, podpisami i czcionką napisów
python main.py route Warszawa Wiedeń Mediolan "Monaco" "San Sebastian" Lizbona --title "Road Trip 2025" --footer-left "Autor: Mikołaj" --footer-right "Dystans 3200 km" --text-font "Avenir"
```

### Wyświetlenie aktualnej trasy
```bash
python main.py show
```

### Czyszczenie trasy
```bash
python main.py clear
```

## Funkcje

- ✅ Dodawanie miast przez CLI
- ✅ Automatyczne pobieranie współrzędnych geograficznych (Nominatim API)
- ✅ Przechowywanie trasy w pliku JSON (`route.json`)
- ✅ Generowanie minimalistycznej mapy z połączeniami
- ✅ Jednokrotne zdefiniowanie trasy i automatyczny zapis mapy do pliku
- ✅ Wyświetlanie i eksport mapy
- ✅ Personalizacja wyglądu (kolor tła, czcionka i kolor podpisów, granice państw w tle, format A3 przy zadanym DPI)
- ✅ Zaawansowana personalizacja linii i punktów (kolory, style, szerokości, rozmiary, kształty)
- ✅ Napisy tytułu i stopki (góra, dół lewy/prawy) z możliwością wyboru czcionki
- ✅ Wielokrotne przejazdy tą samą trasą (linie rozchylane przy nałożeniach)
- ✅ Interaktywny kreator dla szybkiego wprowadzania ustawień bez pamięci argumentów CLI
- ✅ Lekki interfejs web oparty o Flask – formularz + API generujące mapy

## Struktura projektu

- `app.py` - Serwer Flask (HTML + API)
- `main.py` - Główny interfejs CLI
- `storage.py` - Zarządzanie przechowywaniem trasy
- `geocoder.py` - Pobieranie współrzędnych geograficznych
- `map_generator.py` - Generowanie mapy
- `templates/` - HTML interfejsu web
- `static/` - Zasoby web (CSS, JS, wygenerowane mapy)
- `route.json` - Plik z zapisaną trasą (tworzony automatycznie)

## Uwagi

- Aplikacja używa Nominatim API (OpenStreetMap), które wymaga opóźnienia między zapytaniami
- Współrzędne są pobierane automatycznie po dodaniu miasta
- Mapa jest automatycznie generowana po każdym dodaniu miasta
- Domyślne tło mapy to głęboki odcień Royal Blue (`#0a3dbb`), dobrze kontrastujący z jasnymi podpisami



