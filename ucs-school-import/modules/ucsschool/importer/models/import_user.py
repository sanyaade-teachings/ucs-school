# -*- coding: utf-8 -*-
#
# Univention UCS@School
"""
Representation of a user read from a file.
"""
# Copyright 2016 Univention GmbH
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


import random
import re
import string
import datetime
from collections import defaultdict

from univention.admin import property as uadmin_property
from ucsschool.lib.roles import role_pupil, role_teacher, role_staff
from ucsschool.lib.models import Staff, Student, Teacher, TeachersAndStaff, User
from ucsschool.importer.configuration import Configuration
from ucsschool.importer.factory import Factory
from ucsschool.importer.exceptions import BadPassword, FormatError, InvalidBirthday, InvalidEmail, MissingMailDomain, MissingMandatoryAttribute, MissingSchoolName, NoUsername, NoUsernameAtAll, UniqueIdError, UnkownDisabledSetting, UsernameToLong


class ImportUser(User):
	"""
	Representation of a user read from a file. Abstract class, please use one
	of its subclasses ImportStaff etc.

	An import profile and a factory must have been loaded, before the class
	can be used:

	from ucsschool.importer.configuration import Configuration
	from ucsschool.importer.factory import Factory, load_class
	config = Configuration("/usr/share/ucs-school-import/config_default.json")
	fac_class = load_class(config["factory"])
	factory = Factory(fac_class())
	user = factory.make_import_user(roles)
	"""
	config = None
	username_max_length = 15
	_unique_ids = defaultdict(set)

	def __init__(self, name=None, school=None, **kwargs):
		self.config = Configuration()
		self.action = None
		self.entry_count = -1
		self.udm_properties = dict()
		self.factory = Factory()
		self.ucr = self.factory.make_ucr()
		self.username_handler = None
		super(ImportUser, self).__init__(name, school, **kwargs)

	# def __str__(self):
	# 	return self.__unicode__().encode("ascii", "replace")
	#
	# def __unicode__(self):
	# 	return (u"name:{name}, school:{school}, action:{action} disabled:{disabled} entry_count:{entry_count}, dn:{DN}, "
	# 		"record_uid:{record_uid}, school_class:{school_class}, udm_properties:{udm_properties}".format(
	# 		DN=self.custom_dn or self.old_dn, **self.__dict__))

	def prepare_uids(self):
		"""
		Necessary preparation to detect if user exists in UCS.
		"""
		self.make_rid()
		self.make_sid()

	def prepare_properties(self, make_username=False):
		"""
		Necessary preparation to modify a user in UCS. Does not create a
		new username!
		"""
		self.prepare_uids()
		if make_username:
			self.make_username()
		self.make_school()
		self.make_classes()
		self.make_email()
		self.make_firstname()
		self.make_lastname()
		self.make_birthday()
		self.make_disabled()
		self.normalize_udm_properties()
		self.make_password()
		self.run_checks(check_username=make_username)

	def make_birthday(self):
		pass

	def make_classes(self):
		"""
		Create classes.
		"""
		# FIXME when/if self.school_class becomes a list instead of a string
		# if self.school_class and isinstance(self.school_class, basestring):
		# 	self.school_class = [c.strip() for c in self.school_class.split(",")]
		pass

	def make_disabled(self):
		if self.disabled is not None:
			return

		try:
			activate = self.config["activate_new_users"][self.role_sting]
		except KeyError:
			try:
				activate = self.config["activate_new_users"]["default"]
			except KeyError:
				raise UnkownDisabledSetting("Cannot find 'disabled' ('activate_new_users') setting for role '{}' or "
					"'default'.".format(self.role_sting), self.entry_count, import_user=self)
		self.disabled = not activate

	def make_firstname(self):
		pass

	def make_lastname(self):
		pass

	def make_email(self):
		"""
		Create email (if not already set).
		"""
		if True or not self.email:  # FIXME: forcing format_from_scheme() for testing purposes
			maildomain = self.config.get("maildomain")
			if not maildomain:
				try:
					maildomain = self.ucr["mail/hosteddomains"].split()[0]
				except (AttributeError, IndexError):
					raise MissingMailDomain("Could not retrieve mail domain from configuration nor from UCRV "
						"mail/hosteddomains.", entry=self.entry_count, import_user=self)
			self.email = self.format_from_scheme("email", self.config["scheme"]["email"], maildomain=maildomain).lower()

	def make_password(self):
		"""
		Create random password.
		"""
		pw = list(random.choice(string.lowercase))
		pw.append(random.choice(string.uppercase))
		pw.append(random.choice(string.digits))
		pw.append(random.choice(u"@#$%^&*-_+=[]{}|\:,.?/`~();"))
		pw.extend(random.choice(string.ascii_letters + string.digits + u"@#$%^&*-_+=[]{}|\:,.?/`~();")
			for _ in range(self.config["password_length"] - 4))
		random.shuffle(pw)
		self.password = u"".join(pw)

	def make_rid(self):
		"""
		Create ucsschoolRecordUID (rid).
		"""
		if not self.record_uid:
			self.record_uid = self.format_from_scheme("rid", self.config["scheme"]["rid"])

	def make_sid(self):
		"""
		Set the ucsschoolSourceUID (sid)
		"""
		if not self.source_uid:
			self.source_uid = self.config["sourceUID"]

	def make_school(self):
		"""
		Create school name.
		"""
		# TODO: support multiple schools, once implemented in lib
		if self.config.get("school"):
			self.school = self.config["school"]
		else:
			if not self.school:
				raise MissingSchoolName("School name was not set on the cmdline or in the configuration file and was "
					"not found in the source data.", entry=self.entry_count, import_user=self)

	def make_username(self):
		"""
		Create username.
		[ALWAYSCOUNTER] and [COUNTER2] are supported, but only one may be used
		per name.
		"""
		if self.name:
			return
		try:
			self.name = self.udm_properties["username"]
			return
		except KeyError:
			pass
		self.name = self.format_from_scheme("username", self.username_scheme)
		if not self.username_handler:
			self.username_handler = self.factory.make_username_handler(self.username_max_length)
		self.name = self.username_handler.format_username(self.name)

	@staticmethod
	def normalize(s):
		"""
		Normalize string (german umlauts etc)

		:param s: str
		:return: str: normalized s
		"""
		if isinstance(s, basestring):
			for umlaut, code in uadmin_property.UMLAUTS.items():
				s = s.replace(umlaut, code)
			return s.encode("ascii", "replace")
		else:
			return s

	def normalize_udm_properties(self):
		"""
		Normalize data in self.udm_properties.
		"""
		def normalize_recursive(item):
			if isinstance(item, dict):
				for k, v in item.items():
					item[k] = normalize_recursive(v)
				return item
			elif isinstance(item, list):
				for part in item:
					normalize_recursive(part)
				return item
			else:
				return ImportUser.normalize(item)

		for k, v in self.udm_properties.items():
			self.udm_properties[k] = normalize_recursive(v)

	def run_checks(self, check_username=False):
		"""
		Run some self-tests.
		"""
		try:
			[self.udm_properties.get(ma) or getattr(self, ma) for ma in self.config["mandatory_attributes"]]
		except (AttributeError, KeyError) as exc:
			raise MissingMandatoryAttribute("A mandatory attribute was not set: {}.".format(exc),
				self.config["mandatory_attributes"], entry=self.entry_count, import_user=self)

		if len(self.password) < self.config["password_length"]:
			raise BadPassword("Password is shorter than {} characters.".format(self.config["password_length"]),
				entry=self.entry_count, import_user=self)

		if self.record_uid in self._unique_ids["rid"]:
			raise UniqueIdError("RecordUID '{}' has already been used in this import.".format(self.record_uid),
				entry=self.entry_count, import_user=self)
		self._unique_ids["rid"].add(self.record_uid)

		if check_username and not self.name:
			raise NoUsername("No username was created.", entry=self.entry_count, import_user=self)

		if check_username and len(self.name) > self.username_max_length:
			raise UsernameToLong("Username '{}' is longer than allowed.".format(self.name),
				entry=self.entry_count, import_user=self)

		if check_username and self.name in self._unique_ids["name"]:
			raise UniqueIdError("Username '{}' has already been used in this import.".format(self.name),
				entry=self.entry_count, import_user=self)
		self._unique_ids["name"].add(self.name)

		if self.email:
			# email_pattern:
			# * must not begin with an @
			# * must have >=1 '@' (yes, more than 1 is allowed)
			# * domain must contain dot
			# * all characters are allowed (international domains)
			email_pattern = r"[^@]+@.+\..+"
			if not re.match(email_pattern, self.email):
				raise InvalidEmail("Email adderss '{}' has invalid format.".format(self.email), entry=self.entry_count,
					import_user=self)

			if self.email in self._unique_ids["email"]:
				raise UniqueIdError("Email address '{}' has already been used in this import.".format(self.email),
					entry=self.entry_count, import_user=self)
			self._unique_ids["email"].add(self.email)

		if self.birthday:
			try:
				self.birthday = datetime.datetime.strptime(self.birthday, "%Y-%m-%d").isoformat()
			except ValueError as exc:
				raise InvalidBirthday("Birthday has invalid format: {}.".format(exc), entry=self.entry_count,
					import_user=self)

	@property
	def role_sting(self):
		if role_pupil in self.roles:
			return "student"
		elif role_teacher in self.roles:
			if role_staff in self.roles:
				return "teacher_and_staff"
			else:
				return "teacher"
		else:
			return "staff"

	@property
	def username_scheme(self):
		"""
		Fetch scheme for username for role.

		:return: str: scheme for the role from configuration
		"""
		try:
			scheme = unicode(self.config["scheme"]["username"][self.role_sting])
		except KeyError:
			try:
				scheme = unicode(self.config["scheme"]["username"]["default"])
			except KeyError:
				raise NoUsernameAtAll("Cannot find scheme to create username for role '{}' or 'default'.".format(
					self.role_sting), self.entry_count, import_user=self)
		return scheme

	def format_from_scheme(self, prop_name, scheme, **kwargs):
		"""
		Format property with scheme for current import_user.
		* Uses the replacement code from users:templates.
		* This does not do the counter variable replacements for username.

		:param prop_name: str: name of property (for error logging)
		:param scheme: str: scheme to use
		:param kwargs: dict: additional data to use for formatting
		:return: str: formatted string
		"""
		all_fields = self.to_dict().copy()
		all_fields.update(self.udm_properties)
		all_fields.update(kwargs)

		prop = uadmin_property("_replace")
		res = prop._replace(scheme, all_fields)
		if not res:
			raise FormatError("Could not create {prop_name} from scheme and input data. ".format(prop_name=prop_name),
				scheme=scheme, data=all_fields, entry=self.entry_count, import_user=self)
		return res

	@classmethod
	def get_class_for_udm_obj(cls, udm_obj, school):
		raise NotImplementedError()

	def update(self, other):
		for k, v in other.to_dict().items():
			if k == "name" and v is None:
				continue
			setattr(self, k, v)
		self.action = other.action
		self.entry_count = other.entry_count
		self.udm_properties.update(other.udm_properties)


class ImportStaff(ImportUser, Staff):
	@classmethod
	def get_class_for_udm_obj(cls, udm_obj, school):
		return cls


class ImportStudent(ImportUser, Student):
	@classmethod
	def get_class_for_udm_obj(cls, udm_obj, school):
		return cls


class ImportTeacher(ImportUser, Teacher):
	@classmethod
	def get_class_for_udm_obj(cls, udm_obj, school):
		return cls


class ImportTeachersAndStaff(ImportUser, TeachersAndStaff):
	@classmethod
	def get_class_for_udm_obj(cls, udm_obj, school):
		return cls
