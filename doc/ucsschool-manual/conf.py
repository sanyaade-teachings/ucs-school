# SPDX-FileCopyrightText: 2021-2024 Univention GmbH
#
# SPDX-License-Identifier: AGPL-3.0-only

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from datetime import date

# -- Project information -----------------------------------------------------

project = "UCS@school - Handbuch für Administratoren"
copyright = "2021-{}, Univention GmbH".format(date.today().year)
author = ""

# The full version, including alpha/beta/rc tags
release = "5.0"

html_show_copyright = True
language = "de"

html_title = project

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "univention_sphinx_extension",
    "sphinxcontrib.spelling",
    "sphinx_last_updated_by_git",
    "sphinx.ext.intersphinx",
    "sphinx_sitemap",
    "sphinx_copybutton",
    "sphinxcontrib.bibtex",
]

bibtex_bibfiles = ["../bibliography-de.bib"]
bibtex_encoding = "utf-8"
bibtex_default_style = "unsrt"
bibtex_reference_style = "label"

copybutton_prompt_text = r"\$ "
copybutton_prompt_is_regexp = True
copybutton_line_continuation_character = "\\"

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
pdf_doc_base = os.path.basename(os.path.dirname(__file__))

html_theme = "univention_sphinx_book_theme"
html_theme_options = {
    "pdf_download_filename": f"{pdf_doc_base}.pdf",
    "show_source_license": True,
    "typesense_search": True,
    "typesense_document": pdf_doc_base,
    "typesense_document_version": release,
    "univention_matomo_tracking": True,
    "univention_docs_deployment": True,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []  # value usually is ['_static']

# https://github.com/mgeier/sphinx-last-updated-by-git
git_last_updated_timezone = "Europe/Berlin"

numfig = True

suppress_warnings = ["git.too_shallow"]

if "spelling" in sys.argv:
    spelling_lang = "de_DE"
    tokenizer_lang = "de_DE"
    spelling_show_suggestions = True
    spelling_warning = True
    spelling_word_list_filename = ["spelling_wordlist"]
    # Don't load extension to speed up the job
    extensions.remove("sphinx_last_updated_by_git")
    extensions.remove("sphinx_sitemap")
    suppress_warnings.append("bibtex")

if "linkcheck" in sys.argv:
    suppress_warnings.append("bibtex")

root_doc = "index"

rst_epilog = """
.. include:: /../substitutions-de.txt

.. include:: /links-de.txt
"""

latex_engine = "lualatex"
latex_show_pagerefs = True
latex_show_urls = "footnote"
latex_documents = [(root_doc, f"{pdf_doc_base}.tex", "", author, "manual", False)]
latex_elements = {
    "papersize": "a4paper",
    "babel": "\\usepackage{babel}",
}

# https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-figure_language_filename
figure_language_filename = "{root}-{language}{ext}"

univention_use_doc_base = True

# See Univention Sphinx Extension for its options.
# https://git.knut.univention.de/univention/documentation/univention_sphinx_extension
# Information about the feedback link.
univention_feedback = True
# Information about the license statement for the source files
univention_pdf_show_source_license = True

intersphinx_mapping = {
    "uv-manual": ("https://docs.software-univention.de/manual/5.0/de", None),
    "uv-kelvin": (
        "https://docs.software-univention.de/ucsschool-kelvin-rest-api/",
        None,
    ),
    "uv-performance": (
        "https://docs.software-univention.de/ext-performance/5.0/en/",
        None,
    ),
    "python-docs": ("https://docs.python.org/3.7/", None),
    "veyon-docs": ("https://docs.veyon.io/de/latest", None),
}

linkcheck_allowed_redirects = {
    r"https://support\.microsoft\.com/kb/\d+": r"https://(support|docs)\.microsoft\.com/en-(us|US)/.+",
    r"https://help\.univention\.com/t/\d+": r"https://help\.univention\.com/t/[\w-]+/\d+",
}
