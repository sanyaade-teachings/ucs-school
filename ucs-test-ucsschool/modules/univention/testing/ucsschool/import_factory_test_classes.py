# -*- coding: utf-8 -*-
#
# UCS test
"""
Classes to test subclassing / factory code of import script
"""
# Copyright 2016-2024 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

# This module (univention.testing.ucsschool) tries to import ucsschool.lib.models.
# Without absolute_import python is looking for lib.modules within THIS file which
# is obviously wrong in this case.

from __future__ import absolute_import

import codecs
import json
import tempfile
import time

from ucsschool.importer.mass_import.mass_import import MassImport
from ucsschool.importer.mass_import.user_import import UserImport
from ucsschool.importer.utils.username_handler import UsernameHandler
from ucsschool.importer.writer.base_writer import BaseWriter
from ucsschool.importer.writer.new_user_password_csv_exporter import NewUserPasswordCsvExporter
from ucsschool.importer.writer.user_import_csv_result_exporter import UserImportCsvResultExporter
from univention.testing.ucsschool.ucs_test_school import get_ucsschool_logger

logger = get_ucsschool_logger()


class NullImport(MassImport):
    """
    This MassImport does not import users.
    """

    def import_users(self):
        self.logger.info("*** NullImport.import_users()")
        self.logger.info("------ NOT importing users. ------")


class UniventionPasswordExporter(NewUserPasswordCsvExporter):
    """
    Export password table as if all passwords were 'univention'.
    """

    def serialize(self, user):
        logger.info("*** UniventionPasswordExporter.serialize()")
        res = super(UniventionPasswordExporter, self).serialize(user)
        res["password"] = "univention"
        return res


class AnonymizeResultExporter(UserImportCsvResultExporter):
    """
    Export import job results with wrong names and birthday.
    """

    def serialize(self, obj):
        logger.info("*** AnonymizeResultExporter.serialize()")
        res = super(AnonymizeResultExporter, self).serialize(obj)
        res.update(dict(firstname="s3cr31", lastname="S3cr3t", birthday="1970-01-01"))
        return res


class BirthdayUserImport(UserImport):
    """
    Prevent deletion of users on their birthday.
    """

    def do_delete(self, user):
        self.logger.info("*** BirthdayUserImport.do_delete() user.birthday=%r", user.birthday)
        if user.birthday == time.strftime("%Y-%m-%d"):
            self.logger.info("Not deleting user %s on its birthday!", user)
            return True
        else:
            return super(BirthdayUserImport, self).do_delete(user)


class FooUsernameHandler(UsernameHandler):
    """
    Adds [FOO] modifier. Always appends "foo" to a username -> works only once per username!
    """

    @property
    def counter_variable_to_function(self):
        res = super(FooUsernameHandler, self).counter_variable_to_function
        res["[FOO]"] = self.foo_counter
        return res

    def foo_counter(self, name_base):
        logger.info("*** FooUsernameHandler.foo_counter")
        return "foo"


class JsonWriter(BaseWriter):
    """
    Crude JSON writer
    """

    def __init__(self, *arg, **kwargs):
        logger.info("*** JsonWrite.__init()")
        self._filename = None
        self._mode = None
        self._objects = []
        super(JsonWriter, self).__init__()

    def open(self, filename, mode="wb"):
        self._filename = filename
        self._mode = mode
        return tempfile.SpooledTemporaryFile(mode=mode)

    def write_obj(self, obj):
        self._objects.append(obj)
        with codecs.open(self._filename, self._mode, encoding="utf-8") as fp:
            json.dump(self._objects, fp, ensure_ascii=False)
