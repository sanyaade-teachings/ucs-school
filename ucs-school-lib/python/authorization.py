# -*- coding: utf-8 -*-
#
# Univention UCS@school
# Copyright 2016-2020 Univention GmbH
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

"""
Module for authorization checks for the ucsschool lib.
"""

try:
	# noinspection PyUnresolvedReferences
	from typing import List, Optional, Dict
except ImportError:
	pass

from univention.udm import UDM

DELIMITER = ' '


class RoleCapability:
	"""
	Represents a capacity that is attached to a role.
	The difference is the optional target role component.
	"""

	def __init__(self, name, display_name, target_role):  # type: (str, str, str) -> RoleCapability
		self._name = name
		self._display_name = display_name
		self._target_role = target_role

	@classmethod
	def from_str(cls, capability_str):  # type: (str) -> RoleCapability
		"""
		Parses a capability string how it would be attached to a ucsschool/role object in UDM.
		Example with whitespace delimiter: 'ucsschool/password_reset teacher'
		"""
		if DELIMITER in capability_str:
			name, target_role = capability_str.split(DELIMITER)
			return cls(name, name, target_role)
		else:
			return cls(capability_str, capability_str, '')

	def __eq__(self, other):
		return self._name == other.name and self._target_role == other.target_role

	def __repr__(self):
		return self.__str__()

	def __str__(self):
		return "{}{}{}".format(self._name, DELIMITER, self._target_role)

	@property
	def name(self):
		return self._name

	@property
	def target_role(self):
		return self._target_role

	def targets_role(self, role):  # type: (ContextRole) -> bool
		"""
		Checks if this RoleCapability targets a given role.
		True if the roles name equals the target_role or the target_role string is empty.
		False otherwise.
		"""
		return self._target_role in ('', role.name)


class ContextRole:
	"""
	Represents a role that is attached to a specific ucsschool object.
	Example: teacher:school:DEMOSCHOOL
	It is an instance of a ucschool/role UDM object
	"""

	def __init__(self, name, display_name, capabilities, context, context_type='school'):
		# type: (str, str, List[RoleCapability], str, Optional[str]) -> None
		self._name = name
		self._display_name = display_name
		self._capabilities = capabilities
		self._context = context
		self._context_type = context_type

	@classmethod
	def from_role_str(cls, role_str):  # type: (str) -> Optional[ContextRole]
		"""
		Creates a ContextRole object from a given role string.

		:param str role_str: a ``ucsschool_role`` string
		:return: ContextRole object or None if the role string is invalid or not found in LDAP
		:rtype: ContextRole or None
		"""
		raise NotImplementedError

	@classmethod
	def from_role_strings(cls, role_strings):  # type: (List[str]) -> List[ContextRole]
		"""
		Creates a list of ContextRole objects from a list of role strings.
		Invalid role strings are filtered out.

		:param str role_str: a ``ucsschool_role`` string
		:return: list of ContextRole objects
		:rtype: list(ContextRole)
		"""
		return [role for role in (cls.from_role_str(role_str) for role_str in role_strings) if role]

	def has_capability(self, capability_name):  # type: (str) -> bool
		"""
		Checks if the ContextRole has a RoleCapability with a given name.

		:param str capability_name: the name of a RoleCapability
		:return: whether this ContextRole object has a RoleCapability
		:rtype: bool
		"""
		return any(True for cap in self._capabilities if cap.name == capability_name)

	def get_capabilities(self, capability_name):  # type: (str) -> List[RoleCapability]
		"""
		Returns all RoleCapabilities with the given name that are attached to
		the ContextRole.

		:param str capability_name: the name of a RoleCapability
		:return: list of RoleCapabilities with name ``capability_name`` that
			are attached tothis ContextRole object
		:rtype: bool
		"""
		return [cap for cap in self._capabilities if cap.name == capability_name]

	@property
	def name(self):
		return self._name

	@property
	def capabilities(self):  # type: () -> List[RoleCapability]
		return self._capabilities

	@property
	def context(self):
		return self._context


def croles_from_dict(obj_dict):  # type: (Dict) -> List[ContextRole]
	"""
	Takes a dictionary and returns a list of ContextRoles by extracting the
	ucsschoolRole values from the dictionary.

	:param dict obj_obj_dict: dictionary with ucsschoolRole values
	:return: list of ContextRoles
	:rtype: list(ContextRole)
	"""
	role_strings = obj_dict.get('ucsschoolRole', [])
	return ContextRole.from_role_strings(role_strings)


def croles_from_dn(dn):  # type: (str) -> List[ContextRole]
	"""
	Takes a dn and returns a list of ContextRoles by extracting the ucsschoolRole values
	from the udm object identified by the dn.
	TODO: Remove from this module to keep it free from dependencies to UDM

	:param str dn: DN in LDAP
	:return: list of ContextRoles attached to LDAP object
	:rtype: list(ContextRole)
	"""
	udm = UDM.machine().version(1)
	udm_obj = udm.obj_by_dn(dn)
	try:
		role_strings = udm_obj.props.ucsschoolRole
	except AttributeError:
		return []
	return ContextRole.from_role_strings(role_strings)


def is_authorized(actor_context_roles, object_context_roles, capability_name):
	# type: (List[ContextRole], List[ContextRole], str) -> bool
	"""
	Check if actor is authorized to execute an action on an object.

	:param actor_context_roles: list of ContextRoles of the actor
	:type actor_context_roles: list(ContextRole)
	:param object_context_roles: list of ContextRoles of the object
	:type object_context_roles: list(ContextRole)
	:param str capability_name: the capability required for the action
	:return: whether the actor is allowed to to performce the desired action
	:rtype: bool
	"""
	effective_roles = []
	for role in actor_context_roles:
		a_capabilities = role.get_capabilities(capability_name)
		if not a_capabilities:  # We are just interested in roles that have the capability
			continue
		# We have to check that the roles that have the specified capability
		# also match in the context and target_role with any given ContextRole of the object
		affected_roles = [o_role for o_role in object_context_roles if role.context == o_role.context and any(
			True for cap in a_capabilities if cap.targets_role(o_role))]
		if affected_roles:
			effective_roles.append(role)
	# special handling will land here
	return len(effective_roles) > 0
