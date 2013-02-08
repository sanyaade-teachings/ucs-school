#!/bin/bash
#
# Copyright (C) 2012-2013 Univention GmbH
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

UPDATER_LOG="/var/log/univention/updater.log"
UPDATE_STATE="$1"
UPDATE_NEXT_VERSION="$2"
export DEBIAN_FRONTEND=noninteractive
exec 3>>"$UPDATER_LOG"
eval "$(univention-config-registry shell)" >&3 2>&3

echo "Running ucsschool 3.1 preup.sh script" >&3
date >&3

# prevent update on inconsistent system
if ! dpkg-query -W -f '${Package} ${Status}\n' univention-samba4 2>&3 | grep "ok installed" >&3 ; then
	if dpkg-query -W -f '${Package} ${Status}\n' python-samba4 libsamdb0 2>&3 | grep "ok installed" >&3 ; then
		echo "ERROR: inconsistent state: univention-samba4 is not installed but python-samba4/libsamdb0 is."
		echo "ERROR: continuing update would break update path - stopping update here"
		exit 1
	fi
fi

echo "ucsschool 3.1 preup.sh script finished" >&3
date >&3

exit 0

