/*
 * Copyright 2015-2024 Univention GmbH
 *
 * http://www.univention.de/
 *
 * All rights reserved.
 *
 * The source code of this program is made available
 * under the terms of the GNU Affero General Public License version 3
 * (GNU AGPL V3) as published by the Free Software Foundation.
 *
 * Binary versions of this program provided by Univention to you as
 * well as other copyrighted, protected or trademarked materials like
 * Logos, graphics, fonts, specific documentations and configurations,
 * cryptographic keys etc. are subject to a license agreement between
 * you and Univention and not subject to the GNU AGPL V3.
 *
 * In the case you use this program under the terms of the GNU AGPL V3,
 * the program is provided in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public
 * License with the Debian GNU/Linux or Univention distribution in file
 * /usr/share/common-licenses/AGPL-3; if not, see
 * <http://www.gnu.org/licenses/>.
 */
/*global define*/

define([
	"dojo/_base/declare",
	"dojo/_base/lang",
	"umc/widgets/MultiObjectSelect",
	"umc/widgets/TextBox",
	"umc/widgets/ComboBox",
	"umc/modules/schoolgroups/DetailPage",
	"umc/i18n!umc/modules/schoolgroups"
], function(declare, lang, MultiObjectSelect, TextBox, ComboBox, DetailPage, _) {

	return declare("umc.modules.schoolgroups.ClassDetailPage", [DetailPage], {
		getWidgets: function() {
			return [{
				type: ComboBox,
				name: 'school',
				label: _('School'),
				staticValues: []
			}, {
				type: TextBox,
				name: 'name',
				label: _('Class'),
				disabled: true
			}, {
				type: TextBox,
				name: 'description',
				label: _('Description'),
				disabled: true
			}, this.getMultiSelectWidget()];
		},

		getMultiSelectWidget: function() {
			return lang.mixin(this.inherited(arguments), {
				label: _('Teachers'),
				description: _('List of teachers which are member of the specified class'),
				queryOptions: function() {
					return { group: 'teacher' };
				}
			});
		},

		getMultiSelectGroup: function() {
			return lang.mixin(this.inherited(arguments), {
				staticValues: [{id: 'teacher', label: _('All teachers')}]
			});
		}

	});
});
