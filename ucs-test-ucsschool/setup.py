#!/usr/bin/env python

import io
from distutils.core import setup
from email.utils import parseaddr
from debian.changelog import Changelog
from debian.deb822 import Deb822

dch = Changelog(io.open("debian/changelog", "r", encoding="utf-8"))
dsc = Deb822(io.open("debian/control", "r", encoding="utf-8"))
realname, email_address = parseaddr(dsc["Maintainer"])

setup(
    packages=["univention.testing.ucsschool"],
    package_dir={"": "modules"},
    description="Sections for ucs-test that test UCS@school.",
    url="https://www.univention.de/",
    license="GNU Affero General Public License v3",
    name=dch.package,
    version=dch.version.full_version,
    maintainer=realname,
    maintainer_email=email_address,
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Testing"
    ],
)
