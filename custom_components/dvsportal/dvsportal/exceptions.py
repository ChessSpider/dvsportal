# -*- coding: utf-8 -*-
"""Exceptions for DVSPortal."""

class DVSPortalError(Exception):
    """Generic DVSPortal exception."""

    pass

class DVSPortalAuthError(Exception):
    """Generic authentication exception."""

    pass

class DVSPortalConnectionError(DVSPortalError):
    """DVSPortal connection exception."""

    pass
