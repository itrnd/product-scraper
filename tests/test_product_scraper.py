import pytest
from product_scraper import ProductScraper


@pytest.fixture
def scraper(mock_config, mocker):
    mocker.patch("selenium.webdriver.Chrome")
    mocker.patch("product_scraper.setup_logger")
    mock_config_file = "mock_config.yaml"
    mock_url = "mock_url"
    mocker.patch("product_scraper.ProductScraper.load_config", return_value=(mock_url, mock_config))
    scraper_instance = ProductScraper(mock_config_file)
    mocker.patch.object(scraper_instance, "config", mock_config)
    return scraper_instance


def test_parse_price_with_usd(scraper):
    """Test parsing a price string with USD currency."""
    result = scraper.parse_price("$1,234.56")
    assert result == ("USD", 1234.56)


def test_parse_price_with_eur(scraper):
    """Test parsing a price string with EUR currency."""
    result = scraper.parse_price("€789.01")
    assert result == ("EUR", 789.01)


def test_parse_price_with_gbp(scraper):
    """Test parsing a price string with GBP currency."""
    result = scraper.parse_price("£456")
    assert result == ("GBP", 456.0)


def test_parse_price_without_currency(scraper):
    """Test parsing a price string without any recognizable currency."""
    result = scraper.parse_price("123.45")
    assert result == (scraper.config["currency"]["default"], 123.45)


def test_parse_price_with_invalid_format(scraper):
    """Test parsing a price string with an invalid format."""
    result = scraper.parse_price("dummy_price")
    assert result == (scraper.config["currency"]["default"], None)


@pytest.fixture
def mock_config():
    return {
        "currency": {
            "default": "USD",
            "target": "EUR",
            "rates": {
                "USD": 1.0,
                "EUR": 0.85,
                "GBP": 0.76,
            },
        },
        "selectors": {
            "card": ".product-card",
            "title": ".product-title",
            "price": ".product-price",
            "description": ".product-description",
        },
    }


def test_process_raw_data_with_valid_products(scraper, mocker):
    """Test that valid raw products are processed correctly."""
    scraper.products_raw = [
        {"title": "Product A", "price": "$100.00"},
        {"title": "Product B", "price": "€200.50"},
    ]
    scraper.config["currency"]["target"] = "GBP"
    scraper.process_raw_data()

    assert len(scraper.products) == 2
    assert scraper.products[0]["price_data"]["currency"] == "USD"
    assert scraper.products[0]["price_data"]["amount"] == 100.0
    assert scraper.products[0]["price_data"]["converted_amount"] == 76.0

    assert scraper.products[1]["price_data"]["currency"] == "EUR"
    assert scraper.products[1]["price_data"]["amount"] == 200.5
    assert scraper.products[1]["price_data"]["converted_amount"] == 179.27


def test_process_raw_data_no_products(scraper):
    """Test that an empty products_raw list results in no processed products."""
    scraper.products_raw = []

    scraper.process_raw_data()

    assert len(scraper.products) == 0


def test_process_raw_data_with_invalid_price(scraper, mocker):
    """Test that products with invalid prices are not processed correctly."""
    scraper.products_raw = [
        {"title": "Product A", "price": "invalid_price"},
        {"title": "Product B", "price": "$300.00"},
    ]

    scraper.process_raw_data()

    assert len(scraper.products) == 2
    assert scraper.products[0]["price_data"]["currency"] == "USD"
    assert scraper.products[0]["price_data"]["amount"] is None
    assert scraper.products[0]["price_data"]["converted_amount"] is None
    assert scraper.products[1]["price_data"]["currency"] == "USD"
    assert scraper.products[1]["price_data"]["amount"] == 300.0
    assert scraper.products[1]["price_data"]["converted_amount"] == 255.0
