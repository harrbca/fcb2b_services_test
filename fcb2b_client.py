#!/usr/bin/env python3
"""
Simple interactive tester for fcB2B services.

Features:
- Fetches the fcB2B service catalog from the /services endpoint.
- Displays available services to the user.
- Lets the user pick a service to test.
- Prompts for required parameters (currently SupplierItemSKU).
- Signs the request using HMAC-SHA256 (same pattern as StockCheck.py).
- Calls the service and prints the response.

Usage:
    python fcb2b_tester.py
"""

import base64
import hashlib
import hmac
import sys
import uuid
import urllib.parse
import re
from xml.dom import minidom
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
import xml.etree.ElementTree as ET

# ====== CONFIGURATION ======

SERVICES_URL = "https://des.buckwold.com/danciko/bwl/dancik-b2b/services"

API_KEY = "anonymous"
SECRET_KEY = "yoursecretkey"

CORE_NS = "http://fcb2b.com/schemas/1.0/core"
NS = {"core": CORE_NS}

# ANSI colors
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = "\033[0m"

TAG_OPEN = re.compile(r'(<[^>]+>)')

# ====== DATA CLASSES ======

@dataclass
class ServiceProfile:
    name: str
    description: str
    anonymous_access: bool
    https_url: str
    version: str
    date: str


# ====== HMAC SIGNING HELPERS (same pattern as your StockCheck.py) ======

def enc(v: str) -> str:
    """RFC3986 percent-encode with safe unreserved set."""
    return urllib.parse.quote(v, safe='-_.~')


def canonical_query(params: Dict[str, str]) -> str:
    """
    Sort by parameter name (case-sensitive lexicographic)
    and build a=1&b=2 query string with RFC3986 encoding.
    """
    items = sorted(params.items(), key=lambda kv: kv[0])
    return "&".join(f"{enc(k)}={enc(v)}" for k, v in items)


def sign_get(full_url: str, params: Dict[str, str], secret_key: str) -> (str, str):
    """
    Given a full https URL and a param dict, build the StringToSign and signed URL.

    StringToSign format:
        GET\n
        {host}\n
        {path}\n
        {canonicalQueryString}
    """
    parsed = urllib.parse.urlparse(full_url)

    host = parsed.netloc
    path = parsed.path

    cq = canonical_query(params)
    string_to_sign = f"GET\n{host}\n{path}\n{cq}"

    digest = hmac.new(
        secret_key.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).digest()

    signature_b64 = base64.b64encode(digest).decode()
    signature_enc = enc(signature_b64)

    signed_url = f"https://{host}{path}?{cq}&Signature={signature_enc}"
    return string_to_sign, signed_url


# ====== SERVICE DISCOVERY ======

def fetch_service_profiles() -> List[ServiceProfile]:
    """
    Call the /services endpoint and parse the XML into ServiceProfile objects.
    """
    resp = requests.get(SERVICES_URL, timeout=20)
    resp.raise_for_status()

    xml_response = resp.text
    print(colorize_xml(pretty_xml(xml_response)))


    # The XML declares some elements in the core namespace.
    root = ET.fromstring(xml_response)

    profiles: List[ServiceProfile] = []
    for sp in root.findall("ServiceProfile"):
        name_el = sp.find("core:Name", NS)
        desc_el = sp.find("core:Description", NS)
        anon_el = sp.find("core:AnonymousAccessPermitted", NS)
        version_el = sp.find("Version")

        if name_el is None or desc_el is None or anon_el is None or version_el is None:
            # Skip malformed entries
            continue

        https_path = version_el.findtext("HTTPSRequestPath", default="").strip()
        version_number = version_el.findtext("VersionNumber", default="").strip()
        date = version_el.findtext("Date", default="").strip()

        profiles.append(
            ServiceProfile(
                name=name_el.text.strip(),
                description=desc_el.text.strip(),
                anonymous_access=(anon_el.text.strip().lower() == "true"),
                https_url=https_path,
                version=version_number,
                date=date,
            )
        )

    return profiles


def print_service_profiles(profiles: List[ServiceProfile]) -> None:
    """
    Nicely print the discovered services.
    """
    print("\nAvailable fcB2B Services:\n")
    for idx, sp in enumerate(profiles, start=1):
        anon = "Yes" if sp.anonymous_access else "No"
        print(f"{idx}. {sp.name} (v{sp.version}, {sp.date})")
        print(f"   Description : {sp.description}")
        print(f"   Anonymous   : {anon}")
        print(f"   HTTPS URL   : {sp.https_url}")
        print()


