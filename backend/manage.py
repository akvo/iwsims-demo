#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
from pathlib import Path
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mis.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    """Create fake storage and cache folder"""
    Path("./tmp/fake_storage").mkdir(parents=True, exist_ok=True)
    Path("./tmp/cache").mkdir(parents=True, exist_ok=True)
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
