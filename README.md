# Product Scraper

A configurable Python web scraper that extracts product data from the WebScraper.io test site.

## Description

This project scrapes product information from the [WebScraper.io test site](https://webscraper.io/test-sites/e-commerce/more). It navigates through the catalog, clicks the "Load More" button and parses products incrementally after each click, extracting the following information for each product:

- Title (e.g., "Lenovo ThinkPad X1 Carbon 6th Gen Ultrabook")
- Price (e.g., $1,229.00)
- Description (short text with product specs)
- Star rating (1-5)
- Number of reviews

The scraper separates raw data (as scraped from the website) from structured data (processed and normalized). It includes currency detection and conversion functionality, allowing prices to be converted from their original currency to a target currency specified in the configuration.

The extracted data is saved in both CSV and JSON formats, with separate files for raw and structured data. The scraper is configurable via a YAML file, making it easy to repoint to different product categories (e.g., laptops, tablets) and customize currency conversion rates without changing the code.

## Installation

1. Ensure you have Python 3.12 or higher installed.

2. Install uv (a fast Python package installer):
   ```
   pip install uv
   ```

3. Clone this repository:
   ```
   git clone https://github.com/itrnd/product-scraper.git
   cd product-scraper
   ```

4. Create a virtual environment using uv:
   ```
   uv venv
   ```

5. Activate the virtual environment:
   - On Windows:
     ```
     .venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source .venv/bin/activate
     ```

6. Install the required dependencies using uv sync:
   ```
   uv sync
   ```

   For development dependencies:
   ```
   uv sync --group dev
   ```

7. Make sure you have Chrome browser installed, as the script uses ChromeDriver.

## Usage

Run the script with:

```
python product_scraper.py [--headed] [--config CONFIG_FILE] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
```

Options:
- `--headed`: Run with browser GUI visible (default is headless mode)
- `--config`: Path to the configuration file (default: config.yaml)
- `--log-level`: Override the log level from config (default: use config setting)

The script will:
1. Load the configuration from the specified YAML file
2. Open a Chrome browser (headless by default, or with GUI if --headed is specified)
3. Navigate to the target website specified in the configuration
4. Parse the initial products on the page
5. Click "Load More" and parse newly loaded products incrementally, waiting dynamically for content
6. Process raw data into structured data, including currency detection and conversion
7. Save both raw and structured data to CSV and JSON files as specified in the configuration
8. Close the browser

## Configuration

The scraper uses a YAML configuration file to define:
- Base URL and category path
- CSS selectors for various elements
- Currency conversion settings
- Output file formats and paths
- Logging configuration

Example configuration (config.yaml):

```yaml
base_url: "https://webscraper.io/test-sites/e-commerce/more"
category: "computers/laptops"

selectors:
  card: ".card"
  load_more_button: ".ecomerce-items-scroll-more"
  title: ".title"
  price: ".price"
  description: ".description"
  ratings_container: ".ratings"
  star_icon: ".glyphicon-star"
  reviews: ".ratings p.pull-right"

currency:
  default: "USD"
  target: "EUR"
  rates:
    USD: 1.0
    EUR: 0.85
    GBP: 0.75
    JPY: 110.0
    CAD: 1.25

output:
  csv_filename: "products.csv"
  json_filename: "products.json"
  raw_csv_filename: "products_raw.csv"
  raw_json_filename: "products_raw.json"
  failed_json_filename: "failed_products.json"

logging:
  level: "INFO"
  format: "json"
  file: "scraper.log"
  console: true
```

To scrape a different category (e.g., tablets), simply change the `category` value in the configuration file:

```yaml
category: "computers/tablets"
```

## Output Files

The scraper generates both raw and structured data files in CSV and JSON formats.

### Raw Data

#### CSV Format (products.csv)

The raw CSV file contains the following columns:
- title: The product title
- price: The product price (as a string with currency symbol)
- description: The product description (raw text)
- rating: The star rating (1-5)
- reviews: The number of reviews

#### JSON Format (products.json)

The raw JSON file contains an array of product objects, each with the following properties:
- title: The product title
- price: The product price (as a string with currency symbol)
- description: The product description (raw text)
- rating: The star rating (1-5)
- reviews: The number of reviews

### Structured Data

#### CSV Format (products_structured.csv)

The structured CSV file contains the following columns:
- title: The product title
- description: The product description
- rating: The star rating (1-5)
- reviews: The number of reviews
- price_raw: The original price string
- price_currency: The detected currency code (e.g., USD)
- price_amount: The numeric price amount in the original currency
- price_converted_currency: The target currency code (e.g., EUR)
- price_converted_amount: The converted price amount in the target currency

#### JSON Format (products_structured.json)

The structured JSON file contains an array of product objects, each with the following properties:
- title: The product title
- description: The product description
- rating: The star rating (1-5)
- reviews: The number of reviews
- price_data: An object containing:
  - raw: The original price string
  - currency: The detected currency code
  - amount: The numeric price amount in the original currency
  - converted_currency: The target currency code
  - converted_amount: The converted price amount in the target currency

### Failed Products JSON

The failed_products.json file contains an array of objects representing products that failed to be extracted, each with the following properties:
- index: The index of the product in the list of all products
- reason: The reason for the failure (error message)
- error_type: The type of error that occurred (e.g., NoSuchElementException)

This file is useful for debugging and improving the scraper, as it provides detailed information about which products failed and why.

The output filenames can be customized in the configuration file.

## Dependencies

- selenium: For browser automation
- pandas: For data handling and CSV export
- webdriver-manager: For managing WebDriver binaries
- pyyaml: For parsing YAML configuration files

## Structured JSON Logging

The scraper implements structured JSON logging to provide detailed, machine-readable logs that can be easily parsed and analyzed. When configured with `format: "json"` in the logging section of the configuration file, the logs will be output in JSON format with the following fields:

- `timestamp`: ISO-8601 formatted timestamp of the log entry
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `message`: The log message
- `logger`: Name of the logger
- Additional context fields specific to each log entry

Example JSON log entry:
```json
{
  "timestamp": "2023-05-15T14:32:45.123456",
  "level": "INFO",
  "message": "Loaded more products",
  "logger": "product_scraper",
  "product_count": 24
}
```

The structured logs can be directed to both a file and the console based on the configuration. The log level can be set in the configuration file or overridden via the command-line `--log-level` argument.

## Testing

The project includes a test suite using pytest. The tests cover specific functionality of the `ProductScraper` class, including:

1. Price parsing with different currencies (USD, EUR, GBP)
2. Price parsing without currency
3. Price parsing with invalid format
4. Processing raw data with valid products
5. Processing raw data with no products
6. Processing raw data with invalid price

### Running Tests

To run the tests, first ensure you have the development dependencies installed:

```
uv sync --group dev
```

Then run the tests using pytest:

```
pytest tests/
```

For more detailed test output:

```
pytest -v tests/
```

## Notes

- The script runs Chrome in headless mode by default (no GUI). Use the `--headed` flag to run with the browser GUI visible.
- The script uses dynamic waiting for content loading instead of hard-coded sleeps, ensuring reliable operation even with varying network speeds.
- The script includes comprehensive error handling to manage potential issues during scraping, including handling of stale elements and timeouts.
- The scraper implements robust click handling for the "Load More" button, preventing click interception by fixed elements like the navbar. It centers the button in the viewport and falls back to JavaScript clicking if direct clicking fails.
- The configuration-based approach makes it easy to repoint the scraper to different product categories without changing the code.
- All selectors, URLs, and output formats are defined in the external configuration file, making the scraper highly customizable.
- The scraper parses products incrementally after each "Load More" click, rather than waiting for all products to be loaded first. This approach is more efficient, especially for large catalogs, as it processes data as it becomes available.
- The scraper logs failures per product with detailed reasons (e.g., missing selector, invalid data format) and saves this information to a `failed_products.json` file for later analysis and debugging.
- The scraper implements retry logic with exponential backoff for transient page errors. Critical operations like navigation, clicking, and data extraction will be retried up to 3 times with increasing delays between attempts, making the scraper more resilient to network issues and temporary page glitches.
- The scraper separates raw data (as scraped from the website) from structured data (processed and normalized), providing both for maximum flexibility in downstream processing.
- The currency detection functionality automatically identifies currency symbols in price strings and converts them to a standardized format.
- The currency conversion feature allows prices to be converted from their original currency to any target currency specified in the configuration, using the conversion rates defined in the config file.
- The structured data output includes both the original price information and the converted price, making it easy to compare prices across different currencies.
