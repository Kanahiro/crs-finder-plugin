import os

from PyQt5.QtWidgets import QAction
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from .crs_finder_dock import CrsFinderDockWidget

PLUGIN_NAME = "CRS Finder"

class CrsFinderPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.win = self.iface.mainWindow()
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = PLUGIN_NAME
        self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
        self.toolbar.setObjectName(PLUGIN_NAME)
        self.dock_widget = None
        
    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        icon = QIcon(icon_path) if icon_path else QIcon()
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "imgs", "icon.png")
        self.add_action(
            icon_path=icon_path,
            text="CRS Finder",
            callback=self.show_dock_widget,
            parent=self.win,
        )

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(PLUGIN_NAME, action)
            self.iface.removeToolBarIcon(action)
        self.actions.clear()
        if hasattr(self, "toolbar"):
            del self.toolbar
        if self.dock_widget:
            try:
                self.iface.removeDockWidget(self.dock_widget)
            except AttributeError:
                pass
            self.dock_widget.deleteLater()
            self.dock_widget = None

    def show_dock_widget(self):
        if not self.dock_widget:
            self.dock_widget = CrsFinderDockWidget()
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.show()
        self.dock_widget.raise_()
