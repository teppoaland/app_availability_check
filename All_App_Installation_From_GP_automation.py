import time
import os
import sys
import subprocess
import pytest
import allure
import json
from allure_commons.types import AttachmentType
from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from appium.webdriver.common.appiumby import AppiumBy
from datetime import datetime

print("\nAll_App_Installation_From_GP_automation.py - App availability testing starting!\n")

# Apps to test - (package_name, app_name_for_search, ui_check_element)
TEST_APPS = [
    ("fi.sbweather.app", "Sebitti Sää", ("ACCESSIBILITY_ID", "KOTI\nTab 1 of 3")),
    ("fi.reportronic.app", "Reportronic", ("XPATH", "//android.widget.Button[@text='Login with QR code']")),
    ("com.feelment", "Feelment", ("ACCESSIBILITY_ID", "Kirjaudu sisään")),
    ("com.coubonga.app", "Coubonga", ("ACCESSIBILITY_ID", "PUHELINNUMERO")),
    ("com.iloq.smartlock.s50", "iLOQ", ("XPATH", "//android.widget.TextView[@resource-id='android:id/message']")),
]

PLAY_STORE_PACKAGE = "com.android.vending"
PLAY_STORE_ACTIVITY = "com.google.android.finsky.activities.MainActivity"

# Global test results storage
installation_results = []

def uninstall_package(package_name):
    """Uninstall package using ADB"""
    try:
        result = subprocess.run(
            ["adb", "shell", "pm", "uninstall", package_name],
            capture_output=True,
            text=True
        )
        if "Success" in result.stdout:
            print(f"Successfully uninstalled {package_name}")
            return True
        else:
            print(f"Uninstall of {package_name} failed or package not found: {result.stdout}")
            return False
    except Exception as e:
        print(f"Error uninstalling {package_name}: {e}")
        return False

def is_package_installed(package_name):
    """Check if a package is installed on the connected Android device using adb"""
    result = subprocess.run(
        ["adb", "shell", "pm", "list", "packages", package_name],
        capture_output=True,
        text=True
    )
    return f"package:{package_name}" in result.stdout

def get_app_version(package_name):
    """Get app version using ADB"""
    try:
        result = subprocess.run([
            'adb', 'shell', 'dumpsys', 'package', package_name, '|', 
            'grep', '-E', 'versionName'
        ], capture_output=True, text=True, shell=True)
        
        if result.returncode == 0 and result.stdout:
            for line in result.stdout.strip().split('\n'):
                if 'versionName=' in line:
                    return line.split('versionName=')[1].strip()
    except Exception as e:
        print(f"Error getting app version for {package_name}: {e}")
    
    return "Unknown"

def save_installation_results():
    """Save installation results to file for workflow processing"""
    with open("installation_results.json", "w") as f:
        json.dump(installation_results, f, indent=2)
    print(f"Saved installation results for {len(installation_results)} apps")

@pytest.fixture(scope="function")
def play_store_driver():
    """Setup Play Store driver for app installation"""
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.device_name = "Android_test_device"
    options.app_package = PLAY_STORE_PACKAGE
    options.app_activity = PLAY_STORE_ACTIVITY
    options.automation_name = "UiAutomator2"
    options.no_reset = True

    driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
    yield driver
    driver.quit()

@pytest.fixture(scope="function")
def app_driver():
    """Setup generic app driver for UI verification"""
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.device_name = "Android_test_device"
    options.automation_name = "UiAutomator2"
    options.no_reset = True

    driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
    yield driver
    driver.quit()

def save_allure_screenshot(driver, name, failed=False):
    """Save screenshot to Allure report"""
    allure.attach(
        driver.get_screenshot_as_png(),
        name=f"{name}_{'failed' if failed else 'success'}",
        attachment_type=AttachmentType.PNG
    )

def check_element(driver, by_type, value, timeout=10):
    """Check if element exists and return True/False"""
    try:
        if by_type == "ACCESSIBILITY_ID":
            by = AppiumBy.ACCESSIBILITY_ID
        elif by_type == "CLASS_NAME":
            by = AppiumBy.CLASS_NAME
        elif by_type == "XPATH":
            by = AppiumBy.XPATH
        else:
            by = AppiumBy.ACCESSIBILITY_ID
            
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        return True
    except TimeoutException:
        return False

@allure.feature("App Uninstallation")
@pytest.mark.parametrize("package_name,app_name,ui_check", TEST_APPS)
def test_uninstall_app(package_name, app_name, ui_check):
    """Test app uninstallation before fresh installation"""
    with allure.step(f"Uninstalling {app_name} ({package_name})"):
        if is_package_installed(package_name):
            success = uninstall_package(package_name)
            assert not is_package_installed(package_name), f"Failed to uninstall {package_name}"
            allure.dynamic.parameter("Uninstall Status", "Success" if success else "Failed")
        else:
            allure.dynamic.parameter("Uninstall Status", "Not installed")

