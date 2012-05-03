/*
 * Copyright 2012 Univention GmbH
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
/*global console MyError dojo dojox dijit umc window Image */

dojo.provide("umc.modules._computerroom.Settings");

dojo.require("umc.dialog");
dojo.require("umc.i18n");
dojo.require("umc.tools");
dojo.require("umc.widgets.Button");
dojo.require("umc.widgets.Form");
dojo.require("umc.widgets.Page");
dojo.require("umc.widgets.Text");
dojo.require("umc.widgets.StandbyMixin");
dojo.require("umc.widgets.ContainerWidget");
dojo.require("dijit.layout.ContentPane");
dojo.require("dijit.Dialog");

dojo.declare("umc.modules._computerroom.SettingsDialog", [ dijit.Dialog, umc.widgets.StandbyMixin, umc.i18n.Mixin ], {
	// summary:
	//		This class represents the screenshot view

	// internal reference to the flavored umcpCommand function
	umcpCommand: null,

	// use i18n information from umc.modules.schoolgroups
	i18nClass: 'umc.modules.computerroom',

	_form: null,

	postMixInProperties: function() {
		this.inherited(arguments);
	},

	buildRendering: function() {
		this.inherited( arguments );
		// add remaining elements of the search form
		this.set( 'title', this._( 'Access control and Internet settings' ) );

		var widgets = [ {
			type: 'ComboBox',
			name: 'internetRule',
			label: this._('Active web access profile'),
			dynamicValues: 'computerroom/internetrules',
			staticValues: [ { id: 'none', label: this._( 'None' ) },
							{ id: 'custom', label: this._( 'personal rules' ) } ],
			onChange: dojo.hitch( this, function( value ) {
				this._form.getWidget( 'customRule' ).set( 'disabled', value != 'custom' );
			} )
		}, {
			type: 'TextArea',
			name: 'customRule',
			label: this._('Allowed web servers'),
			disabled: true
		}, {
			type: 'ComboBox',
			name: 'shareMode',
			label: this._('share access'),
			description: this._( 'Defines restriction for the share access' ),
			staticValues: [
				{ id : 'none', label: this._( 'no access' ) },
				{ id: 'home', label : this._('home directory only') },
				{ id: 'all', label : this._('no restrictions' ) }
			]
		}, {
			type: 'ComboBox',
			name: 'printMode',
			label: this._('Print mode'),
			staticValues: [
				{ id : 'default', label: this._( 'Default setting' ) },
				{ id: 'none', label : this._('Printing deactivated') },
				{ id: 'all', label : this._('Free printing' ) }
			]
		}, {
			type: 'ComboBox',
			name: 'period',
			label: this._('Reservation until end of'),
			size: 'TwoThirds',
			dynamicValues: 'computerroom/lessons'
		}];

		var buttons = [ {
			name: 'submit',
			label: this._( 'Set' ),
			style: 'float: right',
			onClick: dojo.hitch( this, function() {
				this.hide();
				this.umcpCommand( 'computerroom/settings/set', {
					internetRule: this._form.getWidget( 'internetRule' ).get( 'value' ),
					customRule: this._form.getWidget( 'customRule' ).get( 'value' ),
					printMode: this._form.getWidget( 'printMode' ).get( 'value' ),
					shareMode: this._form.getWidget( 'shareMode' ).get( 'value' ),
					period: this._form.getWidget( 'period' ).get( 'value' ),
				} ).then( dojo.hitch( this, function( response ) {
					console.log( response );
				} ) );
			} )
		} , {
			name: 'cancel',
			label: this._( 'cancel' ),
			onClick: dojo.hitch( this, function() {
				this.hide();
				this.onClose();
			} )
		} ];

		var layout = [
			'internetRule', 'customRule', 'shareMode', 'printMode', 'period'
		];

		// generate the search form
		this._form = new umc.widgets.Form({
			// property that defines the widget's position in a dijit.layout.BorderContainer
			widgets: widgets,
			layout: layout,
			buttons: buttons
		});

		this.set( 'content', this._form );
	},

	update: function( school, room ) {
		this.umcpCommand( 'computerroom/settings/get', {} ).then( dojo.hitch( this, function( response ) {
			umc.tools.forIn( response.result, function( key, value ) {
				this._form.getWidget( key ).set( 'value', value );
			}, this )
		} ) );
	},

	personalActive: function() {
		return this._form.getWidget( 'internetRule' ).get( 'value' ) != 'none' || this._form.getWidget( 'shareMode' ).get( 'value' ) != 'all' || this._form.getWidget( 'printMode' ).get( 'value' ) != 'default'
	},

	onClose: function() {
		// event stub
	}
});




