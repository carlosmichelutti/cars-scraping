import logging

logger = logging.getLogger('cars_scraping')


def configure_logging() -> None:
    """
    Configures timestamped console logging for the scraper.

    Returns:
        None: Console logging is configured at INFO level.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def log_page_progress(brand: str | None, page_number: int, total_pages: int | None) -> None:
    """
    Logs the catalog page being collected and the remaining pages when known.

    Args:
        brand (str | None): Brand being collected, or None for the general catalog.
        page_number (int): Current catalog page number.
        total_pages (int | None): Total pages reported by the catalog, or None if unavailable.

    Returns:
        None: Page progress was sent to the logger.
    """
    catalog = f'brand {brand}' if brand is not None else 'the general catalog'
    if total_pages is None:
        logger.info('Collecting page %d for %s', page_number, catalog)
        return

    logger.info(
        'Collecting page %d of %d for %s (%d remaining)',
        page_number,
        total_pages,
        catalog,
        total_pages - page_number
    )