@allure.feature("App Installation")
@pytest.mark.parametrize("package_name,app_name,ui_check", TEST_APPS)
def test_install_app_from_play_store(play_store_driver, package_name, app_name, ui_check):
    """Test app installation from Google Play Store"""
    global installation_results
    
    with allure.step(f"Installing {app_name} from Play Store"):
        driver = play_store_driver
        time.sleep(3)
        
        # Navigate directly to app page using market intent
        driver.execute_script('mobile: shell', {
            'command': 'am',
            'args': ['start', '-a', 'android.intent.action.VIEW', '-d', f'market://details?id={package_name}'],
            'includeStderr': True,
            'timeout': 5000
        })
        time.sleep(5)
        
        try:
            # Look for Install button
            install_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable(
                    (AppiumBy.XPATH, "//*[contains(@text, 'Install') or contains(@text, 'INSTALL')]")
                )
            )
            install_button.click()
            save_allure_screenshot(driver, f"{package_name}_install_clicked")
            
            # Wait for installation to complete
            installation_success = False
            for _ in range(30):  # Wait up to 90 seconds
                if is_package_installed(package_name):
                    installation_success = True
                    break
                time.sleep(3)
            
            assert installation_success, f"Failed to install {package_name} within timeout"
            
            # Get installed version
            version = get_app_version(package_name)
            
            # Save results
            result = {
                "package_name": package_name,
                "app_name": app_name,
                "installation_status": "Success",
                "installed_version": version,
                "timestamp": datetime.now().isoformat()
            }
            installation_results.append(result)
            save_installation_results()
            
            allure.dynamic.parameter("Installation Status", "Success")
            allure.dynamic.parameter("App Version", version)
            save_allure_screenshot(driver, f"{package_name}_installed")
            
        except TimeoutException:
            # Check if app got installed anyway
            if is_package_installed(package_name):
                version = get_app_version(package_name)
                result = {
                    "package_name": package_name,
                    "app_name": app_name,
                    "installation_status": "Success (no install button)",
                    "installed_version": version,
                    "timestamp": datetime.now().isoformat()
                }
                installation_results.append(result)
                save_installation_results()
                allure.dynamic.parameter("Installation Status", "Success (already installed)")
                allure.dynamic.parameter("App Version", version)
            else:
                result = {
                    "package_name": package_name,
                    "app_name": app_name,
                    "installation_status": "Failed",
                    "installed_version": "N/A",
                    "timestamp": datetime.now().isoformat()
                }
                installation_results.append(result)
                save_installation_results()
                save_allure_screenshot(driver, f"{package_name}_install_failed", failed=True)
                pytest.fail(f"Install button not found and {package_name} not installed")

@allure.feature("App UI Verification")
@pytest.mark.parametrize("package_name,app_name,ui_check", TEST_APPS)
def test_verify_app_ui(app_driver, package_name, app_name, ui_check):
    """Test that installed app launches and UI loads correctly"""
    
    with allure.step(f"Verifying {app_name} UI loads correctly"):
        # Skip if app is not installed
        if not is_package_installed(package_name):
            pytest.skip(f"{package_name} is not installed, skipping UI verification")
        
        driver = app_driver
        
        # Launch the app
        driver.execute_script('mobile: shell', {
            'command': 'monkey',
            'args': ['-p', package_name, '-c', 'android.intent.category.LAUNCHER', '1'],
            'includeStderr': True,
            'timeout': 10000
        })
        time.sleep(5)
        
        # Check for expected UI element
        by_type, element_value = ui_check
        
        if by_type and element_value and element_value != "android.widget.TextView":  # Skip generic placeholder
            ui_found = check_element(driver, by_type, element_value, timeout=10)
            
            if ui_found:
                allure.dynamic.parameter("UI Verification", "Success")
                save_allure_screenshot(driver, f"{package_name}_ui_verified")
                assert True, f"{app_name} UI loaded successfully"
            else:
                allure.dynamic.parameter("UI Verification", "Failed")
                save_allure_screenshot(driver, f"{package_name}_ui_failed", failed=True)
                pytest.fail(f"{app_name} UI element not found: {element_value}")
        else:
            # Take screenshot for manual verification
            save_allure_screenshot(driver, f"{package_name}_ui_manual_check")
            allure.dynamic.parameter("UI Verification", "Manual check required")
            # Don't fail the test for apps without defined UI checks yet

if __name__ == "__main__":
    # Save results at the end
    save_installation_results()
    print("App availability testing completed!")