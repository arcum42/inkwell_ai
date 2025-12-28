"""Dialog for managing models across providers."""

from __future__ import annotations

from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QLabel,
    QCheckBox,
)
from PySide6.QtCore import Qt, QSettings

from core.model_manager import (
    ModelManager,
    ModelPreferenceStore,
    build_default_sources,
)


class ModelManagerDialog(QDialog):
    def __init__(self, app_settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model Manager")
        self.resize(900, 500)
        self._populating = False

        self.settings = app_settings
        self.prefs = ModelPreferenceStore(self.settings)
        self.manager = ModelManager(build_default_sources(self.settings), prefs=self.prefs)
        self._models_index = {}
        self._updating_settings_controls = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Models across providers. Favorites and notes are scoped per provider."))

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "★",
            "Provider",
            "Model",
            "Loaded",
            "Vision",
            "Tools",
            "Base",
            "Context",
            "Note",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.currentCellChanged.connect(lambda *_: self._on_selection_changed())
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        # Per-model settings
        settings_row = QHBoxLayout()
        self.hide_structured_cb = QCheckBox("Hide structured JSON (if supported)")
        self.hide_structured_cb.setToolTip("Render structured outputs as summaries with a Show JSON toggle.")
        self.hide_structured_cb.stateChanged.connect(self._on_hide_structured_changed)
        settings_row.addWidget(self.hide_structured_cb)
        settings_row.addStretch()
        layout.addLayout(settings_row)

        button_row = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self.refresh_models(force_refresh=True))
        button_row.addWidget(refresh_btn)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._on_load)
        button_row.addWidget(load_btn)

        unload_btn = QPushButton("Unload")
        unload_btn.clicked.connect(self._on_unload)
        button_row.addWidget(unload_btn)

        import_btn = QPushButton("Import…")
        import_btn.clicked.connect(self._on_import)
        button_row.addWidget(import_btn)

        export_btn = QPushButton("Export…")
        export_btn.clicked.connect(self._on_export)
        button_row.addWidget(export_btn)

        button_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)

        layout.addLayout(button_row)

        self.refresh_models(force_refresh=False)
        self._update_settings_controls()

    def refresh_models(self, force_refresh: bool = False):
        self._populating = True
        try:
            models = self.manager.list_models(refresh=force_refresh)
            self._models_index = {(m.provider, m.name): m for m in models}
            self.table.setRowCount(len(models))
            for row, model in enumerate(models):
                self._populate_row(row, model)
            self.table.resizeColumnsToContents()
        finally:
            self._populating = False
        self._update_settings_controls()

    def _populate_row(self, row: int, model):
        fav_item = QTableWidgetItem()
        fav_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        fav_item.setCheckState(Qt.Checked if "favorite" in model.tags else Qt.Unchecked)
        fav_item.setData(Qt.UserRole, (model.provider, model.name))
        self.table.setItem(row, 0, fav_item)

        def make_item(text: str, editable: bool = False):
            item = QTableWidgetItem(text)
            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            if editable:
                flags |= Qt.ItemIsEditable
            item.setFlags(flags)
            item.setData(Qt.UserRole, (model.provider, model.name))
            return item

        provider_item = make_item(model.provider)
        model_item = make_item(model.display_name or model.name)
        loaded_item = make_item(self._fmt_bool(model.is_loaded))
        vision_item = make_item(self._fmt_bool(model.supports_vision))
        tools_item = make_item(self._fmt_bool(model.supports_tools))
        base_item = make_item(model.base_model or "")
        ctx_item = make_item(str(model.context_length) if model.context_length is not None else "")
        note_item = make_item(model.note or "", editable=True)

        self.table.setItem(row, 1, provider_item)
        self.table.setItem(row, 2, model_item)
        self.table.setItem(row, 3, loaded_item)
        self.table.setItem(row, 4, vision_item)
        self.table.setItem(row, 5, tools_item)
        self.table.setItem(row, 6, base_item)
        self.table.setItem(row, 7, ctx_item)
        self.table.setItem(row, 8, note_item)

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._populating:
            return
        payload = item.data(Qt.UserRole)
        # Qt stores tuples as lists, so check for both
        if not payload or not isinstance(payload, (tuple, list)):
            return
        provider, model = payload
        col = item.column()
        if col == 0:
            self.manager.set_favorite(provider, model, item.checkState() == Qt.Checked)
        elif col == 8:
            self.manager.set_note(provider, model, item.text())

    def _selected_provider_model(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)  # provider column
        if not item:
            return None
        # Get provider and model from UserRole data (not display text)
        # Qt stores tuples as lists, so check for both
        data = item.data(Qt.UserRole)
        if not data or not isinstance(data, (tuple, list)) or len(data) != 2:
            return None
        provider, model = data
        if not provider or not model:
            return None
        return provider, model

    def _current_model_info(self):
        target = self._selected_provider_model()
        if not target:
            return None
        return self._models_index.get((target[0], target[1]))

    def _on_load(self):
        target = self._selected_provider_model()
        if not target:
            QMessageBox.information(self, "No Selection", "Select a model to load.")
            return
        provider, model = target
        success, message = self.manager.load_model(provider, model)
        if success:
            QMessageBox.information(self, "Model Loaded", f"Loaded {model} ({provider}).")
        else:
            detail = f"\n\n{message}" if message else ""
            QMessageBox.warning(self, "Load Failed", f"Could not load {model} ({provider}).{detail}")
        self.refresh_models(force_refresh=True)

    def _on_selection_changed(self):
        self._update_settings_controls()

    def _on_unload(self):
        target = self._selected_provider_model()
        if not target:
            QMessageBox.information(self, "No Selection", "Select a model to unload.")
            return
        provider, model = target
        success, message = self.manager.unload_model(provider, model)
        if success:
            QMessageBox.information(self, "Model Unloaded", f"Unloaded {model} ({provider}).")
        else:
            detail = f"\n\n{message}" if message else ""
            QMessageBox.warning(self, "Unload Failed", f"Could not unload {model} ({provider}).{detail}")
        self.refresh_models(force_refresh=True)

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Favorites/Notes", "model_prefs.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            self.manager.export_preferences(path)
            QMessageBox.information(self, "Exported", f"Exported preferences to {path}.")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export preferences: {exc}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Favorites/Notes", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            self.manager.import_preferences(path, merge_strategy="skip_existing")
            QMessageBox.information(self, "Imported", f"Imported preferences from {path}.")
            self.refresh_models(force_refresh=False)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", f"Could not import preferences: {exc}")

    def _on_hide_structured_changed(self, state: int):
        if self._updating_settings_controls:
            return
        info = self._current_model_info()
        if not info:
            return
        settings = self.manager.get_settings(info.provider, info.name)
        settings.hide_structured_output_json = bool(state)
        self.manager.set_settings(info.provider, info.name, settings)

    def _update_settings_controls(self):
        info = self._current_model_info()
        self._updating_settings_controls = True
        try:
            if not info:
                self.hide_structured_cb.setChecked(False)
                self.hide_structured_cb.setEnabled(False)
                self.hide_structured_cb.setToolTip("Select a model to edit settings.")
                return

            settings = self.manager.get_settings(info.provider, info.name)
            should_hide = True if settings.hide_structured_output_json is None else bool(settings.hide_structured_output_json)
            self.hide_structured_cb.setChecked(should_hide)

            supports_structured = info.supports_structured_output
            if supports_structured is False:
                self.hide_structured_cb.setEnabled(False)
                self.hide_structured_cb.setToolTip("Structured output not detected for this model.")
            else:
                self.hide_structured_cb.setEnabled(True)
                if supports_structured:
                    self.hide_structured_cb.setToolTip("Render structured outputs as summaries with a Show JSON toggle.")
                else:
                    self.hide_structured_cb.setToolTip("Support unknown; toggle applies when structured output is available.")
        finally:
            self._updating_settings_controls = False

    @staticmethod
    def _fmt_bool(value):
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        return "Unknown"
