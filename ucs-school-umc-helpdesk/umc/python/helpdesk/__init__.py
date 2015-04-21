#!/usr/bin/python2.7
#
# Univention Management Console
#  module: Helpdesk Module
#
# Copyright 2007-2015 Univention GmbH
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

from univention.management.console.log import MODULE
from univention.management.console.config import ucr
from univention.management.console.modules.decorators import simple_response, sanitize
from univention.management.console.modules.sanitizers import StringSanitizer

from univention.lib.i18n import Translation
from univention.admin.handlers.users.user import object as User

from ucsschool.lib import LDAP_Connection, SchoolBaseModule
from ucsschool.lib.models import School

import traceback
import notifier
import notifier.popen

import smtplib
import ldap

_ = Translation('ucs-school-umc-helpdesk').translate


def sanitize_header(header):
	for chr_ in '\x00\r\n':
		header = header.replace(chr_, u'?')
	return header


class Instance(SchoolBaseModule):

	@simple_response
	@LDAP_Connection()
	def configuration(self, ldap_user_read=None, ldap_position=None, search_base=None):
		ucr.load()
		MODULE.process('return configuration')
		username = self._username

		MODULE.info('username=%r school=%r' % (self._username, search_base.school))

		school = School.from_dn(School(search_base.school).dn, None, ldap_user_read)
		return {
			'username': username,
			'school': school.display_name,
			'recipient': ucr.get('ucsschool/helpdesk/recipient')
		}

	@sanitize(
		username=StringSanitizer(required=True),
		school=StringSanitizer(required=True),
		message=StringSanitizer(required=True),
		category=StringSanitizer(required=True),
	)
	@LDAP_Connection()
	def send(self, request, ldap_user_read=None, ldap_position=None, search_base=None):
		def _send_thread(sender, recipients, subject, message):
			MODULE.info('sending mail: thread running')

			msg = u'From: %s\r\n' % (sanitize_header(sender),)
			msg += u'To: %s\r\n' % (sanitize_header(', '.join(recipients)),)
			msg += u'Subject: =?UTF-8?Q?%s?=\r\n' % (sanitize_header(subject).encode('quopri'),)
			msg += u'Content-Type: text/plain; charset="UTF-8"\r\n'
			msg += u'\r\n'
			msg += message
			msg += u'\r\n'
			msg = msg.encode('UTF-8')

			server = smtplib.SMTP('localhost')
			server.set_debuglevel(0)
			server.sendmail(sender, recipients, msg)
			server.quit()

		def _send_return(thread, result, request):
			import traceback

			if not isinstance(result, BaseException):
				MODULE.info('sending mail: completed successfully')
				self.finished(request.id, True)
			else:
				msg = ''.join(traceback.format_exception(*thread.exc_info))
				MODULE.process('sending mail: An internal error occurred: %s' % (msg,))
				self.finished(request.id, False, message=msg, status=500)

		if ucr.get('ucsschool/helpdesk/recipient'):
			recipients = ucr['ucsschool/helpdesk/recipient'].split(' ')
			username = request.options['username']
			#username = self._username
			school = request.options['school']
			category = request.options['category']
			message = request.options['message']

			subject = u'%s (%s: %s)' % (category, _('School'), school)

			try:
				user = User(None, ldap_user_read, ldap_position, self._user_dn)
				user.open()
			except ldap.LDAPError:
				MODULE.error('Errror receiving user information: %s' % (traceback.format_exception(),))
				user = {
					'displayName': username,
					'mailPrimaryAddress': '',
					'mailAlternativeAddress': [],
					'e-mail': [],
					'phone': []
				}
			mails = set([user['mailPrimaryAddress']]) | set(user['mailAlternativeAddress']) | set(user['e-mail'])

			sender = user['mailPrimaryAddress']
			if not sender:
				if ucr.get('hostname') and ucr.get('domainname'):
					sender = 'ucsschool-helpdesk@%s.%s' % (ucr['hostname'], ucr['domainname'])
				else:
					sender = 'ucsschool-helpdesk@localhost'

			data = [
				(_('Sender'), u'%s (%s)' % (user['displayName'], username)),
				(_('School'), school),
				(_('Mail address'), u', '.join(mails)),
				(_('Phone number'), u', '.join(user['phone'])),
				(_('Category'), category),
				(_('Message'), u'\r\n%s' % (message,)),
			]
			msg = u'\r\n'.join(u'%s: %s' % (key, value) for key, value in data)

			MODULE.info('sending message: %s' % ('\n'.join(map(lambda x: repr(x.strip()), msg.splitlines()))),)

			func = notifier.Callback(_send_thread, sender, recipients, subject, msg)
			MODULE.info('sending mail: starting thread')
			thread = notifier.threads.Simple('HelpdeskMessage', func, notifier.Callback(_send_return, request))
			thread.run()
		else:
			MODULE.error('HELPDESK: cannot send mail - config-registry variable "ucsschool/helpdesk/recipient" is not set')
			self.finished(request.id, False, _('The email address for the helpdesk team is not configured.'))

	@LDAP_Connection()
	def categories(self, request, ldap_user_read=None, ldap_position=None, search_base=None):
		categories = []
		res = ldap_user_read.searchDn(filter='objectClass=univentionUMCHelpdeskClass', base=ldap_position.getBase())
		# use only first object found
		if res and res[0]:
			categories = ldap_user_read.getAttr(res[0], 'univentionUMCHelpdeskCategory')

		self.finished(request.id, map(lambda x: {'id': x, 'label': x}, categories))
