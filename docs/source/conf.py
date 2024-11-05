# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# Path handling
import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

project = "FSO Switch Sim"
copyright = "2024, Victor Virag"
author = "Victor Virag"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
autodoc_default_options = {
    "exclude-members": "bell_index, success, measurement_basis, outcome"
}
autosummary_generate = True
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # Recommended for Google and NumPy style docstrings
    "sphinx.ext.viewcode",  # Adds links to highlighted source code
    "sphinx.ext.autosummary",  # Optional: Generates summary tables for modules
]

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
