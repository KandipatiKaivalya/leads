from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from lead_pipeline.src.linkedin_scraper import LinkedInScraper

@pytest.fixture
def mock_config():
    return {
        "scrape": {
            "linkedin": {
                "enabled": True,
                "search_term": "solar sales manager",
                "max_pages": 1,
                "delay_seconds": 0.1,
                "headless": True,
                "max_results": 5
            }
        },
        "selectors": {
            "linkedin": {
                "card_container": ".test-card",
                "name": ".test-name",
                "title": ".test-title",
                "location": ".test-loc",
                "link": ".test-link"
            }
        }
    }

def test_clean_name():
    scraper = LinkedInScraper({"scrape": {"linkedin": {}}})
    assert scraper._clean_name("Hemanth Gona • 1st") == "Hemanth Gona"
    assert scraper._clean_name("Sampangi Srikanth • 3rd+") == "Sampangi Srikanth"
    assert scraper._clean_name("  John Doe  ") == "John Doe"
    assert scraper._clean_name("") == ""

def test_parse_title_and_company():
    scraper = LinkedInScraper({"scrape": {"linkedin": {}}})
    # Title at Company
    title, company = scraper._parse_title_and_company("Solar Sales Manager at AmityEco Renew")
    assert title == "Solar Sales Manager"
    assert company == "AmityEco Renew"

    # Title | Company
    title, company = scraper._parse_title_and_company("Solar Installer | BR Enterprises")
    assert title == "Solar Installer"
    assert company == "BR Enterprises"

    # Just title
    title, company = scraper._parse_title_and_company("Solar Sales Consultant")
    assert title == "Solar Sales Consultant"
    assert company == ""

@patch("lead_pipeline.src.linkedin_scraper.sync_playwright")
def test_scraper_run_mocked(mock_sync_playwright, mock_config):
    # Set up mock Playwright chain
    mock_playwright = MagicMock()
    mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
    
    mock_browser = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    
    mock_page = MagicMock()
    mock_browser.new_page.return_value = mock_page
    
    # Mock URLs and login checks
    mock_page.url = "https://www.linkedin.com/feed"
    mock_page.title.return_value = "LinkedIn Feed"
    mock_page.query_selector.return_value = None
    
    # Create mock result cards
    mock_card = MagicMock()
    
    mock_name_el = MagicMock()
    mock_name_el.inner_text.return_value = "Hemanth Gona • 1st"
    
    mock_title_el = MagicMock()
    mock_title_el.inner_text.return_value = "Solar Sales Manager at AmityEco Renew"
    
    mock_loc_el = MagicMock()
    mock_loc_el.inner_text.return_value = "Hyderabad, TS"
    
    mock_link_el = MagicMock()
    mock_link_el.get_attribute.return_value = "https://www.linkedin.com/in/hemanth-gona-12345?query=1"

    # Map selectors inside query_selector
    def mock_query_selector(selector):
        if selector == ".test-name":
            return mock_name_el
        elif selector == ".test-title":
            return mock_title_el
        elif selector == ".test-loc":
            return mock_loc_el
        elif selector == ".test-link":
            return mock_link_el
        return None
        
    mock_card.query_selector.side_effect = mock_query_selector
    mock_page.query_selector_all.return_value = [mock_card]
    
    # Run the scraper
    scraper = LinkedInScraper(mock_config)
    df = scraper.run()
    
    # Assertions
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    
    row = df.iloc[0]
    assert row["name"] == "Hemanth Gona"
    assert row["title"] == "Solar Sales Manager"
    assert row["company"] == "AmityEco Renew"
    assert row["location"] == "Hyderabad, TS"
    assert row["source"] == "linkedin"
    assert row["source_url"] == "https://www.linkedin.com/in/hemanth-gona-12345"
    assert "scraped_at" in row

def test_check_auth_status_authenticated():
    scraper = LinkedInScraper({"scrape": {"linkedin": {}}})
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/feed/"
    mock_page.title.return_value = "LinkedIn Feed"
    mock_page.query_selector.return_value = None
    
    # URL matches /feed
    assert scraper._check_auth_status(mock_page, timeout_ms=50) == "authenticated"

def test_check_auth_status_unauthenticated():
    scraper = LinkedInScraper({"scrape": {"linkedin": {}}})
    
    # URL matches /login
    mock_page1 = MagicMock()
    mock_page1.url = "https://www.linkedin.com/login"
    mock_page1.title.return_value = "LinkedIn Login"
    mock_page1.query_selector.return_value = None
    assert scraper._check_auth_status(mock_page1, timeout_ms=50) == "unauthenticated"
    
    # Username field present
    mock_page2 = MagicMock()
    mock_page2.url = "https://www.linkedin.com/"
    mock_page2.title.return_value = "LinkedIn"
    def mock_query_selector(sel):
        return MagicMock() if sel == "#username" else None
    mock_page2.query_selector.side_effect = mock_query_selector
    assert scraper._check_auth_status(mock_page2, timeout_ms=50) == "unauthenticated"

def test_check_auth_status_challenge():
    scraper = LinkedInScraper({"scrape": {"linkedin": {}}})
    
    # URL matches /challenge
    mock_page1 = MagicMock()
    mock_page1.url = "https://www.linkedin.com/checkpoint/challenge/verify"
    mock_page1.title.return_value = "LinkedIn"
    mock_page1.query_selector.return_value = None
    assert scraper._check_auth_status(mock_page1, timeout_ms=50) == "challenge"
    
    # Title matches Security Challenge
    mock_page2 = MagicMock()
    mock_page2.url = "https://www.linkedin.com/"
    mock_page2.title.return_value = "Security Challenge | LinkedIn"
    mock_page2.query_selector.return_value = None
    assert scraper._check_auth_status(mock_page2, timeout_ms=50) == "challenge"

