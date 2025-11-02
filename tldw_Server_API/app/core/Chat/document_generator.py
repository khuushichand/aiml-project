# document_generator.py
# Description: Service for generating different document types from chat conversations with multi-user support
# Adapted from single-user to multi-user architecture with per-user isolation
#
"""
Document Generator Service for Multi-User Environment
-----------------------------------------------------

Provides functionality to generate various document types from chat conversations:
- Timeline documents
- Study guides
- Briefing documents
- Summary documents
- Q&A documents
- Meeting notes

Key Adaptations from Single-User:
- Per-user conversation isolation
- Stateless service instances (no global state)
- Request-scoped processing (instantiated per API request)
- User-specific configurations and quotas
- Background job support for long generations
"""

import base64
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum

from loguru import logger

# Local imports
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    InputError
)
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAPIError
from tldw_Server_API.app.core.Chat.chat_orchestrator import chat_api_call


class DocumentType(Enum):
    """Enumeration of supported document types."""
    TIMELINE = "timeline"
    STUDY_GUIDE = "study_guide"
    BRIEFING = "briefing"
    SUMMARY = "summary"
    QA = "q_and_a"
    MEETING_NOTES = "meeting_notes"


class GenerationStatus(Enum):
    """Status of document generation job."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentGeneratorService:
    """
    Service class for generating documents from conversations in a multi-user environment.

    This is a request-scoped service that is instantiated per API request.
    It works with the per-user database model where each user has their own
    separate conversation history.
    """

    # Default prompt configurations (can be overridden per user)
    DEFAULT_PROMPTS = {
        DocumentType.TIMELINE: {
            "system": "You are an expert at creating clear, chronological timelines from conversations and content.",
            "user": "Create a detailed text-based timeline based on the following conversation/materials:",
            "temperature": 0.3,
            "max_tokens": 2000
        },
        DocumentType.STUDY_GUIDE: {
            "system": "You are an educational expert specializing in creating comprehensive study guides.",
            "user": "Create a detailed and well-produced study guide based on the following conversation/materials:",
            "temperature": 0.5,
            "max_tokens": 3000
        },
        DocumentType.BRIEFING: {
            "system": "You are an expert at creating executive briefing documents with actionable insights.",
            "user": "Create a detailed and well-produced executive briefing document regarding the following conversation:",
            "temperature": 0.4,
            "max_tokens": 2500
        },
        DocumentType.SUMMARY: {
            "system": "You are an expert at creating concise, informative summaries.",
            "user": "Create a comprehensive summary of the following conversation, highlighting key points and conclusions:",
            "temperature": 0.3,
            "max_tokens": 1500
        },
        DocumentType.QA: {
            "system": "You are an expert at extracting questions and answers from conversations.",
            "user": "Extract all questions and their corresponding answers from the following conversation, formatting them clearly:",
            "temperature": 0.2,
            "max_tokens": 2000
        },
        DocumentType.MEETING_NOTES: {
            "system": "You are an expert at creating professional meeting notes and action items.",
            "user": "Create professional meeting notes from the following conversation, including action items, decisions, and key discussion points:",
            "temperature": 0.3,
            "max_tokens": 2000
        }
    }

    def __init__(self, db: CharactersRAGDB, user_id: Optional[str] = None):
        """
        Initialize the service with a user-specific database connection.

        Args:
            db: User-specific database instance from dependency injection
            user_id: Optional user identifier for logging and tracking
        """
        self.db = db
        # Load external overrides from Prompts/chat if available
        try:
            from tldw_Server_API.app.core.Utils.prompt_loader import load_prompt  # local import to avoid cycles
            overrides = {
                DocumentType.TIMELINE: (load_prompt("chat", "timeline_system"), load_prompt("chat", "timeline_user")),
                DocumentType.STUDY_GUIDE: (load_prompt("chat", "study_guide_system"), load_prompt("chat", "study_guide_user")),
                DocumentType.BRIEFING: (load_prompt("chat", "briefing_system"), load_prompt("chat", "briefing_user")),
                DocumentType.SUMMARY: (load_prompt("chat", "summary_system"), load_prompt("chat", "summary_user")),
                DocumentType.QA: (load_prompt("chat", "qa_system"), load_prompt("chat", "qa_user")),
                DocumentType.MEETING_NOTES: (load_prompt("chat", "meeting_notes_system"), load_prompt("chat", "meeting_notes_user")),
            }
            for dtype, (sys_p, usr_p) in overrides.items():
                if sys_p and isinstance(sys_p, str):
                    self.DEFAULT_PROMPTS[dtype]["system"] = sys_p
                if usr_p and isinstance(usr_p, str):
                    self.DEFAULT_PROMPTS[dtype]["user"] = usr_p
        except Exception:
            pass
        self.user_id = user_id or "unknown"
        self._init_tables()

        # Request-scoped cache for prompts
        self._prompt_cache: Dict[DocumentType, Dict[str, Any]] = {}

        # No longer need provider mapping - using chat_api_call abstraction
    @staticmethod
    def _normalize_conversation_id(conversation_id: Optional[Union[str, int]]) -> Optional[str]:
        """Normalize conversation identifiers provided by API/legacy callers."""
        if conversation_id is None:
            return None
        if isinstance(conversation_id, str):
            cleaned = conversation_id.strip()
            return cleaned or None
        try:
            numeric = int(conversation_id)
        except (TypeError, ValueError):
            return None
        if numeric <= 0:
            return None
        return str(numeric)

    def _init_tables(self):
        """Initialize document generation tables in the user's database if they don't exist."""
        try:
            with self.db.get_connection() as conn:
                # Create generation_jobs table for tracking async jobs
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS generation_jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL UNIQUE,
                        conversation_id TEXT,
                        document_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        provider TEXT,
                        model TEXT,
                        prompt_config TEXT,
                        result_content TEXT,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        metadata TEXT DEFAULT '{}'
                    )
                """)

                # Create user_prompts table for custom prompts
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_prompts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_type TEXT NOT NULL,
                        system_prompt TEXT NOT NULL,
                        user_prompt TEXT NOT NULL,
                        temperature REAL DEFAULT 0.7,
                        max_tokens INTEGER DEFAULT 2000,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(document_type, is_active)
                    )
                """)

                # Create generated_documents table for storing results
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS generated_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT,
                        document_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        generation_time_ms INTEGER,
                        token_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}'
                    )
                """)

                # Create indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gen_jobs_status ON generation_jobs(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gen_jobs_job_id ON generation_jobs(job_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gen_docs_conv_id ON generated_documents(conversation_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gen_docs_type ON generated_documents(document_type)")

                conn.commit()
                logger.info("Document generator tables initialized")
        except Exception as e:
            logger.error(f"Failed to initialize document generator tables: {e}")
            raise CharactersRAGDBError(f"Failed to initialize document generator tables: {e}")

    def get_conversation_context(
        self,
        conversation_id: str,
        limit: int = 50,
        include_system: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get conversation context including recent messages.

        Args:
            conversation_id: ID of the conversation (UUID string)
            limit: Maximum number of messages to include
            include_system: Whether to include system messages

        Returns:
            List of message dictionaries suitable for prompt construction.
        """
        try:
            raw_history = self.db.get_messages_for_conversation(
                conversation_id,
                limit,
                0,
                "DESC",
            )
            raw_history = list(reversed(raw_history))
        except Exception as exc:
            logger.error(f"Failed to get conversation context: {exc}")
            return []

        messages: List[Dict[str, Any]] = []
        for db_msg in raw_history:
            sender = (db_msg.get("sender") or "").strip().lower()
            if sender == "system" and not include_system:
                continue
            if sender == "system":
                role = "system"
            elif sender == "user":
                role = "user"
            else:
                role = "assistant"

            msg_parts: List[Dict[str, Any]] = []

            text_content = db_msg.get("content") or ""
            if text_content:
                msg_parts.append({"type": "text", "text": text_content})

            raw_images = db_msg.get("images") or []
            if (not raw_images) and db_msg.get("image_data") and db_msg.get("image_mime_type"):
                raw_images = [{
                    "position": 0,
                    "image_data": db_msg.get("image_data"),
                    "image_mime_type": db_msg.get("image_mime_type"),
                }]

            for image_entry in raw_images:
                try:
                    img_bytes = image_entry.get("image_data")
                    if isinstance(img_bytes, memoryview):
                        img_bytes = img_bytes.tobytes()
                    if not img_bytes:
                        continue
                    img_mime = (
                        image_entry.get("image_mime_type")
                        or db_msg.get("image_mime_type")
                        or "image/png"
                    )
                    b64_img = base64.b64encode(img_bytes).decode("utf-8")
                    msg_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{img_mime};base64,{b64_img}"},
                    })
                except Exception as img_err:
                    logger.warning(
                        "Error encoding image from history (msg_id %s): %s",
                        db_msg.get("id"),
                        img_err,
                    )

            if not msg_parts:
                continue

            message_entry: Dict[str, Any] = {"role": role}
            if len(msg_parts) == 1 and msg_parts[0].get("type") == "text":
                message_entry["content"] = msg_parts[0].get("text", "")
            else:
                message_entry["content"] = msg_parts

            if role == "assistant":
                sender_name = (db_msg.get("sender") or "Assistant")
                safe_name = (
                    sender_name.replace(" ", "_")
                    .replace("<", "")
                    .replace(">", "")
                    .replace("|", "")
                    .replace("\\", "")
                    .replace("/", "")
                )
                if safe_name and safe_name.lower() not in {"user", "system"}:
                    message_entry["name"] = safe_name

            messages.append(message_entry)

        return messages

    def format_context_for_llm(
        self,
        messages: List[Dict[str, Any]],
        specific_message: Optional[str] = None,
        max_context_length: int = 8000
    ) -> str:
        """
        Format conversation context for LLM processing.

        Args:
            messages: List of message dictionaries
            specific_message: Optional specific message to highlight
            max_context_length: Maximum context length in characters

        Returns:
            Formatted context string
        """
        context_parts = []

        # Add conversation history
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', '')

            # Format timestamp if present
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logger.debug(f"Timestamp parse failed in chat context: value={timestamp}, error={e}")

            context_parts.append(f"[{timestamp}] {role.upper()}: {content}")

        # Add specific message if provided
        if specific_message:
            context_parts.append("\n--- SPECIFIC MESSAGE TO FOCUS ON ---")
            context_parts.append(specific_message)
            context_parts.append("--- END SPECIFIC MESSAGE ---\n")

        # Join and truncate if necessary
        context = "\n".join(context_parts)
        if len(context) > max_context_length:
            # Truncate from the beginning, keeping recent messages
            context = "...[truncated]\n" + context[-max_context_length:]

        return context

    def get_user_prompt_config(self, document_type: DocumentType) -> Dict[str, Any]:
        """
        Get user-specific prompt configuration or default.

        Args:
            document_type: Type of document to generate

        Returns:
            Prompt configuration dictionary
        """
        # Check cache first
        if document_type in self._prompt_cache:
            return self._prompt_cache[document_type]

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT system_prompt, user_prompt, temperature, max_tokens
                    FROM user_prompts
                    WHERE document_type = ? AND is_active = 1
                    """,
                    (document_type.value,)
                )
                row = cursor.fetchone()

                if row:
                    config = {
                        "system": row[0],
                        "user": row[1],
                        "temperature": row[2],
                        "max_tokens": row[3]
                    }
                    self._prompt_cache[document_type] = config
                    return config

        except Exception as e:
            logger.warning(f"Failed to get user prompt config: {e}")

        # Return default
        default_config = self.DEFAULT_PROMPTS.get(document_type, self.DEFAULT_PROMPTS[DocumentType.SUMMARY])
        self._prompt_cache[document_type] = default_config
        return default_config

    def save_user_prompt_config(
        self,
        document_type: DocumentType,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> bool:
        """
        Save user-specific prompt configuration.

        Args:
            document_type: Type of document
            system_prompt: System prompt
            user_prompt: User prompt template
            temperature: Generation temperature
            max_tokens: Maximum tokens

        Returns:
            True if saved successfully
        """
        try:
            with self.db.get_connection() as conn:
                # Deactivate existing active prompt
                conn.execute(
                    "UPDATE user_prompts SET is_active = 0 WHERE document_type = ? AND is_active = 1",
                    (document_type.value,)
                )

                # Insert new prompt
                conn.execute(
                    """
                    INSERT INTO user_prompts
                    (document_type, system_prompt, user_prompt, temperature, max_tokens, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (document_type.value, system_prompt, user_prompt, temperature, max_tokens)
                )
                conn.commit()

                # Clear cache
                if document_type in self._prompt_cache:
                    del self._prompt_cache[document_type]

                logger.info(f"Saved user prompt config for {document_type.value}")
                return True

        except Exception as e:
            logger.error(f"Failed to save user prompt config: {e}")
            return False

    def generate_document(
        self,
        conversation_id: Union[str, int],
        document_type: DocumentType,
        provider: str,
        model: str,
        api_key: str,
        specific_message: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        stream: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate a document from conversation.

        Args:
            conversation_id: ID of the conversation
            document_type: Type of document to generate
            provider: LLM provider name
            model: Model name
            api_key: API key for the provider
            specific_message: Optional specific message to focus on
            custom_prompt: Optional custom prompt override
            stream: Whether to stream the response

        Returns:
            Generated document content or job info for async generation
        """
        start_time = time.time()
        normalized_conversation_id = self._normalize_conversation_id(conversation_id)
        if not normalized_conversation_id:
            logger.warning("Invalid conversation identifier provided: %s", conversation_id)
            return {
                "success": False,
                "error": "Invalid conversation identifier",
                "document_type": document_type.value,
                "conversation_id": conversation_id,
            }

        logger.info(
            "Generating %s for conversation %s (user: %s)",
            document_type.value,
            normalized_conversation_id,
            self.user_id,
        )

        # Get conversation context
        try:
            messages = self.get_conversation_context(normalized_conversation_id)
            if not messages:
                logger.warning("No messages found for conversation %s", normalized_conversation_id)
                return {
                    "success": False,
                    "error": f"No messages found for conversation {conversation_id}",
                    "document_type": document_type.value,
                    "conversation_id": conversation_id
                }
        except Exception as e:
            logger.error(f"Error retrieving conversation: {e}")
            return {
                "success": False,
                "error": f"Error retrieving conversation: {str(e)}",
                "document_type": document_type.value,
                "conversation_id": conversation_id
            }

        context = self.format_context_for_llm(messages, specific_message)

        # Get prompt configuration
        prompt_config = self.get_user_prompt_config(document_type)

        # Build prompts
        system_prompt = prompt_config["system"]
        if custom_prompt:
            user_prompt = f"{custom_prompt}\n\nConversation Context:\n{context}"
        else:
            user_prompt = f"{prompt_config['user']}\n\nConversation Context:\n{context}"

        # Call LLM
        try:
            result = self._call_llm(
                provider=provider,
                model=model,
                api_key=api_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=prompt_config.get('temperature', 0.7),
                max_tokens=prompt_config.get('max_tokens', 2000),
                stream=stream
            )

            if not stream:
                # Save the generated document
                generation_time_ms = int((time.time() - start_time) * 1000)
                self._save_generated_document(
                    conversation_id=normalized_conversation_id,
                    document_type=document_type,
                    title=f"{document_type.value.replace('_', ' ').title()} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    content=result,
                    provider=provider,
                    model=model,
                    generation_time_ms=generation_time_ms
                )

                logger.info(f"Generated {document_type.value} in {generation_time_ms}ms")

            return result

        except Exception as e:
            logger.error(f"Failed to generate {document_type.value}: {e}")
            raise ChatAPIError(f"Failed to generate document: {str(e)}")

    def _call_llm(
        self,
        provider: str,
        model: str,
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> Union[str, Any]:
        """
        Call the appropriate LLM provider using the chat abstraction layer.

        Args:
            provider: Provider name
            model: Model name
            api_key: API key
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Generation temperature
            max_tokens: Maximum tokens
            stream: Whether to stream

        Returns:
            Generated content or stream generator
        """
        # Prepare messages in OpenAI format
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Use the chat_api_call abstraction layer
        response = chat_api_call(
            api_endpoint=provider.lower(),
            messages_payload=messages,
            api_key=api_key,
            model=model,
            temp=temperature,
            max_tokens=max_tokens,
            streaming=stream,
            system_message=system_prompt
        )

        return response

    def _save_generated_document(
        self,
        conversation_id: Optional[Union[str, int]],
        document_type: DocumentType,
        title: str,
        content: str,
        provider: str,
        model: str,
        generation_time_ms: int,
        token_count: Optional[int] = None
    ) -> int:
        """
        Save a generated document to the database.

        Args:
            conversation_id: Conversation ID
            document_type: Type of document
            title: Document title
            content: Document content
            provider: LLM provider used
            model: Model used
            generation_time_ms: Generation time in milliseconds
            token_count: Optional token count

        Returns:
            Document ID
        """
        normalized_conversation_id = self._normalize_conversation_id(conversation_id)

        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO generated_documents
                    (conversation_id, document_type, title, content, provider, model,
                     generation_time_ms, token_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (normalized_conversation_id, document_type.value, title, content, provider,
                     model, generation_time_ms, token_count)
                )
                document_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Saved generated document {document_id}")
                return document_id

        except Exception as e:
            logger.error(f"Failed to save generated document: {e}")
            raise CharactersRAGDBError(f"Failed to save document: {e}")

    def record_streamed_document(
        self,
        *,
        conversation_id: Optional[Union[str, int]],
        document_type: DocumentType,
        content: str,
        provider: str,
        model: str,
        generation_time_ms: int,
        token_count: Optional[int] = None
    ) -> Optional[int]:
        """
        Persist the result of a streamed document generation once all chunks are received.

        Args:
            conversation_id: Conversation ID associated with the document
            document_type: Type of the generated document
            content: Concatenated document content collected during streaming
            provider: Provider that produced the document
            model: Model name
            generation_time_ms: Total generation time in milliseconds
            token_count: Optional token count metadata

        Returns:
            Generated document ID if persisted, otherwise None.
        """
        if not content or not content.strip():
            logger.info("Skipping persistence for streamed document with empty content (conversation_id=%s)", conversation_id)
            return None

        try:
            document_id = self._save_generated_document(
                conversation_id=conversation_id,
                document_type=document_type,
                title=f"{document_type.value.replace('_', ' ').title()} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                content=content,
                provider=provider,
                model=model,
                generation_time_ms=generation_time_ms,
                token_count=token_count
            )
            return document_id
        except Exception as exc:
            logger.error(
                "Failed to persist streamed document for conversation %s: %s",
                conversation_id,
                exc
            )
            return None

    def create_manual_document(
        self,
        *,
        title: str,
        content: str,
        document_type: DocumentType = DocumentType.BRIEFING,
        metadata: Optional[Dict[str, Any]] = None,
        provider: str = "watchlists",
        model: str = "watchlists",
        conversation_id: Optional[Union[str, int]] = None,
        token_count: Optional[int] = None,
    ) -> int:
        """
        Persist an externally generated document (e.g., watchlist output) into the user's Chatbook DB.
        """
        doc_id = self._save_generated_document(
            conversation_id,
            document_type,
            title,
            content,
            provider,
            model,
            generation_time_ms=0,
            token_count=token_count,
        )
        if metadata:
            try:
                with self.db.get_connection() as conn:
                    conn.execute(
                        "UPDATE generated_documents SET metadata = ? WHERE id = ?",
                        (json.dumps(metadata), doc_id),
                    )
                    conn.commit()
            except Exception as exc:
                logger.warning(f"Failed to store metadata for generated document {doc_id}: {exc}")
        return doc_id

    def get_generated_documents(
        self,
        conversation_id: Optional[Union[str, int]] = None,
        document_type: Optional[DocumentType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get previously generated documents.

        Args:
            conversation_id: Optional conversation ID filter
            document_type: Optional document type filter
            limit: Maximum number of documents to return

        Returns:
            List of document dictionaries
        """
        try:
            with self.db.get_connection() as conn:
                query = "SELECT * FROM generated_documents WHERE 1=1"
                params = []

                normalized_conversation_id = self._normalize_conversation_id(conversation_id)
                if normalized_conversation_id:
                    query += " AND conversation_id = ?"
                    params.append(normalized_conversation_id)

                if document_type:
                    query += " AND document_type = ?"
                    params.append(document_type.value)

                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, params)
                documents = []

                for row in cursor.fetchall():
                    conv_id = row[1]
                    conv_id_str = str(conv_id) if conv_id is not None else ""
                    documents.append({
                        'id': row[0],
                        'conversation_id': conv_id_str,
                        'document_type': row[2],
                        'title': row[3],
                        'content': row[4],
                        'provider': row[5],
                        'model': row[6],
                        'generation_time_ms': row[7],
                        'token_count': row[8],
                        'created_at': row[9],
                        'metadata': json.loads(row[10]) if row[10] else {}
                    })

                return documents

        except Exception as e:
            logger.error(f"Failed to get generated documents: {e}")
            return []

    def get_generated_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single generated document by its identifier.

        Args:
            document_id: Document ID

        Returns:
            Document dictionary if found, otherwise None
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM generated_documents WHERE id = ?",
                    (document_id,)
                )
                row = cursor.fetchone()

                if not row:
                    return None

                conv_id = row[1]
                conv_id_str = str(conv_id) if conv_id is not None else ""
                return {
                    'id': row[0],
                    'conversation_id': conv_id_str,
                    'document_type': row[2],
                    'title': row[3],
                    'content': row[4],
                    'provider': row[5],
                    'model': row[6],
                    'generation_time_ms': row[7],
                    'token_count': row[8],
                    'created_at': row[9],
                    'metadata': json.loads(row[10]) if row[10] else {}
                }
        except Exception as e:
            logger.error(f"Failed to get generated document {document_id}: {e}")
            return None

    def delete_generated_document(self, document_id: int) -> bool:
        """
        Delete a generated document.

        Args:
            document_id: Document ID

        Returns:
            True if deleted successfully
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM generated_documents WHERE id = ?",
                    (document_id,)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Deleted generated document {document_id}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to delete generated document: {e}")
            return False

    # --- Job Management for Async Generation ---

    def create_generation_job(
        self,
        conversation_id: Union[str, int],
        document_type: DocumentType,
        provider: str,
        model: str,
        prompt_config: Dict[str, Any]
    ) -> str:
        """
        Create a job for async document generation.

        Args:
            conversation_id: Conversation ID
            document_type: Type of document
            provider: LLM provider
            model: Model name
            prompt_config: Prompt configuration

        Returns:
            Job ID
        """
        import uuid
        job_id = str(uuid.uuid4())
        normalized_conversation_id = self._normalize_conversation_id(conversation_id)

        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO generation_jobs
                    (job_id, conversation_id, document_type, status, provider, model, prompt_config)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (job_id, normalized_conversation_id, document_type.value, GenerationStatus.PENDING.value,
                     provider, model, json.dumps(prompt_config))
                )
                conn.commit()

                logger.info(f"Created generation job {job_id}")
                return job_id

        except Exception as e:
            logger.error(f"Failed to create generation job: {e}")
            raise CharactersRAGDBError(f"Failed to create job: {e}")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a generation job.

        Args:
            job_id: Job ID

        Returns:
            Job status dictionary or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT job_id, conversation_id, document_type, status, provider, model,
                           result_content, error_message, created_at, started_at, completed_at
                    FROM generation_jobs
                    WHERE job_id = ?
                    """,
                    (job_id,)
                )
                row = cursor.fetchone()

                if row:
                    conv_id = row[1]
                    conv_id_str = str(conv_id) if conv_id is not None else ""
                    return {
                        'job_id': row[0],
                        'conversation_id': conv_id_str,
                        'document_type': row[2],
                        'status': row[3],
                        'provider': row[4],
                        'model': row[5],
                        'result_content': row[6],
                        'error_message': row[7],
                        'created_at': row[8],
                        'started_at': row[9],
                        'completed_at': row[10]
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None

    def update_job_status(
        self,
        job_id: str,
        status: GenerationStatus,
        result_content: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update the status of a generation job.

        Args:
            job_id: Job ID
            status: New status
            result_content: Optional result content
            error_message: Optional error message

        Returns:
            True if updated successfully
        """
        try:
            with self.db.get_connection() as conn:
                updates = ["status = ?"]
                params = [status.value]

                if status == GenerationStatus.IN_PROGRESS:
                    updates.append("started_at = CURRENT_TIMESTAMP")
                elif status in [GenerationStatus.COMPLETED, GenerationStatus.FAILED, GenerationStatus.CANCELLED]:
                    updates.append("completed_at = CURRENT_TIMESTAMP")

                if result_content:
                    updates.append("result_content = ?")
                    params.append(result_content)

                if error_message:
                    updates.append("error_message = ?")
                    params.append(error_message)

                params.append(job_id)

                cursor = conn.execute(
                    f"UPDATE generation_jobs SET {', '.join(updates)} WHERE job_id = ?",
                    params
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Updated job {job_id} status to {status.value}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a generation job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    UPDATE generation_jobs
                    SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP
                    WHERE job_id = ? AND status IN ('pending', 'in_progress')
                    """,
                    (job_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error cancelling job: {e}")
            return False

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a generated document.

        Args:
            document_id: Document ID

        Returns:
            Document data or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM generated_documents WHERE id = ?",
                    (document_id,)
                )
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    # Parse metadata if it's JSON
                    if result.get('metadata'):
                        try:
                            result['metadata'] = json.loads(result['metadata'])
                        except Exception as e:
                            logger.debug(f"Failed to parse document metadata JSON: id={document_id}, error={e}")
                    return result
                return None

        except Exception as e:
            logger.error(f"Error getting document: {e}")
            return None

    def list_documents(
        self,
        conversation_id: Optional[str] = None,
        document_type: Optional[DocumentType] = None
    ) -> List[Dict[str, Any]]:
        """
        List generated documents.

        Args:
            conversation_id: Optional conversation filter
            document_type: Optional type filter

        Returns:
            List of document summaries
        """
        try:
            with self.db.get_connection() as conn:
                query = "SELECT * FROM generated_documents WHERE 1=1"
                params = []

                if conversation_id:
                    query += " AND conversation_id = ?"
                    params.append(conversation_id)

                if document_type:
                    query += " AND document_type = ?"
                    params.append(document_type.value if isinstance(document_type, DocumentType) else document_type)

                query += " ORDER BY created_at DESC"

                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a generated document.

        Args:
            document_id: Document ID

        Returns:
            True if deleted successfully
        """
        return self.delete_generated_document(document_id)

    def save_prompt_config(self, config: Dict[DocumentType, str]) -> bool:
        """
        Save custom prompt configuration.

        Args:
            config: Dictionary mapping document types to custom prompts

        Returns:
            True if saved successfully
        """
        try:
            with self.db.get_connection() as conn:
                for doc_type, prompt in config.items():
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO user_prompt_configs
                        (user_id, document_type, custom_prompt, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (self.user_id, doc_type.value, prompt)
                    )
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving prompt config: {e}")
            return False

    def get_prompt_config(self, document_type: DocumentType) -> Optional[str]:
        """
        Get custom prompt configuration for a document type.

        Args:
            document_type: Document type

        Returns:
            Custom prompt or None if not configured
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT custom_prompt FROM user_prompt_configs
                    WHERE user_id = ? AND document_type = ?
                    """,
                    (self.user_id, document_type.value)
                )
                row = cursor.fetchone()
                if row:
                    return row['custom_prompt']
                return None

        except Exception as e:
            logger.error(f"Error getting prompt config: {e}")
            return None

    async def bulk_generate(
        self,
        conversation_id: str,
        document_types: List[DocumentType]
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple document types at once.

        Args:
            conversation_id: Conversation ID
            document_types: List of document types to generate

        Returns:
            List of generation results
        """
        results = []
        for doc_type in document_types:
            result = self.generate_document(
                conversation_id,
                doc_type,
                self.llm_config['provider'],
                self.llm_config['model']
            )
            results.append(result)
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get document generation statistics.

        Returns:
            Statistics dictionary
        """
        try:
            with self.db.get_connection() as conn:
                # Get total documents
                cursor = conn.execute(
                    "SELECT COUNT(*) as total_documents FROM generated_documents"
                )
                total_docs = cursor.fetchone()['total_documents']

                # Get documents by type
                cursor = conn.execute(
                    """
                    SELECT document_type, COUNT(*) as count
                    FROM generated_documents
                    GROUP BY document_type
                    """
                )
                docs_by_type = {row['document_type']: row['count'] for row in cursor.fetchall()}

                # Get job statistics
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_jobs,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_jobs
                    FROM generation_jobs
                    """
                )
                job_stats = dict(cursor.fetchone())

                success_rate = 0
                if job_stats['total_jobs'] > 0:
                    success_rate = job_stats['completed_jobs'] / job_stats['total_jobs']

                return {
                    "total_documents": total_docs,
                    "documents_by_type": docs_by_type,
                    "total_jobs": job_stats['total_jobs'],
                    "completed_jobs": job_stats['completed_jobs'],
                    "failed_jobs": job_stats['failed_jobs'],
                    "success_rate": success_rate
                }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "total_documents": 0,
                "documents_by_type": {},
                "total_jobs": 0,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "success_rate": 0
            }


# Export main classes
__all__ = [
    'DocumentGeneratorService',
    'DocumentType',
    'GenerationStatus'
]
