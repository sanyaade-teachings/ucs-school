# Univention UCS@school
#
# Copyright 2007-2024 Univention GmbH
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

from __future__ import absolute_import

import os
import shutil
import signal
import subprocess

import ldap
import listener
from ldap.filter import filter_format

import univention.admin.modules
import univention.debug
from ucsschool.netlogon import SqliteQueue, get_netlogon_path_list
from univention.admin.uldap import getMachineConnection

try:
    from typing import Dict, List, Optional
except ImportError:
    pass

univention.admin.modules.update()
users_user_module = univention.admin.modules.get("users/user")
groups_group_module = univention.admin.modules.get("groups/group")
shares_share_module = univention.admin.modules.get("shares/share")

name = "ucs-school-user-logonscript"
description = "Create user-specific netlogon-scripts"
filter = (
    "(|"
    "(&(uid=*)(objectClass=sambaSamAccount)(!(uid=*$)))"
    "(objectClass=univentionGroup)"
    "(objectClass=univentionShare)"
    ")"
)
attributes = []  # type: List[str]

FN_PID = "/var/run/ucs-school-user-logonscript-daemon.pid"
lo = None  # type: Optional[univention.admin.uldap.access]


class Log(object):
    @classmethod
    def debug(cls, msg):  # type: (str) -> None
        cls.emit(univention.debug.ALL, msg)

    @staticmethod
    def emit(level, msg):  # type: (str) -> None
        univention.debug.debug(univention.debug.LISTENER, level, "{}: {}".format(name, msg))

    @classmethod
    def error(cls, msg):  # type: (str) -> None
        cls.emit(univention.debug.ERROR, msg)

    @classmethod
    def info(cls, msg):  # type: (str) -> None
        cls.emit(univention.debug.INFO, msg)

    @classmethod
    def process(cls, msg):  # type: (str) -> None
        cls.emit(univention.debug.PROCESS, msg)

    @classmethod
    def warn(cls, msg):  # type: (str) -> None
        cls.emit(univention.debug.WARN, msg)


def relevant_change(
    old, new, attr_list
):  # type: (Dict[str,List[str]], Dict[str,List[str]], List[str]) -> bool
    """
    Check for differences between old and new.

    :param dict old: attribute dictionary
    :param dict new:  attribute dictionary
    :param list attr_list:  list of attribute names (case sensitive!)
    :return: True, if any attribute specified in attr_list differs between old and new, otherwise False.
    :rtype: bool
    """
    return any(set(old.get(attr, [])) != set(new.get(attr, [])) for attr in attr_list)


def handle_share(dn, new, old, lo, user_queue):
    # type: (str, Dict[str,List[str]], Dict[str,List[str]], univention.admin.uldap.access, SqliteQueue) -> None  # noqa: E501
    """
    Handles changes of share objects by triggering group changes for the relevant groups.
    """

    def add_group_change_to_queue(gidNumber):  # type: (str) -> None
        if not gidNumber:
            Log.warn("handle_share: no gidNumber specified")
            return
        filter_s = filter_format("(gidNumber=%s)", (gidNumber,))
        Log.info("handle_share: looking for %s" % (filter_s,))
        try:
            grplist = groups_group_module.lookup(None, lo, filter_s=filter_s)
            # use only first group of search result (should be only one)
            grp = grplist[0]
        except (univention.admin.uexceptions.noObject, IndexError):
            Log.info(
                "handle_share: cannot find group with %s - may have already been deleted" % (filter_s,)
            )
            return
        Log.info("handle_share: trigger group change for %s" % (grp.dn,))
        handle_group(grp.dn, grp.oldattr, {}, lo, user_queue)

    if not old and new:
        # update all members of new group
        add_group_change_to_queue(new.get("univentionShareGid", [None])[0])
    elif old and not new:
        # update all members of old group
        add_group_change_to_queue(old.get("univentionShareGid", [None])[0])
    if old and new:
        attr_list = [
            "univentionShareSambaName",
            "univentionShareHost",
            "univentionShareGid",
        ]
        if not relevant_change(old, new, attr_list):
            Log.info("handle_share: no relevant attribute change")
            return
        # update all members of old and new group
        add_group_change_to_queue(old.get("univentionShareGid", [None])[0])
        add_group_change_to_queue(new.get("univentionShareGid", [None])[0])


