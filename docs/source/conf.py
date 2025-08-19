# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# Path handling
import os
import sys

# Add the `src` directory to the Python path
sys.path.insert(0, os.path.abspath("../../src"))

project = "FSO Switch Simulation"
copyright = "2024, Victor Virag"
author = "Victor Virag"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Exclude specific members from autodoc
autodoc_default_options = {
    "exclude-members": "bell_index, success, measurement_basis, outcome"
}

autosummary_generate = True  # Generate summary tables for modules
extensions = [
    "sphinx.ext.autodoc",  # Automatically include docstrings
    "sphinx.ext.napoleon",  # Support Google and NumPy style docstrings
    "sphinx.ext.viewcode",  # Add links to source code
    "sphinx.ext.autosummary",  # Generate module summary tables
]

templates_path = ["_templates"]

# Exclude unnecessary files and directories
exclude_patterns = [
    "_build",  # Ignore build artifacts
    "Thumbs.db",  # Windows file
    ".DS_Store",  # macOS file
    "**/__pycache__",
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
