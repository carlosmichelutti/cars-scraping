# cars-scraping

`cars-scraping` is a Python command-line application that uses Playwright and Chromium to collect vehicle listings from the [Web Scraper demo car catalog](https://webscraper.io/test-sites/pagination). It follows pagination, extracts vehicle details, and exports structured CSV files for analysis.

You can collect the entire catalog into one file, export a separate file for each brand, or select a single brand. The application logs its progress to the terminal, including the pages processed and the files exported.

## Requirements

- Git to clone the repository.
- `uv` to manage Python, the virtual environment, and dependencies.
- Python 3.13 or newer. The repository selects Python 3.13 through `.python-version`; you can install it with `uv` as shown below.
- Internet access to download dependencies and Chromium and to access the demo catalog.
- A graphical desktop for the default visible browser mode. Use `--headless` on servers or in terminals without a display.

## Installation

### 1. Install uv

Follow the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/), or use the command for your operating system below.

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS or Linux (shell):**

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal after installation so that `uv` is available on your `PATH`, then verify the installation:

```sh
uv --version
```

### 2. Clone the repository

```sh
git clone https://github.com/carlosmichelutti/cars-scraping.git
cd cars-scraping
```

If you already have a local copy, open a terminal in its root directory. Run all remaining commands from that directory.

### 3. Install Python and project dependencies

```sh
uv python install 3.13
uv sync --locked
```

`uv sync --locked` creates the local `.venv` environment and installs the dependency versions recorded in `uv.lock`. You do not need to activate the environment manually when using `uv run`. See the uv guides for [installing Python](https://docs.astral.sh/uv/guides/install-python/) and [working on projects](https://docs.astral.sh/uv/guides/projects/) for more details.

### 4. Install Chromium

```sh
uv run playwright install chromium
```

The scraper also installs the Chromium build needed for the selected browser mode automatically if it is missing at launch. Installing it in advance makes the first run ready to scrape immediately.

On a supported Linux distribution, install Chromium together with its required system libraries:

```sh
uv run playwright install --with-deps chromium
```

Installing system libraries may require administrator privileges. Refer to the [Playwright browser installation documentation](https://playwright.dev/python/docs/browsers#install-system-dependencies) for supported environments and dependency details.

## Running the application

### Export the entire catalog

```sh
uv run scripts/cars_scraping.py
```

This opens a visible Chromium window, collects every page of the general catalog, writes `data/cars.csv`, and closes the browser when finished.

To run the same extraction without a browser window:

```sh
uv run scripts/cars_scraping.py --headless
```

### Export one CSV per brand

```sh
uv run scripts/cars_scraping.py --extraction-mode brands --headless
```

This discovers the brands in the catalog's sidebar and exports each brand to its own file, such as `data/bmw.csv` and `data/mercedes-benz.csv`.

### Export a single brand

```sh
uv run scripts/cars_scraping.py --extraction-mode brands --brand BMW
```

This exports only `data/bmw.csv`. Brand selection is case-insensitive. You can also pass a quoted name, such as `--brand "Mercedes-Benz"`. Add `--headless` to hide the browser window.

### Command-line options

| Option | Description | Default |
| --- | --- | --- |
| `--extraction-mode {general,brands}` | Export one file for the full catalog or one file per brand. | `general` |
| `--brand BRAND` | Select one brand. Requires `--extraction-mode brands`; omit it to collect all brands in that mode. | All brands in `brands` mode |
| `--headless` | Run Chromium without a visible window. | Disabled |
| `--no-headless` | Explicitly run Chromium with a visible window. | Visible browser |
| `-h`, `--help` | Display usage information and exit. | — |

To display the available options:

```sh
uv run scripts/cars_scraping.py --help
```

## CSV output

The application creates `data/` if necessary. Each export includes a header and uses UTF-8 encoding with a byte order mark (BOM). A successful export replaces an existing file with the same name; it does not append rows. Files from other extraction modes or brands remain in place.

| Column | Description |
| --- | --- |
| `name` | Vehicle listing name. |
| `description` | Description displayed in the catalog. |
| `year` | Vehicle year as an integer. |
| `country_of_origin` | Country of origin displayed in the listing. |
| `mileage_km` | Mileage in kilometers as an integer. |
| `status` | Catalog availability status: `Available`, `Reserved`, or `Sold`. |
| `available_quantity` | Available stock count; empty for reserved or sold vehicles. |
| `price_usd` | Price in US dollars as an integer. |
| `rating` | Number of filled stars displayed in the listing. |

## Project structure

```text
cars-scraping/
├── scripts/
│   ├── cars_scraping.py  # CLI, browser automation, extraction, and CSV export
│   └── _logging.py       # Console logging and pagination progress
├── data/                 # Exported CSV files
├── .python-version       # Python version selected by uv
├── pyproject.toml        # Project metadata and dependencies
├── uv.lock               # Locked dependency versions
└── README.md
```

## Troubleshooting

- **`uv` is not recognized:** restart the terminal and check that the installation directory reported by the uv installer is on your `PATH`.
- **Chromium fails to install:** check your internet connection and rerun `uv run playwright install chromium`.
- **Missing system libraries on Linux:** run `uv run playwright install --with-deps chromium` on a supported distribution.
- **No graphical display:** add `--headless` to the execution command.
- **Unknown brand:** use a brand from the catalog sidebar. The error message lists the available brands; `--brand` must be used with `--extraction-mode brands`.
- **Extraction fails:** check the error logged in the terminal and your access to the demo catalog. Changes to the catalog's HTML or listing format may require updates to the scraper.

The application exits with code `0` on success, `1` when extraction fails, or `2` for invalid command-line arguments.