def handle_group(dn, new, old, lo, user_queue):
    # type: (str, Dict[str,List[str]], Dict[str,List[str]], univention.admin.uldap.access, SqliteQueue) -> None  # noqa: E501
    """
    Handles group changes by adding relevant user object DNs to the user queue.
    """
    old_members = set(old.get("uniqueMember", []))
    new_members = set(new.get("uniqueMember", []))
    Log.info("handle_group: dn: %s" % (dn,))
    newGidNumber = new.get("gidNumber", [""])[0]
    if new and newGidNumber:
        # performance optimization:
        # the group members only have to be processed if there is at least one share object
        # that is using this group.
        filter_s = filter_format("(univentionShareGid=%s)", (newGidNumber,))
        try:
            share_list = shares_share_module.lookup(None, lo, filter_s=filter_s)
            found = bool(share_list)
        except (univention.admin.uexceptions.noObject, IndexError):
            found = False
        if not found:
            Log.info(
                "handle_group: cannot find share that uses gid=%s - skipping group" % (newGidNumber,)
            )
            return
    Log.info("handle_group: difference: %r" % (old_members.symmetric_difference(new_members),))
    # get set of users that are NOT IN BOTH user sets (==> the difference between both sets)
    # "uid=" to filter out computer or group objects (computers in groups resp. groups in groups)
    user_queue.add(
        [
            (user_dn, None)
            for user_dn in old_members.symmetric_difference(new_members)
            if user_dn.startswith("uid=")
        ]
    )


def handle_user(dn, new, old, lo, user_queue):
    # type: (str, Dict[str,List[str]], Dict[str,List[str]], univention.admin.uldap.access, SqliteQueue) -> None  # noqa: E501
    """
    Handles user changes by adding the DN of the user object to the user queue.
    """
    Log.info("handle_user: add %s" % (dn,))
    if old and new:
        attr_list = [
            "uid",
            "gidNumber",
            "homeDirectory",
        ]
        if not relevant_change(old, new, attr_list):
            Log.debug("no relevant attribute has changed - skipping user object")
            return
    username = new.get("uid", old.get("uid", [None]))[0]
    user_queue.add([(dn, username)])


def handler(dn, new, old):  # type: (str, Dict[str,List[str]], Dict[str,List[str]]) -> None
    global lo
    attrs = new if new else old

    listener.setuid(0)
    try:
        if lo is None:
            # establish connection to local LDAP server
            lo = getMachineConnection(ldap_master=False)[0]
        user_queue = SqliteQueue(logger=Log)

        # identify object
        if users_user_module.identify(dn, attrs):
            handle_user(dn, new, old, lo, user_queue)
        elif groups_group_module.identify(dn, attrs):
            handle_group(dn, new, old, lo, user_queue)
        elif shares_share_module.identify(dn, attrs):
            handle_share(dn, new, old, lo, user_queue)
        else:
            Log.error("handler: unknown object type: dn: %r\nold=%s\nnew=%s" % (dn, old, new))

        pid = None
        try:
            if os.path.isfile(FN_PID):
                content = open(FN_PID, "r").read().strip()
                try:
                    pid = int(content)
                except ValueError:
                    Log.error("%s does not contain a valid PID (%r)" % (FN_PID, content))
        except (IOError, OSError) as exc:
            Log.error("failed to open and read %s: %s" % (FN_PID, exc))

        if pid is not None:
            # inform daemon about pending changes
            os.kill(pid, signal.SIGUSR1)
    except (univention.admin.uexceptions.ldapError, ldap.LDAPError):
        # if a LDAP error occured, invalidate the LDAP connection (just in case the connection is broken)
        if lo:
            lo.unbind()
            lo = None
        raise
    finally:
        listener.unsetuid()


def postrun():  # type: () -> None
    # invalidate/close LDAP connection after 15seconds of idle time
    global lo
    if lo:
        lo.unbind()
        lo = None


def initialize():  # type: () -> None
    listener.setuid(0)
    try:
        for path in get_netlogon_path_list():
            if not os.path.exists(path):
                os.makedirs(path)

            # copy the umc icon to the netlogon share, maybe there is a better way? ...
            if not os.path.isfile(os.path.join(path, "univention-management-console.ico")):
                shutil.copy(
                    "/usr/share/ucs-school-netlogon-user-logonscripts/univention-management-console.ico",
                    path,
                )
    finally:
        listener.unsetuid()


def run_daemon(cmd):  # type: (List[str]) -> None
    cmd_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec
    cmd_out, cmd_err = cmd_proc.communicate()
    if cmd_proc.returncode:
        Log.error(
            "Command {!r} returned with exit code {!r}. stdout={!r} stderr={!r}".format(
                cmd, cmd_proc.returncode, cmd_out, cmd_err
            )
        )


def clean():  # type: () -> None
    listener.setuid(0)
    try:
        Log.warn("Stopping logon script generator daemon...")
        run_daemon(["systemctl", "stop", "ucs-school-netlogon-user-logonscripts.service"])
        Log.warn("Deleting all *.vbs scripts in {!r}...".format(get_netlogon_path_list()))
        for path in get_netlogon_path_list():
            if os.path.isdir(path):
                for filename in os.listdir(path):
                    filepath = os.path.join(path, filename)
                    if os.path.isfile(filepath) and filename.lower().endswith(".vbs"):
                        os.unlink(filepath)
            else:
                Log.info("{!r} does not exist or is no directory!".format(path))
        Log.warn("Purging SQLite DB...")
        SqliteQueue(logger=Log).truncate_database()
        Log.warn("Starting logon script generator daemon...")
        run_daemon(["systemctl", "start", "ucs-school-netlogon-user-logonscripts.service"])
    finally:
        listener.unsetuid()
