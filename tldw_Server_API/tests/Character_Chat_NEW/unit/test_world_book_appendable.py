"""
Tests for appendable text block concatenation in world book process_context().

Verifies that entries with appendable=true in metadata are concatenated
directly (no separator) when consecutive, while non-appendable entries
maintain normal "\n\n" separation.
"""

import pytest

from tldw_Server_API.app.core.Character_Chat.world_book_manager import WorldBookService


class TestAppendableConcatenation:
    """Test appendable-aware grouping in process_context()."""

    def _add_entry(self, service, wb_id, keyword, content, priority, *, appendable=False):
        """Helper to add an entry with optional appendable metadata."""
        return service.add_entry(
            world_book_id=wb_id,
            keywords=[keyword],
            content=content,
            priority=priority,
            metadata={"appendable": appendable},
        )

    def _get_processed_context(self, service, wb_id, text, **kwargs):
        """Call process_context with list form and return the processed_context string."""
        # Pass world_book_ids as a list to get the dict response (non-compact).
        # Use scan_depth=100 to avoid per-book entry limits interfering with tests.
        kwargs.setdefault("scan_depth", 100)
        result = service.process_context(text=text, world_book_ids=[wb_id], **kwargs)
        if isinstance(result, dict):
            return result.get("processed_context", "")
        return ""

    @pytest.mark.unit
    def test_appendable_consecutive_entries_concatenated(self, world_book_service):
        """Two appendable entries followed by non-appendable: 'AB\\n\\nC'."""
        service = world_book_service

        wb_id = service.create_world_book(name="test_wb", description="test")
        # Higher priority = sorted first. All share keyword "dragon".
        self._add_entry(service, wb_id, "dragon", "A", priority=30, appendable=True)
        self._add_entry(service, wb_id, "dragon", "B", priority=20, appendable=True)
        self._add_entry(service, wb_id, "dragon", "C", priority=10, appendable=False)

        injected = self._get_processed_context(service, wb_id, "I saw a dragon")
        assert injected == "AB\n\nC"

    @pytest.mark.unit
    def test_all_non_appendable_standard_separation(self, world_book_service):
        """All non-appendable entries use standard '\\n\\n' separation."""
        service = world_book_service

        wb_id = service.create_world_book(name="test_wb", description="test")
        self._add_entry(service, wb_id, "castle", "X", priority=30, appendable=False)
        self._add_entry(service, wb_id, "castle", "Y", priority=20, appendable=False)
        self._add_entry(service, wb_id, "castle", "Z", priority=10, appendable=False)

        injected = self._get_processed_context(service, wb_id, "the castle stands")
        assert injected == "X\n\nY\n\nZ"

    @pytest.mark.unit
    def test_all_appendable_single_block(self, world_book_service):
        """All appendable entries form a single concatenated block."""
        service = world_book_service

        wb_id = service.create_world_book(name="test_wb", description="test")
        self._add_entry(service, wb_id, "sword", "P", priority=30, appendable=True)
        self._add_entry(service, wb_id, "sword", "Q", priority=20, appendable=True)
        self._add_entry(service, wb_id, "sword", "R", priority=10, appendable=True)

        injected = self._get_processed_context(service, wb_id, "a magic sword")
        assert injected == "PQR"

    @pytest.mark.unit
    def test_mixed_appendable_pattern(self, world_book_service):
        """Mixed pattern: [non, app, app, non, app] → 'N1\\n\\nA1A2\\n\\nN2\\n\\nA3'."""
        service = world_book_service

        wb_id = service.create_world_book(name="test_wb", description="test", scan_depth=10)
        self._add_entry(service, wb_id, "elf", "N1", priority=50, appendable=False)
        self._add_entry(service, wb_id, "elf", "A1", priority=40, appendable=True)
        self._add_entry(service, wb_id, "elf", "A2", priority=30, appendable=True)
        self._add_entry(service, wb_id, "elf", "N2", priority=20, appendable=False)
        self._add_entry(service, wb_id, "elf", "A3", priority=10, appendable=True)

        injected = self._get_processed_context(service, wb_id, "an elf appeared")
        assert injected == "N1\n\nA1A2\n\nN2\n\nA3"

    @pytest.mark.unit
    def test_diagnostic_includes_appendable_field(self, world_book_service):
        """Diagnostics should include the appendable field."""
        service = world_book_service

        wb_id = service.create_world_book(name="test_wb", description="test")
        self._add_entry(service, wb_id, "orc", "Orc lore", priority=10, appendable=True)

        result = service.process_context(
            text="an orc attacks",
            world_book_ids=[wb_id],
            scan_depth=100,
            include_diagnostics=True,
        )

        assert isinstance(result, dict)
        diagnostics = result.get("diagnostics", [])
        assert len(diagnostics) >= 1
        diag = diagnostics[0]
        assert "appendable" in diag
        assert diag["appendable"] is True
