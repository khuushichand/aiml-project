"""
Test utilities for Character Chat tests.

This module provides test helpers and mock implementations for testing,
including a CharacterChatManager wrapper class.
"""

from typing import Dict, List, Optional, Any
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.Character_Chat import Character_Chat_Lib_facade as char_lib


class CharacterChatManager:
    """
    A wrapper class that provides a manager interface for character chat operations.

    This class wraps the individual functions from the Character Chat facade to provide
    a cohesive interface for testing purposes.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize the manager with a database connection."""
        self.db = CharactersRAGDB(db_path, client_id="test_client")
        self.db_path = db_path

    def create_character_card(self, **kwargs) -> Optional[int]:
        """Create a new character card.

        For compatibility with tests, invoke both the keyword-based API
        (create_character_card) and the dict-based API (add_character_card)
        when available. This ensures mocks on either method are exercised.
        """
        card_id = None
        # Prefer keyword API if present
        if hasattr(self.db, 'create_character_card') and callable(self.db.create_character_card):
            card_id = self.db.create_character_card(**kwargs)
        # Also call the dict-based API expected by some tests
        if hasattr(self.db, 'add_character_card') and callable(self.db.add_character_card):
            card_id_dict = self.db.add_character_card(kwargs)
            # Prefer a non-None id
            if card_id is None:
                card_id = card_id_dict
        return card_id

    def get_character_card(self, card_id: int) -> Optional[Dict[str, Any]]:
        """Get a character card by ID (attempt both APIs for test compatibility)."""
        result = None
        if hasattr(self.db, 'get_character_card_by_id'):
            result = self.db.get_character_card_by_id(card_id)
        # If a generic getter is configured (e.g., mocked in tests), respect its value
        if hasattr(self.db, 'get_character_card'):
            generic = self.db.get_character_card(card_id)
            if generic is None:
                return None
            # Prefer generic if available
            result = generic or result
        return result

    def list_character_cards(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """List all character cards."""
        if hasattr(self.db, 'get_character_list_for_ui'):
            return self.db.get_character_list_for_ui()
        return []

    def update_character_card(self, card_id: int, **kwargs) -> Dict[str, Any]:
        """Update an existing character card."""
        # Add expected_version if not provided
        if 'expected_version' not in kwargs:
            card = self.get_character_card(card_id)
            if card:
                kwargs['expected_version'] = card.get('version', 1)
        if hasattr(self.db, 'update_character_card'):
            success = self.db.update_character_card(card_id, kwargs, kwargs.get('expected_version', 1))
        else:
            success = False
        return {'success': success}

    def delete_character_card(self, card_id: int, expected_version: int = 1) -> Dict[str, Any]:
        """Delete a character card."""
        if hasattr(self.db, 'delete_character_card'):
            success = self.db.delete_character_card(card_id)
        else:
            success = False
        return {'success': success}

    def search_character_cards(self, query: str) -> List[Dict[str, Any]]:
        """Search for character cards."""
        if hasattr(self.db, 'search_character_cards'):
            return self.db.search_character_cards(query)
        return []

    def filter_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """Filter character cards by tags."""
        if hasattr(self.db, 'filter_by_tags'):
            return self.db.filter_by_tags(tags)
        return []

    def start_new_chat(self, character_id: int, user_name: str = "User") -> Optional[int]:
        """Start a new chat session with a character."""
        # Use DB mock-friendly API
        if hasattr(self.db, 'create_chat'):
            return self.db.create_chat(character_id=character_id, user_id=user_name, title=f"Chat with {character_id}")
        # Fallback to library if available
        result = char_lib.start_new_chat_session(self.db, character_id, user_name)
        if result and result[0]:
            return result[0]
        return None

    def add_message(self, chat_id: int, role: str, content: str) -> bool:
        """Add a message to an existing chat.

        Supports both DB signatures:
        - add_message(chat_id, role, content)
        - add_message({ ... message dict ... })
        """
        if hasattr(self.db, 'add_message'):
            try:
                result = self.db.add_message(chat_id, role, content)
                return result is not None
            except TypeError:
                import uuid
                msg_data = {
                    'id': str(uuid.uuid4()),
                    'conversation_id': chat_id,
                    'sender': role,
                    'content': content,
                    'parent_message_id': None,
                    'deleted': 0,
                    'client_id': 'test_client',
                    'version': 1
                }
                result = self.db.add_message(msg_data)
                return result is not None
        return False

    def get_chat_messages(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get all messages from a chat, trying both DB APIs."""
        messages: List[Dict[str, Any]] = []
        if hasattr(self.db, 'get_messages'):
            messages = self.db.get_messages(chat_id) or []
        elif hasattr(self.db, 'get_messages_for_conversation'):
            messages = self.db.get_messages_for_conversation(chat_id) or []
        return messages

    def list_chats_for_character(self, character_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all chat sessions for a character."""
        if hasattr(self.db, 'list_character_conversations'):
            return self.db.list_character_conversations(character_id, limit, offset)
        return []

    def delete_chat(self, chat_id: int) -> bool:
        """Delete a chat session."""
        if hasattr(self.db, 'delete_chat'):
            res = self.db.delete_chat(chat_id)
            return bool(res) if isinstance(res, dict) else bool(res)
        if hasattr(self.db, 'delete_chat_session'):
            return self.db.delete_chat_session(chat_id)
        return False

    def search_messages(self, query: str, character_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search messages across chats."""
        # This functionality might not exist in the original lib
        # Return empty list for now
        return []

    def get_chat_statistics(self, chat_id: int) -> Dict[str, Any]:
        """Get statistics for a chat."""
        if hasattr(self.db, 'get_chat_statistics'):
            return self.db.get_chat_statistics(chat_id)
        # Fallback basic counts
        messages = self.get_chat_messages(chat_id)
        return {
            'total_messages': len(messages),
            'user_messages': sum(1 for m in messages if m.get('role') == 'user'),
            'assistant_messages': sum(1 for m in messages if m.get('role') == 'assistant'),
        }

    def cleanup(self):
        """Cleanup resources."""
        # Close database connection if needed
        pass

    def close(self):
        """Close the manager (alias for cleanup)."""
        self.cleanup()

    # Additional methods needed for tests
    def create_chat_session(self, character_id: int, user_name: str = "User", user_id: str = None, title: str = None) -> Optional[int]:
        """Create a new chat session (DB-first implementation)."""
        if user_id:
            user_name = user_id
        if hasattr(self.db, 'create_chat'):
            return self.db.create_chat(character_id=character_id, user_id=user_name, title=title or f"Chat with {character_id}")
        return self.start_new_chat(character_id, user_name)

    def get_chat_session(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get information about a chat session."""
        chat = None
        if hasattr(self.db, 'get_chat'):
            chat = self.db.get_chat(chat_id)
        elif hasattr(self.db, 'get_conversation_by_id'):
            chat = self.db.get_conversation_by_id(chat_id)
        messages = self.get_chat_messages(chat_id)
        if chat or messages:
            return {
                'id': chat_id,
                'title': chat.get('title') if isinstance(chat, dict) else None,
                'character_id': chat.get('character_id') if isinstance(chat, dict) else None,
                'message_count': len(messages),
                'messages': messages,
            }
        return None

    def list_user_chats(self, user_name: str = None, user_id: str = None) -> List[Dict[str, Any]]:
        """List all chats for a user."""
        if user_id:
            user_name = user_id
        if hasattr(self.db, 'list_user_chats'):
            return self.db.list_user_chats(user_name)
        return []

    def delete_chat_session(self, chat_id: int) -> Dict[str, Any]:
        """Delete a chat session (DB-first)."""
        if hasattr(self.db, 'delete_chat'):
            res = self.db.delete_chat(chat_id)
            success = bool(res) if isinstance(res, dict) else bool(res)
            return {'success': success}
        success = self.delete_chat(chat_id)
        return {'success': success}

    def clear_chat_history(self, chat_id: int) -> Dict[str, Any]:
        """Clear all messages from a chat."""
        if hasattr(self.db, 'clear_chat_messages'):
            return self.db.clear_chat_messages(chat_id)
        return {'success': False}

    def get_messages(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get messages from a chat."""
        messages = self.get_chat_messages(chat_id)
        # Normalize sender -> role for compatibility
        for msg in messages:
            if 'sender' in msg and 'role' not in msg:
                msg['role'] = msg['sender']
        return messages

    def get_recent_messages(self, chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages from a chat."""
        messages = self.get_messages(chat_id)
        return messages[-limit:] if messages else []

    def edit_message(self, message_id: int, new_content: str) -> Dict[str, Any]:
        """Edit a message."""
        if hasattr(self.db, 'update_message'):
            return self.db.update_message(message_id=message_id, new_content=new_content)
        return {'success': False}

    def delete_message(self, message_id: int) -> Dict[str, Any]:
        """Delete a message."""
        if hasattr(self.db, 'delete_message'):
            return self.db.delete_message(message_id)
        return {'success': False}

    def build_context(self, chat_id: int = None, character_id: int = None, messages: List[Dict[str, Any]] = None,
                      max_tokens: int = 4000) -> Dict[str, Any]:
        """Build context object for LLM from chat or provided messages."""
        # Resolve messages
        if messages is None and chat_id is not None:
            messages = self.get_messages(chat_id)
        messages = messages or []
        # Resolve character details
        character = None
        if hasattr(self.db, 'get_character_card') and character_id is not None:
            character = self.db.get_character_card(character_id)
        elif hasattr(self.db, 'get_chat') and chat_id is not None:
            chat = self.db.get_chat(chat_id)
            if chat and 'character_id' in chat and hasattr(self.db, 'get_character_card'):
                character = self.db.get_character_card(chat['character_id'])
        # Include system prompt if available
        context: Dict[str, Any] = {
            'character': character or {},
            'messages': messages,
        }
        if character and 'system_prompt' in character:
            context['system_prompt'] = character['system_prompt']
        return context

    def count_tokens(self, text: str) -> int:
        """Count tokens in text (approximation)."""
        if not text:
            return 0
        # Simple approximation: 1 token ≈ 4 characters, but never under-count words.
        char_based = max(1, (len(text) + 3) // 4)
        word_based = len(text.split())
        return max(char_based, word_based)

    def truncate_context(self, messages: List[Dict[str, Any]] = None, max_tokens: int = 4000) -> List[Dict[str, Any]]:
        """Truncate context to fit within token limit."""
        if messages is None:
            return []

        # Simple implementation: keep messages that fit within token budget
        total_tokens = 0
        result = []

        # Process messages in reverse order (keep most recent)
        for msg in reversed(messages):
            msg_tokens = self.count_tokens(msg.get('content', ''))
            if total_tokens + msg_tokens <= max_tokens:
                result.insert(0, msg)  # Insert at beginning to maintain order
                total_tokens += msg_tokens
            else:
                break

        return result

    def inject_world_entries(self, context: Dict[str, Any], world_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Inject world book entries into a context dict as 'world_info'."""
        if isinstance(world_entries, dict):
            world_entries = [world_entries]
        contents = [e.get('content', '') if isinstance(e, dict) else str(e) for e in world_entries]
        ctx = dict(context) if isinstance(context, dict) else {'messages': context}
        ctx['world_info'] = contents
        return ctx

    def export_character_card(self, card_id: int, format: str = "json") -> Dict[str, Any]:
        """Export a character card with minimal metadata."""
        card = self.get_character_card(card_id) or {}
        export = {'format': format}
        export.update(card)
        return export

    def import_character_card(self, card_data: Dict[str, Any]) -> Optional[int]:
        """Import a character card (supports V3 format)."""
        # V3 format handling
        if isinstance(card_data, dict) and card_data.get('spec') == 'chara_card_v3' and isinstance(card_data.get('data'), dict):
            data = card_data['data']
            mapped = {
                'name': data.get('name'),
                'description': data.get('description'),
                'personality': data.get('personality'),
                'first_message': data.get('first_mes'),
                'message_example': data.get('mes_example'),
                'scenario': data.get('scenario'),
                'creator_notes': data.get('creator_notes'),
                'system_prompt': data.get('system_prompt'),
                'creator': data.get('creator', 'imported'),
                'tags': data.get('tags') or [],
            }
            if not mapped.get('name'):
                raise ValueError("Invalid character card format: missing name")
            return self.create_character_card(**mapped)

        # Generic dict format
        if isinstance(card_data, dict):
            allowed_fields = {
                'name', 'description', 'personality', 'scenario', 'system_prompt',
                'image', 'post_history_instructions', 'first_message', 'message_example',
                'creator_notes', 'alternate_greetings', 'tags', 'creator', 'extensions'
            }
            import_data = {k: v for k, v in card_data.items() if k in allowed_fields}
            if 'creator' not in import_data:
                import_data['creator'] = 'imported'
            if not import_data.get('name'):
                raise ValueError("Invalid character card format: missing name")
            return self.create_character_card(**import_data)

        raise ValueError("Invalid character card format")

    def export_chat_history(self, chat_id: int, format: str = "json") -> Dict[str, Any]:
        """Export chat history."""
        messages = self.get_messages(chat_id)
        chat = self.db.get_chat(chat_id) if hasattr(self.db, 'get_chat') else None
        meta = {'format': format}
        if chat:
            meta.update({'title': chat.get('title'), 'character_id': chat.get('character_id')})
        return {'chat_id': chat_id, 'messages': messages, 'metadata': meta}

    def import_chat_history(self, history_data: Dict[str, Any], user_id: str = None) -> Optional[int]:
        """Import chat history by creating a chat and inserting messages."""
        if not isinstance(history_data, dict):
            return None
        meta = history_data.get('metadata', {})
        character_id = meta.get('character_id')
        title = meta.get('title') or 'Imported Chat'
        if hasattr(self.db, 'create_chat'):
            chat_id = self.db.create_chat(character_id=character_id, user_id=user_id or 'importer', title=title)
        else:
            chat_id = 1
        for m in history_data.get('messages', []) or []:
            role = m.get('role', 'user')
            content = m.get('content', '')
            self.add_message(chat_id, role, content)
        return chat_id

    def validate_character_name(self, name: str) -> bool:
        """Validate a character name."""
        return bool(name and name.strip() and len(name) <= 100)

    def validate_description(self, description: str) -> bool:
        """Validate a description (allow long descriptions)."""
        return isinstance(description, str) and len(description) <= 10000

    def validate_tags(self, tags: List[str]) -> bool:
        """Validate tags (max 20)."""
        if not isinstance(tags, list):
            return False
        if len(tags) > 20:
            return False
        return all(isinstance(tag, str) and 0 < len(tag) <= 50 for tag in tags)

    def chunk_message(self, message: str, chunk_size: int = 1000) -> List[str]:
        """Chunk a long message into smaller parts."""
        if not message:
            return []

        words = message.split()
        chunks = []
        current_chunk = []

        for word in words:
            # Check if adding this word would exceed the chunk size
            if len(current_chunk) + 1 > chunk_size:
                # Save current chunk and start a new one
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [word]
            else:
                current_chunk.append(word)

        # Add the last chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks if chunks else [message]

    def get_character_statistics(self, character_id: int) -> Dict[str, Any]:
        """Get statistics for a character (DB-first)."""
        if hasattr(self.db, 'get_character_statistics'):
            return self.db.get_character_statistics(character_id)
        chats = self.list_chats_for_character(character_id)
        return {'total_chats': len(chats), 'total_messages': sum(c.get('message_count', 0) for c in chats)}

    def get_user_statistics(self, user_name: str = None, user_id: str = None) -> Dict[str, Any]:
        """Get statistics for a user (DB-first)."""
        uid = user_id or user_name
        if hasattr(self.db, 'get_user_statistics'):
            return self.db.get_user_statistics(uid)
        return {'total_chats': 0, 'total_messages': 0}