def test_check_auth_status_navigation_retry():
    from playwright.sync_api import Error as PlaywrightError
    
    scraper = LinkedInScraper({"scrape": {"linkedin": {}}})
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/feed/"
    mock_page.title.return_value = "LinkedIn Feed"
    
    call_count = 0
    def mock_query_selector_with_error(selector):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PlaywrightError("Execution context was destroyed, most likely because of a navigation")
        return None
        
    mock_page.query_selector.side_effect = mock_query_selector_with_error
    
    # Run status check. It should retry upon error and successfully return "authenticated"
    status = scraper._check_auth_status(mock_page, timeout_ms=100)
    assert status == "authenticated"
    assert call_count > 1  # Verified retry occurred

@patch("lead_pipeline.src.linkedin_scraper.sync_playwright")
def test_scraper_run_paragraph_selectors(mock_sync_playwright):
    # Set up mock Playwright chain
    mock_playwright = MagicMock()
    mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
    
    mock_browser = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    
    mock_page = MagicMock()
    mock_browser.new_page.return_value = mock_page
    
    # Mock URLs and login checks
    mock_page.url = "https://www.linkedin.com/feed"
    mock_page.title.return_value = "LinkedIn Feed"
    mock_page.query_selector.return_value = None
    
    # Create mock result card
    mock_card = MagicMock()
    
    # Mock p tags query_selector_all return values
    p1 = MagicMock()
    p1.inner_text.return_value = "Nikhil Kar • 2nd"
    p2 = MagicMock()
    p2.inner_text.return_value = "Sales manager at Swiggy"
    p3 = MagicMock()
    p3.inner_text.return_value = "Mahasamund, Chhattisgarh, India"
    
    mock_card.query_selector_all.return_value = [p1, p2, p3]
    
    # Mock link query_selector return value
    mock_link_el = MagicMock()
    mock_link_el.get_attribute.return_value = "https://www.linkedin.com/in/nikhil-kar-12345"
    mock_card.query_selector.return_value = mock_link_el
    
    mock_page.query_selector_all.return_value = [mock_card]
    
    # Config setup
    config = {
        "scrape": {
            "linkedin": {
                "enabled": True,
                "search_term": "solar sales manager",
                "max_pages": 1,
                "delay_seconds": 0.1,
                "headless": True,
                "max_results": 5
            }
        },
        "selectors": {
            "linkedin": {
                "card_container": "[role='listitem']",
                "name": "p",
                "title": "p",
                "location": "p",
                "link": "a[href*='/in/']"
            }
        }
    }
    
    scraper = LinkedInScraper(config)
    df = scraper.run()
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["name"] == "Nikhil Kar"
    assert row["title"] == "Sales manager"
    assert row["company"] == "Swiggy"
    assert row["location"] == "Mahasamund, Chhattisgarh, India"
    assert row["source_url"] == "https://www.linkedin.com/in/nikhil-kar-12345"

@patch("lead_pipeline.src.linkedin_scraper.sync_playwright")
def test_scraper_run_enrichment_mocked(mock_sync_playwright):
    mock_playwright = MagicMock()
    mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
    
    mock_browser = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    
    mock_page = MagicMock()
    mock_browser.new_page.return_value = mock_page
    
    mock_page.url = "https://www.linkedin.com/feed"
    mock_page.title.return_value = "LinkedIn Feed"
    mock_page.query_selector.return_value = None
    
    # Create mock result card
    mock_card = MagicMock()
    
    # Mock p tags query_selector_all return values
    p1 = MagicMock()
    p1.inner_text.return_value = "Sampangi Srikanth • 3rd"
    p2 = MagicMock()
    p2.inner_text.return_value = "Solar Consultant at ABC Solar"
    p3 = MagicMock()
    p3.inner_text.return_value = "Hyderabad, Telangana, India"
    
    mock_card.query_selector_all.return_value = [p1, p2, p3]
    
    mock_link_el = MagicMock()
    mock_link_el.get_attribute.return_value = "https://www.linkedin.com/in/srikanth-sampangi-12345"
    mock_card.query_selector.return_value = mock_link_el
    
    mock_page.query_selector_all.return_value = [mock_card]
    
    config = {
        "scrape": {
            "linkedin": {
                "enabled": True,
                "mode": "enrichment",
                "max_pages": 1,
                "delay_seconds": 0.1,
                "headless": True,
                "max_results": 5
            }
        },
        "selectors": {
            "linkedin": {
                "card_container": "[role='listitem']",
                "name": "p",
                "title": "p",
                "location": "p",
                "link": "a[href*='/in/']"
            }
        }
    }
    
    scraper = LinkedInScraper(config)
    results = scraper.run_enrichment(["Sampangi Srikanth"])
    
    assert isinstance(results, list)
    assert len(results) == 1
    res = results[0]
    assert res["status"] == "success"
    assert res["extracted_name"] == "Sampangi Srikanth"
    assert res["title"] == "Solar Consultant"
    assert res["company"] == "ABC Solar"
    assert res["location"] == "Hyderabad, Telangana, India"
    assert res["profile_url"] == "https://www.linkedin.com/in/srikanth-sampangi-12345"

