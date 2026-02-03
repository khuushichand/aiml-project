"""
Character Chat sub-modules for better code organization.
"""

# Re-export all public functions for backward compatibility
from .character_chat import (
    delete_conversation_by_id,
    edit_message_content,
    find_messages_in_conversation,
    get_conversation_metadata,
    list_character_conversations,
    load_chat_and_character,
    post_message_to_conversation,
    process_db_messages_to_rich_ui_history,
    process_db_messages_to_ui_history,
    remove_message_from_conversation,
    retrieve_conversation_messages_for_ui,
    retrieve_message_details,
    search_conversations_by_title_query,
    set_message_ranking,
    start_new_chat_session,
    update_conversation_metadata,
)
from .character_db import (
    _prepare_character_data_for_db_storage,
    create_new_character_from_data,
    delete_character_from_db,
    get_character_details,
    load_character_and_image,
    load_character_wrapper,
    restore_character_from_db,
    search_characters_by_query_text,
    update_existing_character_details,
)
from .character_io import (
    extract_json_from_image_file,
    import_and_save_character_from_file,
    import_character_card_from_json_string,
    load_character_card_from_string_content,
    load_chat_history_from_file_and_save_to_db,
)
from .character_templates import (
    CHARACTER_TEMPLATES,
    create_character_from_template,
    get_character_template,
    list_character_templates,
)
from .character_utils import (
    extract_character_id_from_ui_choice,
    get_character_list_for_ui,
    map_sender_to_role,
    replace_placeholders,
    replace_user_placeholder,
)
from .character_validation import (
    parse_alpaca_card,
    parse_character_book,
    parse_pygmalion_card,
    parse_textgen_card,
    parse_v1_card,
    parse_v2_card,
    validate_character_book,
    validate_character_book_entry,
    validate_v2_card,
)

__all__ = [
    # Utils
    'replace_placeholders',
    'replace_user_placeholder',
    'extract_character_id_from_ui_choice',
    'get_character_list_for_ui',
    'map_sender_to_role',

    # I/O
    'extract_json_from_image_file',
    'import_character_card_from_json_string',
    'load_character_card_from_string_content',
    'import_and_save_character_from_file',
    'load_chat_history_from_file_and_save_to_db',

    # Validation
    'parse_v1_card',
    'parse_v2_card',
    'parse_pygmalion_card',
    'parse_textgen_card',
    'parse_alpaca_card',
    'parse_character_book',
    'validate_character_book',
    'validate_character_book_entry',
    'validate_v2_card',

    # Database
    '_prepare_character_data_for_db_storage',
    'create_new_character_from_data',
    'get_character_details',
    'update_existing_character_details',
    'delete_character_from_db',
    'restore_character_from_db',
    'search_characters_by_query_text',
    'load_character_and_image',
    'load_character_wrapper',

    # Chat
    'process_db_messages_to_ui_history',
    'load_chat_and_character',
    'start_new_chat_session',
    'list_character_conversations',
    'get_conversation_metadata',
    'update_conversation_metadata',
    'delete_conversation_by_id',
    'search_conversations_by_title_query',
    'post_message_to_conversation',
    'retrieve_message_details',
    'retrieve_conversation_messages_for_ui',
    'edit_message_content',
    'set_message_ranking',
    'remove_message_from_conversation',
    'find_messages_in_conversation',
    'process_db_messages_to_rich_ui_history',

    # Templates
    'CHARACTER_TEMPLATES',
    'get_character_template',
    'list_character_templates',
    'create_character_from_template'
]
