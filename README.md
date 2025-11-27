# fcB2B Client Tester

Simple interactive CLI to discover and call fcB2B services. It fetches a service catalog, lets you choose a service, builds the required query parameters, HMAC-signs the request, and prints the response with lightweight XML colorization.

## Overview
This repository contains a single Python script:
- `fcb2b_client.py` — interactive tester for fcB2B services hosted at a configured endpoint. It:
  - Fetches `/services` XML and parses available ServiceProfiles
  - Displays service name/description/version
  - Prompts for inputs (e.g., SupplierItemSKU)
  - Builds canonical query string
  - Signs the request using HMAC-SHA256
  - Executes the GET call and pretty-prints XML results


## Installation and setup
You can run the script directly after installing dependencies.

## Running
From the project root:
- python fcb2b_client.py

You will see a list of discovered services, be prompted to select one, and, for some services, to enter a SupplierItemSKU. The script prints the signed URL and the HTTP/XML response.

Notes:
- The script is interactive; it will keep allowing tests until you exit.
- Network calls target the configured host.

## Configuration
Configuration is currently hard-coded at the top of `fcb2b_client.py`:
- SERVICES_URL = "https://des.buckwold.com/danciko/bwl/dancik-b2b/services"
- API_KEY = "anonymous"
- SECRET_KEY = "yoursecretkey"

## Scripts and entry points
- Entry point: run with `python fcb2b_client.py`
- There are no additional CLI scripts or packaging config.

## How it works (high level)
- Fetch service profiles from SERVICES_URL
- Parse XML and display `ServiceProfile` entries
- Prompt for a choice, build common params: GlobalIdentifier (UUID), TimeStamp (UTC ISO8601), apiKey
- For select services (InventoryInquiry, RelatedItems, StockCheck), prompt for SupplierItemSKU
- Canonicalize query params and compute HMAC-SHA256 signature
- Issue GET request to the service HTTPS URL with the signature
- Pretty-print and colorize XML response


## Sample responses
A set of example XML responses is provided in the `sample_responses` folder. These illustrate what you can expect from a few commonly used services and are helpful for quick reference or offline inspection:
- sample_responses\InventoryInquiry_SampleResponse.xml — sample for the InventoryInquiry service
- sample_responses\RelatedItems_SampleResponse.xml — sample for the RelatedItems service
- sample_responses\StockCheck_SampleResponse.xml — sample for the StockCheck service
- sample_responses\ServiceProfile_SampleResponse.xml - sample of the services profile available

Tip: Open these files in your editor/IDE to view the raw XML. They can also be used to compare against live responses returned by this tester.
