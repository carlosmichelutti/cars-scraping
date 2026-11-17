import argparse
import csv
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

from playwright.sync_api import (
    Browser,
    BrowserType,
    Error,
    Locator,
    Page,
    sync_playwright,
)

if __package__:
    from ._logging import configure_logging, log_page_progress, logger
else:
    from _logging import configure_logging, log_page_progress, logger

CATALOG_URL = 'https://webscraper.io/test-sites/pagination'
DATA_DIR = Path(__file__).resolve().parents[1] / 'data'


@dataclass
class Car:
    """A vehicle listing with the values exported to CSV."""

    name: str
    description: str
    year: int
    country_of_origin: str
    mileage_km: int
    status: str
    available_quantity: int | None
    price_usd: int
    rating: int


def launch_chromium(chromium: BrowserType, headless: bool) -> Browser:
    """
    Launches Chromium and installs its Playwright build if needed.

    Args:
        chromium (BrowserType): Playwright browser type for Chromium.
        headless (bool): Whether to launch without a visible window.

    Returns:
        Browser: Running Chromium instance.

    Raises:
        Error: When Playwright fails to launch an installed browser.
        RuntimeError: When the Playwright browser installer exits with an error.
    """
    try:
        return chromium.launch(headless=headless)
    except Error as exc:
        if "Executable doesn't exist at" not in str(exc):
            raise

    logger.info('Installing Chromium for Playwright')
    install_mode = '--only-shell' if headless else '--no-shell'
    try:
        subprocess.run(
            [sys.executable, '-m', 'playwright', 'install', install_mode, 'chromium'],
            check=True
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError('Failed to install Chromium for Playwright.') from exc
    return chromium.launch(headless=headless)


def open_page(page: Page, url: str) -> None:
    """
    Opens a catalog page and checks its HTTP response.

    Args:
        page (Page): Playwright page used for navigation.
        url (str): Absolute URL to open.

    Returns:
        None: The page is ready for DOM extraction.

    Raises:
        RuntimeError: When navigation returns no response or a failed HTTP status.
    """
    response = page.goto(url, wait_until='domcontentloaded')
    if response is None:
        raise RuntimeError(f'No HTTP response for {url}')
    if not response.ok:
        raise RuntimeError(f'HTTP {response.status} while opening {url}')


def brand_slug(name: str) -> str:
    """
    Converts a brand name to a lowercase key suitable for filenames.

    Args:
        name (str): Brand label from the menu or the command line.

    Returns:
        str: Brand key with words separated by hyphens.
    """
    return re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')


def discover_brands(page: Page, catalog_url: str, brand: str | None = None) -> dict[str, str]:
    """
    Reads the top-level brand links and optionally selects one brand.

    Args:
        page (Page): Playwright page used to read the menu.
        catalog_url (str): URL of the general catalog.
        brand (str | None): Brand name to select, or None to include all brands.

    Returns:
        dict[str, str]: Brand keys mapped to absolute catalog URLs.

    Raises:
        RuntimeError: When the menu contains no usable brand links.
        ValueError: When the requested brand is absent from the menu.
    """
    open_page(page, catalog_url)
    brands: dict[str, str] = {}
    for link in page.locator('ul#side-menu > li > a.category-link[href]').all():
        slug = brand_slug(link.inner_text())
        href = link.get_attribute('href')
        if slug and href:
            brands[slug] = urljoin(page.url, href)

    if not brands:
        raise RuntimeError(f'No brands found at {catalog_url}')
    if brand is None:
        return brands

    slug = brand_slug(brand)
    if slug not in brands:
        raise ValueError(f'Unknown brand {brand!r}. Available brands are {", ".join(brands)}.')
    return {slug: brands[slug]}


def parse_availability(text: str) -> tuple[str, int | None]:
    """
    Reads the listing status and the stock count when available.

    Args:
        text (str): Text displayed on the availability badge.

    Returns:
        tuple[str, int | None]: Status and available quantity, if shown.

    Raises:
        ValueError: When the status or quantity does not match the catalog format.
    """
    status = text.strip()
    if status in ('Reserved', 'Sold'):
        return status, None

    available = re.fullmatch(r'Available:\s*(\d+)', status)
    if available:
        return 'Available', int(available[1])
    raise ValueError(f'Unexpected availability value {text!r}')


def extract_car(card: Locator) -> Car:
    """
    Extracts one vehicle from a listing card.

    Args:
        card (Locator): Playwright locator for a single vehicle card.

    Returns:
        Car: Listing values including mileage in km, price in USD, and active stars.

    Raises:
        ValueError: When a required detail is missing or a value cannot be parsed.
    """
    name = card.locator('[itemprop="name"]').inner_text().strip()
    details: dict[str, str] = {}
    for text in card.locator('.card-text').all_text_contents():
        label, _, value = text.partition(':')
        details[label.strip()] = value.strip()

    price = card.locator('[itemprop="price"]').inner_text().strip()
    availability = card.locator('.availability .badge').inner_text()
    rating = card.locator('.rarity-rating')
    rating.wait_for(state='attached')

    try:
        status, quantity = parse_availability(availability)
        year = int(details['Year'])
        country = details['Country of origin']
        mileage = int(''.join(details['Mileage'].removesuffix(' km').split()))
        price_usd = int(''.join(price.removeprefix('USD ').split()))
    except (KeyError, ValueError) as exc:
        raise ValueError(f'Invalid data for listing {name!r}. {exc}') from exc

    return Car(
        name=name,
        description=card.locator('[itemprop="description"]').inner_text().strip(),
        year=year,
        country_of_origin=country,
        mileage_km=mileage,
        status=status,
        available_quantity=quantity,
        price_usd=price_usd,
        rating=rating.locator('.ws-icon-star.active').count()
    )


def scrape_catalog(page: Page, start_url: str, brand: str | None = None) -> list[Car]:
    """
    Extracts all pages of a general or brand catalog in listing order.

    Args:
        page (Page): Playwright page used across the catalog.
        start_url (str): URL of the first catalog page.
        brand (str | None): Brand being collected, or None for the general catalog.

    Returns:
        list[Car]: All listings found by following the next-page links.

    Raises:
        RuntimeError: When a page fails to load, is empty, repeats, or lacks its next link.
        ValueError: When a listing value cannot be parsed.
    """
    cars: list[Car] = []
    visited: set[str] = set()
    url = start_url

    while url not in visited:
        visited.add(url)
        open_page(page, url)
        catalog = page.locator('.test-items-container')
        cards = catalog.locator('.test-sites-card').all()
        if not cards:
            raise RuntimeError(f'No vehicles found at {page.url}')

        current_page = catalog.get_attribute('data-current-page')
        last_page = catalog.get_attribute('data-last-page')
        page_number = int(current_page) if current_page and current_page.isdecimal() else len(visited)
        total_pages = int(last_page) if last_page and last_page.isdecimal() else None
        log_page_progress(brand, page_number, total_pages)
        cars.extend(extract_car(card) for card in cards)

        next_links = page.locator('ul.pagination a[rel="next"][href]').all()
        if next_links:
            href = next_links[0].get_attribute('href')
            if href:
                url = urljoin(page.url, href)
                continue
        if total_pages is not None and page_number != total_pages:
            raise RuntimeError(f'Missing next-page link at {page.url}')
        return cars

    raise RuntimeError(f'Pagination returned to an already visited page at {url}')


def write_csv(cars: list[Car], destination: Path) -> None:
    """
    Writes the listings to a UTF-8 CSV file with a header.

    Args:
        cars (list[Car]): Listings to write in catalog order.
        destination (Path): Path to the final CSV file.

    Returns:
        None: The CSV has been written to its destination.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode='w', encoding='utf-8-sig', newline='', dir=destination.parent, delete=False
        ) as output:
            temp_path = Path(output.name)
            writer = csv.DictWriter(output, fieldnames=[field.name for field in fields(Car)])
            writer.writeheader()
            writer.writerows(asdict(car) for car in cars)
        temp_path.replace(destination)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parses the browser and catalog options.

    Args:
        argv (list[str] | None): Arguments to parse, or None to use the command line.

    Returns:
        argparse.Namespace: Parsed headless, extraction mode, and brand options.

    Raises:
        SystemExit: When help is requested or the arguments are invalid.
    """
    parser = argparse.ArgumentParser(description='Extract vehicles from the demo catalog.')
    parser.add_argument(
        '--headless',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Run Chromium without a window. The browser is visible by default.'
    )
    parser.add_argument(
        '--extraction-mode',
        choices=('general', 'brands'),
        default='general',
        help='Write cars.csv in general mode (default) or one CSV per brand in brands mode.'
    )
    parser.add_argument(
        '--brand',
        help='Select one brand in brands mode. Omit this option to extract all brands.'
    )

    args = parser.parse_args(argv)
    if args.brand is not None and args.extraction_mode != 'brands':
        parser.error('--brand requires --extraction-mode brands')
    return args


def main() -> int:
    """
    Runs the requested extraction and reports the CSV files written.

    Returns:
        int: Zero on success or one if extraction fails.

    Raises:
        SystemExit: When help is requested or the command-line arguments are invalid.
    """
    args = parse_args()
    configure_logging()
    logger.info(
        'Starting extraction in %s mode. Browser is %s (headless=%s)',
        args.extraction_mode,
        'hidden' if args.headless else 'visible',
        args.headless
    )
    if args.extraction_mode == 'brands' and args.brand is None:
        logger.info('Collecting all brands from the catalog')

    try:
        with sync_playwright() as playwright:
            browser = launch_chromium(playwright.chromium, args.headless)
            try:
                page = browser.new_page()
                catalogs = {'cars': CATALOG_URL}
                if args.extraction_mode == 'brands':
                    catalogs = discover_brands(page, CATALOG_URL, args.brand)

                for name, url in catalogs.items():
                    brand = name if args.extraction_mode == 'brands' else None
                    if brand is not None:
                        logger.info('Collecting brand %s', brand)
                    cars = scrape_catalog(page, url, brand)
                    destination = DATA_DIR / f'{name}.csv'
                    write_csv(cars, destination)
                    logger.info('Exported %d vehicles to %s', len(cars), destination)
            finally:
                browser.close()
    except (Error, OSError, RuntimeError, ValueError) as exc:
        logger.error('Extraction failed. %s', exc)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
