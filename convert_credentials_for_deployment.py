"""
Helper script to convert JSON credentials to environment variable format
Run this to get the credentials string for deployment platforms
"""

import json
import os

def convert_credentials_to_env_string(json_file_path):
    """
    Convert JSON credentials file to a single-line string for environment variables
    
    Args:
        json_file_path: Path to your credentials JSON file
        
    Returns:
        Single-line JSON string ready for environment variable
    """
    try:
        with open(json_file_path, 'r') as f:
            credentials = json.load(f)
        
        # Convert to compact JSON string (single line)
        json_string = json.dumps(credentials, separators=(',', ':'))
        
        print("=" * 80)
        print("✅ Credentials converted successfully!")
        print("=" * 80)
        print("\nCopy the following and paste it as the GCP_CREDENTIALS_JSON environment variable:")
        print("-" * 80)
        print(json_string)
        print("-" * 80)
        print("\n⚠️  IMPORTANT:")
        print("   - This is sensitive information!")
        print("   - Only paste this in your deployment platform's environment variables")
        print("   - NEVER commit this to Git")
        print("   - The .gitignore file protects your JSON files")
        print("=" * 80)
        
        return json_string
        
    except FileNotFoundError:
        print(f"❌ Error: File not found: {json_file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON file: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    # Path to your credentials file
    credentials_file = "static-chiller-472906-f3-4ee4a099f2f1.json"
    
    if os.path.exists(credentials_file):
        convert_credentials_to_env_string(credentials_file)
    else:
        print(f"❌ Credentials file not found: {credentials_file}")
        print("   Please update the path in this script or run from the correct directory")
