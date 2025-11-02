#!/usr/bin/env python3
"""
Test script to verify that API keys are properly loaded from .env file.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import from tldw_Server_API
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_env_loading():
    print("Testing API key loading from .env file...\n")
    print("=" * 50)

    # Test 1: Direct environment variable check
    print("1. Checking environment variables directly:")
    env_vars_to_check = [
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY',
        'GOOGLE_API_KEY',
        'GROQ_API_KEY',
        'DEEPSEEK_API_KEY',
    ]

    for var in env_vars_to_check:
        value = os.getenv(var)
        if value and value not in ['', 'None', f'<{var.lower()}>', 'your-api-key-here']:
            print(f"  ✓ {var}: {value[:10]}..." if len(value) > 10 else f"  ✓ {var}: Set")
        else:
            print(f"  ✗ {var}: Not set or using placeholder")

    print("\n" + "=" * 50)

    # Test 2: Load through config system
    print("2. Testing config.py loading:")
    try:
        from tldw_Server_API.app.core.config import load_and_log_configs

        config_data = load_and_log_configs()
        if config_data:
            print("  ✓ Config loaded successfully")

            # Check specific API keys
            api_keys_to_check = [
                ('openai_api', 'api_key'),
                ('anthropic_api', 'api_key'),
                ('google_api', 'api_key'),
            ]

            for api_name, key_name in api_keys_to_check:
                api_data = config_data.get(api_name, {})
                if api_data and isinstance(api_data, dict):
                    api_key = api_data.get(key_name)
                    if api_key and api_key not in ['', 'None', f'<{api_name}_key>', 'your-api-key-here']:
                        print(f"    ✓ {api_name}: {api_key[:10]}...")
                    else:
                        print(f"    ✗ {api_name}: Not set or using placeholder")
        else:
            print("  ✗ Failed to load config")
    except Exception as e:
        print(f"  ✗ Error loading config: {e}")

    print("\n" + "=" * 50)

    # Test 3: Load through secret manager
    print("3. Testing secret_manager.py loading:")
    try:
        from tldw_Server_API.app.core.Security.secret_manager import get_api_key

        providers = ['openai', 'anthropic', 'google', 'groq', 'deepseek']

        for provider in providers:
            api_key = get_api_key(provider)
            if api_key and api_key not in ['', 'None', f'<{provider}_api_key>', 'your-api-key-here']:
                print(f"  ✓ {provider}: {api_key[:10]}...")
            else:
                print(f"  ✗ {provider}: Not set or using placeholder")
    except Exception as e:
        print(f"  ✗ Error with secret manager: {e}")

    print("\n" + "=" * 50)
    print("\nTest complete!")

    # Check if .env file exists
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        print(f"\n✓ .env file found at: {env_path}")
    else:
        print(f"\n✗ No .env file found at: {env_path}")
        print("  Run 'python migrate_api_keys.py' to create it from config.txt")

if __name__ == "__main__":
    test_env_loading()
