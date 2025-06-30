"""
Custom template tags and filters for the projects app.
"""

# This file makes Python treat the directory as a package
# Import the custom filters to ensure they're registered
from . import custom_filters

# This ensures the template tags are loaded when Django starts