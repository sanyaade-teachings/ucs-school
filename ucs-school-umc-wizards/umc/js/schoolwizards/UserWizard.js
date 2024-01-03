/*
 * Copyright 2012-2024 Univention GmbH
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
	"umc/tools",
	"umc/widgets/TextBox",
	"umc/widgets/ComboBox",
	"umc/widgets/MultiInput",
	"umc/widgets/CheckBox",
	"umc/widgets/DateBox",
	"umc/widgets/PasswordInputBox",
	"umc/modules/schoolwizards/Wizard",
	"umc/modules/schoolwizards/utils",
	"umc/i18n!umc/modules/schoolwizards"
], function(declare, lang, array, topic, tools, TextBox, ComboBox, MultiInput, CheckBox, DateBox, PasswordInputBox, Wizard, utils, _) {

	return declare("umc.modules.schoolwizards.UserWizard", [Wizard], {
		description: _('Create a new user'),

		_examUserPrefix: 'exam-',
		_maxUsernameLength: 15,
		_checkMaxUsernameLength: "true",
		_optionalVisibleFields: [],

		_isOptionalFieldVisible: function(fieldName) {
			return array.indexOf(this._optionalVisibleFields, fieldName) > -1;
		},

		loadVariables: function() {
			return tools.ucr([
				'ucsschool/ldap/default/userprefix/exam',
				'ucsschool/ldap/check/username/lengthlimit',
				'ucsschool/username/max_length',
				'ucsschool/wizards/schoolwizards/users/optional_visible_fields'
			]).then(lang.hitch(this, function(result) {
				// cache the user prefix and update help text
				this._examUserPrefix = result['ucsschool/ldap/default/userprefix/exam'] || 'exam-';
				this._checkMaxUsernameLength = result['ucsschool/ldap/check/username/lengthlimit'] || "true";
				this._maxUsernameLengthUcr = result['ucsschool/username/max_length'] || 20;
				this._maxUsernameLength = this._maxUsernameLengthUcr - this._examUserPrefix.length;
				var optionalVisibleFieldsStr = result['ucsschool/wizards/schoolwizards/users/optional_visible_fields'] || '';
				this._optionalVisibleFields = optionalVisibleFieldsStr.split(' ');
			}));
		},

		getGeneralPage: function() {
			var page = this.inherited(arguments);
			page.widgets.push({
				type: ComboBox,
				name: 'type',
				label: _('Role'),
				sortDynamicValues: false,
				dynamicValues: utils.getStaticValuesUserRolesWithoutAll
			});
			page.layout.push('type');
			return page;
		},

		getItemPage: function() {
			return {
				name: 'item',
				headerText: this.description,
				helpText: this.editMode ? _('Enter details of the user') : _('Enter details to create a new user'),
				buttons: [{
					name: 'newClass',
					label: _('Create a new class'),
					callback: lang.hitch(this, function() {
						topic.publish('/umc/modules/open', 'schoolwizards', 'schoolwizards/classes');
					})
				}],
				widgets: [{
					type: MultiInput,
					name: 'schools',
					label: _('Schools'),
					initialValue: [this.selectedSchool],
					disabled: true,
					subtypes: [{
						type: TextBox,
					}]
				}, {
					type: MultiInput,
					name: 'ucsschool_roles',
					label: _('UCS@school roles'),
					initialValue: [],
					disabled: true,
					subtypes: [{
						type: TextBox,
					}]
				}, {
					type: TextBox,
					name: 'firstname',
					label: _('Firstname'),
					required: true
				}, {
					type: CheckBox,
					name: 'disabled',
					label: _('Disabled'),
					required: true
				}, {
					type: DateBox,
					name: 'birthday',
					label: _('Birthday'),
					required: false
				}, {
					type: DateBox,
					name: 'expiration_date',
					label: _('Expiration date'),
					required: false
				},
				 {
					type: TextBox,
					name: 'lastname',
					label: _('Lastname'),
					required: true
				}, {
					type: TextBox,
					name: 'name',
					label: _('Username'),
					disabled: this.editMode,
					required: true,
					validator: lang.hitch(this, function(value) {
						if (tools.isTrue(this._checkMaxUsernameLength)) {
							var widget = this.getWidget('item', 'name');
							if (widget) {
								widget.set('invalidMessage', _('Microsoft Active Directory limits usernames to 20 characters. To prevent logon problems with exam user accounts, usernames must not be longer than %s characters. Please choose a shorter username.', this._maxUsernameLength));
							}
							return value.length <= this._maxUsernameLength;
						}
						return true;
					}),
					invalidMessage: _('Microsoft Active Directory limits usernames to 20 characters. To prevent logon problems with exam user accounts, usernames must not be longer than %s characters. Please choose a shorter username.', this._maxUsernameLength)
				}, {
					type: ComboBox,
					name: 'school_classes',
					sortStaticValues: true,
					label: _('Class')
				}, {
					type: TextBox,
					name: 'email',
					label: _('E-Mail')
				}, {
					type: PasswordInputBox,
					name: 'password',
					label: _('Password'),
					focus: lang.hitch(this, function() {
						// just a workaround for Bug #30110
						var widget = this.getWidget('item', 'password');
						if (! widget._firstWidget.get('value')) {
							widget._firstWidget.focus();
						} else {
							widget._secondWidget.focus();
						}
					}),
					validate: lang.hitch(this, function() {
						// ...and another one for Bug #30109
						return this.getWidget('item', 'password').isValid();
					})
				}],
				layout: [
					['firstname', 'lastname'],
					['disabled'],
					['name', 'birthday'],
					['school_classes', 'newClass'],
					['email', 'expiration_date'],
					['password'],
					['schools', 'ucsschool_roles'],
				]
			};
		},

		restart: function() {
			tools.forIn(this.getPage('item')._form._widgets, function(iname, iwidget) {
				if (iname === 'password') {
					iwidget._setValueAttr(null);
				} else if (iname !== 'school_classes' && iwidget.reset) {
					iwidget.reset();
				}
			});
			this.inherited(arguments);
		},

		addNote: function() {
			var name = this.getWidget('item', 'name').get('value');
			var message = _('User "%s" has been successfully created. Continue to create another user or press "Cancel" to close this wizard.', name);
			this.getPage('item').clearNotes();
			this.getPage('item').addNote(message);
		},

		updateWidgets: function(/*String*/ currentPage) {
			if (currentPage === 'general') {
				var classBox = this.getWidget('item', 'school_classes');
				var newClassButton = this.getPage('item')._form.getButton('newClass');
				array.forEach(['schools', 'ucsschool_roles', 'birthday', 'disabled', 'password', 'email', 'expiration_date'], function(fieldName) {
					var optionalWidget = this.getWidget('item', fieldName);
					optionalWidget.set('visible', this._isOptionalFieldVisible(fieldName));
				}, this)
				if (!this.hasClassWidget()) {
					classBox.set('value', null);
					classBox.set('required', false);
					classBox.hide();
					newClassButton.hide();
				} else {
					classBox.set('required', true);
					classBox.show();
					newClassButton.show();
					this.reloadClasses();
				}
			}
		},

		onShow: function() {
			this.reloadClasses();
		},

		hasClassWidget: function() {
			var selectedType = this.getWidget('general', 'type').get('value');
			return selectedType == 'student';
		},

		getValues: function() {
			var values = this.inherited(arguments);
			var school = this.selectedSchool;
			if (!this.hasClassWidget()) {
				delete values.school_classes;
			} else {
				var school_class = values.school_classes;
				if (this.loadedValues) {
					values.school_classes = this.loadedValues.school_classes;
				} else {
					values.school_classes = {};
				}
				if (!values.school_classes[school]) {
					values.school_classes[school] = [null];
				}
				values.school_classes[school][0] = school_class;
			}
			return values;
		},

		reloadClasses: function() {
			var school = this.selectedSchool;
			if (!school || !this.hasClassWidget()) {
				return;
			}
			this.umcpCommand('schoolwizards/classes', {'school': school}).then(lang.hitch(this, function(response) {
				var classes = array.map(response.result, function(item) {
					return {
						id: tools.explodeDn(item.id, true)[0],
						label: item.label
					};
				});
				var widget = this.getWidget('item', 'school_classes');
				widget.set('staticValues', classes);
				if (this.loadedValues) {
					widget.set('value', (this.loadedValues.school_classes[school] || [null])[0]);
				}
			}));
		}
	});
});

