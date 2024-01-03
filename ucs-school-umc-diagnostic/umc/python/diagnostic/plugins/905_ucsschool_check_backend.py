#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
#
# UCS@school Diagnosis Module
#
# Copyright 2019-2024 Univention GmbH
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
#
# This module checks if the hosts role is either a master, slave or backup
# domain controller and samba4 is installed (Bug #50503)

from __future__ import absolute_import

import subprocess

from univention.lib.i18n import Translation
from univention.management.console.config import ucr
from univention.management.console.modules.diagnostic import Problem

_ = Translation("ucs-school-umc-diagnostic").translate
title = _("UCS@school Check if Samba4 is installed")
description = "\n".join(
    [
        _(
            "UCS@school: Test that checks if Samba4 is installed on a single master or on a school "
            "server in a multi-server-environment."
        ),
    ]
)


def run(_umc_instance):
    server_role = ucr["server/role"]
    if server_role == "domaincontroller_backup":
        return
    if server_role == "domaincontroller_master" and ucr.is_false("ucsschool/singlemaster", default=True):
        # not a single master
        return
    if server_role == "domaincontroller_slave":
        host_dn = ucr["ldap/hostdn"]
        lo = _umc_instance.get_user_ldap_connection()
        edu_dc_dns = lo.getAttr(
            "cn=DC-Edukativnetz,cn=ucsschool,cn=groups,{}".format(ucr["ldap/base"]), "uniqueMember"
        )
        admin_dc_dns = lo.getAttr(
            "cn=DC-Verwaltungsnetz,cn=ucsschool,cn=groups,{}".format(ucr["ldap/base"]), "uniqueMember"
        )
        if not any(host_dn in dns for dns in [edu_dc_dns, admin_dc_dns]):
            # not a school server
            return

    cmd = ["/usr/bin/dpkg-query", "-W", "-f", "${Status},${Version}", "samba"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec
    stdout, stderr = p.communicate()
    installed, version = stdout.split(",")
    is_installed = "ok installed" in installed
    is_correct_version = ":4." in version
    if ucr.get("dns/backend") != "samba4" or not is_installed:
        raise Problem("Samba4 is not installed correctly on this server.")
    elif not is_correct_version:
        raise Problem("Samba is installed but outdated.")


if __name__ == "__main__":
    run(None)
