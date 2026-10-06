"""Список доступних impersonate у curl_cffi."""

from curl_cffi.requests import BrowserType

print("Доступні impersonate:")
for bt in BrowserType:
    print(f"  {bt.value}")
