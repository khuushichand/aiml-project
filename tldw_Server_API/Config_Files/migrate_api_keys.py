#!/usr/bin/env python3
"""
Migration script to move API keys from config.txt to .env file.

This script:
1. Reads API keys from config.txt
2. Creates/updates .env file with the API keys
3. Optionally removes API keys from config.txt
4. Creates a backup of the original config.txt

Usage:
    python migrate_api_keys.py [--remove-from-config]
"""

import argparse
import configparser
import shutil
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger


def main():
    parser = argparse.ArgumentParser(description='Migrate API keys from config.txt to .env file')
    parser.add_argument('--remove-from-config', action='store_true',
                        help='Remove API keys from config.txt after migration (keeps backup)')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing values in .env file')
    args = parser.parse_args()

    # Get paths
    script_dir = Path(__file__).parent
    config_path = script_dir / 'config.txt'
    env_path = script_dir / '.env'
    env_template_path = script_dir / '.env.template'

    # Check if config.txt exists
    if not config_path.exists():
        print(f"Error: config.txt not found at {config_path}")
        sys.exit(1)

    # Create backup of config.txt
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = script_dir / f'config.txt.backup_{timestamp}'
    shutil.copy2(config_path, backup_path)
    print(f"✓ Created backup: {backup_path}")

    # Read config.txt
    config = configparser.ConfigParser()
    config.read(config_path)

    # Define API key mappings (config section/key -> env variable name)
    api_key_mappings = {
        ('API', 'openai_api_key'): 'OPENAI_API_KEY',
        ('API', 'anthropic_api_key'): 'ANTHROPIC_API_KEY',
        ('API', 'cohere_api_key'): 'COHERE_API_KEY',
        ('API', 'groq_api_key'): 'GROQ_API_KEY',
        ('API', 'deepseek_api_key'): 'DEEPSEEK_API_KEY',
        ('API', 'qwen_api_key'): 'QWEN_API_KEY',
        ('API', 'google_api_key'): 'GOOGLE_API_KEY',
        ('API', 'huggingface_api_key'): 'HUGGINGFACE_API_KEY',
        ('API', 'mistral_api_key'): 'MISTRAL_API_KEY',
        ('API', 'openrouter_api_key'): 'OPENROUTER_API_KEY',
        ('API', 'elevenlabs_api_key'): 'ELEVENLABS_API_KEY',
        ('API', 'custom_openai_api_key'): 'CUSTOM_OPENAI_API_KEY',
        ('API', 'custom_openai2_api_key'): 'CUSTOM_OPENAI2_API_KEY',
        ('API', 'kobold_api_key'): 'KOBOLD_API_KEY',
        ('API', 'llama_api_key'): 'LLAMA_API_KEY',
        ('API', 'ooba_api_key'): 'OOBA_API_KEY',
        ('API', 'tabby_api_key'): 'TABBY_API_KEY',
        ('API', 'vllm_api_key'): 'VLLM_API_KEY',
        ('API', 'ollama_api_key'): 'OLLAMA_API_KEY',
        ('API', 'aphrodite_api_key'): 'APHRODITE_API_KEY',
        # Search engine keys
        ('Search-Engines', 'search_engine_api_key_bing'): 'BING_SEARCH_API_KEY',
        ('Search-Engines', 'search_engine_api_key_brave_regular'): 'BRAVE_SEARCH_API_KEY',
        ('Search-Engines', 'search_engine_api_key_brave_ai'): 'BRAVE_AI_API_KEY',
        ('Search-Engines', 'search_engine_api_key_google'): 'GOOGLE_SEARCH_API_KEY',
        ('Search-Engines', 'search_engine_id_google'): 'GOOGLE_SEARCH_ENGINE_ID',
        ('Search-Engines', 'search_engine_api_key_kagi'): 'KAGI_API_KEY',
        ('Search-Engines', 'search_engine_api_key_tavily'): 'TAVILY_API_KEY',
        ('Search-Engines', 'search_engine_api_key_baidu'): 'BAIDU_API_KEY',
        ('Search-Engines', 'search_engine_api_key_yandex'): 'YANDEX_API_KEY',
        ('Search-Engines', 'search_engine_id_yandex'): 'YANDEX_SEARCH_ID',
        # Web scraper
        ('Web-Scraper', 'web_scraper_api_key'): 'WEB_SCRAPER_API_KEY',
        # Embeddings
        ('Embeddings', 'embedding_api_key'): 'EMBEDDING_API_KEY',
    }

    # Read existing .env if it exists
    existing_env = {}
    if env_path.exists() and not args.force:
        print(f"✓ Found existing .env file at {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing_env[key] = value

    # Collect API keys from config
    env_vars = {}
    keys_found = []

    for (section, key), env_name in api_key_mappings.items():
        value = config.get(section, key, fallback=None)
        if value and value not in ['', 'None', f'<{key}>', 'your-api-key-here', 'your_api_key_here']:
            # Don't overwrite existing values unless --force is used
            if env_name in existing_env and not args.force:
                print(f"  Skipping {env_name} (already in .env, use --force to overwrite)")
            else:
                env_vars[env_name] = value
                keys_found.append((section, key, env_name))
                print(f"  Found {env_name}: {value[:10]}...")

    if not env_vars and not existing_env:
        print("\nNo API keys found to migrate.")
        sys.exit(0)

    # Copy template if .env doesn't exist
    if not env_path.exists() and env_template_path.exists():
        shutil.copy2(env_template_path, env_path)
        print("\n✓ Created .env from template")

    # Write to .env file
    if env_vars:
        # Read the entire file if it exists
        lines = []
        if env_path.exists():
            with open(env_path) as f:
                lines = f.readlines()

        # Update or append new keys
        with open(env_path, 'w') as f:
            updated_keys = set()

            # Process existing lines
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    key = stripped.split('=', 1)[0]
                    if key in env_vars:
                        # Update existing key
                        f.write(f"{key}={env_vars[key]}\n")
                        updated_keys.add(key)
                        print(f"  Updated {key} in .env")
                    else:
                        # Keep existing line
                        f.write(line)
                else:
                    # Keep comments and empty lines
                    f.write(line)

            # Append new keys that weren't in the file
            new_keys = set(env_vars.keys()) - updated_keys
            if new_keys:
                f.write("\n# Migrated from config.txt on " + datetime.now().isoformat() + "\n")
                for key in sorted(new_keys):
                    f.write(f"{key}={env_vars[key]}\n")
                    print(f"  Added {key} to .env")

        print(f"\n✓ Migrated {len(env_vars)} API keys to {env_path}")

    # Remove from config.txt if requested
    if args.remove_from_config and keys_found:
        print("\nRemoving API keys from config.txt...")

        # Create new config without API keys
        new_config = configparser.ConfigParser()
        new_config.read(config_path)

        for section, key, _env_name in keys_found:
            try:
                # Replace with placeholder
                new_config.set(section, key, f'<{key}>')
                print(f"  Removed {key} from [{section}]")
            except (configparser.NoSectionError, configparser.NoOptionError) as e:
                logger.warning(f"migrate_api_keys: failed to remove {key} from [{section}]: {e}")

        # Write updated config
        with open(config_path, 'w') as f:
            new_config.write(f)

        print(f"✓ Updated config.txt (backup saved as {backup_path})")

    # Final instructions
    print("\n" + "=" * 50)
    print("Migration complete!")
    print("\nIMPORTANT:")
    print("1. Your API keys are now in:", env_path)
    print("2. Make sure .env is in .gitignore (should be already)")
    print("3. Test your application to ensure API keys are loaded correctly")

    if not args.remove_from_config and keys_found:
        print("\nNote: API keys are still in config.txt. Run with --remove-from-config to remove them.")

    print("=" * 50)

if __name__ == "__main__":
    main()
