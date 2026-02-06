# character_schemas.py
# Description:
#
# Imports
import json
from typing import Any, Optional, Union

#
# Third-party imports
from pydantic import BaseModel, Field, ValidationInfo, field_validator

#
######################################################################################################################
#
# --- Pydantic Schemas ---

# Maximum lengths for character fields to prevent unbounded database growth
MAX_NAME_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 50_000
MAX_PERSONALITY_LENGTH = 50_000
MAX_SCENARIO_LENGTH = 50_000
MAX_SYSTEM_PROMPT_LENGTH = 100_000
MAX_FIRST_MESSAGE_LENGTH = 50_000
MAX_MESSAGE_EXAMPLE_LENGTH = 100_000
MAX_CREATOR_NOTES_LENGTH = 50_000
MAX_CREATOR_LENGTH = 500
MAX_VERSION_LENGTH = 100
MAX_IMAGE_BASE64_LENGTH = 20_000_000  # ~15MB image when decoded


class CharacterBase(BaseModel):
    name: Optional[str] = Field(None, max_length=MAX_NAME_LENGTH)
    description: Optional[str] = Field(None, examples=["A brave knight"], max_length=MAX_DESCRIPTION_LENGTH)
    personality: Optional[str] = Field(None, examples=["Stoic and honorable"], max_length=MAX_PERSONALITY_LENGTH)
    scenario: Optional[str] = Field(None, examples=["Guarding the ancient ruins"], max_length=MAX_SCENARIO_LENGTH)
    system_prompt: Optional[str] = Field(None, examples=["You are a helpful character."], max_length=MAX_SYSTEM_PROMPT_LENGTH)
    post_history_instructions: Optional[str] = Field(None, max_length=MAX_SYSTEM_PROMPT_LENGTH)
    first_message: Optional[str] = Field(None, examples=["Greetings, traveler!"], max_length=MAX_FIRST_MESSAGE_LENGTH)
    message_example: Optional[str] = Field(None, examples=["<START>\nUSER: Hello\nASSISTANT: Hi there!\n<END>"], max_length=MAX_MESSAGE_EXAMPLE_LENGTH)
    creator_notes: Optional[str] = Field(None, max_length=MAX_CREATOR_NOTES_LENGTH)
    alternate_greetings: Optional[Union[list[str], str]] = Field(None,
                                                                 description="List of strings or a JSON string representation of a list.",
                                                                 examples=[["Hello!", "Good day!"]])
    tags: Optional[Union[list[str], str]] = Field(None,
                                                  description="List of strings or a JSON string representation of a list.",
                                                  examples=[["fantasy", "knight"]])
    creator: Optional[str] = Field(None, max_length=MAX_CREATOR_LENGTH)
    character_version: Optional[str] = Field(None, max_length=MAX_VERSION_LENGTH)
    extensions: Optional[Union[dict[str, Any], str]] = Field(None,
                                                             description="Dictionary or a JSON string representation of a dictionary.")
    image_base64: Optional[str] = Field(None,
                                        description="Base64 encoded image string (without 'data:image/...;base64,' prefix).",
                                        max_length=MAX_IMAGE_BASE64_LENGTH)

    @field_validator("alternate_greetings", "tags", "extensions", mode="before")
    @classmethod
    def parse_json_string(cls, value: Any, info: ValidationInfo) -> Any:
        """Parse JSON strings and validate the resulting structure.

        Unlike the previous implementation that silently returned empty values on
        parse failure, this raises a ValueError to prevent invalid data from being
        accepted without the caller's knowledge.

        Empty String Conversion Behavior:
            - Empty or whitespace-only strings are converted to appropriate empty types:
              - alternate_greetings, tags: "" -> []
              - extensions: "" -> {}
            - This is intentional to allow form submissions with empty fields.
            - If you want to explicitly clear a field, pass the appropriate empty
              type ([] or {}) or null/None.

        Raises:
            ValueError: If the string contains invalid JSON or the parsed type
                doesn't match the expected type for the field.
        """
        if value is None:
            return value

        if isinstance(value, str):
            # Empty or whitespace-only string -> convert to appropriate empty type
            # This allows form submissions with empty fields to work correctly.
            # NOTE: This is intentional behavior. Pass [] or {} explicitly if needed.
            if not value.strip():
                if info.field_name in ["alternate_greetings", "tags"]:
                    return []
                if info.field_name == "extensions":
                    return {}
                return value

            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as e:
                # Raise error instead of silently returning empty - caller should know about invalid JSON
                raise ValueError(
                    f"Invalid JSON in field '{info.field_name}': {str(e)[:100]}"
                ) from e

            # Validate the parsed structure matches expected type
            if info.field_name in ["alternate_greetings", "tags"]:
                if not isinstance(parsed, list):
                    raise ValueError(
                        f"Field '{info.field_name}' must be a list, got {type(parsed).__name__}"
                    )
                # Validate list contents are strings
                for i, item in enumerate(parsed):
                    if not isinstance(item, str):
                        raise ValueError(
                            f"Field '{info.field_name}' must contain only strings, "
                            f"item at index {i} is {type(item).__name__}"
                        )
            elif info.field_name == "extensions":
                if not isinstance(parsed, dict):
                    raise ValueError(
                        f"Field 'extensions' must be a dictionary, got {type(parsed).__name__}"
                    )

            return parsed

        # If already the correct type, validate it
        if info.field_name in ["alternate_greetings", "tags"]:
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if not isinstance(item, str):
                        raise ValueError(
                            f"Field '{info.field_name}' must contain only strings, "
                            f"item at index {i} is {type(item).__name__}"
                        )
        elif info.field_name == "extensions" and not isinstance(value, dict):
            raise ValueError(
                f"Field 'extensions' must be a dictionary, got {type(value).__name__}"
            )

        return value


class CharacterCreate(CharacterBase):
    name: str = Field(..., examples=["Sir Gideon"], min_length=1, max_length=MAX_NAME_LENGTH)


class CharacterUpdate(CharacterBase):
    pass  # All fields optional


class CharacterResponse(CharacterBase):
    id: int
    version: int
    image_present: bool = False
    model_config = {"from_attributes": True}


class CharacterImportResponse(BaseModel):
    id: int = Field(..., description="ID of the imported character")
    name: str = Field(..., description="Name of the imported character")
    message: str = Field(..., description="Import status message")
    character: Optional[CharacterResponse] = Field(
        default=None,
        description="Full character details when available"
    )


class DeletionResponse(BaseModel):
    message: str
    character_id: int

#
# End of character_schemas.py
######################################################################################################################
