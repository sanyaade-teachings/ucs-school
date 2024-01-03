/*
 * Copyright 2014-2024 Univention GmbH
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
	"dojo/_base/array",
	"dojo/topic",
	"umc/widgets/SearchBox",
	"umc/widgets/ComboBox",
	"umc/modules/schoolwizards/ComputerWizard",
	"umc/modules/schoolwizards/Grid",
	"umc/i18n!umc/modules/schoolwizards"
], function(declare, lang, array, topic, SearchBox, ComboBox, ComputerWizard, Grid, _) {

	return declare("umc.modules.schoolwizards.ComputerGrid", [Grid], {

		headerText: _('Management of school computers'),
		helpText: '',
		objectNamePlural: _('computers'),
		objectNameSingular: _('computer'),
		firstObject: _('the first computer'),
		createObjectWizard: ComputerWizard,

		getGridColumns: function() {
			return [{
				name: 'name',
				label: _('Name')
			}, {
				name: 'type_name',
				label: _('Computer type')
			}, {
				name: 'ip_address',
				label: _('IP address')
			}, {
				name: 'mac_address',
				label: _('MAC address')
			}, {
				name: 'inventory_number',
				label: _('Inventory number')
			}];
		},

		getObjectIdName: function(item) {
			return item.name;
		},

		getSearchWidgets: function() {
			var schools = lang.clone(this.schools);
			if (schools.length > 1) {
				schools.unshift({id: '/', label: _('All')});
			}
			return [{
				type: ComboBox,
				size: 'TwoThirds',
				name: 'school',
				label: _('School'),
				staticValues: schools,
				autoHide: true
			}, {
				type: ComboBox,
				size: 'TwoThirds',
				name: 'type',
				label: _('Computer type'),
				dynamicValues: 'schoolwizards/computers/types',
				umcpCommand: lang.hitch(this, function() {
					return this.umcpCommand.apply(this.umcpCommand, arguments).then(function(response) {
						response.result.unshift({
							id: 'all',
							label: _('All')
						});
						return response;
					});
				}),
				sortDynamicValues: false
			}, {
				type: SearchBox,
				size: 'TwoThirds',
				name: 'filter',
				label: _('Filter'),
				inlineLabel: _('Search...'),
				onSearch: lang.hitch(this, function() {
					this._searchForm.submit();
				})
			}];
		},

		getSearchLayout: function() {
			return [['school', 'type', 'filter']];
		}
	});
});
