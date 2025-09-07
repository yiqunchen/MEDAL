from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import time
import random
import json
import logging
from datetime import datetime
import tqdm
import pickle

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cochrane_download.log"),
        logging.StreamHandler()
    ]
)

def download_cochrane_with_auth(doi, username, password, download_dir=None, session=None):
    """
    Download Cochrane data with institutional authentication using Selenium.
    
    Args:
        doi (str): DOI of the article to download data from
        username (str): Institutional username
        password (str): Institutional password
        download_dir (str, optional): Directory to save downloads
        session (webdriver, optional): Existing webdriver session to reuse
    
    Returns:
        tuple: (success_bool, file_path_or_none, driver_or_none)
    """
    if session is not None:
        try:
            # Test if the session is still valid
            session.current_url
        except:
            # Session is invalid, close it if possible
            try:
                session.quit()
            except:
                pass
            session = None
    # Clean DOI
    clean_doi = doi.strip().replace("http://doi.org/", "").replace("https://doi.org/", "")
    article_id = clean_doi.split('.')[-1].replace('CD', '')
    
    # Set up download directory
    if download_dir is None:
        download_dir = os.getcwd()
    download_dir = os.path.abspath(download_dir)
    os.makedirs(download_dir, exist_ok=True)
    
    # Expected filename patterns
    expected_patterns = [
        f"CD{article_id}-dataPackage.zip",
        f"CD{article_id}StatsDataOnly.rm5",
        f"{article_id}-dataPackage.zip",
        f"{article_id}StatsDataOnly.rm5"
    ]
    
    # Check if file already exists
    for pattern in expected_patterns:
        existing_file = os.path.join(download_dir, pattern)
        if os.path.exists(existing_file):
            logging.info(f"File already exists: {existing_file}")
            return (True, existing_file, session)
    
    # Record current time
    start_time = time.time()
    
    # Create or reuse webdriver session
    driver_created = False
    if session is None:
        driver_created = True
        
        # Set up Chrome options
        chrome_options = Options()
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Initialize driver
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except:
            # Fallback if webdriver_manager is not installed
            driver = webdriver.Chrome(options=chrome_options)
    else:
        driver = session
    
    try:
        # Navigate to article page
        article_url = f"https://www.cochranelibrary.com/cdsr/doi/{clean_doi}/full"
        logging.info(f"Navigating to: {article_url}")
        driver.get(article_url)
        time.sleep(random.uniform(1, 3))  # Random delay to appear more human-like
        
        # First, remove any modal overlays that might be present
        try:
            driver.execute_script("""
                var overlays = document.querySelectorAll('.scolaris-modal-overlay.open');
                for(var i = 0; i < overlays.length; i++) {
                    overlays[i].style.display = 'none';
                    overlays[i].classList.remove('open');
                }
            """)
        except:
            pass
        
        # Check if we're already logged in
        logged_in = driver.execute_script("""
            return document.body.textContent.includes('Sign Out') || 
                   !document.body.textContent.includes('Sign In');
        """)
        
        if not logged_in:
            logging.info("Not logged in. Starting login process...")
            
            # Click Sign In using approach that worked (CSS selector)
            try:
                sign_in_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.login, a.signin, a#login, a#signin"))
                )
                sign_in_btn.click()
                logging.info("Clicked Sign In button")
                time.sleep(random.uniform(1, 3))
            except Exception as e:
                logging.warning(f"Sign In button not found: {e}")
            
            # Click on Institutional Login using approach that worked
            try:
                inst_login_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Institutional')]"))
                )
                inst_login_btn.click()
                logging.info("Clicked Institutional Login button")
                time.sleep(random.uniform(1, 3))
            except Exception as e:
                logging.warning(f"Institutional Login button not found: {e}")
            
            # Enter username and password
            try:
                # From the debug output, the correct IDs are:
                # ID: _58_INSTANCE_4_login for username
                # ID: _58_INSTANCE_4_password for password
                username_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "_58_INSTANCE_4_login"))
                )
                username_field.clear()
                username_field.send_keys(username)
                logging.info("Entered username")
                
                password_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "_58_INSTANCE_4_password"))
                )
                password_field.clear()
                password_field.send_keys(password)
                logging.info("Entered password")
                
                # Remove modal overlays before clicking submit
                driver.execute_script("""
                    var overlays = document.querySelectorAll('.scolaris-modal-overlay.open');
                    for(var i = 0; i < overlays.length; i++) {
                        overlays[i].style.display = 'none';
                        overlays[i].classList.remove('open');
                    }
                """)
                
                # Use JavaScript to click the submit button to avoid overlay issues
                login_clicked = driver.execute_script("""
                    // Find the submit button near the password field
                    var password = document.getElementById('_58_INSTANCE_4_password');
                    if (password) {
                        var form = password.closest('form');
                        if (form) {
                            var button = form.querySelector('button[type="submit"]');
                            if (button) {
                                button.click();
                                return true;
                            }
                        }
                    }
                    
                    // Try finding any submit button
                    var allSubmitButtons = document.querySelectorAll('button[type="submit"]');
                    if (allSubmitButtons.length > 0) {
                        allSubmitButtons[0].click();
                        return true;
                    }
                    
                    return false;
                """)
                
                if login_clicked:
                    logging.info("Clicked submit button using JavaScript")
                else:
                    logging.warning("Could not find submit button with JavaScript")
                
                time.sleep(random.uniform(8, 10))  # Wait for login to process
                
            except Exception as e:
                logging.error(f"Login process failed: {e}")
        else:
            logging.info("Already logged in")
        
        # After logging in, navigate back to article page
        logging.info("Navigating back to article page...")
        driver.get(article_url)
        # time.sleep(random.uniform(3, 5))
        
        # Get the exact URL from the "Download data" link
        logging.info("Extracting download URL directly from the Download data link...")
        download_url = driver.execute_script("""
            // Find all links with text containing 'Download data'
            var downloadLinks = Array.from(document.querySelectorAll('a')).filter(function(link) {
                return link.textContent.trim().includes('Download data');
            });
            
            if (downloadLinks.length > 0) {
                console.log("Found download link with href: " + downloadLinks[0].href);
                return downloadLinks[0].href;
            }
            
            // Try to find links in Supplementary materials section
            var suppSection = document.querySelector('.supplementary-materials');
            if (suppSection) {
                var suppLinks = suppSection.querySelectorAll('a');
                for (var i = 0; i < suppLinks.length; i++) {
                    if (suppLinks[i].href.includes('dataPackage') || 
                        suppLinks[i].href.includes('zip') || 
                        suppLinks[i].textContent.includes('Download')) {
                        console.log("Found supplementary link: " + suppLinks[i].href);
                        return suppLinks[i].href;
                    }
                }
            }
            
            // Look for any link containing zip or dataPackage in the href
            var allLinks = document.querySelectorAll('a[href*="dataPackage"], a[href*=".zip"]');
            if (allLinks.length > 0) {
                console.log("Found link with dataPackage or zip in href: " + allLinks[0].href);
                return allLinks[0].href;
            }
            
            return null;
        """)
        
        download_success = False
        
        if download_url:
            logging.info(f"Found download URL: {download_url}")
            
            # Navigate directly to the download URL
            logging.info(f"Navigating directly to download URL: {download_url}")
            driver.get(download_url)
            time.sleep(random.uniform(1, 3))  # Wait for download to complete
        else:
            logging.warning("Could not find download URL in the page")
            
            # Try clicking the "Download data" link and handling the dialog
            logging.info("Trying to click Download data link and handle dialog...")
            download_clicked = driver.execute_script("""
                var downloadLinks = Array.from(document.querySelectorAll('a')).filter(function(link) {
                    return link.textContent.trim().includes('Download data');
                });
                
                if (downloadLinks.length > 0) {
                    downloadLinks[0].click();
                    return true;
                }
                return false;
            """)
            
            if download_clicked:
                logging.info("Clicked Download data link")
                time.sleep(random.uniform(0, 1.5))
                
                # Handle checkbox in dialog
                driver.execute_script("""
                    var checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    for(var i = 0; i < checkboxes.length; i++) {
                        checkboxes[i].checked = true;
                        
                        // Trigger change event
                        var event = new Event('change', { 'bubbles': true });
                        checkboxes[i].dispatchEvent(event);
                    }
                """)
                logging.info("Checked checkboxes in dialog")
                time.sleep(random.uniform(0, 1))
                
                # Click download button in dialog
                download_btn_clicked = driver.execute_script("""
                    var buttons = document.querySelectorAll('button');
                    for (var i = 0; i < buttons.length; i++) {
                        if (buttons[i].textContent.includes('Download data')) {
                            buttons[i].click();
                            return true;
                        }
                    }
                    return false;
                """)
                
                if download_btn_clicked:
                    logging.info("Clicked download button in dialog")
                    time.sleep(random.uniform(0, 1))
        
        # Check for downloaded files
        logging.info("Checking for downloaded files...")
        new_files = []
        for f in os.listdir(download_dir):
            file_path = os.path.join(download_dir, f)
            if os.path.isfile(file_path) and os.path.getmtime(file_path) > start_time:
                if f.endswith('.zip') or f.endswith('.rm5') or 'data' in f.lower():
                    new_files.append(f)
        
        if new_files:
            download_success = True
            logging.info(f"Found new downloaded files: {new_files}")
            return (True, os.path.join(download_dir, new_files[0]), driver)
        
        if not download_success:
            logging.warning("Download attempts failed.")
            return (False, None, driver)
    
    except Exception as e:
        logging.error(f"Error during download process: {e}")
        return (False, None, driver)
    
    finally:
        # Only close the driver if we created it
        if driver_created:
            logging.info("Closing browser...")
            driver.quit()
            return (download_success, None, None)

