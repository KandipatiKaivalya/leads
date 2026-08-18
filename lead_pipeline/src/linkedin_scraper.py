import time
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
from loguru import logger
from playwright.sync_api import sync_playwright

class LinkedInScraper:
    def __init__(self, config: dict):
        self.config = config
        self.scrape_cfg = config.get("scrape", {}).get("linkedin", {})
        self.selectors = config.get("selectors", {}).get("linkedin", {})
        self.headless = self.scrape_cfg.get("headless", False)
        self.max_pages = self.scrape_cfg.get("max_pages", 2)
        self.delay_seconds = self.scrape_cfg.get("delay_seconds", 5.0)
        self.max_results = self.scrape_cfg.get("max_results", 20)
        self.search_term = self.scrape_cfg.get("search_term", "solar sales manager")

    def run(self, search_term: str = None) -> pd.DataFrame:
        if search_term:
            self.search_term = search_term

        logger.info("Initializing Playwright scraper...")
        with sync_playwright() as p:
            # Use launch options to ensure normal user-agent behavior
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # Setup normal browser context with standard viewport and user-agent
            context = browser.new_page(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Navigate to LinkedIn feed (forces authentication check)
            logger.info("Opening LinkedIn feed page...")
            context.goto("https://www.linkedin.com/feed")

            # Check authentication state (Case A, B, C)
            auth_status = self._check_auth_status(context, timeout_ms=5000)
            logger.info(f"Initial authentication status detection: {auth_status}")

            if auth_status == "challenge":
                logger.error("LinkedIn security challenge / CAPTCHA detected on initial load.")
                logger.warning("Please solve the challenge manually. The scraper will wait.")
                auth_status = self._wait_for_manual_auth(context)
                if auth_status != "authenticated":
                    logger.error("Failed to authenticate or solve security challenge.")
                    browser.close()
                    return pd.DataFrame()
            elif auth_status == "unauthenticated":
                logger.warning("LinkedIn requires authentication. Please log in manually in the browser window.")
                auth_status = self._wait_for_manual_auth(context)
                if auth_status != "authenticated":
                    logger.error("Authentication timed out or failed.")
                    browser.close()
                    return pd.DataFrame()
            elif auth_status == "authenticated":
                logger.success("Already authenticated. Proceeding directly to search.")
            else:
                # If unknown, check again or wait just in case
                logger.warning("Authentication state is unknown. Waiting a moment to confirm...")
                auth_status = self._wait_for_manual_auth(context, timeout_sec=15)
                if auth_status != "authenticated":
                    logger.error("Failed to confirm authenticated state.")
                    browser.close()
                    return pd.DataFrame()

            results = []
            
            for page_num in range(1, self.max_pages + 1):
                if len(results) >= self.max_results:
                    logger.info(f"Reached configured limit of {self.max_results} results. Stopping.")
                    break

                search_url = f"https://www.linkedin.com/search/results/people/?keywords={self.search_term}&page={page_num}"
                logger.info(f"Navigating to page {page_num}: {search_url}")
                
                try:
                    context.goto(search_url)
                except Exception as e:
                    logger.error(f"Failed to navigate to page {page_num}: {e}")
                    break

                # Wait for page load
                time.sleep(self.delay_seconds)

                # Check for security challenge / captcha
                if "challenge" in context.url or context.query_selector(".challenge-dialog") or "Security Challenge" in context.title():
                    logger.error(f"LinkedIn security challenge / CAPTCHA detected on page {page_num}.")
                    logger.warning("Please complete the challenge manually if the browser is visible, or the pipeline will pause/stop.")
                    try:
                        # Wait up to 60s for challenge bypass
                        context.wait_for_url(lambda url: "challenge" not in url, timeout=60000)
                    except Exception:
                        logger.error("Challenge not solved in time. Stopping scraper to prevent account restrictions.")
                        self._save_debug_artifact(context, f"captcha_page_{page_num}")
                        break

                # Look for result cards
                card_selector = self.selectors.get("card_container", ".reusable-search__result-container")
                cards = context.query_selector_all(card_selector)
                
                if not cards:
                    logger.warning(f"No result cards found on page {page_num} using selector: {card_selector}")
                    # Save a screenshot and HTML for debugging purposes
                    self._save_debug_artifact(context, f"empty_page_{page_num}")
                    
                    # Check if there is an empty search result message
                    if "No results found" in context.content() or "no-results" in context.content():
                        logger.info("LinkedIn reported no results for this query.")
                        break
                    
                    # If we might have been logged out or rate limited
                    if self._is_login_required(context):
                        logger.error("Scraper was logged out. Stopping.")
                        break
                    
                    continue

                logger.info(f"Found {len(cards)} search result cards on page {page_num}")
                
                for card in cards:
                    if len(results) >= self.max_results:
                        break

                    try:
                        # Extract Name, Title, and Location
                        name_sel = self.selectors.get("name", "span.entity-result__title-text a span[aria-hidden='true']")
                        if name_sel == "p":
                            p_els = card.query_selector_all("p")
                            p_texts = [p.inner_text().strip() for p in p_els if p.inner_text().strip()]
                            name_raw = p_texts[0] if len(p_texts) > 0 else ""
                            title_raw = p_texts[1] if len(p_texts) > 1 else ""
                            location_raw = p_texts[2] if len(p_texts) > 2 else ""
                        else:
                            name_el = card.query_selector(name_sel)
                            name_raw = name_el.inner_text().strip() if name_el else ""
                            
                            # Extract Title/Subtitle
                            title_sel = self.selectors.get("title", ".entity-result__primary-subtitle")
                            title_el = card.query_selector(title_sel)
                            title_raw = title_el.inner_text().strip() if title_el else ""

                            # Extract Location
                            loc_sel = self.selectors.get("location", ".entity-result__secondary-subtitle")
                            loc_el = card.query_selector(loc_sel)
                            location_raw = loc_el.inner_text().strip() if loc_el else ""

                        # Extract Profile URL
                        link_sel = self.selectors.get("link", "span.entity-result__title-text a")
                        link_el = card.query_selector(link_sel)
                        profile_url = link_el.get_attribute("href") if link_el else ""
                        
                        # Clean whitespace (newlines, tabs, multiple spaces)
                        name_raw = " ".join(name_raw.split())
                        title_raw = " ".join(title_raw.split())
                        location_raw = " ".join(location_raw.split())
                        
                        # Clean name (remove connection level like "• 1st", "• 2nd", etc.)
                        name = self._clean_name(name_raw)
                        
                        # Clean title and parse company from it if company is not separately structured
                        title, company = self._parse_title_and_company(title_raw)

                        # If fields are empty, mark as pending
                        name = name if name else "pending"
                        title = title if title else "pending"
                        company = company if company else "pending"
                        location = location_raw if location_raw else "pending"

                        results.append({
                            "name": name,
                            "title": title,
                            "company": company,
                            "location": location,
                            "source": "linkedin",
                            "search_term": self.search_term,
                            "source_url": profile_url.split("?")[0] if profile_url else "pending",
                            "scraped_at": datetime.now().isoformat()
                        })

                    except Exception as card_err:
                        logger.warning(f"Error parsing result card: {card_err}")
                        continue

            logger.info("Closing browser context...")
            browser.close()

        df = pd.DataFrame(results)
        logger.success(f"Scraping complete. Collected {len(df)} records.")
        return df

    def _check_auth_status(self, page, timeout_ms=5000) -> str:
        """
        Determines the current authentication state using reliable signals.
        Handles page navigation and context destruction errors gracefully.
        Returns:
            "authenticated": Feed loaded, logged-in indicators present.
            "unauthenticated": Redirected to login page or fields present.
            "challenge": Security challenge or CAPTCHA page.
            "unknown": Unable to determine.
        """
        from playwright.sync_api import Error as PlaywrightError
        
        start_time = time.time()
        while True:
            try:
                current_url = page.url.lower()
                try:
                    title = page.title().lower()
                except Exception:
                    title = ""
                
                # CASE C: Check for security challenges
                # Check URL for challenge terms
                if "challenge" in current_url or "security challenge" in title:
                    return "challenge"
                
                challenge_el = page.query_selector(".challenge-dialog")
                if challenge_el and (not hasattr(challenge_el, 'is_visible') or challenge_el.is_visible()):
                    return "challenge"
                    
                # CASE B: Authenticated indicators
                if "/feed" in current_url or "/search" in current_url:
                    return "authenticated"
                
                if any(term in title for term in ["feed", "home", "search", "messaging", "jobs", "notifications", "network"]):
                    return "authenticated"
                
                authenticated_selectors = [
                    ".global-nav", 
                    "#global-nav-typeahead", 
                    "input[aria-label='Search']",
                    ".feed-identity-module",
                    ".share-box-feed-entry__trigger",
                    ".feed-shared-update-v2",
                    "[data-view-name='profile-card']"
                ]
                for sel in authenticated_selectors:
                    el = page.query_selector(sel)
                    if el and (not hasattr(el, 'is_visible') or el.is_visible()):
                        return "authenticated"

                # CASE A: Unauthenticated indicators
                if "login" in current_url or "checkpoint" in current_url or "signup" in current_url:
                    return "unauthenticated"
                    
                if any(term in title for term in ["login", "sign in", "join now", "sign up"]):
                    return "unauthenticated"
                    
                unauth_selectors = [
                    "#username",
                    "#session_key",
                    ".login__form",
                    "input[name='session_key']",
                    "input[name='session_password']"
                ]
                for sel in unauth_selectors:
                    el = page.query_selector(sel)
                    if el and (not hasattr(el, 'is_visible') or el.is_visible()):
                        return "unauthenticated"
                        
            except (PlaywrightError, Exception) as e:
                err_msg = str(e).lower()
                if "context was destroyed" in err_msg or "navigation" in err_msg or "context destroyed" in err_msg:
                    logger.info("Page navigation or context destruction detected. Waiting for context to settle...")
                    time.sleep(1.0)
                    continue
                else:
                    logger.debug(f"Unexpected error in auth status check: {e}")
                    time.sleep(0.5)
                    continue

            # Wait a bit and retry until timeout
            elapsed = (time.time() - start_time) * 1000
            if elapsed >= timeout_ms:
                break
            time.sleep(0.5)

        # Fallback check
        try:
            current_url = page.url.lower()
            if "/feed" in current_url or "/search" in current_url:
                return "authenticated"
            if "login" in current_url or "checkpoint" in current_url:
                return "unauthenticated"
        except Exception:
            pass
            
        return "unknown"

    def _wait_for_manual_auth(self, page, timeout_sec=300) -> str:
        """
        Waits up to timeout_sec for the user to complete login/CAPTCHA.
        Returns the final authenticated status if successful.
        """
        logger.info(f"Waiting for manual authentication / CAPTCHA resolution (timeout: {timeout_sec}s)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout_sec:
            # Poll status every 2 seconds
            status = self._check_auth_status(page, timeout_ms=1000)
            logger.info(f"Polling auth status... URL: {page.url} | Title: {page.title()} | Status: {status}")
            
            if status == "authenticated":
                logger.success("Authentication confirmed successfully!")
                return "authenticated"
            elif status == "challenge":
                logger.warning("Waiting for manual CAPTCHA / security challenge resolution...")
            else:
                logger.info("Waiting for manual login...")
            time.sleep(2.0)
            
        return "unauthenticated"

    def _is_login_required(self, page) -> bool:
        return self._check_auth_status(page, timeout_ms=500) == "unauthenticated"

    def _clean_name(self, name: str) -> str:
        if not name:
            return ""
        # Remove connection degree indicator like "• 2nd" or "• 3rd+"
        name = re.sub(r"\s*•\s*\d+(?:st|nd|rd|th)(?:\+)?\s*", "", name)
        # Remove trailing/leading spaces and newlines
        return name.strip()

    def _parse_title_and_company(self, title_text: str) -> tuple:
        if not title_text:
            return "", ""
        
        # Clean up newlines/tabs
        title_text = " ".join(title_text.split())
        
        # Try to parse "Title at Company" or "Title | Company"
        # Example: "Solar Sales Manager at AmityEco Renew"
        company = ""
        title = title_text
        
        for separator in [" at ", " @ ", " | ", " - "]:
            if separator in title_text:
                parts = title_text.split(separator, 1)
                title = parts[0].strip()
                company = parts[1].strip()
                break
                
        return title, company

    def run_enrichment(self, names: list) -> list:
        """
        Runs LinkedIn profile searches and data extraction to enrich a list of lead names.
        """
        logger.info("Initializing Playwright scraper for Lead Enrichment...")
        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_page(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            logger.info("Opening LinkedIn feed page...")
            context.goto("https://www.linkedin.com/feed")

            auth_status = self._check_auth_status(context, timeout_ms=5000)
            logger.info(f"Initial authentication status detection: {auth_status}")

            if auth_status in ["challenge", "unauthenticated", "unknown"]:
                auth_status = self._wait_for_manual_auth(context)
                if auth_status != "authenticated":
                    logger.error("Authentication failed. Cannot perform enrichment.")
                    browser.close()
                    return []

            logger.success("Authenticated successfully. Commencing enrichment loop.")
            
            for idx, name in enumerate(names):
                logger.info(f"[{idx+1}/{len(names)}] Enriching lead: {name}")
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={name}"
                
                try:
                    context.goto(search_url)
                    time.sleep(self.delay_seconds)
                    
                    # Check for security challenge
                    if "challenge" in context.url or context.query_selector(".challenge-dialog"):
                        logger.error("Security challenge detected during search. Please solve it manually.")
                        context.wait_for_url(lambda url: "challenge" not in url, timeout=60000)
                    
                    card_selector = self.selectors.get("card_container", "[role='listitem']")
                    cards = context.query_selector_all(card_selector)
                    
                    if not cards:
                        logger.warning(f"No profiles found for: {name}")
                        results.append({"name": name, "status": "not_found"})
                        continue
                        
                    card = cards[0]
                    
                    # Extract info from the first matching card
                    p_els = card.query_selector_all("p")
                    p_texts = [p.inner_text().strip() for p in p_els if p.inner_text().strip()]
                    
                    extracted_name = p_texts[0] if len(p_texts) > 0 else ""
                    title_raw = p_texts[1] if len(p_texts) > 1 else ""
                    location_raw = p_texts[2] if len(p_texts) > 2 else ""
                    
                    # Normalize whitespace
                    extracted_name = " ".join(extracted_name.split())
                    title_raw = " ".join(title_raw.split())
                    location_raw = " ".join(location_raw.split())
                    
                    # Clean name (remove connection levels)
                    clean_name = self._clean_name(extracted_name)
                    
                    link_sel = self.selectors.get("link", "a[href*='/in/']")
                    link_el = card.query_selector(link_sel)
                    profile_url = link_el.get_attribute("href") if link_el else ""
                    if profile_url:
                        profile_url = profile_url.split("?")[0]
                        
                    title, company = self._parse_title_and_company(title_raw)
                    
                    logger.success(f"  Found: {clean_name} | Role: {title} at {company} | Location: {location_raw}")
                    
                    results.append({
                        "name": name,
                        "status": "success",
                        "extracted_name": clean_name,
                        "title": title,
                        "company": company,
                        "location": location_raw,
                        "profile_url": profile_url
                    })
                    
                except Exception as e:
                    logger.error(f"Error enriching lead {name}: {e}")
                    results.append({"name": name, "status": "error", "error": str(e)})
                    
            browser.close()
            return results

    def _save_debug_artifact(self, page, filename_prefix: str):
        try:
            # Save screenshots in the project root's output folder
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = output_dir / f"{filename_prefix}_{timestamp}.png"
            html_path = output_dir / f"{filename_prefix}_{timestamp}.html"
            
            page.screenshot(path=str(screenshot_path))
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
                
            logger.info(f"Saved debug screenshot to {screenshot_path}")
            logger.info(f"Saved debug HTML to {html_path}")
        except Exception as e:
            logger.warning(f"Could not save debug artifacts: {e}")

import re
