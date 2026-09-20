#!/usr/bin/env python3
"""Unit-test server.py mask_secrets against known-leak samples."""
import importlib.util as u, sys, re

spec = u.from_file_location("wiki_server", "server.py")
m = u.module_from_spec(spec)
spec.loader.exec_module(m)

leaks = [
    "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=1124