def batch_download_cochrane_data(doi_list, username, password, download_dir=None, resume_file="download_progress.json"):
    """
    Download Cochrane data for a list of DOIs with progress tracking, resume capability,
    and automatic session recovery.
    """
    if download_dir is None:
        download_dir = os.getcwd()
    download_dir = os.path.abspath(download_dir)
    os.makedirs(download_dir, exist_ok=True)
    
    # Load progress if exists
    progress = {}
    if os.path.exists(resume_file):
        try:
            with open(resume_file, 'r') as f:
                progress = json.load(f)
            logging.info(f"Loaded progress from {resume_file}")
        except Exception as e:
            logging.error(f"Error loading progress file: {e}")
    
    results = {
        "total": len(doi_list),
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "details": {}
    }
    
    # Incorporate previous progress
    for doi, result in progress.get('details', {}).items():
        if doi in doi_list and result.get('status') == 'success':
            results['details'][doi] = result
            results['completed'] += 1
            results['successful'] += 1
            results['skipped'] += 1
    
    # Initialize driver to None - we'll create it when needed
    driver = None
    
    try:
        # Process DOIs
        for i, doi in tqdm.tqdm(enumerate(doi_list)):
            # Skip if already successfully downloaded
            if doi in results['details'] and results['details'][doi]['status'] == 'success':
                logging.info(f"[{i+1}/{len(doi_list)}] Skipping {doi} - already downloaded")
                continue
            
            logging.info(f"[{i+1}/{len(doi_list)}] Processing {doi}")
            
            # Add delay between requests to avoid triggering rate limits
            if i > 0:
                delay = random.uniform(0, 2)  # Reduced delay to 10-15 seconds
                logging.info(f"Waiting {delay:.2f} seconds before next download...")
                time.sleep(delay)
            
            # Create a new driver if needed
            if driver is None:
                try:
                    logging.info("Creating new WebDriver session...")
                    chrome_options = Options()
                    prefs = {
                        "download.default_directory": download_dir,
                        "download.prompt_for_download": False,
                        "download.directory_upgrade": True,
                        "plugins.always_open_pdf_externally": True
                    }
                    chrome_options.add_experimental_option("prefs", prefs)
                    
                    try:
                        from webdriver_manager.chrome import ChromeDriverManager
                        from selenium.webdriver.chrome.service import Service
                        service = Service(ChromeDriverManager().install())
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                    except:
                        # Fallback if webdriver_manager is not installed
                        driver = webdriver.Chrome(options=chrome_options)
                except Exception as e:
                    logging.error(f"Failed to create WebDriver: {e}")
                    # Wait before retrying
                    time.sleep(3)
                    continue
            
            # Attempt download with session recovery
            max_retries = 2
            for retry in range(max_retries + 1):
                try:
                    success, file_path, driver = download_cochrane_with_auth(doi, username, password, download_dir, driver)
                    break  # Break out of retry loop if successful
                except Exception as e:
                    logging.error(f"Error on attempt {retry+1}/{max_retries+1}: {e}")
                    # Close the failed driver
                    try:
                        if driver:
                            driver.quit()
                    except:
                        pass
                    
                    driver = None  # Reset driver to force recreation
                    
                    if retry < max_retries:
                        recovery_delay = random.uniform(0, 2)
                        logging.info(f"Waiting {recovery_delay:.2f} seconds before retrying...")
                        time.sleep(recovery_delay)
                    else:
                        success = False
                        file_path = None
            
            # Update results
            results['completed'] += 1
            if success:
                results['successful'] += 1
                results['details'][doi] = {
                    'status': 'success',
                    'file_path': file_path,
                    'timestamp': datetime.now().isoformat()
                }
                logging.info(f"Successfully downloaded data for {doi}")
            else:
                results['failed'] += 1
                results['details'][doi] = {
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                }
                logging.warning(f"Failed to download data for {doi}")
            
            # Save progress after each download
            with open(resume_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Print progress
            percentage = (results['completed'] / results['total']) * 100
            logging.info(f"Progress: {results['completed']}/{results['total']} ({percentage:.2f}%)")
            logging.info(f"Success: {results['successful']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
            
            # Periodically restart the driver to avoid memory issues
            if results['completed'] % 100 == 0 and driver is not None:
                logging.info("Performing scheduled WebDriver restart...")
                try:
                    driver.quit()
                except:
                    pass
                driver = None
                time.sleep(2)  # Wait a bit before creating a new session
                
    except KeyboardInterrupt:
        logging.info("Process interrupted by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        # Close the shared driver session
        try:
            if driver:
                driver.quit()
        except:
            pass
        
        logging.info("Download process completed")
        logging.info(f"Final results: {results['successful']} successful, {results['failed']} failed, {results['skipped']} skipped")
        
        return results

import os
from medal import load_dotenv_if_present, require_env
json_path = os.getenv("COCHRANE_INPUT_PKL", "./data/intermediate/clean_pubmed_abstract_data_no_protocol.pkl")
with open(json_path, 'rb') as f:
    clean_pubmed_abstract_data_no_protocol = pickle.load(f)

file_keys = list(clean_pubmed_abstract_data_no_protocol.keys())[::-1]
# Example usage
if __name__ == "__main__":
    # List of DOIs to download
    load_dotenv_if_present()
    doi_list = list(clean_pubmed_abstract_data_no_protocol.keys())[::-1]
    username = require_env("COCHRANE_USERNAME")
    password = require_env("COCHRANE_PASSWORD")
    download_dir = os.getenv("COCHRANE_DOWNLOAD_DIR", "./downloads/cochrane_cache/download_data")
    os.makedirs(download_dir, exist_ok=True)

    # Run batch download
    results = batch_download_cochrane_data(doi_list, username, password, download_dir)

    print("Download process completed!")
    print(f"Total DOIs: {len(doi_list)}")
    print(f"Successfully downloaded: {results['successful']}")
    print(f"Failed downloads: {results['failed']}")
    print(f"Skipped (already downloaded): {results['skipped']}")