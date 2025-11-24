#!/usr/bin/env python3
"""
Główny moduł aplikacji - interfejs CLI do zarządzania trasą i generowania mapy.
"""
import argparse
import sys
from storage import StorageManager
from geocoder import Geocoder
from map_generator import MapGenerator
from label_overrides import load_overrides


def add_city_command(storage: StorageManager, geocoder: Geocoder, city_name: str) -> None:
    """Dodaje miasto do trasy i pobiera jego współrzędne."""
    print(f"Dodawanie miasta: {city_name}")
    
    # Pobierz współrzędne
    print("Pobieranie współrzędnych...")
    coords = geocoder.get_coordinates(city_name)
    
    if coords:
        lat, lon = coords
        storage.add_city(city_name, lat, lon)
        print(f"✓ Dodano '{city_name}' (lat: {lat:.4f}, lon: {lon:.4f})")
    else:
        storage.add_city(city_name)  # Dodaj bez współrzędnych
        print(f"⚠ Dodano '{city_name}', ale nie udało się pobrać współrzędnych")


def show_route_command(storage: StorageManager) -> None:
    """Wyświetla aktualną listę miast w trasie."""
    route = storage.get_route()
    
    if not route:
        print("Trasa jest pusta.")
        return
    
    print("\nAktualna trasa:")
    print("-" * 60)
    for i, city in enumerate(route, 1):
        name = city["name"]
        lat = city.get("latitude")
        lon = city.get("longitude")
        
        if lat is not None and lon is not None:
            print(f"{i}. {name} (lat: {lat:.4f}, lon: {lon:.4f})")
        else:
            print(f"{i}. {name} (brak współrzędnych)")
    print("-" * 60)


def generate_map_command(
    storage: StorageManager,
    output_file: str = None,
    background_color: str | None = None,
    font_family: str | None = None,
    font_color: str | None = None,
    show_borders: bool | None = None,
    paper_format: str | None = None,
    dpi: int | None = None,
    line_style: str | None = None,
    line_color: str | None = None,
    line_width: float | None = None,
    point_style: str | None = None,
    point_color: str | None = None,
    point_size: float | None = None,
    title_text: str | None = None,
    footer_left_text: str | None = None,
    footer_right_text: str | None = None,
    text_font_family: str | None = None,
) -> None:
    """Generuje i wyświetla/zapisuje mapę trasy."""
    route = storage.get_route()
    
    if not route:
        print("Trasa jest pusta. Dodaj miasta przed generowaniem mapy.")
        return
    
    generator = MapGenerator()
    generator.generate_map(route, output_file, label_overrides=load_overrides(), render_labels=True)


def clear_route_command(storage: StorageManager) -> None:
    """Czyści całą trasę."""
    storage.clear_route()
    print("Trasa została wyczyszczona.")


def build_route_command(
    storage: StorageManager,
    geocoder: Geocoder,
    cities: list[str],
    output_file: str,
    background_color: str | None = None,
    font_family: str | None = None,
    font_color: str | None = None,
    show_borders: bool | None = None,
    paper_format: str | None = None,
    dpi: int | None = None,
    line_style: str | None = None,
    line_color: str | None = None,
    line_width: float | None = None,
    point_style: str | None = None,
    point_color: str | None = None,
    point_size: float | None = None,
    title_text: str | None = None,
    footer_left_text: str | None = None,
    footer_right_text: str | None = None,
    text_font_family: str | None = None,
) -> None:
    """Czyści trasę, dodaje miasta w kolejności i generuje mapę."""
    storage.clear_route()
    print("Rozpoczynam budowę nowej trasy...\n")

    for city_name in cities:
        print(f"• Dodawanie miasta: {city_name}")
        coords = geocoder.get_coordinates(city_name)
        if coords:
            lat, lon = coords
            storage.add_city(city_name, lat, lon)
            print(f"  ✓ Dodano '{city_name}' (lat: {lat:.4f}, lon: {lon:.4f})")
        else:
            storage.add_city(city_name)
            print(f"  ⚠ Dodano '{city_name}', ale nie udało się pobrać współrzędnych")

    print("\nGenerowanie mapy dla całej trasy...")
    generator = MapGenerator(
        background_color=background_color or "#0a3dbb",
        font_family=font_family or "Helvetica",
        font_color=font_color or "#ffffff",
        show_borders=show_borders,
        paper_format=paper_format,
        dpi=dpi,
    )
    generator.generate_map(route, output_file, label_overrides=load_overrides(), render_labels=True)


