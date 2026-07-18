"""Tests for UI design improvements (Request 5).

Covers:
1. Export modal: dual tabs (Python Code + JSON Data), download JSON
2. Load modal: preview buttons, "View Current JSON" button
3. Templates modal: preview buttons on each template card
4. Save as Template modal: description field, hint text
5. i18n: all new keys present in both EN and ZH
6. CSS: styles for all new UI elements
"""

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. Export modal: dual tabs
# ---------------------------------------------------------------------------
class TestExportModalTabs:
    """Test the export modal has dual tabs (Python Code + JSON Data)."""

    @property
    def index_html(self):
        return Path(__file__).resolve().parent.parent / "static" / "index.html"

    @property
    def app_js(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"

    def test_export_modal_has_tabs(self):
        content = self.index_html.read_text(encoding="utf-8")
        assert 'class="export-tabs"' in content
        assert 'data-export-tab="code"' in content
        assert 'data-export-tab="json"' in content

    def test_export_modal_has_json_pre_element(self):
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="export-json"' in content

    def test_export_modal_has_download_button(self):
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="btn-download-json"' in content

    def test_export_modal_title_changed_from_code_only(self):
        """The export modal title should be 'Export' not 'Exported Python Code'."""
        content = self.index_html.read_text(encoding="utf-8")
        # The old title was "Exported Python Code"
        idx = content.index('id="export-modal"')
        section = content[idx:idx + 500]
        assert "Exported Python Code" not in section

    def test_app_js_has_tab_switching_logic(self):
        content = self.app_js.read_text(encoding="utf-8")
        assert "export-tab" in content
        assert "exportTab" in content or "export_tab" in content.lower() or "dataset.exportTab" in content

    def test_app_js_populates_json_on_export(self):
        """The export button should populate the JSON tab."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "export-json" in content
        assert "JSON.stringify(graph, null, 2)" in content

    def test_app_js_has_download_json_handler(self):
        """The download JSON button should have an event handler."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "btn-download-json" in content
        assert "Blob" in content
        assert "application/json" in content
        assert "createObjectURL" in content

    def test_copy_button_copies_active_tab(self):
        """The copy button should copy the active tab's content."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "export-tab active" in content or "export-tab.active" in content
        assert "export-json" in content


# ---------------------------------------------------------------------------
# 2. Load modal: preview and view current JSON
# ---------------------------------------------------------------------------
class TestLoadModalPreview:
    """Test the load modal has preview and view current JSON features."""

    @property
    def index_html(self):
        return Path(__file__).resolve().parent.parent / "static" / "index.html"

    @property
    def app_js(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"

    def test_load_modal_has_view_current_json_button(self):
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="btn-view-current-json"' in content

    def test_load_modal_has_textarea_header(self):
        content = self.index_html.read_text(encoding="utf-8")
        assert 'class="load-textarea-header"' in content

    def test_app_js_has_view_current_json_handler(self):
        content = self.app_js.read_text(encoding="utf-8")
        assert "btn-view-current-json" in content
        assert "Store.toGraph()" in content

    def test_app_js_has_preview_button_in_saved_pipelines(self):
        """Saved pipelines should have a preview button."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "btn-pipeline-preview" in content

    def test_app_js_preview_loads_json_to_textarea(self):
        """Clicking preview should fill the textarea with JSON."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "btn-pipeline-preview" in content
        assert "load-textarea" in content


# ---------------------------------------------------------------------------
# 3. Templates modal: preview buttons
# ---------------------------------------------------------------------------
class TestTemplatesModalPreview:
    """Test the templates modal has preview buttons."""

    @property
    def app_js(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"

    def test_builtin_template_has_preview_button(self):
        content = self.app_js.read_text(encoding="utf-8")
        assert 'data-action="preview"' in content
        assert "btn-template-preview" in content

    def test_template_preview_handler_exists(self):
        """The preview action should be handled in the event listener."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "action === 'preview'" in content or 'action === "preview"' in content

    def test_template_preview_shows_json(self):
        """Preview should show JSON in a pre element."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "template-json-preview" in content
        assert "JSON.stringify(graph, null, 2)" in content

    def test_template_preview_is_toggleable(self):
        """Preview should be toggleable (close on second click)."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "preview_close" in content or "Close Preview" in content


# ---------------------------------------------------------------------------
# 4. Save as Template modal: description and hint
# ---------------------------------------------------------------------------
class TestSaveTemplateModalEnhancements:
    """Test the save template modal has description and hint text."""

    @property
    def index_html(self):
        return Path(__file__).resolve().parent.parent / "static" / "index.html"

    @property
    def app_js(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"

    def test_modal_has_description_field(self):
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="save-template-desc"' in content

    def test_modal_has_hint_text(self):
        content = self.index_html.read_text(encoding="utf-8")
        assert 'class="save-template-hint"' in content

    def test_app_js_reads_description(self):
        """saveAsTemplate should read the description field."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "save-template-desc" in content
        assert "graph.description" in content

    def test_app_js_clears_description_on_save(self):
        """After saving, the description field should be cleared."""
        content = self.app_js.read_text(encoding="utf-8")
        # Find the saveAsTemplate function
        idx = content.index("async function saveAsTemplate")
        section = content[idx:idx + 800]
        assert "save-template-desc" in section
        assert ".value = ''" in section


# ---------------------------------------------------------------------------
# 5. i18n: all new keys in both EN and ZH
# ---------------------------------------------------------------------------
class TestI18nNewKeys:
    """Test that all new i18n keys exist in both English and Chinese."""

    @property
    def i18n_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "i18n.js"

    NEW_KEYS = [
        "modal.export_code",
        "modal.export_json",
        "modal.download_json",
        "modal.preview",
        "modal.preview_close",
        "modal.view_current_json",
        "modal.save_template_hint",
        "toast.downloaded",
        "toast.preview_loaded",
        "toast.json_filled",
    ]

    def test_all_keys_present(self):
        content = self.i18n_content.read_text(encoding="utf-8")
        for key in self.NEW_KEYS:
            assert f"'{key}'" in content, f"i18n key '{key}' not found"

    def test_export_title_changed(self):
        """The export title should no longer be 'Exported Python Code'."""
        content = self.i18n_content.read_text(encoding="utf-8")
        # Should not have the old title
        assert "'Exported Python Code'" not in content

    def test_zh_translations_present(self):
        """Chinese translations for new keys should exist."""
        content = self.i18n_content.read_text(encoding="utf-8")
        assert "导出" in content
        assert "Python 代码" in content
        assert "JSON 数据" in content
        assert "下载 JSON" in content
        assert "预览" in content
        assert "查看当前 JSON" in content


# ---------------------------------------------------------------------------
# 6. CSS: styles for new UI elements
# ---------------------------------------------------------------------------
class TestCSSForNewElements:
    """Test that CSS styles exist for all new UI elements."""

    @property
    def css_content(self):
        return Path(__file__).resolve().parent.parent / "static" / "css" / "style.css"

    def test_export_tabs_style(self):
        content = self.css_content.read_text(encoding="utf-8")
        assert ".export-tabs" in content
        assert ".export-tab" in content
        assert ".export-tab.active" in content
        assert ".export-tab-content" in content

    def test_load_textarea_header_style(self):
        content = self.css_content.read_text(encoding="utf-8")
        assert ".load-textarea-header" in content

    def test_pipeline_preview_button_style(self):
        content = self.css_content.read_text(encoding="utf-8")
        assert ".btn-pipeline-preview" in content

    def test_template_preview_button_style(self):
        content = self.css_content.read_text(encoding="utf-8")
        assert ".btn-template-preview" in content

    def test_template_json_preview_style(self):
        content = self.css_content.read_text(encoding="utf-8")
        assert ".template-json-preview" in content

    def test_save_template_hint_style(self):
        content = self.css_content.read_text(encoding="utf-8")
        assert ".save-template-hint" in content


# ---------------------------------------------------------------------------
# 7. HTML structure integrity
# ---------------------------------------------------------------------------
class TestHTMLIntegrity:
    """Test that the HTML structure is valid after changes."""

    @property
    def index_html(self):
        return Path(__file__).resolve().parent.parent / "static" / "index.html"

    def test_export_modal_still_has_code_element(self):
        """The export code element should still exist."""
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="export-code"' in content

    def test_export_modal_still_has_copy_button(self):
        """The copy button should still exist."""
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="btn-copy-code"' in content

    def test_load_modal_still_has_textarea(self):
        """The load textarea should still exist."""
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="load-textarea"' in content

    def test_load_modal_still_has_file_input(self):
        """The load file input should still exist."""
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="load-file-input"' in content

    def test_save_template_modal_still_has_name_input(self):
        """The save template name input should still exist."""
        content = self.index_html.read_text(encoding="utf-8")
        assert 'id="save-template-name"' in content

    def test_all_modals_have_close_buttons(self):
        """All modals should still have close buttons."""
        content = self.index_html.read_text(encoding="utf-8")
        modals = ["export-modal", "validate-modal", "load-modal",
                  "templates-modal", "save-template-modal"]
        for modal_id in modals:
            idx = content.index(f'id="{modal_id}"')
            section = content[idx:idx + 800]
            assert 'data-close=' in section, f"Modal '{modal_id}' missing close button"

    def test_version_cache_busting_updated(self):
        """CSS/JS version parameters should be updated."""
        content = self.index_html.read_text(encoding="utf-8")
        # Should not use the old version strings
        assert "v=20260717c" not in content
        assert "v=20260717d" not in content


# ---------------------------------------------------------------------------
# 8. App.js integrity
# ---------------------------------------------------------------------------
class TestAppJSIntegrity:
    """Test that app.js is valid after changes."""

    @property
    def app_js(self):
        return Path(__file__).resolve().parent.parent / "static" / "js" / "app.js"

    def test_save_pipeline_still_works(self):
        """The save pipeline handler should still exist."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "btn-save" in content
        assert "API.savePipeline" in content

    def test_load_pipeline_still_works(self):
        """The load pipeline handler should still exist."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "btn-load" in content
        assert "API.loadPipeline" in content

    def test_export_still_calls_exportPython(self):
        """The export button should still call API.exportPython."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "API.exportPython" in content

    def test_run_pipeline_still_works(self):
        """The run pipeline handler should still exist."""
        content = self.app_js.read_text(encoding="utf-8")
        assert "btn-run" in content
        assert "runPipeline" in content

    def test_no_duplicate_event_listeners(self):
        """No duplicate event listeners should exist for the same element."""
        content = self.app_js.read_text(encoding="utf-8")
        # Check that btn-copy-code is only bound once
        count = content.count("getElementById('btn-copy-code')")
        assert count <= 1, "btn-copy-code bound multiple times"

    def test_preview_action_does_not_load_graph(self):
        """The preview action should not call Store.fromGraph."""
        content = self.app_js.read_text(encoding="utf-8")
        # Find the preview action block
        idx = content.index("action === 'preview'")
        section = content[idx:idx + 500]
        assert "Store.fromGraph" not in section
        assert "JSON.stringify(graph, null, 2)" in section
