from __future__ import annotations

from typing import Optional

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsGeometry,
    QgsMapLayer,
    QgsProject,
    QgsRectangle,
    QgsWkbTypes,
    
)
from qgis.gui import QgsMapLayerComboBox, QgsProjectionSelectionWidget, QgsRubberBand
from qgis.utils import iface


class CrsFinderDockWidget(QDockWidget):
    """Dock widget implementing the CRS Finder UI and behavior."""

    WINDOW_TITLE = "CRS Finder"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CrsFinderDockWidget")
        self.setWindowTitle(self.WINDOW_TITLE)

        self._rubber_band: Optional[QgsRubberBand] = None
        self._build_ui()
        self._connect_signals()
        self._on_layer_change()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Layer picker row
        layer_row = QHBoxLayout()
        layer_row.addWidget(QLabel("Layer:"))
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setObjectName("layerCombo")
        layer_row.addWidget(self.layer_combo, 1)
        layout.addLayout(layer_row)

        layout.addWidget(QLabel("Target CRS:"))
        self.crs_widget = QgsProjectionSelectionWidget()
        self.crs_widget.setObjectName("targetCrsWidget")
        layout.addWidget(self.crs_widget)

        button_row = QHBoxLayout()
        self.zoom_button = QPushButton("Zoom to Preview")
        self.zoom_button.setObjectName("zoomPreviewButton")
        self.zoom_button.setEnabled(False)
        button_row.addWidget(self.zoom_button)
        self.apply_button = QPushButton("Apply to Layer CRS")
        self.apply_button.setObjectName("applyButton")
        self.apply_button.setEnabled(False)
        button_row.addWidget(self.apply_button)
        layout.addLayout(button_row)

        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #555555;")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        layout.addStretch(1)
        self.setWidget(container)

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.layer_combo.layerChanged.connect(self._on_layer_change)
        self.zoom_button.clicked.connect(self.zoom_to_preview)
        self.apply_button.clicked.connect(self.apply_selected_crs)
        self.crs_widget.crsChanged.connect(self._on_target_crs_change)

    def selected_layer(self) -> Optional[QgsMapLayer]:
        return self.layer_combo.currentLayer()

    def _on_target_crs_change(self, _crs) -> None:
        self.preview_extent(auto_zoom=True)

    def _on_layer_change(self, *_args) -> None:
        layer = self.selected_layer()
        if layer is None:
            self._clear_preview()
            self._set_status("Select a layer to begin.")
            return
        self._set_preview_ready(False)

        # When a new layer is selected, align the CRS picker with its CRS.
        crs = layer.crs()
        if crs and crs.isValid():
            self.crs_widget.blockSignals(True)
            self.crs_widget.setCrs(crs)
            self.crs_widget.blockSignals(False)

        self.preview_extent()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_crs(crs: QgsCoordinateReferenceSystem) -> str:
        if not crs or not crs.isValid():
            return "Undefined CRS"
        authid = crs.authid() or "Custom"
        description = crs.description()
        return f"{authid} ({description})"

    @staticmethod
    def _format_extent(extent: QgsRectangle) -> str:
        if extent.isNull() or extent.isEmpty():
            return "Unavailable"
        return (
            f"xmin={extent.xMinimum():.4f}, xmax={extent.xMaximum():.4f}, "
            f"ymin={extent.yMinimum():.4f}, ymax={extent.yMaximum():.4f}"
        )

    # ------------------------------------------------------------------
    # Extent preview & CRS application
    # ------------------------------------------------------------------
    def selected_crs(self) -> Optional[QgsCoordinateReferenceSystem]:
        crs = self.crs_widget.crs()
        return crs if crs and crs.isValid() else None

    def preview_extent(self, *, auto_zoom: bool = False) -> None:
        layer = self.selected_layer()
        target_crs = self.selected_crs()

        if layer is None:
            self._set_status("Select a layer before previewing.", True)
            self._clear_preview()
            return

        if target_crs is None:
            self._set_status("Select a target CRS before previewing.", True)
            self._clear_preview()
            return

        extent = layer.extent()
        if extent.isNull() or extent.isEmpty():
            self._set_status("The selected layer does not have a valid extent.", True)
            self._clear_preview()
            return

        # Interpret the numbers from the layer extent as coordinates expressed
        # in the user selected CRS (no reprojection of the raw values).
        target_extent = QgsRectangle(extent)

        success = self._draw_extent(target_extent, target_crs)
        if success:
            self._clear_error_label()
            self._set_preview_ready(True)
            pretty_extent = self._format_extent(target_extent)
            if auto_zoom:
                self.zoom_to_preview()
        else:
            self._clear_preview()
            self._set_status(
                "CRSの変換に失敗しました。選択したCRSがこの範囲を表現できません。",
                True,
                inline_error=True,
            )

    def _draw_extent(
        self,
        extent: QgsRectangle,
        extent_crs: QgsCoordinateReferenceSystem,
    ) -> bool:
        if not iface.mapCanvas():
            return False

        transform_context = QgsProject.instance().transformContext()
        project_crs = QgsProject.instance().crs()

        project_extent = extent
        project_extent_crs = extent_crs

        if project_crs.isValid() and project_crs != extent_crs:
            try:
                to_project = QgsCoordinateTransform(
                    extent_crs, project_crs, transform_context
                )
                project_extent = to_project.transformBoundingBox(extent)
                project_extent_crs = project_crs
            except QgsCsException:
                return False

        dest_crs = iface.mapCanvas().mapSettings().destinationCrs()
        display_extent = project_extent
        if dest_crs.isValid() and dest_crs != project_extent_crs:
            try:
                to_canvas = QgsCoordinateTransform(
                    project_extent_crs, dest_crs, transform_context
                )
                display_extent = to_canvas.transformBoundingBox(project_extent)
            except QgsCsException:
                return False

        geometry = QgsGeometry.fromRect(display_extent)
        rubber_band = self._ensure_rubber_band()
        rubber_band.setToGeometry(geometry, QgsCoordinateReferenceSystem())
        rubber_band.show()

        return True

    def apply_selected_crs(self) -> None:
        layer = self.selected_layer()
        target_crs = self.selected_crs()

        if layer is None or target_crs is None:
            self._set_status("Select both a layer and target CRS before applying.", True)
            return

        if layer.crs() == target_crs:
            self._set_status("Layer already uses the selected CRS.")
            return

        layer.setCrs(target_crs)
        layer.triggerRepaint()
        self._set_status(
            f"Layer '{layer.name()}' CRS overwritten with {self._format_crs(target_crs)}."
        )
        

    def zoom_to_preview(self) -> None:
        if not self._rubber_band:
            return
        geometry = self._rubber_band.asGeometry()
        if geometry is None or geometry.isEmpty():
            return
        extent = geometry.boundingBox()
        if extent.isNull() or extent.isEmpty():
            return
        iface.mapCanvas().setExtent(extent)
        iface.mapCanvas().refresh()

    # ------------------------------------------------------------------
    # Rubber band helpers
    # ------------------------------------------------------------------
    def _ensure_rubber_band(self) -> QgsRubberBand:
        if self._rubber_band is None and iface.mapCanvas():
            self._rubber_band = QgsRubberBand(
                iface.mapCanvas(), QgsWkbTypes.PolygonGeometry
            )
            outline = QColor(255, 136, 0)
            outline.setAlpha(200)
            fill = QColor(255, 136, 0, 40)
            self._rubber_band.setColor(outline)
            self._rubber_band.setFillColor(fill)
        return self._rubber_band

    def _clear_preview(self) -> None:
        if self._rubber_band:
            self._rubber_band.hide()
            self._rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self._set_preview_ready(False)
        self._clear_error_label()

    def _set_preview_ready(self, ready: bool) -> None:
        self.zoom_button.setEnabled(ready)
        has_layer = self.selected_layer() is not None
        self.apply_button.setEnabled(ready and has_layer)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------
    def _set_status(self, message: str, is_error: bool = False, *, inline_error: bool = False) -> None:
        if not hasattr(self, "status_label"):
            return

        if inline_error and is_error:
            color = "#c0392b"
            self.status_label.setStyleSheet(
                f"color: {color}; font-weight: bold;"
            )
            self.status_label.setText(message)
            self.status_label.show()
            return

        self._clear_error_label()


        iface.messageBar().clearWidgets()
        push_fn = iface.messageBar().pushWarning if is_error else iface.messageBar().pushInfo
        push_fn(self.WINDOW_TITLE, message)

    def _clear_error_label(self) -> None:
        if not hasattr(self, "status_label"):
            return
        self.status_label.clear()
        self.status_label.hide()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self._clear_preview()
        super().closeEvent(event)
