#!/usr/bin/env python3
"""
Configuration Migration Script for tldw_server

This script migrates API keys and sensitive data from config.txt to .env file,
following the new configuration structure where:
- .env contains all sensitive data (API keys, secrets, passwords)
- config.txt contains only non-sensitive application settings

Usage:
    python migrate_config.py [--dry-run] [--backup]
"""

import argparse
import configparser
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


class ConfigMigrator:
    """Handles migration of configuration from config.txt to .env"""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """Initialize the migrator with config directory path"""
        if config_dir is None:
            # Default to current directory (Config_Files)
            self.config_dir = Path(__file__).parent
        else:
            self.config_dir = Path(config_dir)

        self.config_file = self.config_dir / "config.txt"
        self.env_file = self.config_dir / ".env"
        self.env_template = self.config_dir / ".env.template"
        self.backup_dir = self.config_dir / "backups"

        # Mapping of config.txt keys to .env keys
        self.key_mapping = {
            # API Section
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "cohere_api_key": "COHERE_API_KEY",
            "deepseek_api_key": "DEEPSEEK_API_KEY",
            "google_api_key": "GOOGLE_API_KEY",
            "groq_api_key": "GROQ_API_KEY",
            "huggingface_api_key": "HUGGINGFACE_API_KEY",
            "mistral_api_key": "MISTRAL_API_KEY",
            "openai_api_key": "OPENAI_API_KEY",
            "openrouter_api_key": "OPENROUTER_API_KEY",
            "qwen_api_key": "QWEN_API_KEY",
            "elevenlabs_api_key": "ELEVENLABS_API_KEY",
            "custom_openai_api_key": "CUSTOM_OPENAI_API_KEY",
            "custom_openai_api_ip": "CUSTOM_OPENAI_API_IP",
            "custom_openai2_api_key": "CUSTOM_OPENAI2_API_KEY",
            "custom_openai2_api_ip": "CUSTOM_OPENAI2_API_IP",

            # Local API Section (only keys, not IPs - IPs stay in config.txt)
            "kobold_api_key": "KOBOLD_API_KEY",
            "llama_api_key": "LLAMA_API_KEY",
            "ooba_api_key": "OOBA_API_KEY",
            "tabby_api_key": "TABBY_API_KEY",
            "vllm_api_key": "VLLM_API_KEY",
            "ollama_api_key": "OLLAMA_API_KEY",
            "aphrodite_api_key": "APHRODITE_API_KEY",

            # Embeddings Section
            "embedding_api_key": "EMBEDDING_API_KEY",
            "embedding_api_url": "EMBEDDING_API_URL",
        }

        self.extracted_keys = {}
        self.existing_env_keys = {}

    def backup_files(self) -> tuple[Optional[Path], Optional[Path]]:
        """Create backups of existing config files"""
        self.backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        config_backup = None
        env_backup = None

        if self.config_file.exists():
            config_backup = self.backup_dir / f"config.txt.backup_{timestamp}"
            shutil.copy2(self.config_file, config_backup)
            logger.success("Backed up config.txt to {}", config_backup)

        if self.env_file.exists():
            env_backup = self.backup_dir / f".env.backup_{timestamp}"
            shutil.copy2(self.env_file, env_backup)
            logger.success("Backed up .env to {}", env_backup)

        return config_backup, env_backup

    def extract_keys_from_config(self) -> dict[str, str]:
        """Extract API keys and sensitive data from config.txt"""
        if not self.config_file.exists():
            logger.warning("Config file not found: {}", self.config_file)
            return {}

        config = configparser.ConfigParser()
        config.read(self.config_file)

        extracted = {}

        # Process API section
        if config.has_section("API"):
            for key, env_key in self.key_mapping.items():
                if config.has_option("API", key):
                    value = config.get("API", key)
                    # Skip placeholder values
                    if value and not value.startswith("<") and not value.endswith(">"):
                        if value != "your_api_key_here" and value != "":
                            extracted[env_key] = value
                            logger.info("Found API key for migration: {}", key)

        # Process Local-API section
        if config.has_section("Local-API"):
            for key, env_key in self.key_mapping.items():
                if config.has_option("Local-API", key):
                    value = config.get("Local-API", key)
                    # Skip empty values, placeholders, and IPs (not sensitive)
                    if value and not value.startswith("<") and not value.endswith(">"):
                        # Skip IP addresses - they stay in config.txt
                        if "_IP" in key or "_ip" in key:
                            continue
                        if value != "":
                            extracted[env_key] = value
                            logger.info("Found local API key for migration: {}", key)

        # Process Embeddings section
        if config.has_section("Embeddings"):
            if config.has_option("Embeddings", "embedding_api_key"):
                value = config.get("Embeddings", "embedding_api_key")
                if value and value != "your_api_key_here" and value != "":
                    extracted["EMBEDDING_API_KEY"] = value
                    logger.info("Found embedding API key for migration")

            if config.has_option("Embeddings", "embedding_api_url"):
                value = config.get("Embeddings", "embedding_api_url")
                if value and value != "http://localhost:8080/v1/embeddings":
                    extracted["EMBEDDING_API_URL"] = value
                    logger.info("Found embedding API URL for migration")

        self.extracted_keys = extracted
        return extracted

    def read_existing_env(self) -> dict[str, str]:
        """Read existing .env file if it exists"""
        if not self.env_file.exists():
            return {}

        existing = {}
        try:
            with open(self.env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing[key.strip()] = value.strip()
        except (OSError, UnicodeError) as exc:
            logger.error("Failed to read .env file: {}", exc)
            raise

        self.existing_env_keys = existing
        return existing

    def write_env_file(
        self,
        keys: dict[str, str],
        preserve_existing: bool = True,
    ) -> None:
        """Write the .env file with migrated keys"""
        # Read template for structure
        template_lines = []
        if self.env_template.exists():
            try:
                with open(self.env_template, encoding="utf-8") as f:
                    template_lines = f.readlines()
            except (OSError, UnicodeError) as exc:
                logger.warning("Failed to read .env template, using fallback format: {}", exc)
                template_lines = []

        # Merge with existing keys if preserving
        final_keys = {}
        if preserve_existing:
            final_keys.update(self.existing_env_keys)
        final_keys.update(keys)

        # Write new .env file
        try:
            with open(self.env_file, "w", encoding="utf-8") as f:
                if template_lines:
                    # Use template structure
                    for line in template_lines:
                        if "=" in line and not line.strip().startswith("#"):
                            key = line.split("=")[0].strip()
                            if key in final_keys:
                                # Skip empty values
                                if final_keys[key]:
                                    f.write(f"{key}={final_keys[key]}\n")
                                    final_keys.pop(key)  # Mark as written
                                else:
                                    f.write(line)  # Keep original empty line
                            else:
                                f.write(line)
                        else:
                            f.write(line)

                    # Add any keys not in template
                    if final_keys:
                        f.write("\n# Additional migrated keys\n")
                        for key, value in final_keys.items():
                            if value:  # Skip empty values
                                f.write(f"{key}={value}\n")
                else:
                    # No template, write simple format
                    f.write("# Migrated configuration\n")
                    f.write(f"# Generated on {datetime.now().isoformat()}\n\n")

                    # Group by type
                    api_keys = {k: v for k, v in final_keys.items() if "API_KEY" in k}
                    api_ips = {k: v for k, v in final_keys.items() if "API_IP" in k}
                    others = {
                        k: v for k, v in final_keys.items() if k not in api_keys and k not in api_ips
                    }

                    if api_keys:
                        f.write("# API Keys\n")
                        for key, value in sorted(api_keys.items()):
                            if value:
                                f.write(f"{key}={value}\n")
                        f.write("\n")

                    if api_ips:
                        f.write("# API Endpoints\n")
                        for key, value in sorted(api_ips.items()):
                            if value:
                                f.write(f"{key}={value}\n")
                        f.write("\n")

                    if others:
                        f.write("# Other Settings\n")
                        for key, value in sorted(others.items()):
                            if value:
                                f.write(f"{key}={value}\n")
        except OSError as exc:
            logger.error("Failed to write .env file: {}", exc)
            raise

        try:
            self.env_file.chmod(0o600)
        except OSError as exc:
            logger.warning("Unable to set permissions on .env: {}", exc)

    def migrate(self, dry_run: bool = False, backup: bool = True) -> bool:
        """Perform the migration"""
        logger.info("\n" + "="*60)
        logger.info("Configuration Migration Tool")
        logger.info("="*60)

        if dry_run:
            logger.info("\n🔍 DRY RUN MODE - No changes will be made\n")

        # Step 1: Backup if requested
        if backup and not dry_run:
            logger.info("\n📦 Creating backups...")
            self.backup_files()

        # Step 2: Read existing .env
        logger.info("\n📖 Reading existing .env file...")
        existing_env = self.read_existing_env()
        if existing_env:
            logger.info("  Found {} existing keys in .env", len(existing_env))
        else:
            logger.info("  No existing .env file found")

        # Step 3: Extract keys from config.txt
        logger.info("\n🔍 Extracting keys from config.txt...")
        extracted = self.extract_keys_from_config()

        if not extracted:
            logger.info("\n✅ No API keys found to migrate")
            return True

        logger.info("\n📊 Found {} keys to migrate", len(extracted))

        # Step 4: Check for conflicts
        conflicts = []
        for key in extracted:
            if key in existing_env and existing_env[key] != extracted[key]:
                conflicts.append(key)

        if conflicts:
            logger.warning(
                "Warning: {} keys already exist in .env with different values: {}",
                len(conflicts),
                ", ".join(sorted(conflicts)),
            )

            if not dry_run:
                response = input("\nOverwrite existing values? (y/N): ")
                if response.lower() != "y":
                    logger.info("Migration cancelled")
                    return False

        # Step 5: Write new .env file
        if not dry_run:
            logger.info("\n✍ Writing .env file...")
            self.write_env_file(extracted, preserve_existing=True)
            logger.info("✓ Updated .env file with {} keys", len(extracted))
        else:
            logger.info(
                "Would write {} keys to .env: {}",
                len(extracted),
                ", ".join(sorted(extracted)),
            )

        # Step 6: Summary
        logger.info("\n" + "="*60)
        if dry_run:
            logger.info("DRY RUN COMPLETE - No changes were made")
            logger.info("Run without --dry-run to perform actual migration")
        else:
            logger.info("✅ MIGRATION COMPLETE")
            logger.info("\nNext steps:")
            logger.info("1. Review the .env file to ensure all keys are correct")
            logger.info("2. Test the application to verify it works with new config")
            logger.info("3. The cleaned config.txt no longer contains API keys")
            logger.info("\nIMPORTANT: Never commit .env to version control!")
        logger.info("="*60 + "\n")

        return True


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate API keys from config.txt to .env file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backups before migration (default: True)"
    )
    parser.add_argument(
        "--no-backup",
        dest="backup",
        action="store_false",
        help="Skip creating backups"
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        help="Path to config directory (default: current directory)"
    )

    args = parser.parse_args()

    # Run migration
    migrator = ConfigMigrator(config_dir=args.config_dir)
    success = migrator.migrate(dry_run=args.dry_run, backup=args.backup)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