# ====== INTERACTIVE TESTING ======

def colorize_xml(xml: str) -> str:
    """
    Very lightweight XML syntax highlighter.
    Colors:
        - tags        = cyan
        - attributes  = yellow
        - attr values = green
    """
    def colorize_tag(tag: str) -> str:
        # <tag attr="value">
        # break tag into < + content + >
        content = tag[1:-1]

        # Colorize attributes inside tag
        def repl_attr(match):
            attr = match.group(1)
            val = match.group(2)
            return f"{YELLOW}{attr}{RESET}={GREEN}\"{val}\"{RESET}"

        content = re.sub(r'(\w+)\s*=\s*"([^"]*)"', repl_attr, content)

        return f"{CYAN}<{content}>{RESET}"

    # Replace tags with colorized versions
    colored = TAG_OPEN.sub(lambda m: colorize_tag(m.group(1)), xml)
    return colored

def pretty_xml(raw_xml: str) -> str:
    try:
        dom = minidom.parseString(raw_xml.encode("utf-8"))
        return dom.toprettyxml(indent="  ")
    except Exception:
        return raw_xml

def choose_service(profiles: List[ServiceProfile]) -> Optional[ServiceProfile]:
    """
    Ask the user to pick a service by number.
    """
    while True:
        choice = input("Enter the number of the service to test (or 'q' to quit): ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            return None
        if not choice.isdigit():
            print("Please enter a valid number.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(profiles):
            return profiles[idx - 1]

        print("Choice out of range. Try again.")


def build_params_for_service(service: ServiceProfile) -> Dict[str, str]:
    """
    Build the querystring parameters for the chosen service.

    For now, we assume:
      - All services require:
          GlobalIdentifier, TimeStamp, apiKey
      - InventoryInquiry/RelatedItems/StockCheck all use SupplierItemSKU
        as their primary item parameter.

    You can expand this later with per-service logic (e.g. location, customer, etc.).
    """
    # Common required fields
    global_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"\nTesting service: {service.name}")
    print(f"Generated GlobalIdentifier: {global_id}")
    print(f"Generated TimeStamp       : {timestamp}")

    # Basic params everyone gets
    params: Dict[str, str] = {
        "GlobalIdentifier": global_id,
        "TimeStamp": timestamp,  # NOTE: capital 'S' as per your server
        "apiKey": API_KEY,
    }

    # Service-specific input (you can expand this logic as needed)
    if service.name in ("InventoryInquiry", "RelatedItems", "StockCheck"):
        sku = input("Enter item number (SupplierItemSKU): ").strip()
        params["SupplierItemSKU"] = sku
    else:
        print("No specific parameters implemented for this service yet.")
        print("You can extend build_params_for_service() to handle it.")
        # Optionally still ask for a generic SKU
        sku = input("Enter item number (SupplierItemSKU) or leave blank: ").strip()
        if sku:
            params["SupplierItemSKU"] = sku

    return params


def call_service(service: ServiceProfile, params: Dict[str, str]) -> None:
    """
    Sign and call the selected service, then print the response.
    """
    if not service.https_url:
        print("This service does not specify an HTTPS URL. Cannot call it.")
        return

    string_to_sign, signed_url = sign_get(service.https_url, params, SECRET_KEY)

    print("\n--- Request Details ---")
    #print("StringToSign:")
    #print(string_to_sign)
    print("\nSigned URL:")
    print(signed_url)

    try:
        resp = requests.get(signed_url, headers={"Accept": "application/xml"}, timeout=20)
        print("\n--- Response ---")
        print(f"HTTP {resp.status_code}")
        if resp.status_code == 200:
            print("\n--- XML Response ---")
            pretty = pretty_xml(resp.text)
            print(colorize_xml(pretty))
        else:
            print("\n--- Raw Response ---")
            print(resp.text)
    except Exception as e:
        print("Request failed:", e)


# ====== MAIN ======

def main() -> None:
    print("Fetching fcB2B service profiles from:\n ", SERVICES_URL)

    try:
        profiles = fetch_service_profiles()
    except Exception as e:
        print("Failed to fetch or parse service profiles:", e)
        sys.exit(1)

    if not profiles:
        print("No services found in the profiles document.")
        sys.exit(1)



    while True:
        print_service_profiles(profiles)
        service = choose_service(profiles)
        if service is None:
            print("Exiting.")
            break

        params = build_params_for_service(service)
        call_service(service, params)

        again = input("\nDo you want to test another service? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("Goodbye.")
            break


if __name__ == "__main__":
    main()
