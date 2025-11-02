# template_initialization.py
"""
Initialize built-in chunking templates in the database.
This module loads templates from JSON files and seeds them into the database.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
import importlib
import importlib.resources as ires
from loguru import logger

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def load_builtin_templates() -> List[Dict[str, Any]]:
    """
    Load all built-in templates from the template_library directory.

    Returns:
        List of template dictionaries
    """
    templates: List[Dict[str, Any]] = []
    seen_names: set[str] = set()

    def _append_template(td: Dict[str, Any], src: str) -> None:
        name = td.get('name')
        if not name:
            logger.error(f"Template missing 'name' field (source={src})")
            return
        if name in seen_names:
            return
        templates.append({
            'name': name,
            'description': td.get('description', ''),
            'tags': td.get('tags', []),
            'template': td,
        })
        seen_names.add(name)
        logger.info(f"Loaded template: {name} from {src}")

    # Strategy 1: importlib.resources (works with wheels/zip and packages)
    try:
        pkg = 'tldw_Server_API.app.core.Chunking'
        base = ires.files(pkg).joinpath('template_library')
        if getattr(base, 'is_dir', lambda: False)():
            for entry in base.iterdir():
                try:
                    if not entry.name.endswith('.json'):
                        continue
                    with entry.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                    _append_template(data, f"pkg:{entry.name}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in template resource {entry}: {e}")
                except Exception as e:
                    logger.error(f"Error loading template resource {entry}: {e}")
    except Exception as e:
        logger.debug(f"importlib.resources scan failed for chunking templates: {e}")

    # Strategy 2: filesystem path relative to this file
    try:
        template_dir = Path(__file__).parent / "template_library"
        if template_dir.exists():
            for template_file in template_dir.glob("*.json"):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    _append_template(template_data, f"fs:{template_file.name}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in template file {template_file}: {e}")
                except Exception as e:
                    logger.error(f"Error loading template file {template_file}: {e}")
        else:
            logger.warning(f"Template library directory not found: {template_dir}")
    except Exception as e:
        logger.debug(f"Filesystem scan failed for chunking templates: {e}")

    # Strategy 3: minimal, safe built-ins as last resort
    if not templates:
        logger.warning("No built-in chunking templates found via resources or filesystem; using minimal fallbacks")
        minimal: List[Dict[str, Any]] = [
            {
                'name': 'academic_paper',
                'description': 'Template for processing academic papers',
                'tags': ['academic', 'research', 'papers'],
                'template': {
                    'name': 'academic_paper',
                    'preprocessing': [
                        {'operation': 'normalize_whitespace', 'config': {'max_line_breaks': 2}},
                        {'operation': 'extract_sections', 'config': {'pattern': r'^#+\s+(.+)$'}},
                    ],
                    'chunking': {'method': 'sentences', 'config': {'max_size': 5, 'overlap': 1}},
                    'postprocessing': [
                        {'operation': 'filter_empty', 'config': {'min_length': 20}},
                        {'operation': 'merge_small', 'config': {'min_size': 200}},
                    ],
                },
            },
            {
                'name': 'code_documentation',
                'description': 'Template for processing code documentation',
                'tags': ['code', 'docs'],
                'template': {
                    'name': 'code_documentation',
                    'preprocessing': [{'operation': 'clean_markdown', 'config': {'remove_images': True}}],
                    'chunking': {
                        'method': 'structure_aware',
                        'config': {'max_size': 500, 'overlap': 50, 'preserve_code_blocks': True, 'preserve_headers': True},
                    },
                    'postprocessing': [{'operation': 'filter_empty', 'config': {'min_length': 50}}],
                },
            },
            {
                'name': 'chat_conversation',
                'description': 'Template for processing chat conversations',
                'tags': ['chat', 'conversation'],
                'template': {
                    'name': 'chat_conversation',
                    'preprocessing': [{'operation': 'normalize_whitespace', 'config': {'max_line_breaks': 1}}],
                    'chunking': {'method': 'sentences', 'config': {'max_size': 10, 'overlap': 2}},
                    'postprocessing': [{'operation': 'add_overlap', 'config': {'size': 100, 'marker': '---'}}],
                },
            },
            {
                'name': 'book_chapters',
                'description': 'Template for processing book chapters',
                'tags': ['books', 'chapters'],
                'template': {
                    'name': 'book_chapters',
                    'preprocessing': [{'operation': 'normalize_whitespace', 'config': {'max_line_breaks': 2}}],
                    'chunking': {'method': 'ebook_chapters', 'config': {'max_size': 1200, 'overlap': 100}},
                    'postprocessing': [{'operation': 'filter_empty', 'config': {'min_length': 50}}],
                },
            },
            {
                'name': 'transcript_dialogue',
                'description': 'Template for processing transcripts and dialogue',
                'tags': ['transcript', 'dialogue', 'audio'],
                'template': {
                    'name': 'transcript_dialogue',
                    'preprocessing': [{'operation': 'normalize_whitespace', 'config': {'max_line_breaks': 1}}],
                    'chunking': {'method': 'sentences', 'config': {'max_size': 8, 'overlap': 2}},
                    'postprocessing': [{'operation': 'merge_small', 'config': {'min_size': 80}}],
                },
            },
            {
                'name': 'legal_document',
                'description': 'Template for processing legal documents',
                'tags': ['legal', 'contracts'],
                'template': {
                    'name': 'legal_document',
                    'preprocessing': [{'operation': 'normalize_whitespace', 'config': {'max_line_breaks': 2}}],
                    'chunking': {'method': 'paragraphs', 'config': {'max_size': 1, 'overlap': 0}},
                    'postprocessing': [{'operation': 'filter_empty', 'config': {'min_length': 50}}],
                },
            },
        ]
        templates.extend(minimal)

    return templates


def initialize_chunking_templates(db_path: str = None, client_id: str = 'system', db: MediaDatabase = None) -> int:
    """
    Initialize built-in chunking templates in the database.

    Args:
        db_path: Path to the database file (uses default if None and db is None)
        client_id: Client ID for database operations (only used if creating new db)
        db: MediaDatabase instance (if provided, db_path is ignored)

    Returns:
        Number of templates successfully seeded
    """
    try:
        # Backward compat: allow passing MediaDatabase as first positional arg
        if isinstance(db_path, MediaDatabase) and db is None:
            db = db_path
            db_path = None
        # Use provided database instance or create one
        if db is None:
            # For backward compatibility and startup initialization
            # This will be called for the default/single-user database
            if db_path is None:
                from pathlib import Path
                from tldw_Server_API.app.core.config import settings
                # Use proper user database path for single-user mode
                user_db_base = settings.get("USER_DB_BASE_DIR")
                single_user_id = settings.get("SINGLE_USER_FIXED_ID", "1")
                if user_db_base:
                    db_path = Path(user_db_base) / str(single_user_id) / "Media_DB_v2.db"
                    # Ensure directory exists
                    db_path.parent.mkdir(parents=True, exist_ok=True)
                    db_path = str(db_path)
                else:
                    # Fallback anchored to project or package root if config not available
                    try:
                        from tldw_Server_API.app.core.Utils.Utils import get_project_root
                        db_path = str(Path(get_project_root()) / 'Databases' / 'user_databases' / '1' / 'Media_DB_v2.db')
                    except Exception:
                        db_path = str(Path(__file__).resolve().parents[5] / 'Databases' / 'user_databases' / '1' / 'Media_DB_v2.db')

            # Create database instance
            db = MediaDatabase(db_path=db_path, client_id=client_id)

        # Load built-in templates
        templates = load_builtin_templates()

        if not templates:
            logger.warning("No built-in templates found to seed")
            return 0

        # Seed templates into database
        count = db.seed_builtin_templates(templates)

        logger.info(f"Successfully seeded {count} built-in templates into database")
        return count

    except Exception as e:
        logger.error(f"Error initializing chunking templates: {e}")
        return 0


def update_builtin_templates(db_path: str = None, client_id: str = 'system', force: bool = False, db: MediaDatabase = None) -> int:
    """
    Update existing built-in templates with latest definitions.

    Args:
        db_path: Path to the database file
        client_id: Client ID for database operations
        force: If True, overwrites existing templates even if not changed

    Returns:
        Number of templates updated
    """
    try:
        # Backward compat: allow passing MediaDatabase as first positional arg
        if isinstance(db_path, MediaDatabase) and db is None:
            db = db_path
            db_path = None
        # Use provided database instance or create one
        if db is None:
            if db_path is None:
                from pathlib import Path
                from tldw_Server_API.app.core.config import settings
                # Use proper user database path for single-user mode
                user_db_base = settings.get("USER_DB_BASE_DIR")
                single_user_id = settings.get("SINGLE_USER_FIXED_ID", "1")
                if user_db_base:
                    db_path = Path(user_db_base) / str(single_user_id) / "Media_DB_v2.db"
                    # Ensure directory exists
                    db_path.parent.mkdir(parents=True, exist_ok=True)
                    db_path = str(db_path)
                else:
                    # Fallback anchored to project or package root if config not available
                    try:
                        from tldw_Server_API.app.core.Utils.Utils import get_project_root
                        db_path = str(Path(get_project_root()) / 'Databases' / 'user_databases' / '1' / 'Media_DB_v2.db')
                    except Exception:
                        db_path = str(Path(__file__).resolve().parents[5] / 'Databases' / 'user_databases' / '1' / 'Media_DB_v2.db')

            db = MediaDatabase(db_path=db_path, client_id=client_id)
        templates = load_builtin_templates()

        updated_count = 0

        for template in templates:
            existing = db.get_chunking_template(name=template['name'])

            if existing and existing['is_builtin']:
                # Compare template content
                existing_template = json.loads(existing['template_json'])
                new_template = template['template']

                if force or existing_template != new_template:
                    # Update the template
                    success = db.update_chunking_template(
                        name=template['name'],
                        template_json=json.dumps(new_template),
                        description=template.get('description'),
                        tags=template.get('tags')
                    )

                    if success:
                        updated_count += 1
                        logger.info(f"Updated built-in template: {template['name']}")

        return updated_count

    except Exception as e:
        logger.error(f"Error updating built-in templates: {e}")
        return 0


# Convenience function to be called during application startup
def ensure_templates_initialized(db_path: str = None, db: MediaDatabase = None) -> bool:
    """
    Ensure built-in templates are initialized in the database.
    Called during application startup.

    Args:
        db_path: Path to the database file

    Returns:
        True if templates are properly initialized
    """
    try:
        count = initialize_chunking_templates(db_path=db_path, db=db)

        if count > 0:
            logger.info(f"Initialized {count} chunking templates on startup")
        else:
            # Check if templates already exist
            if db is None:
                if db_path is None:
                    from pathlib import Path
                    from tldw_Server_API.app.core.config import settings
                    # Use proper user database path for single-user mode
                    user_db_base = settings.get("USER_DB_BASE_DIR")
                    single_user_id = settings.get("SINGLE_USER_FIXED_ID", "1")
                    if user_db_base:
                        db_path = Path(user_db_base) / str(single_user_id) / "Media_DB_v2.db"
                        # Ensure directory exists
                        db_path.parent.mkdir(parents=True, exist_ok=True)
                        db_path = str(db_path)
                else:
                    # Fallback anchored to project or package root if config not available
                    try:
                        from tldw_Server_API.app.core.Utils.Utils import get_project_root
                        db_path = str(Path(get_project_root()) / 'Databases' / 'user_databases' / '1' / 'Media_DB_v2.db')
                    except Exception:
                        db_path = str(Path(__file__).resolve().parents[5] / 'Databases' / 'user_databases' / '1' / 'Media_DB_v2.db')

                db = MediaDatabase(db_path=db_path, client_id='system')
            existing = db.list_chunking_templates(include_builtin=True, include_custom=False)

            if existing:
                logger.debug(f"Found {len(existing)} existing built-in templates")
            else:
                logger.warning("No chunking templates found in database")

        return True

    except Exception as e:
        logger.error(f"Failed to ensure templates initialized: {e}")
        return False


if __name__ == "__main__":
    # If run directly, initialize templates
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    count = initialize_chunking_templates(db_path)
    print(f"Initialized {count} templates")
