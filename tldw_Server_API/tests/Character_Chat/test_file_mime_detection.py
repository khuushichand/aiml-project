# test_file_mime_detection.py
"""
Tests for file MIME type detection and validation in characters_endpoint.py.

These tests verify that the security functions correctly identify file types
based on magic bytes rather than trusting file extensions.
"""
import pytest

from tldw_Server_API.app.api.v1.endpoints.characters_endpoint import (
    _detect_mime_type,
    _validate_file_type,
    MAX_CHARACTER_FILE_SIZE,
    ALLOWED_EXTENSIONS,
)


class TestDetectMimeType:
    """Tests for the _detect_mime_type function."""

    # --- PNG Tests ---
    def test_valid_png_signature(self):
             """PNG files should be detected by their 8-byte signature."""
        # Real PNG header: 89 50 4E 47 0D 0A 1A 0A
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # PNG signature + padding
        assert _detect_mime_type(png_data) == 'image/png'

    def test_png_with_real_ihdr(self):

             """PNG with IHDR chunk should still be detected."""
        # PNG signature + IHDR chunk header (simplified)
        png_data = (
            b'\x89PNG\r\n\x1a\n'  # PNG signature
            b'\x00\x00\x00\rIHDR'  # IHDR chunk
            b'\x00\x00\x00\x10'    # Width: 16
            b'\x00\x00\x00\x10'    # Height: 16
            b'\x08\x06\x00\x00\x00'  # Bit depth, color type, etc.
        )
        assert _detect_mime_type(png_data) == 'image/png'

    # --- WebP Tests ---
    def test_valid_webp_signature(self):
             """WebP files should be detected by RIFF....WEBP signature."""
        # WebP format: RIFF + size (4 bytes) + WEBP
        webp_data = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 100
        assert _detect_mime_type(webp_data) == 'image/webp'

    def test_riff_without_webp_not_detected_as_webp(self):

             """RIFF files that aren't WebP (e.g., WAV, AVI) should not be detected as WebP."""
        # WAV file: RIFF + size + WAVE
        wav_data = b'RIFF' + b'\x00\x00\x00\x00' + b'WAVE' + b'\x00' * 100
        # Should return None or not 'image/webp'
        result = _detect_mime_type(wav_data)
        assert result != 'image/webp'

    # --- JPEG Tests ---
    def test_valid_jpeg_signature(self):
             """JPEG files should be detected by their FF D8 signature."""
        # JPEG starts with FF D8 FF
        jpeg_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        assert _detect_mime_type(jpeg_data) == 'image/jpeg'

    def test_jpeg_jfif_variant(self):

             """JPEG JFIF variant should be detected."""
        # JFIF marker: FF D8 FF E0 + size + JFIF
        jfif_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00' + b'\x00' * 100
        assert _detect_mime_type(jfif_data) == 'image/jpeg'

    def test_jpeg_exif_variant(self):

             """JPEG EXIF variant should be detected."""
        # EXIF marker: FF D8 FF E1 + size + Exif
        exif_data = b'\xff\xd8\xff\xe1\x00\x10Exif\x00\x00' + b'\x00' * 100
        assert _detect_mime_type(exif_data) == 'image/jpeg'

    # --- JSON Tests ---
    def test_json_object(self):
             """JSON object starting with { should be detected."""
        json_data = b'{"name": "test", "value": 123}'
        assert _detect_mime_type(json_data) == 'application/json'

    def test_json_array(self):

             """JSON array starting with [ should be detected."""
        json_data = b'["item1", "item2", "item3"]'
        assert _detect_mime_type(json_data) == 'application/json'

    def test_json_with_leading_whitespace(self):

             """JSON with leading whitespace should be detected."""
        json_data = b'  \n\t  {"name": "test"}'
        assert _detect_mime_type(json_data) == 'application/json'

    def test_json_with_bom(self):

             """JSON with UTF-8 BOM should be detected."""
        # UTF-8 BOM: EF BB BF
        json_data = b'\xef\xbb\xbf{"name": "test"}'
        assert _detect_mime_type(json_data) == 'application/json'

    # --- Text Tests ---
    def test_plain_text(self):
             """Plain text files should be detected as text/plain."""
        text_data = b'This is a plain text file with normal content.\nLine 2 here.'
        assert _detect_mime_type(text_data) == 'text/plain'

    def test_yaml_as_text(self):

             """YAML content should be detected as text/plain."""
        yaml_data = b'name: test\nvalue: 123\nitems:\n  - one\n  - two'
        assert _detect_mime_type(yaml_data) == 'text/plain'

    def test_markdown_as_text(self):

             """Markdown content should be detected as text/plain."""
        md_data = b'# Header\n\nThis is **bold** and *italic* text.'
        assert _detect_mime_type(md_data) == 'text/plain'

    # --- Edge Cases ---
    def test_empty_data(self):
             """Empty data should return None."""
        assert _detect_mime_type(b'') is None

    def test_data_too_short(self):

             """Data shorter than 12 bytes should return None."""
        assert _detect_mime_type(b'12345678901') is None  # 11 bytes
        assert _detect_mime_type(b'1234567890') is None   # 10 bytes
        assert _detect_mime_type(b'12345') is None        # 5 bytes

    def test_exactly_12_bytes_minimum(self):

             """Data of exactly 12 bytes should be processed."""
        # 12 bytes of printable text
        text_data = b'Hello World!'
        result = _detect_mime_type(text_data)
        assert result == 'text/plain'

    def test_unknown_binary_data(self):

             """Unknown binary data should return None (if not decodable as UTF-8)."""
        # Use high bytes that can't be valid UTF-8 sequences
        binary_data = b'\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b' + b'\xff' * 100
        assert _detect_mime_type(binary_data) is None

    def test_corrupted_png_signature(self):

             """Corrupted PNG signature should not match PNG."""
        # Almost PNG but wrong bytes
        corrupted = b'\x89PnG\r\n\x1a\n' + b'\x00' * 100  # lowercase 'n'
        result = _detect_mime_type(corrupted)
        assert result != 'image/png'

    def test_executable_not_detected_as_image(self):

             """ELF/PE executables should not be detected as images."""
        # ELF signature
        elf_data = b'\x7fELF' + b'\x00' * 100
        result = _detect_mime_type(elf_data)
        assert result not in ('image/png', 'image/webp', 'image/jpeg')


