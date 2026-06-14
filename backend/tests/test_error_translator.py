import pytest
from services.error_translator import error_translator

def test_exact_match():
    tamil = error_translator.translate("Application not found")
    assert tamil == "இந்த கணினியில் அந்த பயன்பாடு நிறுவப்படவில்லை."

def test_substring_match():
    tamil = error_translator.translate("Failed to start chrome.exe: Not found")
    assert tamil == "பயன்பாட்டை திறக்க முடியவில்லை."

def test_access_denied():
    tamil = error_translator.translate("Permission denied: C:\\Windows")
    assert tamil == "இந்த செயலை செய்ய அனுமதி இல்லை."

def test_unknown_error():
    tamil = error_translator.translate("Something weird happened")
    assert tamil == "Something weird happened"
