# -*- coding: utf-8 -*-

def classFactory(iface):
    from .manager import MonPlugIn_
    return MonPlugIn_(iface)

    from .main import MonPlugIn
    return MonPlugIn(iface)