class TestValidateFileType:
    """Tests for the _validate_file_type function."""

    # --- Valid Cases ---
    def test_valid_png_with_png_extension(self):
             """PNG file with .png extension should be valid."""
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(png_data, "character.png")
        assert is_valid is True
        assert error == ""
        assert file_type == "image"

    def test_valid_webp_with_webp_extension(self):

             """WebP file with .webp extension should be valid."""
        webp_data = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(webp_data, "character.webp")
        assert is_valid is True
        assert error == ""
        assert file_type == "image"

    def test_valid_json_with_json_extension(self):

             """JSON file with .json extension should be valid."""
        json_data = b'{"name": "Test Character", "description": "A test"}'
        is_valid, error, file_type = _validate_file_type(json_data, "character.json")
        assert is_valid is True
        assert error == ""
        assert file_type == "json"

    def test_valid_yaml_with_yaml_extension(self):

             """YAML file with .yaml extension should be valid."""
        yaml_data = b'name: Test Character\ndescription: A test'
        is_valid, error, file_type = _validate_file_type(yaml_data, "character.yaml")
        assert is_valid is True
        assert error == ""
        assert file_type == "yaml"

    def test_valid_yml_extension(self):

             """YAML file with .yml extension should be valid."""
        yaml_data = b'name: Test\nvalue: 123'
        is_valid, error, file_type = _validate_file_type(yaml_data, "config.yml")
        assert is_valid is True
        assert error == ""
        assert file_type == "yaml"

    def test_valid_markdown_extension(self):

             """Markdown file with .md extension should be valid."""
        md_data = b'# Character Name\n\nDescription here.'
        is_valid, error, file_type = _validate_file_type(md_data, "character.md")
        assert is_valid is True
        assert error == ""
        # Implementation treats .md files as "json" type for processing
        assert file_type in ("json", "text")

    def test_valid_txt_extension(self):

             """Text file with .txt extension should be valid."""
        txt_data = b'Plain text character description.'
        is_valid, error, file_type = _validate_file_type(txt_data, "notes.txt")
        assert is_valid is True
        assert error == ""
        # Implementation treats .txt files as "json" type for text-based processing
        assert file_type in ("json", "text")

    # --- Security: Mismatch Detection ---
    def test_png_content_with_webp_extension_rejected(self):
             """PNG content masquerading as WebP should be rejected."""
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(png_data, "malicious.webp")
        assert is_valid is False
        assert "doesn't match extension" in error

    def test_jpeg_content_with_png_extension_rejected(self):

             """JPEG content masquerading as PNG should be rejected."""
        jpeg_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(jpeg_data, "fake.png")
        assert is_valid is False
        assert "doesn't match extension" in error

    def test_webp_content_with_png_extension_rejected(self):

             """WebP content masquerading as PNG should be rejected."""
        webp_data = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(webp_data, "fake.png")
        assert is_valid is False
        assert "doesn't match extension" in error

    def test_jpeg_extension_in_allowed_list(self):

             """JPEG extension (.jpg) is allowed."""
        jpeg_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(jpeg_data, "image.jpg")
        assert is_valid is True
        assert error == ""
        assert file_type == "image"

    # --- Invalid Extension Tests ---
    def test_invalid_extension_rejected(self):
             """Files with disallowed extensions should be rejected."""
        any_data = b'some content here' * 10
        is_valid, error, file_type = _validate_file_type(any_data, "script.py")
        assert is_valid is False
        assert "not allowed" in error

    def test_executable_extension_rejected(self):

             """Executable extensions should be rejected."""
        for ext in [".exe", ".sh", ".bat", ".cmd", ".ps1"]:
            is_valid, error, file_type = _validate_file_type(b'any data' * 10, f"file{ext}")
            assert is_valid is False, f"Extension {ext} should be rejected"
            assert "not allowed" in error

    def test_html_extension_rejected(self):

             """HTML extension should be rejected (XSS risk)."""
        html_data = b'<html><script>alert("xss")</script></html>'
        is_valid, error, file_type = _validate_file_type(html_data, "page.html")
        assert is_valid is False
        assert "not allowed" in error

    # --- No Filename Tests ---
    def test_png_without_filename(self):
             """PNG file without filename should be valid (detected by magic bytes)."""
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(png_data, None)
        assert is_valid is True
        assert file_type == "image"

    def test_json_without_filename(self):

             """JSON file without filename should be valid (detected by content)."""
        json_data = b'{"name": "Test"}'
        is_valid, error, file_type = _validate_file_type(json_data, None)
        assert is_valid is True
        assert file_type == "json"

    # --- Edge Cases ---
    def test_empty_filename(self):
             """Empty filename should be treated as no filename."""
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(png_data, "")
        assert is_valid is True
        assert file_type == "image"

    def test_case_insensitive_extension(self):

             """Extensions should be case-insensitive."""
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        is_valid, error, file_type = _validate_file_type(png_data, "image.PNG")
        assert is_valid is True
        assert file_type == "image"

    def test_double_extension(self):

             """Files with double extensions should check final extension."""
        json_data = b'{"name": "test"}'
        is_valid, error, file_type = _validate_file_type(json_data, "file.tar.json")
        assert is_valid is True
        assert file_type == "json"


class TestConstants:
    """Tests for module constants."""

    def test_max_file_size_is_reasonable(self):

             """MAX_CHARACTER_FILE_SIZE should be a reasonable limit."""
        assert MAX_CHARACTER_FILE_SIZE > 0
        assert MAX_CHARACTER_FILE_SIZE <= 100 * 1024 * 1024  # Not more than 100MB
        assert MAX_CHARACTER_FILE_SIZE == 10 * 1024 * 1024  # Exactly 10MB

    def test_allowed_extensions_are_safe(self):

             """ALLOWED_EXTENSIONS should not include dangerous types."""
        dangerous = {".exe", ".sh", ".bat", ".cmd", ".ps1", ".js", ".html", ".htm", ".php"}
        assert not dangerous.intersection(ALLOWED_EXTENSIONS)

    def test_expected_extensions_present(self):

             """Expected safe extensions should be present."""
        expected = {".png", ".webp", ".json", ".yaml", ".yml", ".txt", ".md"}
        assert expected.issubset(ALLOWED_EXTENSIONS)
