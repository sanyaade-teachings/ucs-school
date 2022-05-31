#!/usr/share/ucs-test/runner python3
## -*- coding: utf-8 -*-
## desc: Import computers via python API
## tags: [apptest,ucsschool,ucsschool_import1]
## roles: [domaincontroller_master]
## exposure: dangerous
## packages:
##   - ucs-school-import

from univention.testing.ucsschool.importcomputers import import_computers_basics

if __name__ == "__main__":
    import_computers_basics(use_cli_api=False, use_python_api=True)
