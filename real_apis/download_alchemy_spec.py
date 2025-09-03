#!/usr/bin/env python3
"""
Download Alchemy OpenAPI specifications for local parsing and analysis.
Based on official Alchemy documentation: https://github.com/alchemyplatform/docs
"""

import requests
import json
from pathlib import Path

def download_alchemy_openapi_specs():
    """Download Alchemy OpenAPI specifications from their official dev-docs domain."""
    
    # Create specs directory if it doesn't exist
    specs_dir = Path(__file__).parent / "specs"
    specs_dir.mkdir(exist_ok=True)
    
    # Official Alchemy API specs URLs from their documentation
    # Source: https://github.com/alchemyplatform/docs?tab=readme-ov-file#consuming-specs
    
    # First, get the metadata to see all available specs
    metadata_url = "https://dev-docs.alchemy.com/metadata.json"
    
    print(f"🔍 Fetching Alchemy API metadata...")
    print(f"📥 URL: {metadata_url}")
    
    try:
        metadata_response = requests.get(metadata_url)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        
        # Save metadata
        metadata_file = specs_dir / "alchemy_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Saved metadata to: {metadata_file}")
        
        # Parse metadata to find available specs
        files = metadata.get("files", [])
        print(f"📊 Found {len(files)} API specification files")
        
        # Download REST API specs (OpenAPI) - look for /rest/ in URLs
        rest_specs = []
        for file_url in files:
            if "/rest/" in file_url:
                rest_specs.append(file_url)
        
        print(f"🔗 Found {len(rest_specs)} REST API specifications")
        
        # Download each REST API spec
        for spec_url in rest_specs:
            # Extract spec name from URL
            spec_name = spec_url.split("/")[-1].replace(".json", "")
            print(f"📥 Downloading {spec_name}...")
            
            try:
                spec_response = requests.get(spec_url)
                spec_response.raise_for_status()
                
                # Save the spec
                spec_file = specs_dir / f"alchemy_{spec_name}_openapi.json"
                with open(spec_file, 'w') as f:
                    json.dump(spec_response.json(), f, indent=2)
                
                print(f"✅ Saved {spec_name} to: {spec_file}")
                print(f"📊 Size: {len(spec_response.content)} bytes")
                
            except Exception as e:
                print(f"❌ Failed to download {spec_name}: {e}")
        
        return True
        
    except requests.RequestException as e:
        print(f"❌ Failed to fetch metadata: {e}")
        return False

def create_endpoint_summary():
    """Create a summary of common Alchemy endpoints based on documentation."""
    
    print(f"\n🔍 Creating endpoint summary...")
    
    # Common Alchemy API endpoints (based on documentation)
    base_urls = [
        "https://eth-mainnet.g.alchemy.com/v2",
        "https://base-mainnet.g.alchemy.com/v2",
        "https://polygon-mainnet.g.alchemy.com/v2"
    ]
    
    # Common endpoints to test (based on Alchemy documentation)
    endpoints = [
        "/getAssetTransfers",
        "/getTransactionReceipts", 
        "/getLogs",
        "/getTransaction",
        "/getBlock",
        "/getBalance",
        "/getTokenBalances",
        "/getTokenMetadata"
    ]
    
    specs_dir = Path(__file__).parent / "specs"
    specs_dir.mkdir(exist_ok=True)
    
    # Create a summary of endpoints
    endpoint_summary = {
        "base_urls": base_urls,
        "common_endpoints": endpoints,
        "note": "These are common Alchemy endpoints based on documentation. Test with actual API calls.",
        "source": "https://github.com/alchemyplatform/docs"
    }
    
    summary_file = specs_dir / "alchemy_endpoints_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(endpoint_summary, f, indent=2)
    
    print(f"📁 Saved endpoint summary to: {summary_file}")
    return str(summary_file)

if __name__ == "__main__":
    print(f"🚀 Alchemy OpenAPI Specification Discovery")
    print(f"=" * 60)
    print(f"Based on official documentation: https://github.com/alchemyplatform/docs")
    print(f"=" * 60)
    
    # Download OpenAPI specifications
    specs_result = download_alchemy_openapi_specs()
    
    # Create endpoint summary
    summary_result = create_endpoint_summary()
    
    if specs_result:
        print(f"\n🎯 Next steps:")
        print(f"1. Review downloaded OpenAPI specifications")
        print(f"2. Parse specs to identify wallet transaction endpoints")
        print(f"3. Test endpoints with curl")
        print(f"4. Document response sizes and features")
    else:
        print(f"\n❌ Failed to download specifications. Will proceed with manual endpoint discovery.")
