#!/usr/bin/python2.6
# -*- coding: iso-8859-15 -*-
#
# UCS@school lib
#  module: Role specific shares
#
# Copyright 2014 Univention GmbH
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

import os
import sys
import grp
import subprocess
import univention.config_registry
from ucsschool.lib.roles import role_pupil, role_teacher, role_staff
from ucsschool.lib.i18n import ucs_school_name_i18n
from ucsschool.lib.schoolldap import get_all_local_searchbases, LDAP_Connection, MACHINE_READ, USER_READ, USER_WRITE, set_credentials
import univention.admin.uexceptions
import univention.admin.uldap as udm_uldap
import univention.admin.modules as udm_modules
udm_modules.update()

def roleshare_name(role, school_ou, ucr):
	custom_roleshare_name = ucr.get('ucsschool/import/roleshare/%s' % (role,))
	if custom_roleshare_name:
		return custom_roleshare_name
	else:
		return "-".join((ucs_school_name_i18n(role), school_ou))

def roleshare_path(role, school_ou, ucr):
	custom_roleshare_path = ucr.get('ucsschool/import/roleshare/%s/path' % (role,))
	if custom_roleshare_path:
		return custom_roleshare_path
	else:
		return os.path.join(school_ou, ucs_school_name_i18n(role))

def roleshare_home_subdir(school_ou, roles, ucr=None):
	if not ucr:
		ucr = univention.config_registry.ConfigRegistry()
		ucr.load()
		
	if ucr.is_true('ucsschool/import/roleshare', True):
		for role in (role_pupil, role_teacher, role_staff):
			if role in roles:
				return roleshare_path(role, school_ou, ucr)
	return ''


@LDAP_Connection(MACHINE_READ)
def get_gid_from_groupname(groupname, ucr=None, ldap_machine_read=None, ldap_position=None, search_base=None):
	if not ucr:
		ucr = univention.config_registry.ConfigRegistry()
		ucr.load()

	udm_filter = '(name=%s)' % (groupname,)
	udm_module_name = 'groups/group'
	udm_modules.init(ldap_machine_read, ldap_position, udm_modules.get(udm_module_name))
	try:
		group = udm_modules.lookup(udm_module_name, None, ldap_machine_read, filter=udm_filter, base=ucr['ldap/base'], scope='sub')[0]
	except IndexError as ex:
		return None
	return group['gidNumber']

@LDAP_Connection(USER_READ, USER_WRITE)
def create_roleshare(role, school_ou, share_container, ucr=None, ldap_user_read=None, ldap_user_write=None, ldap_position=None, search_base=None):
	if not ucr:
		ucr = univention.config_registry.ConfigRegistry()
		ucr.load()
		
	teacher_groupname = "-".join((ucs_school_name_i18n(role_teacher), school_ou))
	teacher_gid = get_gid_from_groupname(teacher_groupname, ucr)
	if not teacher_gid:
		raise univention.admin.uexceptions.noObject, "Group not found: %s." % teacher_groupname

	try:
		udm_module_name = 'shares/share'
		udm_modules.init(ldap_user_write, ldap_position, udm_modules.get(udm_module_name))
		share_container = udm_uldap.position(share_container)
		udm_obj = udm_modules.get(udm_module_name).object(None, ldap_user_write, share_container)
		udm_obj.open()
		udm_obj["name"] = roleshare_name(role, school_ou, ucr)
		udm_obj["path"] = os.path.join("/home", roleshare_path(role, school_ou, ucr))
		udm_obj["host"] = "%(hostname)s.%(domainname)s" % ucr
		udm_obj["group"] = teacher_gid
		udm_obj["sambaWriteable"] = 0
		udm_obj["sambaValidUsers"] = '@"%s"' % (teacher_groupname,)
		udm_obj["sambaCustomSettings"] = [("admin users", '@"%s"' % (teacher_groupname,))]
		udm_obj.create()
	except univention.admin.uexceptions.objectExists, dn:
		pass

def create_roleshares(role_list, ucr=None):
	if not ucr:
		ucr = univention.config_registry.ConfigRegistry()
		ucr.load()
		
	for searchbase in get_all_local_searchbases():
		school_ou = searchbase.school
		share_container = searchbase.shares
		for role in role_list:
			create_roleshare(role, school_ou, share_container, ucr)

if __name__ == '__main__':
	from optparse import OptionParser
	parser = OptionParser()
	parser.add_option("--setup", dest="setup",
		help="setup directories",
		action="store_true", default=False)
	parser.add_option("--binddn", dest="binddn",
		help="udm binddn")
	parser.add_option("--bindpwd", dest="bindpwd",
		help="udm bindpwd")
	(opts, args) = parser.parse_args()

	ucr = univention.config_registry.ConfigRegistry()
	ucr.load()

	set_credentials(opts.binddn, opts.bindpwd)
		
	if opts.setup:
		if ucr.is_true('ucsschool/import/roleshare', True):
			create_roleshares([role_pupil, role_teacher, role_staff], ucr)