def _prompt_yes_no(message: str, default: bool = False) -> bool:
    """Proste pytanie tak/nie."""
    suffix = "[T/n]" if default else "[t/N]"
    prompt = f"{message} {suffix}: "
    while True:
        answer = input(prompt).strip().lower()
        if not answer:
            return default
        if answer in ("t", "tak", "y", "yes"):
            return True
        if answer in ("n", "nie", "no"):
            return False
        print("Proszę odpowiedzieć 't' (tak) lub 'n' (nie).")


def interactive_command(storage: StorageManager, geocoder: Geocoder) -> None:
    """Uruchamia interaktywny kreator trasy."""
    print(
        "\n=== Kreator trasy ===\n"
        "Podaj miasta w kolejności odwiedzania. Wpisz pustą linię, aby zakończyć.\n"
        "Możesz powtarzać miasta, aby odtworzyć przejazdy tam i z powrotem.\n"
    )

    cities: list[str] = []
    while True:
        city = input(f"Miasto #{len(cities) + 1}: ").strip()
        if not city:
            if cities:
                break
            print("Lista miast nie może być pusta. Podaj co najmniej jedno miasto.")
            continue
        cities.append(city)

    print("\n=== Ustawienia wyglądu ===")
    background = input("Kolor tła (np. #0a3dbb) [ENTER=domyślny]: ").strip() or None
    font_family = input("Rodzina czcionki (np. Helvetica) [ENTER=domyślna]: ").strip() or None
    font_color = input("Kolor podpisów (np. #ffffff) [ENTER=domyślny]: ").strip() or None
    show_borders = _prompt_yes_no("Czy dodać granice państw w tle?", default=False)

    print("\n=== Styl linii i punktów ===")
    line_style = input("Styl linii (solid/dashed/dotted/dashdot/dot) [ENTER=dashed]: ").strip() or None
    line_color = input("Kolor linii (np. #f2f4ff) [ENTER=domyślny]: ").strip() or None
    line_width_input = input("Szerokość linii (liczba, ENTER=auto): ").strip()
    line_width = None
    if line_width_input:
        try:
            line_width = float(line_width_input)
        except ValueError:
            print("Nieprawidłowa szerokość linii. Używam wartości domyślnej.")
            line_width = None

    point_style = input("Kształt punktów (circle/square/triangle/diamond/cross/star) [ENTER=circle]: ").strip() or None
    point_color = input("Kolor punktów (np. #f2f4ff) [ENTER=domyślny]: ").strip() or None
    point_size_input = input("Rozmiar punktów (liczba, ENTER=auto): ").strip()
    point_size = None
    if point_size_input:
        try:
            point_size = float(point_size_input)
        except ValueError:
            print("Nieprawidłowy rozmiar punktów. Używam wartości domyślnej.")
            point_size = None

    print("\n=== Napisy na plakacie ===")
    title_text = input("Tytuł na górze plakatu [ENTER=brak]: ").strip() or None
    footer_left_text = input("Podpis w lewym dolnym rogu [ENTER=brak]: ").strip() or None
    footer_right_text = input("Podpis w prawym dolnym rogu [ENTER=brak]: ").strip() or None
    text_font_family = input("Czcionka napisów (np. Futura) [ENTER=jak podpisy miast]: ").strip() or None

    paper_format = None
    dpi_value: int | None = None
    if _prompt_yes_no("Czy wygenerować plakat w formacie A3?", default=True):
        paper_format = "A3"
        dpi_input = input("Podaj DPI (np. 300) [ENTER=300]: ").strip()
        if dpi_input:
            try:
                dpi_value = int(dpi_input)
            except ValueError:
                print("Nieprawidłowa wartość DPI. Używam domyślnej (300).")
                dpi_value = 300
        else:
            dpi_value = 300

    output_path = input("Ścieżka pliku wyjściowego [ENTER=route_map.png]: ").strip() or "route_map.png"

    print("\nGeneruję trasę i mapę...")
    build_route_command(
        storage,
        geocoder,
        cities,
        output_path,
        background_color=background,
        font_family=font_family,
        font_color=font_color,
        show_borders=show_borders,
        paper_format=paper_format,
        dpi=dpi_value,
        line_style=line_style,
        line_color=line_color,
        line_width=line_width,
        point_style=point_style,
        point_color=point_color,
        point_size=point_size,
        title_text=title_text,
        footer_left_text=footer_left_text,
        footer_right_text=footer_right_text,
        text_font_family=text_font_family,
    )
    print("\nGotowe! Możesz znaleźć mapę pod wskazaną ścieżką.")


