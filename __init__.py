def classFactory(iface):
    from .crs_finder_plugin import CrsFinderPlugin
    return CrsFinderPlugin(iface)
