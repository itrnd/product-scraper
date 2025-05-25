"""
Product Scraper

This script scrapes product data from the WebScraper.io test site and saves it to CSV and JSON files.
It navigates through the catalog, clicks "Load More" until all products are loaded, and extracts
information for each product including title, price, description, rating, and reviews.
"""

import json
import argparse
import os
import sys
from typing import Tuple

import yaml
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

from utils import CURRENCY_SYMBOLS, retry, setup_logger


class ProductScraper:
    """Class to scrape product data from WebScraper.io test site."""

    def __init__(self, config_file="config.yaml", headless=True):
        """Initialize the scraper with Chrome WebDriver and configuration.

        Args:
            config_file (str): Path to the configuration file. Default is "config.yaml".
            headless (bool): Whether to run Chrome in headless mode. Default is True.
        """
        self.url, self.config = self.load_config(config_file)

        self.logger = setup_logger(self.config.get("logging", {}))
        self.logger.info("Initializing ProductScraper", extra={"config_file": config_file, "headless": headless})

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        self.logger.debug("Configuring Chrome options", extra={"options": chrome_options.arguments})
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.products_raw = []
        self.products = []
        self.failed_products = []

    def load_config(self, config_file) -> Tuple[str, dict]:
        """Load configuration from YAML file and construct target URL.

        Args:
            config_file (str): Path to the configuration file.

        Returns:
            Tuple[str, dict]: A tuple containing the constructed URL and loaded config dictionary.

        Raises:
            FileNotFoundError: If the specified configuration file does not exist.
        """
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, "r") as cfg:
            config_data = yaml.safe_load(cfg)

        url = f"{config_data['base_url']}/{config_data['category']}"

        return url, config_data

    @retry(retries=3, backoff_factor=0.5, error_types=(TimeoutException,))
    def navigate_to_site(self):
        """Navigate to the target website."""
        self.logger.info("Navigating to website", extra={"url": self.url})
        self.driver.get(self.url)
        card_selector = self.config["selectors"]["card"]
        self.logger.debug("Waiting for page to load", extra={"selector": card_selector})
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, card_selector)))
        self.logger.info("Successfully navigated to website", extra={"url": self.url})

    def load_all_products(self):
        """Click 'Load More' button until all products are loaded, parsing products after each load."""
        self.logger.info("Loading and parsing products incrementally")
        previous_product_count = 0
        processed_product_count = 0

        card_selector = self.config["selectors"]["card"]
        load_more_button_selector = self.config["selectors"]["load_more_button"]

        self.logger.debug(
            "Using selectors",
            extra={"card_selector": card_selector, "load_more_button_selector": load_more_button_selector},
        )

        self.extract_product_data(start_index=processed_product_count)
        processed_product_count = len(self.products_raw)
        self.logger.info("Initially processed products", extra={"count": processed_product_count})

        while True:
            try:
                current_products = self.driver.find_elements(By.CSS_SELECTOR, card_selector)
                current_product_count = len(current_products)

                if current_product_count > 0 and current_product_count == previous_product_count:
                    self.logger.info(
                        "No new products loaded. All products loaded.", extra={"product_count": current_product_count}
                    )
                    break

                previous_product_count = current_product_count

                self.logger.debug("Waiting for 'Load More' button to be clickable")
                load_more_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, load_more_button_selector))
                )

                if not load_more_button.is_displayed() or not load_more_button.is_enabled():
                    self.logger.info("No more products to load. Button not visible or enabled.")
                    break

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)

                self.wait.until(EC.visibility_of(load_more_button))

                self._click_load_more(load_more_button)

                try:
                    self.wait.until(
                        lambda driver: len(driver.find_elements(By.CSS_SELECTOR, card_selector)) > current_product_count
                    )

                    new_product_count = len(self.driver.find_elements(By.CSS_SELECTOR, card_selector))
                    self.logger.info("Loaded more products", extra={"product_count": new_product_count})

                    self.extract_product_data(start_index=processed_product_count)
                    processed_product_count = len(self.products_raw)
                    self.logger.info("Processed products so far", extra={"processed_count": processed_product_count})
                except TimeoutException:
                    self.logger.info("No new products loaded after clicking 'Load More'. All products loaded.")
                    break

            except TimeoutException:
                self.logger.info("No more 'Load More' button found. All products loaded.")
                break
            except StaleElementReferenceException:
                self.logger.info("Page refreshing with new content. Continuing...")
                continue
            except Exception as e:
                self.logger.error(
                    "Error while loading more products", extra={"error": str(e), "error_type": type(e).__name__}
                )
                break

    @retry(retries=3, backoff_factor=0.5, error_types=(WebDriverException, StaleElementReferenceException))
    def _click_load_more(self, load_more_button):
        """Click the 'Load More' button with retry logic.

        Args:
            load_more_button: The WebElement representing the 'Load More' button.
        """
        try:
            load_more_button.click()
            self.logger.debug("Clicked 'Load More' button")
        except Exception as e:
            self.logger.warning("Direct click failed", extra={"error": str(e), "error_type": type(e).__name__})
            self.driver.execute_script("arguments[0].click();", load_more_button)
            self.logger.debug("Clicked 'Load More' button using JavaScript")

    @retry(retries=3, backoff_factor=0.5, error_types=(WebDriverException, StaleElementReferenceException))
    def _extract_single_product(self, card, selectors):
        """Extract data from a single product card with retry logic.

        Args:
            card: The WebElement representing the product card.
            selectors: Dictionary of CSS selectors for different elements.

        Returns:
            dict: A dictionary containing the extracted product data.

        Raises:
            NoSuchElementException: If a required element is not found.
            Exception: For any other unexpected errors.
        """
        title_selector = selectors["title"]
        price_selector = selectors["price"]
        description_selector = selectors["description"]
        ratings_container_selector = selectors["ratings_container"]
        star_icon_selector = selectors["star_icon"]
        reviews_selector = selectors["reviews"]

        title_element = card.find_element(By.CSS_SELECTOR, title_selector)
        title = title_element.get_attribute("title") or title_element.text

        price = card.find_element(By.CSS_SELECTOR, price_selector).text

        description = card.find_element(By.CSS_SELECTOR, description_selector).text

        rating_element = card.find_element(By.CSS_SELECTOR, ratings_container_selector)
        full_stars = rating_element.find_elements(By.CSS_SELECTOR, star_icon_selector)
        rating = len(full_stars)

        reviews_text = card.find_element(By.CSS_SELECTOR, reviews_selector).text
        reviews = int(reviews_text.split()[0])

        return {
            "title": title,
            "price": price,
            "description": description,
            "rating": rating,
            "reviews": reviews,
        }

    def extract_product_data(self, start_index=0):
        """Extract data for each product.

        Args:
            start_index (int): The index to start extracting from. Default is 0.
        """
        self.logger.info("Extracting product data", extra={"start_index": start_index})

        selectors = self.config["selectors"]
        card_selector = selectors["card"]

        product_cards = self.driver.find_elements(By.CSS_SELECTOR, card_selector)
        self.logger.debug(
            "Found product cards",
            extra={"total_cards": len(product_cards), "processing_cards": len(product_cards[start_index:])},
        )

        for card in product_cards[start_index:]:
            try:
                product_data = self._extract_single_product(card, selectors)

                self.products_raw.append(product_data)
                self.logger.debug(
                    "Extracted product data", extra={"product_title": product_data.get("title", "Unknown")}
                )

            except NoSuchElementException as e:
                card_index = start_index + product_cards.index(card)
                self.logger.error(
                    "Error extracting data from product card: missing element",
                    extra={"error": str(e), "error_type": "NoSuchElementException", "product_index": card_index},
                )
                self.failed_products.append(
                    {
                        "index": card_index,
                        "reason": f"Missing element: {str(e)}",
                        "error_type": "NoSuchElementException",
                    }
                )
            except Exception as e:
                card_index = start_index + product_cards.index(card)
                self.logger.error(
                    "Unexpected error extracting data from product card",
                    extra={"error": str(e), "error_type": type(e).__name__, "product_index": card_index},
                )
                self.failed_products.append({"index": card_index, "reason": str(e), "error_type": type(e).__name__})

        self.logger.info("Completed product data extraction", extra={"total_products": len(self.products_raw)})

    def parse_price(self, price_str):
        """Extract currency and price value from price string.

        Detects currency symbol and extracts numeric value.

        Args:
            price_str (str): The price string to extract value from.

        Returns:
            tuple: (currency_code, numeric_price_value)
        """
        default_currency = self.config["currency"]["default"]
        detected_currency = default_currency

        for symbol, code in CURRENCY_SYMBOLS.items():
            if symbol in price_str:
                detected_currency = code
                price_str = price_str.replace(symbol, "").strip()
                break

        numeric_match = re.search(r"[\d,]+\.?\d*", price_str)
        if numeric_match:
            numeric_str = numeric_match.group(0)
            numeric_value = float(numeric_str.replace(",", ""))
        else:
            numeric_value = None

        return detected_currency, numeric_value

    def convert_currency(self, amount, from_currency, to_currency):
        """Convert an amount from one currency to another.

        Args:
            amount (float): The amount to convert
            from_currency (str): The source currency code
            to_currency (str): The target currency code

        Returns:
            float: The converted amount
        """
        if amount is None:
            return None

        rates = self.config["currency"]["rates"]

        if from_currency == to_currency:
            return amount

        if from_currency not in rates or to_currency not in rates:
            print(f"Warning: Currency conversion not possible. Missing rate for {from_currency} or {to_currency}")
            return None

        amount_in_usd = amount / rates[from_currency]
        converted_amount = amount_in_usd * rates[to_currency]

        return round(converted_amount, 2)

    def process_raw_data(self):
        """Process raw data into structured data."""
        self.logger.info("Processing raw data into structured data")

        target_currency = self.config["currency"]["target"]
        self.logger.debug("Target currency for conversion", extra={"target_currency": target_currency})

        for raw_prod in self.products_raw:
            product = raw_prod.copy()

            price_str = raw_prod["price"]
            currency, amount = self.parse_price(price_str)

            converted_amount = self.convert_currency(amount, currency, target_currency)

            product["price_data"] = {
                "raw": price_str,
                "currency": currency,
                "amount": amount,
                "converted_currency": target_currency,
                "converted_amount": converted_amount,
            }

            del product["price"]

            self.products.append(product)
            self.logger.debug(
                "Processed product",
                extra={
                    "title": product.get("title", "Unknown"),
                    "original_currency": currency,
                    "original_amount": amount,
                    "converted_amount": converted_amount,
                },
            )

        self.logger.info("Completed raw data processing", extra={"processed_products": len(self.products)})

    def save_raw_to_json(self):
        """Save the raw data to a JSON file."""
        if not self.products_raw:
            self.logger.warning("No raw data to save")
            return

        filename = self.config["output"].get("raw_json_filename", "products_raw.json")
        self.logger.debug(
            "Saving raw data to JSON", extra={"file_path": filename, "product_count": len(self.products_raw)}
        )

        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(self.products_raw, json_file, indent=4)
        self.logger.info(
            "Raw data saved to JSON file", extra={"file_path": filename, "product_count": len(self.products_raw)}
        )

    def save_to_json(self):
        """Save the structured data to a JSON file."""
        if not self.products:
            self.logger.warning("No structured data to save")
            return

        filename = self.config["output"].get("json_filename", "products.json")
        self.logger.debug(
            "Saving structured data to JSON", extra={"file_path": filename, "product_count": len(self.products)}
        )

        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(self.products, json_file, indent=4)
        self.logger.info(
            "Structured data saved to JSON file", extra={"file_path": filename, "product_count": len(self.products)}
        )

    def save_raw_to_csv(self):
        """Save the raw data to a CSV file."""
        if not self.products_raw:
            self.logger.warning("No raw data to save")
            return

        filename = self.config["output"].get("raw_csv_filename", "products_raw.csv")
        self.logger.debug(
            "Saving raw data to CSV", extra={"file_path": filename, "product_count": len(self.products_raw)}
        )

        df = pd.DataFrame(self.products_raw)
        df.to_csv(filename, index=False)
        self.logger.info(
            "Raw data saved to CSV file", extra={"file_path": filename, "product_count": len(self.products_raw)}
        )

    def save_to_csv(self):
        """Save the structured data to a CSV file."""
        if not self.products:
            self.logger.warning("No structured data to save")
            return

        filename = self.config["output"].get("csv_filename", "products.csv")
        self.logger.debug(
            "Saving structured data to CSV", extra={"file_path": filename, "product_count": len(self.products)}
        )

        flattened_data = []
        for product in self.products:
            flat_product = {
                "title": product.get("title", ""),
                "description": product.get("description", ""),
                "rating": product.get("rating", 0),
                "reviews": product.get("reviews", 0),
                "price_raw": product["price_data"].get("raw", ""),
                "price_currency": product["price_data"].get("currency", ""),
                "price_amount": product["price_data"].get("amount", 0),
                "price_converted_currency": product["price_data"].get("converted_currency", ""),
                "price_converted_amount": product["price_data"].get("converted_amount", 0),
            }
            flattened_data.append(flat_product)

        df = pd.DataFrame(flattened_data)
        df.to_csv(filename, index=False)
        self.logger.info(
            "Structured data saved to CSV file", extra={"file_path": filename, "product_count": len(self.products)}
        )

    def save_failed_products(self):
        """Save information about failed products to a JSON file."""
        if not self.failed_products:
            self.logger.info("No failed products to save")
            return

        filename = self.config["output"].get("failed_json_filename", "failed_products.json")
        self.logger.debug(
            "Saving failed products data", extra={"file_path": filename, "failed_count": len(self.failed_products)}
        )

        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(self.failed_products, json_file, indent=4)
        self.logger.info(
            "Failed products saved to JSON file",
            extra={"file_path": filename, "failed_count": len(self.failed_products)},
        )

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.logger.info("WebDriver closed")

    def run(self):
        """Run the complete scraping process."""
        self.logger.info("Starting the scraping process")
        try:
            self.navigate_to_site()
            self.load_all_products()

            self.logger.info("Saving raw data")
            self.save_raw_to_json()
            self.save_raw_to_csv()

            self.logger.info("Processing raw data into structured data")
            self.process_raw_data()

            self.logger.info("Saving processed data")
            self.save_to_csv()
            self.save_to_json()
            self.save_failed_products()

            self.logger.info(
                "Scraping process completed successfully",
                extra={"total_products": len(self.products), "failed_products": len(self.failed_products)},
            )
        except Exception as e:
            self.logger.error("Error during scraping process", extra={"error": str(e), "error_type": type(e).__name__})
            raise
        finally:
            self.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape product data from WebScraper.io test site")
    parser.add_argument("--headed", action="store_true", help="Run in headed mode (with browser GUI)")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Override the log level from config (default: use config setting)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Error: Configuration file not found: {args.config}")
        sys.exit(1)

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    if args.log_level:
        if "logging" not in config:
            config["logging"] = {}
        config["logging"]["level"] = args.log_level

    scraper = ProductScraper(config_file=args.config, headless=not args.headed)
    scraper.run()