def main():
    """Główna funkcja CLI."""
    parser = argparse.ArgumentParser(
        description="Aplikacja do zarządzania trasą i generowania mapy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady użycia:
  python main.py add "Barcelona"
  python main.py add "Madryt"
  python main.py show
  python main.py map
  python main.py map --output mapa.png
  python main.py clear
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Dostępne komendy')
    
    # Komenda add
    add_parser = subparsers.add_parser('add', help='Dodaj miasto do trasy')
    add_parser.add_argument('city', type=str, help='Nazwa miasta do dodania')
    
    # Komenda show
    subparsers.add_parser('show', help='Wyświetl aktualną trasę')
    
    # Komenda map
    map_parser = subparsers.add_parser('map', help='Generuj mapę trasy')
    map_parser.add_argument('--output', '-o', type=str, default=None,
                            help='Ścieżka do zapisania mapy (opcjonalne)')
    map_parser.add_argument('--background', '-b', type=str, default=None,
                            help='Kolor tła mapy (np. "#f0f0f0" lub "white")')
    map_parser.add_argument('--font', '-f', type=str, default=None,
                            help='Rodzina czcionki dla podpisów miast (np. "Helvetica")')
    map_parser.add_argument('--font-color', type=str, default=None,
                            help='Kolor podpisów miast (np. "#ffffff")')
    map_parser.add_argument('--borders', action='store_true', default=False,
                            help='Wyświetl granice państw na mapie')
    map_parser.add_argument('--paper', type=str, choices=['A3'], default=None,
                            help='Format papieru (obecnie dostępny: A3)')
    map_parser.add_argument('--dpi', type=int, default=None,
                            help='Rozdzielczość DPI dla zapisu mapy (np. 300)')
    map_parser.add_argument('--line-style', type=str,
                            choices=['solid', 'dashed', 'dotted', 'dashdot', 'dot'],
                            default=None,
                            help='Styl linii trasy')
    map_parser.add_argument('--line-color', type=str, default=None,
                            help='Kolor linii trasy (np. "#f2f4ff")')
    map_parser.add_argument('--line-width', type=float, default=None,
                            help='Szerokość linii trasy (domyślnie zależna od liczby przejazdów)')
    map_parser.add_argument('--point-style', type=str,
                            choices=['circle', 'square', 'triangle', 'diamond', 'cross', 'star'],
                            default=None,
                            help='Kształt punktów miast')
    map_parser.add_argument('--point-color', type=str, default=None,
                            help='Kolor punktów miast (np. "#f2f4ff")')
    map_parser.add_argument('--point-size', type=float, default=None,
                            help='Rozmiar punktów miast (wartość "s" w Matplotlib)')
    map_parser.add_argument('--title', type=str, default=None,
                            help='Tytuł na górze plakatu')
    map_parser.add_argument('--footer-left', type=str, default=None,
                            help='Tekst w lewym dolnym rogu plakatu')
    map_parser.add_argument('--footer-right', type=str, default=None,
                            help='Tekst w prawym dolnym rogu plakatu')
    map_parser.add_argument('--text-font', type=str, default=None,
                            help='Czcionka tytułu i podpisów (domyślnie jak podpisy miast)')
    
    # Komenda clear
    subparsers.add_parser('clear', help='Wyczyść trasę')
    
    # Komenda route
    route_parser = subparsers.add_parser(
        'route',
        help='Zastąp trasę nową listą miast i wygeneruj mapę do pliku'
    )
    route_parser.add_argument(
        'cities',
        nargs='+',
        help='Lista miast w kolejności podróży'
    )
    route_parser.add_argument(
        '--output', '-o',
        type=str,
        default='route_map.png',
        help='Ścieżka pliku, do którego zapisze się mapa (domyślnie route_map.png)'
    )
    route_parser.add_argument(
        '--background', '-b',
        type=str,
        default=None,
        help='Kolor tła mapy (np. "#f0f0f0" lub "white")'
    )
    route_parser.add_argument(
        '--font', '-f',
        type=str,
        default=None,
        help='Rodzina czcionki dla podpisów miast (np. "Helvetica")'
    )
    route_parser.add_argument(
        '--font-color',
        type=str,
        default=None,
        help='Kolor podpisów miast (np. "#ffffff")'
    )
    route_parser.add_argument(
        '--borders',
        action='store_true',
        default=False,
        help='Wyświetl granice państw na mapie'
    )
    route_parser.add_argument(
        '--paper',
        type=str,
        choices=['A3'],
        default=None,
        help='Format papieru (obecnie dostępny: A3)'
    )
    route_parser.add_argument(
        '--dpi',
        type=int,
        default=None,
        help='Rozdzielczość DPI dla zapisu mapy (np. 300)'
    )
    route_parser.add_argument(
        '--line-style',
        type=str,
        choices=['solid', 'dashed', 'dotted', 'dashdot', 'dot'],
        default=None,
        help='Styl linii trasy'
    )
    route_parser.add_argument(
        '--line-color',
        type=str,
        default=None,
        help='Kolor linii trasy (np. "#f2f4ff")'
    )
    route_parser.add_argument(
        '--line-width',
        type=float,
        default=None,
        help='Szerokość linii trasy'
    )
    route_parser.add_argument(
        '--point-style',
        type=str,
        choices=['circle', 'square', 'triangle', 'diamond', 'cross', 'star'],
        default=None,
        help='Kształt punktów miast'
    )
    route_parser.add_argument(
        '--point-color',
        type=str,
        default=None,
        help='Kolor punktów miast (np. "#f2f4ff")'
    )
    route_parser.add_argument(
        '--point-size',
        type=float,
        default=None,
        help='Rozmiar punktów miast'
    )
    route_parser.add_argument(
        '--title',
        type=str,
        default=None,
        help='Tytuł na górze plakatu'
    )
    route_parser.add_argument(
        '--footer-left',
        type=str,
        default=None,
        help='Tekst w lewym dolnym rogu plakatu'
    )
    route_parser.add_argument(
        '--footer-right',
        type=str,
        default=None,
        help='Tekst w prawym dolnym rogu plakatu'
    )
    route_parser.add_argument(
        '--text-font',
        type=str,
        default=None,
        help='Czcionka tytułu i podpisów (domyślnie jak podpisy miast)'
    )

    # Komenda interactive
    subparsers.add_parser(
        'interactive',
        help='Uruchom interaktywny kreator trasy'
    )

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Inicjalizuj moduły
    storage = StorageManager()
    geocoder = Geocoder()
    
    # Wykonaj komendę
    if args.command == 'add':
        add_city_command(storage, geocoder, args.city)
        # Po dodaniu miasta automatycznie generuj mapę
        print("\nGenerowanie mapy...")
        generate_map_command(storage)
    
    elif args.command == 'show':
        show_route_command(storage)
    
    elif args.command == 'map':
        generate_map_command(
            storage,
            output_file=args.output,
            background_color=args.background,
            font_family=args.font,
            font_color=args.font_color,
            show_borders=args.borders,
            paper_format=args.paper,
            dpi=args.dpi,
            line_style=args.line_style,
            line_color=args.line_color,
            line_width=args.line_width,
            point_style=args.point_style,
            point_color=args.point_color,
            point_size=args.point_size,
            title_text=args.title,
            footer_left_text=args.footer_left,
            footer_right_text=args.footer_right,
            text_font_family=args.text_font,
        )
    
    elif args.command == 'clear':
        clear_route_command(storage)

    elif args.command == 'route':
        build_route_command(
            storage,
            geocoder,
            args.cities,
            args.output,
            background_color=args.background,
            font_family=args.font,
            font_color=args.font_color,
            show_borders=args.borders,
            paper_format=args.paper,
            dpi=args.dpi,
            line_style=args.line_style,
            line_color=args.line_color,
            line_width=args.line_width,
            point_style=args.point_style,
            point_color=args.point_color,
            point_size=args.point_size,
            title_text=args.title,
            footer_left_text=args.footer_left,
            footer_right_text=args.footer_right,
            text_font_family=args.text_font,
        )

    elif args.command == 'interactive':
        interactive_command(storage, geocoder)


if __name__ == "__main__":
    main()



