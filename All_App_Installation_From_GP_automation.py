import time
import os
import sys
import subprocess
from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from appium.webdriver.common.appiumby import AppiumBy
from datetime import datetime

print("\nAny_App_Installation_From_GP_automation.py - GP installation starting!\n")

# Fixed package names
FIXED_PACKAGES = [
    ("fi.sbweather.app", "Sebitti Sää"),
    ("fi.reportronic.app", "Reportronic")
]

import argparse

# Parse command-line arguments for additional package installation
parser = argparse.ArgumentParser(description="Automate app installation from Google Play Store.")
parser.add_argument("--extra-package", type=str, help="Extra package name to install (e.g., com.example.app)")
parser.add_argument("--extra-app-name", type=str, help="App name for Play Store search (required if --extra-package is used)")
args = parser.parse_args()

if args.extra_package and args.extra_app_name:
    FIXED_PACKAGES.append((args.extra_package, args.extra_app_name))
elif args.extra_package and not args.extra_app_name:
    print("Error: --extra-app-name is required if --extra-package is specified.")
    sys.exit(1)

PLAY_STORE_PACKAGE = "com.android.vending"
PLAY_STORE_ACTIVITY = "com.google.android.finsky.activities.MainActivity"

def is_package_installed(package_name):
    """
    Check if a package is installed on the connected Android device using adb.
    """
    result = subprocess.run(
        ["adb", "shell", "pm", "list", "packages", package_name],
        capture_output=True,
        text=True
    )
    return f"package:{package_name}" in result.stdout

def save_screenshot(driver, filename_prefix, timestamp, failed=False):
    dirname = "screenshots_failed" if failed else "screenshots"
    os.makedirs(dirname, exist_ok=True)
    filename = f"{filename_prefix}_{timestamp}.png"
    filepath = os.path.join(dirname, filename)
    driver.save_screenshot(filepath)
    print(f"Screenshot saved: {filepath}")
    return filepath

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    overall_passed = True

    for PACKAGE_NAME, APP_NAME in FIXED_PACKAGES:
        print(f"\nChecking installation for: {PACKAGE_NAME} ({APP_NAME})")
        test_passed = False
        try:
            if is_package_installed(PACKAGE_NAME):
                print(f"{PACKAGE_NAME} is already installed. No installation needed.")
                test_passed = True
            else:
                print(f"{PACKAGE_NAME} not installed. Launching Play Store for installation...")

                play_options = UiAutomator2Options()
                play_options.platform_name = "Android"
                play_options.device_name = "Android_test_device"
                play_options.app_package = PLAY_STORE_PACKAGE
                play_options.app_activity = PLAY_STORE_ACTIVITY
                play_options.automation_name = "UiAutomator2"
                play_options.no_reset = True

                play_driver = webdriver.Remote("http://127.0.0.1:4723", options=play_options)
                time.sleep(5)

                # Try direct Play Store intent first
                play_driver.execute_script('mobile: shell', {
                    'command': 'am',
                    'args': ['start', '-a', 'android.intent.action.VIEW', '-d', f'market://details?id={PACKAGE_NAME}'],
                    'includeStderr': True,
                    'timeout': 5000
                })
                time.sleep(5)
                # Optionally, fallback to search if direct intent fails - removed for simplicity

                try:
                    install_button = WebDriverWait(play_driver, 15).until(
                        EC.element_to_be_clickable(
                            (AppiumBy.XPATH, "//*[contains(@text, 'Install') or contains(@text, 'INSTALL')]")
                        )
                    )
                    install_button.click()
                    print("Install clicked. Waiting for installation to complete...")

                    for _ in range(30):
                        if is_package_installed(PACKAGE_NAME):
                            print(f"{PACKAGE_NAME} successfully installed!")
                            # always take a screenshot of a successful installation
                            save_screenshot(play_driver, f"{PACKAGE_NAME}_installed", timestamp)
                            print(f"Screenshot taken of the installation of package {PACKAGE_NAME}.")
                            test_passed = True
                            break
                        time.sleep(3)
                    else:
                        print(f"Failed to install {PACKAGE_NAME}.")
                        test_passed = False

                except TimeoutException:
                    print("Install button not found. Installation may have failed.")
                    if is_package_installed(PACKAGE_NAME):
                        print(f"{PACKAGE_NAME} was installed successfully anyway!")
                        test_passed = True
                    else:
                        print(f"{PACKAGE_NAME} installation failed.")
                        test_passed = False

                play_driver.quit()

        except Exception as e:
            print(f"Unexpected exception: {e}")
            test_passed = False
            if 'play_driver' in locals():
                save_screenshot(play_driver, "Unexpected_Error", timestamp, failed=True)

        overall_passed = overall_passed and test_passed

    if overall_passed:
        print("\nAll installations completed successfully.")
        print("Exiting...")
    else:
        print("\nSome installations failed. Exiting...")
        print("Exiting...")
    sys.exit(0 if overall_passed else 1)

if __name__ == "__main__":
    main()
