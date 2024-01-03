#!/bin/bash
#
# Univention UCS@school italc-windows
#
# Copyright 2013-2024 Univention GmbH
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
#
# ### SETTINGS ##############################
#

REPOUSER=""
REPODIR="/root/mingw-repo"
BUILDDIR="/root/src/italc"
CROSSCOMPILER="192.168.0.10:/var/univention/buildsystem2/contrib/iTALC-mingw-xenial/*/*/*.deb"
SVN_ITALC="192.168.0.3/var/svn/dev/branches/ucs-4.2/ucs-school-4.2/italc-windows"
TIMESERVER="192.168.0.3"

#
# ###########################################
#

if [ -z "$1" -a -z "$REPOUSER" ] || [ "$1" = "--help" -o "$1" = "-h" ] ; then
	echo "$(basename "$0") <USERNAME>"
	echo "Please pass an username as first argument for login on server	omar"
	exit 1
fi

[ -z "$REPOUSER" ] && REPOUSER="$1"

#
# prepare local repo
#
if [ ! -d "$REPODIR" ] ; then
	mkdir -p "$REPODIR"
	echo "Please enter ${REPOUSER}'s password for scp access to the crosscompiler:"
	scp "${REPOUSER}@${CROSSCOMPILER}" "$REPODIR"
	cd "$REPODIR"
	apt-ftparchive packages . > Packages
	gzip < Packages > Packages.gz
	echo "# repo for cross compiler" >> /etc/apt/sources.list.d/italc-crosscompiler.list
	echo "deb file://${REPODIR}/ ./" >> /etc/apt/sources.list.d/italc-crosscompiler.list
fi

#
# prepare build environment
#
apt-get update
apt-get install -y --force-yes git subversion cmake nsis tofrodos gcj-jdk make
apt-get --no-install-recommends install -y --force-yes qt5base-mingw-w64 qt5tools-mingw-w64 gcc-mingw-w64 g++-mingw-w64 openssl-mingw-w64 libz-mingw-w64-dev libpng-mingw-w64 libjpeg-mingw-w64 qt4-linguist-tools

#
# get source
#
rm -Rf "$BUILDDIR"
mkdir -p "$(dirname "$BUILDDIR")"
echo "Please enter ${REPOUSER}'s password for SVN checkout:"
svn checkout "svn+ssh://${REPOUSER}@${SVN_ITALC}" "$BUILDDIR"

#
# build win32 version
#
cd "$BUILDDIR/italc.git/"
rm -Rf build32
mkdir -p build32
cd build32
../build_mingw32
make -j4
make win-nsi
cp *.exe ..

#
# build win64 version
#
cd "$BUILDDIR/italc.git/"
rm -Rf build64
mkdir -p build64
cd build64
../build_mingw64
make -j4
make win-nsi
cp *.exe ..

echo
echo
echo
echo "HINT: The italc windows binaries may be found in $BUILDDIR/italc.git/"
