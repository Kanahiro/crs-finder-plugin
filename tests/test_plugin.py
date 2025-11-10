import unittest

from ..crs_finder_dock import CrsFinderDockWidget
from ..crs_finder_plugin import CrsFinderPlugin

from .utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()


class TestCrsFinderDock(unittest.TestCase):
    def test_visibility_toggles(self):
        dock = CrsFinderDockWidget()

        assert dock.isVisible() is False
        dock.show()
        assert dock.isVisible() is True
        dock.hide()
        assert dock.isVisible() is False


class TestCrsFinderPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = CrsFinderPlugin(IFACE)

    def tearDown(self):
        if self.plugin is not None:
            self.plugin.unload()
            self.plugin = None

    def test_show_dock_widget_reuses_single_instance(self):
        assert self.plugin.dock_widget is None

        self.plugin.show_dock_widget()
        first_instance = self.plugin.dock_widget

        assert first_instance is not None

        self.plugin.show_dock_widget()
        assert self.plugin.dock_widget is first_instance

    def test_unload_clears_dock_widget(self):
        self.plugin.show_dock_widget()
        assert self.plugin.dock_widget is not None

        self.plugin.unload()
        assert self.plugin.dock_widget is None
        # Prevent tearDown from calling unload twice
        self.plugin = None


if __name__ == "__main__":
    unittest.main()
