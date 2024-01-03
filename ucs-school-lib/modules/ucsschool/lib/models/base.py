# -*- coding: utf-8 -*-
#
# UCS@school python lib: models
#
# Copyright 2014-2024 Univention GmbH
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

import os.path
import tempfile
from copy import deepcopy

import lazy_object_proxy
import ldap
from ldap import explode_dn
from ldap.dn import escape_dn_chars
from ldap.filter import escape_filter_chars
from six import add_metaclass, iteritems

import univention.admin.modules as udm_modules
import univention.admin.objects as udm_objects
import univention.admin.uldap as udm_uldap
from univention.admin.filter import conjunction, expression
from univention.admin.uexceptions import noObject

from ..pyhooks.pyhooks_loader import PyHooksLoader
from ..roles import create_ucsschool_role_string
from ..schoolldap import SchoolSearchBase
from .attributes import CommonName, Roles, SchoolAttribute, ValidationError
from .meta import UCSSchoolHelperMetaClass
from .utils import _, exec_cmd, ucr
from .validator import validate

try:
    from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Type, TypeVar, Union

    import univention.admin.handlers.simpleLdap
    from univention.admin.uldap import access as LoType, position as PoType  # noqa: F401

    UdmObject = univention.admin.handlers.simpleLdap
    SuperOrdinateType = Union[str, UdmObject]
    UldapFilter = Union[str, conjunction, expression]
    UCSSchoolModel = TypeVar("UCSSchoolModel", bound="UCSSchoolHelperAbstractClass")
    UCSSchoolHelperAbstractClassTV = TypeVar(
        "UCSSchoolHelperAbstractClassTV", bound="UCSSchoolHelperAbstractClass"
    )
except ImportError:
    pass

PYHOOKS_PATH = "/var/lib/ucs-school-lib/hooks"
PYHOOKS_BASE_CLASS = "ucsschool.lib.models.hook.Hook"
_pyhook_loader = lazy_object_proxy.Proxy(
    lambda: PyHooksLoader(PYHOOKS_PATH, PYHOOKS_BASE_CLASS)
)  # type: PyHooksLoader


class NoObject(noObject):
    def __init__(self, dn=None, type=None, *args):  # type: (str, Type[UCSSchoolModel], *Any) -> None
        self.dn = dn
        self.type = type
        if not args:
            args = ("Could not find object of type {!r} with DN {!r}.".format(self.type, self.dn),)
        super(NoObject, self).__init__(*args)


class UnknownModel(NoObject):
    def __init__(self, dn, cls):  # type: (str, Type[UCSSchoolModel]) -> None
        self.dn = dn
        self.wrong_model = cls
        super(UnknownModel, self).__init__("No python class: %r is not a %s" % (dn, cls.__name__))


class WrongModel(NoObject):
    def __init__(self, dn, model, wrong_model):
        # type: (str, Type[UCSSchoolModel], Type[UCSSchoolModel]) -> None
        self.dn = dn
        self.model = model
        self.wrong_model = wrong_model
        super(WrongModel, self).__init__(
            "Wrong python class: %r is not a %r but a %r" % (dn, wrong_model.__name__, model.__name__)
        )


class WrongObjectType(NoObject):
    def __init__(self, dn, cls):  # type: (str, Type[UCSSchoolModel]) -> None
        self.dn = dn
        self.wrong_model = cls
        super(WrongObjectType, self).__init__("Wrong objectClass: %r is not a %r." % (dn, cls.__name__))


class MultipleObjectsError(Exception):
    def __init__(self, objs, *args, **kwargs):  # type: (Sequence[UCSSchoolModel], *Any, **Any) -> None
        super(MultipleObjectsError, self).__init__(*args, **kwargs)
        self.objs = objs


@add_metaclass(UCSSchoolHelperMetaClass)
class UCSSchoolHelperAbstractClass(object):
    """
    Base class of all UCS@school models.
    Hides UDM.

    Attributes used for a class are defined like this::

        class MyModel(UCSSchoolHelperAbstractClass):
            my_attribute = Attribute('Label', required=True, udm_name='myAttr')

    From there on ``my_attribute=value`` may be passed to :py:meth:``__init__()``,
    ``my_model.my_attribute`` can be accessed and the value will be saved
    as ``obj['myAttr']`` in UDM when saving this instance.
    If an attribute of a base class is not wanted, it can be overridden::

        class MyModel(UCSSchoolHelperAbstractClass):
            school = None

    Meta information about the class are defined like this::

        class MyModel(UCSSchoolHelperAbstractClass):
            class Meta:
                udm_module = 'my/model'

    The meta information is then accessible in ``cls._meta``.

    Important functions:

        :py:meth:``__init__(**kwargs)``:
            kwargs should be the defined attributes

        :py:meth:``create(lo)``
            lo is an LDAP connection, specifically univention.admin.access.
            creates a new object. Returns False is the object already exists.
            And True after the creation

        :py:meth:``modify(lo)``
            modifies an existing object. Returns False if the object does not
            exist and True after the modification (regardless whether something
            actually changed or not)

        :py:meth:``remove(lo)``
            deletes the object. Returns False if the object does not exist and True
            after the deletion.

        :py:meth:``get_all(lo, school, filter_str, easy_filter=False)``
            classmethod; retrieves all objects found for this school. filter can be a string
            that is used to narrow down a search. Each property of the class' udm_module
            that is include_in_default_search is queried for that string.
            Example::

                User.get_all(lo, 'school', filter_str='name', easy_filter=True)

            will search in ``cn=users,ou=school,$base``
            for users/user UDM objects with ``|(username=*name*)(firstname=*name*)(...)`` and return
            User objects (not UDM objects)
            With ``easy_filter=False`` (default) it will use this very ``filter_str``

        :py:meth:``get_container(school)``
            a classmethod that points to the container where new instances are created
            and existing ones are searched.

        :py:meth:``dn``
            property, current distinguishable name of the instance. Calculated on the fly, it
            changes if instance.name or instance.school changes.
            ``instance.old_dn`` will be set to the original dn when the instance was created

        :py:meth:``get_udm_object(lo)``
            searches UDM for an entry that corresponds to ``self``. Normally uses the old_dn or dn.
            If ``cls._meta.name_is_unique`` then any object with ``self.name`` will match

        :py:meth:``exists(lo)``
            whether this object can be found in UDM.

        :py:meth:``from_udm_obj(udm_obj, school, lo)``
            classmethod; maps the info of ``udm_obj`` into a new instance (and sets ``school``)

        :py:meth:``from_dn(dn, school, lo)``
            finds dn in LDAP and uses ``from_udm_obj``

        :py:meth:``get_first_udm_obj(lo, filter_str)``
            returns the first found object of type ``cls._meta.udm_module`` that matches an
            arbitrary ``filter_str``

    More features:

    Validation:
        There are some auto checks built in: Attributes of the model that have a
        UDM syntax attached are validated against this syntax. Attributes that are
        required must be present.
        Attributes that are unlikely_to_change give a warning (not error) if the object
        already exists with other values.
        If the Meta information states that name_is_unique, the complete LDAP is searched
        for the instance's name before continuing.
        :py:meth:``validate()`` can be further customized.

    Hooks:
        Before :py:meth:``create``, :py:meth:``modify``, :py:meth:``move`` and :py:meth:``remove``,
        hooks are called if :py:meth:``build_hook_line()``
        returns something. If the operation was successful, another set of hooks
        are called.

        ``/usr/share/ucs-school-import/hooks/%(module)s_{create|modify|move|remove}_{pre|post}.d/``
        are called with the name of a temporary file containing the hook_line via run-parts.
        ``%(module)s`` is ``'ucc'`` for ``cls._meta.udm_module == 'computers/ucc'`` by default and
        can be explicitely set with::

            class Meta:
                hook_path = 'computer'
    """

    _cache = {}  # type: Dict[Tuple[str, Tuple[str, str]], UCSSchoolModel]
    _machine_connection = None  # type: LoType
    _search_base_cache = {}  # type: Dict[str, SchoolSearchBase]
    _initialized_udm_modules = []  # type: List[str]
    _empty_hook_paths = set()  # type: Set[str]

    hook_sep_char = "\t"
    hook_path = "/usr/share/ucs-school-import/hooks/"

    name = CommonName(_("Name"), aka=["Name"])  # type: str
    school = SchoolAttribute(_("School"), aka=["School"])  # type: str

    @classmethod
    def cache(cls, *args, **kwargs):  # type: (*Any, **Any) -> UCSSchoolModel
        """
        Initializes a new instance and caches it for subsequent calls.
        Useful when using School.cache(school_name) a lot in different
        functions, in loops, etc.
        """
        # TODO: rewrite function to have optional positional 'name' and 'school' arguments
        args = list(args)
        if args:
            kwargs["name"] = args.pop(0)
        if args:
            kwargs["school"] = args.pop(0)
        key = [cls.__name__] + [
            (k, kwargs[k]) for k in sorted(kwargs)
        ]  # TODO: rewrite: sorted(kwargs.items())
        key = tuple(key)
        if key not in cls._cache:
            obj = cls(**kwargs)
            cls._cache[key] = obj
        return cls._cache[key]

    @classmethod
    def invalidate_all_caches(cls):  # type: () -> None
        from ucsschool.lib.models.network import Network
        from ucsschool.lib.models.user import User
        from ucsschool.lib.models.utils import _pw_length_cache

        cls._cache.clear()
        # cls._search_base_cache.clear() # useless to clear
        _pw_length_cache.clear()
        Network._netmask_cache.clear()
        User._profile_path_cache.clear()
        User._samba_home_path_cache.clear()

    @classmethod
    def invalidate_cache(cls):  # type: () -> None
        keys_to_remove = [key for key in cls._cache.keys() if key[0] == cls.__name__]
        for key in keys_to_remove:
            del cls._cache[key]

    @classmethod
    def supports_school(cls):  # type: () -> bool
        return "school" in cls._attributes

    @classmethod
    def supports_schools(cls):  # type: () -> bool
        return "schools" in cls._attributes

    def __init__(self, name=None, school=None, **kwargs):
        # type: (Optional[str], Optional[str], **Any) -> None
        """Initializes a new instance with kwargs.
        Not every kwarg is accepted, though: The name
        must be defined as a attribute at class level
        (or by a base class). All attributes are
        initialized at least with None
        Sets self.old_dn to self.dn, i.e. the name
        in __init__ will determine the old_dn, changing
        it after __init__ will result in trying to move the
        object!
        """
        self._udm_obj_searched = False
        self._udm_obj = None
        kwargs["name"] = name
        kwargs["school"] = school
        for key, attr in self._attributes.items():
            default = attr.value_default
            if callable(default):
                default = default()
            setattr(self, key, kwargs.get(key, default))
        self.__position = None
        self.old_dn = None
        self.old_dn = self.dn  # type: str
        self.errors = {}  # type: Dict[str, List[str]]
        self.warnings = {}  # type: Dict[str, List[str]]
        self._in_hook = False  # if a hook is currently running

    @classmethod
    def get_machine_connection(cls):  # type: () -> LoType
        """get a cached ldap connection to the DC Master using this host's credentials"""
        if not cls._machine_connection:
            cls._machine_connection = udm_uldap.getMachineConnection()[0]
        return cls._machine_connection

    @property
    def position(self):  # type: () -> Optional[str]
        if self.__position is None:
            return self.get_own_container()
        return self.__position

    @position.setter
    def position(self, position):  # type: (str) -> None
        if self.position != position:  # allow dynamic school changes until creation
            self.__position = position

    @property
    def dn(self):  # type: () -> str
        """Generates a DN where the lib would assume this
        instance to be. Changing name or school of self will most
        likely change the outcome of self.dn as well
        """
        if self.name and self.position:
            name = self._meta.ldap_map_function(self.name)
            return "%s=%s,%s" % (self._meta.ldap_name_part, escape_dn_chars(name), self.position)
        return self.old_dn

    def set_attributes(self, **kwargs):  # type: (**Any) -> None
        """
        A function to set the attributes of an UCS@school object in one function call.
        Only attributes that exist in self._attributes are set. The rest of the kwargs are
        simply ignored.

        :param kwargs: The attributes to set.
        """
        existing_attributes = self._attributes.keys()
        for key, value in kwargs.items():
            if key in existing_attributes:
                setattr(self, key, value)
            else:
                self.logger.debug(
                    "Setting attribute '{!r}' on {!r} does not work, since it doesn't exist.".format(
                        key, self
                    )
                )

    def set_dn(self, dn):  # type: (str) -> None
        """Does not really set dn, as this is generated
        on-the-fly. Instead, sets old_dn in case it was
        missed in the beginning or after create/modify/remove/move
        Also resets cached udm_obj as it may point to somewhere else
        """
        self._udm_obj_searched = False
        self.position = ldap.dn.dn2str(ldap.dn.str2dn(dn)[1:])
        self.old_dn = dn

    def validate(self, lo, validate_unlikely_changes=False):  # type: (LoType, Optional[bool]) -> None
        from ucsschool.lib.models.school import School

        self.errors.clear()
        self.warnings.clear()
        for name, attr in iteritems(self._attributes):
            value = getattr(self, name)
            try:
                attr.validate(value)
            except ValueError as e:
                self.add_error(name, str(e))
        if self._meta.name_is_unique and not self._meta.allow_school_change:
            if self.exists_outside_school(lo):
                self.add_error(
                    "name",
                    _(
                        "The name is already used somewhere outside the school. It may not be taken "
                        "twice and has to be changed."
                    ),
                )
        if self.supports_school() and self.school:
            if not School.cache(self.school).exists(lo):
                self.add_error(
                    "school",
                    _('The school "%s" does not exist. Please choose an existing one or create it.')
                    % self.school,
                )
        self.validate_roles(lo)
        if validate_unlikely_changes:
            if self.exists(lo):
                udm_obj = self.get_udm_object(lo)
                try:
                    original_self = self.from_udm_obj(udm_obj, self.school, lo)
                except (UnknownModel, WrongModel):
                    pass
                else:
                    for name, attr in iteritems(self._attributes):
                        if attr.unlikely_to_change:
                            new_value = getattr(self, name)
                            old_value = getattr(original_self, name)
                            if new_value and old_value:
                                if new_value != old_value:
                                    self.add_warning(
                                        name,
                                        _("The value changed from %(old)s. This seems unlikely.")
                                        % {"old": old_value},
                                    )

    def validate_roles(self, lo):  # type: (LoType) -> None
        pass

    def add_warning(self, attribute, warning_message):  # type: (str, str) -> None
        warnings = self.warnings.setdefault(attribute, [])
        if warning_message not in warnings:
            warnings.append(warning_message)

    def add_error(self, attribute, error_message):  # type: (str, str) -> None
        errors = self.errors.setdefault(attribute, [])
        if error_message not in errors:
            errors.append(error_message)

    def exists(self, lo):  # type: (LoType) -> bool
        return self.get_udm_object(lo) is not None

    def exists_outside_school(self, lo):  # type: (LoType) -> bool
        if not self.supports_school():
            return False
        from ucsschool.lib.models.school import School

        udm_obj = self.get_udm_object(lo)
        if udm_obj is None:
            return False
        return not udm_obj.dn.endswith(School.cache(self.school).dn)

    def _call_legacy_hooks(self, hook_time, func_name):  # type: (str, str) -> bool
        """
        Run legacy fork hooks (run-parts /usr/share/u-s-i/hooks).

        :param str hook_time: `pre` or `post`
        :param str func_name: `create`, `modify`, `move` or `remove`
        :return: return code of hooks or True if no legacy hook ran
        :rtype: bool
        """
        # verify path
        hook_path = self._meta.hook_path
        path = os.path.join(self.hook_path, "%s_%s_%s.d" % (hook_path, func_name, hook_time))
        if path in self._empty_hook_paths:
            return True
        if not os.path.isdir(path) or not os.listdir(path):
            self.logger.debug("Hook directory %s not found or empty.", path)
            self._empty_hook_paths.add(path)
            return True
        self.logger.debug("Hooks in %s shall be executed", path)

        if hook_time == "post":
            dn = self.old_dn
        else:
            dn = None

        self.logger.debug("Building hook line: %s.build_hook_line(%r, %r)", self, hook_time, func_name)
        line = self.build_hook_line(hook_time, func_name)
        if not line:
            self.logger.debug("No line created. Skipping.")
            return True
        line = line.strip() + "\n"

        # create temporary file with data
        with tempfile.NamedTemporaryFile() as tmpfile:
            tmpfile.write(line)
            tmpfile.flush()

            # invoke hook scripts
            # <script> <temporary file> [<ldap dn>]
            command = ["run-parts", "--verbose", "--report", "--arg", tmpfile.name]
            if dn:
                command.extend(("--arg", dn))
            command.extend(("--", path))

            self.logger.debug("Executing command %r...", command)
            ret_code, stdout, stderr = exec_cmd(command, log=True)
            self.logger.debug("Command %r finished with exit code %r.", command, ret_code)

            return ret_code == 0

    def _call_pyhooks(self, hook_time, func_name, lo):
        # type: (str, str, LoType) -> None
        """
        Run Python based hooks (`*.py` files in `/usr/share/u-s-i/pyhooks`
        containing a subclass of :py:class:`ucsschool.lib.models.hook.Hook`).

        :param str hook_time: `pre` or `post`
        :param str func_name: `create`, `modify`, `move` or `remove`
        :param univention.admin.uldap.access lo: LDAP connection object
        :return: None
        :rtype: None
        """
        self._in_hook = True
        all_hooks = _pyhook_loader.get_hook_objects(lo)
        meth_name = "{}_{}".format(hook_time, func_name)
        try:
            for func in all_hooks.get(meth_name, []):
                if issubclass(self.__class__, func.im_class.model):
                    self.logger.debug(
                        "Running %s hook %s.%s for %s...",
                        meth_name,
                        func.im_class.__name__,
                        func.im_func.func_name,
                        self,
                    )
                    func(self)
        finally:
            self._in_hook = False

    def call_hooks(self, hook_time, func_name, lo):  # type: (str, str, LoType) -> bool
        """
        Calls legacy hooks (run-parts /usr/share/u-s-i/hooks) and then Python
        based hooks (*.py files in /usr/share/u-s-i/pyhooks).

        In the case of `post`, this method is only called, if the corresponding
        function (`create()`, `modify()`, `move()` or `remove()`) returned
        `True`.

        :param str hook_time: `pre` or `post`
        :param str func_name: `create`, `modify`, `move` or `remove`
        :param univention.admin.uldap.access lo: LDAP connection object
        :return: `or`d return value of legacy hooks or True if no hook ran
        :rtype: bool: `or`d return value of legacy hooks or True if no hook ran
        """
        lo_name = lo.__class__.__name__
        if lo_name == "access":
            lo_name = "lo"
        self.logger.debug(
            "Starting %s.call_hooks(%r, %r, %s(%r)) for %r.",
            self.__class__.__name__,
            hook_time,
            func_name,
            lo_name,
            lo.binddn,
            self,
        )

        res = self._call_legacy_hooks(hook_time, func_name)
        self._call_pyhooks(hook_time, func_name, lo)
        return res

    def build_hook_line(self, hook_time, func_name):  # type: (str, str) -> Optional[str]
        """Must be overridden if the model wants to support hooks.
        Do so by something like:
        return self._build_hook_line(self.attr1, self.attr2, 'constant')
        """
        return None

    @classmethod
    def hook_init(cls, hook):  # type: (PYHOOKS_BASE_CLASS) -> None
        """
        Overwrite this method to add individual initialization code to all
        hooks of a ucsschool.lib.model class.
        (See `.SchoolClass.hook_init()` for an example.)

        :param hook: instance of a subclass of :py:class:`ucsschool.lib.model.hook.Hook`
        :return: None
        :rtype: None
        """
        pass

    def _alter_udm_obj(self, udm_obj):  # type: (UdmObject) -> None
        for name, attr in iteritems(self._attributes):
            if attr.udm_name:
                value = getattr(self, name)
                if (value is not None or attr.map_if_none) and attr.map_to_udm:
                    udm_obj[attr.udm_name] = value
        # TODO: move g[s]et_default_options() from User here to update udm_obj.options

    def create(self, lo, validate=True):  # type: (LoType, Optional[bool]) -> bool
        """
        Creates a new UDM instance.
        Calls pre-hooks.
        If the object already exists, returns False.
        If the object does not yet exist, creates it, returns True and
        calls post-hooks.
        """
        if self._in_hook:
            # prevent recursion
            self.logger.warning(
                "Running create() from within a hook, skipping hook execution. Please use "
                "create_without_hooks() from within hooks."
            )
        else:
            self.call_hooks("pre", "create", lo)
        success = self.create_without_hooks(lo, validate)
        if success and not self._in_hook:
            self.call_hooks("post", "create", lo)
        return success

    def create_without_hooks(self, lo, validate):  # type: (LoType, bool) -> bool
        if self.exists(lo):
            return False
        self.logger.info("Creating %r", self)

        self.create_without_hooks_roles(lo)

        if validate:
            self.validate(lo)
            if self.errors:
                raise ValidationError(self.errors.copy())

        pos = udm_uldap.position(ucr.get("ldap/base"))
        container = self.position
        if not container:
            self.logger.error("%r cannot determine a container. Unable to create!", self)
            return False
        try:
            pos.setDn(container)
            udm_obj = udm_modules.get(self._meta.udm_module).object(
                None, lo, pos, superordinate=self.get_superordinate(lo)
            )
            udm_obj.open()

            # here is the real logic
            self.do_create(udm_obj, lo)

            # get it fresh from the database (needed for udm_obj._exists ...)
            self.set_dn(self.dn)
            self.logger.info("%r successfully created", self)
            return True
        finally:
            self.invalidate_cache()

    def create_without_hooks_roles(self, lo):  # type: (LoType) -> bool
        """
        Run by py:meth:`create_without_hooks()` before py:meth:`validate()`
        (and thus before py:meth:`do_create()`).
        """
        pass

    def do_create(self, udm_obj, lo):  # type: (UdmObject, LoType) -> None
        """Actual udm_obj manipulation. Override this if
        you want to further change values of udm_obj, e.g.
        def do_create(self, udm_obj, lo):
            udm_obj['used_in_ucs_school'] = '1'
            super(MyModel, self).do_create(udm_obj, lo)
        """
        self._alter_udm_obj(udm_obj)
        udm_obj.create()

    def modify(self, lo, validate=True, move_if_necessary=None):
        # type: (LoType, Optional[bool], Optional[bool]) -> bool
        """
        Modifies an existing UDM instance.
        Calls pre-hooks.
        If the object does not exist, returns False.
        If the object exists, modifies it, returns True and
        calls post-hooks.
        """
        self.call_hooks("pre", "modify", lo)
        success = self.modify_without_hooks(lo, validate, move_if_necessary)
        if success:
            self.call_hooks("post", "modify", lo)
        return success

    def modify_without_hooks(self, lo, validate=True, move_if_necessary=None):
        # type: (LoType, Optional[bool], Optional[bool]) -> bool
        self.logger.info("Modifying %r", self)

        if move_if_necessary is None:
            move_if_necessary = self._meta.allow_school_change

        self.update_ucsschool_roles(lo)

        if validate:
            self.validate(lo, validate_unlikely_changes=True)
            if self.errors:
                raise ValidationError(self.errors.copy())

        udm_obj = self.get_udm_object(lo)
        if not udm_obj:
            self.logger.info("%s does not exist!", self.old_dn)
            return False

        try:
            old_attrs = deepcopy(udm_obj.info)
            self.modify_without_hooks_roles(udm_obj)
            self.do_modify(udm_obj, lo)
            # get it fresh from the database
            self.set_dn(self.dn)
            udm_obj = self.get_udm_object(lo)
            same = old_attrs == udm_obj.info
            if move_if_necessary:
                if udm_obj.dn != self.dn:
                    if self.move_without_hooks(lo, udm_obj, force=True):
                        same = False
            if same:
                self.logger.info("%r not modified. Nothing changed", self)
            else:
                self.logger.info("%r successfully modified", self)
            # return not same
            return True
        finally:
            self.invalidate_cache()

    def modify_without_hooks_roles(self, udm_obj):  # type: (UdmObject) -> bool
        """Run by py:meth:`modify_without_hooks()` before py:meth:`do_modify()`."""
        pass

    def update_ucsschool_roles(self, lo):  # type: (LoType) -> None
        """Run by py:meth:`modify_without_hooks()` before py:meth:`validate()`."""
        pass

    def do_modify(self, udm_obj, lo):  # type: (UdmObject, LoType) -> None
        """
        Actual udm_obj manipulation. Override this if
        you want to further change values of udm_obj, e.g.
        def do_modify(self, udm_obj, lo):
            udm_obj['used_in_ucs_school'] = '1'
            super(MyModel, self).do_modify(udm_obj, lo)
        """
        self._alter_udm_obj(udm_obj)
        udm_obj.modify(ignore_license=1)

    def move(self, lo, udm_obj=None, force=False):
        # type: (LoType, Optional[UdmObject], Optional[bool]) -> bool
        if self._in_hook:
            # prevent recursion
            self.logger.warning(
                "Running move() from within a hook, skipping hook execution. Please use "
                "move_without_hooks() from within hooks."
            )
        else:
            self.call_hooks("pre", "move", lo)
        success = self.move_without_hooks(lo, udm_obj, force)
        if success and not self._in_hook:
            self.call_hooks("post", "move", lo)
        return success

    def move_without_hooks(self, lo, udm_obj, force=False):
        # type: (LoType, Optional[UdmObject], Optional[bool]) -> bool
        if udm_obj is None:
            udm_obj = self.get_udm_object(lo)
        if udm_obj is None:
            self.logger.warning("No UDM object found to move from (%r)", self)
            return False
        if self.supports_school() and self.get_school_obj(lo) is None:
            self.logger.warning("%r wants to move itself to a not existing school", self)
            return False
        self.logger.info("Moving %r to %r", udm_obj.dn, self)
        if udm_obj.dn == self.dn:
            self.logger.warning("%r wants to move to its own DN!", self)
            return False
        if force or self._meta.allow_school_change:
            try:
                self.do_move(udm_obj, lo)
            finally:
                self.invalidate_cache()
            self.set_dn(self.dn)
        else:
            self.logger.warning("Would like to move %s to %r. But it is not allowed!", udm_obj.dn, self)
            return False
        return True

    def do_move(self, udm_obj, lo):  # type: (UdmObject, LoType) -> None
        old_school, new_school = self.get_school_from_dn(self.old_dn), self.get_school_from_dn(self.dn)
        udm_obj.move(self.dn, ignore_license=1)
        if self.supports_school() and old_school and old_school != new_school:
            self.do_school_change(udm_obj, lo, old_school)
            self.do_move_roles(udm_obj, lo, old_school, new_school)

    def do_move_roles(self, udm_obj, lo, old_school, new_school):
        # type: (UdmObject, LoType, str, str) -> None
        self.update_ucsschool_roles(lo)

    def change_school(self, school, lo):  # type: (str, LoType) -> bool
        if self.school in self.schools:
            self.schools.remove(self.school)
        if school not in self.schools:
            self.schools.append(school)
        self.school = school
        self.position = self.get_own_container()
        return self.move(lo, force=True)

    def do_school_change(self, udm_obj, lo, old_school):  # type: (UdmObject, LoType, str) -> None
        self.logger.info("Going to move %r from school %r to %r", self.old_dn, old_school, self.school)

    def remove(self, lo):  # type: (LoType) -> bool
        """
        Removes an existing UDM instance.
        Calls pre-hooks.
        If the object does not exist, returns False.
        If the object exists, removes it, returns True and
        calls post-hooks.
        """
        if self._in_hook:
            # prevent recursion
            self.logger.warning(
                "Running remove() from within a hook, skipping hook execution. Please use "
                "remove_without_hooks() from within hooks."
            )
        else:
            self.call_hooks("pre", "remove", lo)
        success = self.remove_without_hooks(lo)
        if success and not self._in_hook:
            self.call_hooks("post", "remove", lo)
        return success

    def remove_without_hooks(self, lo):  # type: (LoType) -> bool
        self.logger.info("Deleting %r", self)
        udm_obj = self.get_udm_object(lo)
        if udm_obj:
            try:
                udm_obj.remove(remove_childs=True)
                udm_objects.performCleanup(udm_obj)
                self.set_dn(None)
                self.logger.info("%r successfully removed", self)
                return True
            finally:
                self.invalidate_cache()
        self.logger.info("%r does not exist!", self)
        return False

    @classmethod
    def get_name_from_dn(cls, dn):  # type: (str) -> str
        if dn:
            try:
                name = explode_dn(dn, 1)[0]
            except ldap.DECODING_ERROR:
                name = ""
            return cls._meta.ldap_unmap_function([name])

    @classmethod
    def get_school_from_dn(cls, dn):  # type: (str) -> str
        return SchoolSearchBase.getOU(dn)

    @classmethod
    def find_field_label_from_name(cls, field):  # type: (str) -> str
        for name, attr in cls._attributes.items():
            if name == field:
                return attr.label

    def get_error_msg(self):  # type: () -> str
        return self.create_validation_msg(iteritems(self.errors))

    def get_warning_msg(self):  # type: () -> str
        return self.create_validation_msg(iteritems(self.warnings))

    def create_validation_msg(self, items):  # type: (Iterable[Tuple[str, List[str]]]) -> str
        validation_msg = ""
        for key, msg in items:
            label = self.find_field_label_from_name(key)
            msg_str = ""
            for error in msg:
                msg_str += error
                if not (error.endswith("!") or error.endswith(".")):
                    msg_str += "."
                msg_str += " "
            validation_msg += "%s: %s" % (label, msg_str)
        return validation_msg[:-1]

    def get_udm_object(self, lo):  # type: (LoType) -> UdmObject
        """
        Returns the UDM object that corresponds to self.
        If self._meta.name_is_unique it searches for any UDM object
        with self.name.
        If not (which is the default) it searches for self.old_dn or self.dn
        Returns None if no object was found. Caches the result, even None
        If you want to re-search, you need to explicitely set
        self._udm_obj_searched = False
        """
        self.init_udm_module(lo)
        if self._udm_obj_searched is False or (self._udm_obj and self._udm_obj.lo.binddn != lo.binddn):
            dn = self.old_dn or self.dn
            superordinate = self.get_superordinate(lo)
            if dn is None:
                self.logger.error("Getting %s UDM object: No DN!", self.__class__.__name__)
                return None
            if self._meta.name_is_unique:
                if self.name is None:
                    self.logger.error('Getting %s UDM object: Empty "name"!', self.__class__.__name__)
                    return None
                udm_name = self._attributes["name"].udm_name
                name = self.get_name_from_dn(dn)
                filter_str = "%s=%s" % (udm_name, escape_filter_chars(name))
                self._udm_obj = self.get_first_udm_obj(lo, filter_str, superordinate)
            else:
                self.logger.debug("Getting %s UDM object by dn: %s", self.__class__.__name__, dn)
                try:
                    self._udm_obj = udm_modules.lookup(
                        self._meta.udm_module,
                        None,
                        lo,
                        scope="base",
                        base=dn,
                        superordinate=superordinate,
                    )[0]
                except (noObject, IndexError):
                    self._udm_obj = None
                else:
                    self._udm_obj.open()
                    validate(self._udm_obj, self.logger)
            self._udm_obj_searched = True
        return self._udm_obj

    def get_school_obj(self, lo):  # type: (LoType) -> "School"
        from ucsschool.lib.models.school import School

        if not self.supports_school():
            return None
        school = School.cache(self.school)
        try:
            return School.from_dn(school.dn, None, lo)
        except noObject:
            self.logger.warning("%r does not exist!", school)
            return None

    def get_superordinate(self, lo):  # type: (LoType) -> UdmObject
        return None

    def get_own_container(self):  # type: () -> Optional[str]
        if self.supports_school() and not self.school:
            return None
        return self.get_container(self.school)

    @classmethod
    def get_container(cls, school):  # type: (str) -> str
        """
        raises NotImplementedError by default. Needs to be overridden!
        """
        raise NotImplementedError("%s.get_container()" % (cls.__name__,))

    @classmethod
    def get_search_base(cls, school_name):  # type: (str) -> SchoolSearchBase
        from ucsschool.lib.models.school import School

        if school_name not in cls._search_base_cache:
            school = School(name=school_name)
            cls._search_base_cache[school_name] = SchoolSearchBase([school.name], dn=school.dn)
        return cls._search_base_cache[school_name]

    @classmethod
    def init_udm_module(cls, lo):  # type: (LoType) -> None
        if cls._meta.udm_module in cls._initialized_udm_modules:
            return
        pos = udm_uldap.position(lo.base)
        udm_modules.init(lo, pos, udm_modules.get(cls._meta.udm_module))
        cls._initialized_udm_modules.append(cls._meta.udm_module)

    @classmethod
    def get_all(cls, lo, school, filter_str=None, easy_filter=False, superordinate=None):
        # type: (LoType, str, Optional[str], Optional[bool], Optional[SuperOrdinateType]) -> List[UCSSchoolModel]  # noqa: E501
        """
        Returns a list of all objects that can be found in cls.get_container() with the
        correct udm_module
        If filter_str is given, all udm properties with include_in_default_search are
        queried for that string (so that it should be the value)
        """
        cls.init_udm_module(lo)
        complete_filter = cls._meta.udm_filter
        if complete_filter and not complete_filter.startswith("("):
            complete_filter = "({})".format(complete_filter)
        if easy_filter:
            filter_from_filter_str = cls.build_easy_filter(filter_str)
        else:
            filter_from_filter_str = filter_str
            if filter_from_filter_str and not filter_from_filter_str.startswith("("):
                filter_from_filter_str = "({})".format(filter_from_filter_str)
        if filter_from_filter_str:
            if complete_filter:
                complete_filter = conjunction("&", [complete_filter, filter_from_filter_str])
            else:
                complete_filter = filter_from_filter_str
        complete_filter = str(complete_filter)
        cls.logger.debug("Getting all %s of %s with filter %r", cls.__name__, school, complete_filter)
        ret = []
        for udm_obj in cls.lookup(lo, school, complete_filter, superordinate=superordinate):
            try:
                ret.append(cls.from_udm_obj(udm_obj, school, lo))
            except NoObject:
                continue
        return ret

    @classmethod
    def lookup(cls, lo, school, filter_s="", superordinate=None):
        # type: (LoType, str, Optional[UldapFilter], Optional[SuperOrdinateType]) -> List[UdmObject]
        try:
            return udm_modules.lookup(
                cls._meta.udm_module,
                None,
                lo,
                filter=filter_s,
                base=cls.get_container(school),
                scope="sub",
                superordinate=superordinate,
            )
        except noObject as exc:
            cls.logger.warning(
                "Error while getting all %s of %s (probably %r does not exist): %s",
                cls.__name__,
                school,
                cls.get_container(school),
                exc,
            )
            return []

    @classmethod
    def _attrs_for_easy_filter(cls):  # type: () -> List[str]
        ret = []
        module = udm_modules.get(cls._meta.udm_module)
        for key, prop in iteritems(module.property_descriptions):
            if prop.include_in_default_search:
                ret.append(key)
        return ret

    @classmethod
    def build_easy_filter(cls, filter_str):  # type: (str) -> Optional[conjunction]
        def escape_filter_chars_exc_asterisk(value):  # type: (str) -> str
            value = ldap.filter.escape_filter_chars(value)
            value = value.replace(r"\2a", "*")
            return value

        if filter_str:
            filter_str = escape_filter_chars_exc_asterisk(filter_str)
            expressions = []
            for key in cls._attrs_for_easy_filter():
                expressions.append(expression(key, filter_str))
            if expressions:
                return conjunction("|", expressions)

    @classmethod
    def from_udm_obj(cls, udm_obj, school, lo):  # type: (UdmObject, str, LoType) -> UCSSchoolModel
        """
        Creates a new instance with attributes of the udm_obj.
        Uses get_class_for_udm_obj()
        """
        # Design fault. school is part of the DN or the ucsschoolSchool attribute.
        cls.init_udm_module(lo)
        klass = cls.get_class_for_udm_obj(udm_obj, school)
        if klass is None:
            cls.logger.warning(
                "UDM object %r does not correspond to a Python class in the UCS school lib.", udm_obj.dn
            )
            raise UnknownModel(udm_obj.dn, cls)
        if klass is not cls:
            cls.logger.debug(
                "UDM object %s is not %s, but actually %s", udm_obj.dn, cls.__name__, klass.__name__
            )
            if not issubclass(klass, cls):
                # security!
                # ExamStudent must not be converted into Teacher/Student/etc.,
                # SchoolClass must not be converted into ComputerRoom
                # while Group must be converted into ComputerRoom, etc. and User must be converted into
                # Student, etc.
                raise WrongModel(udm_obj.dn, klass, cls)
            return klass.from_udm_obj(udm_obj, school, lo)
        udm_obj.open()
        validate(udm_obj, cls.logger)
        attrs = {
            "school": cls.get_school_from_dn(udm_obj.dn) or school
        }  # TODO: is this adjustment okay?
        if cls.supports_schools():
            attrs["schools"] = udm_obj["school"]
        for name, attr in iteritems(cls._attributes):
            if attr.udm_name:
                udm_value = udm_obj[attr.udm_name]
                if udm_value == "":
                    udm_value = None
                attrs[name] = udm_value
        obj = cls(**deepcopy(attrs))
        obj.set_dn(udm_obj.dn)
        obj._udm_obj_searched = True
        obj._udm_obj = udm_obj
        return obj

    @classmethod
    def get_class_for_udm_obj(cls, udm_obj, school):  # type: (UdmObject, str) -> Type[UCSSchoolModel]
        """
        Returns cls by default.

        Can be overridden for base classes:
        class User(UCSSchoolHelperAbstractClass):
            @classmethod
            def get_class_for_udm_obj(cls, udm_obj, school)
                if something:
                    return SpecialUser
                return cls

        class SpecialUser(User):
            pass

        Now, User.get_all() will return a list of User and SpecialUser objects
        If this function returns None for a udm_obj, that obj will not
        yield a new instance in get_all() and from_udm_obj() will return None
        for that udm_obj
        """
        return cls

    def __repr__(self):  # type: () -> str
        dn = self.dn
        dn = "%r, old_dn=%r" % (dn, self.old_dn) if dn != self.old_dn else repr(dn)
        if self.supports_school():
            return "%s(name=%r, school=%r, dn=%s)" % (
                self.__class__.__name__,
                self.name,
                self.school,
                dn,
            )
        else:
            return "%s(name=%r, dn=%s)" % (self.__class__.__name__, self.name, dn)

    def __lt__(self, other):  # type: (UCSSchoolModel) -> bool
        return self.name < other.name

    @classmethod
    def from_dn(cls, dn, school, lo, superordinate=None):
        # type: (str, str, LoType, Optional[SuperOrdinateType]) -> UCSSchoolModel
        """
        Returns a new instance based on the UDM object found at dn
        raises noObject if the udm_module does not match the dn
        or dn is not found
        """
        cls.init_udm_module(lo)
        if school is None and cls.supports_school():
            school = cls.get_school_from_dn(dn)
            if school is None:
                cls.logger.warning("Unable to guess school from %r", dn)
        try:
            cls.logger.debug("Looking up %s with dn %r", cls.__name__, dn)
            udm_obj = udm_modules.lookup(
                cls._meta.udm_module,
                None,
                lo,
                filter=cls._meta.udm_filter,
                base=dn,
                scope="base",
                superordinate=superordinate,
            )[0]
        except IndexError:
            # happens when cls._meta.udm_module does not "match" the dn
            raise WrongObjectType(dn, cls)
        return cls.from_udm_obj(udm_obj, school, lo)

    @classmethod
    def get_only_udm_obj(cls, lo, filter_str, superordinate=None, base=None):
        # type: (LoType, str, Optional[str], Optional[SuperOrdinateType]) -> UdmObject
        """
        Returns the one UDM object of class cls._meta.udm_module that
        matches a given filter.
        If more than one is found, a MultipleObjectsError is raised
        If none is found, None is returned
        """
        cls.init_udm_module(lo)
        if cls._meta.udm_filter:
            filter_str = "(&(%s)(%s))" % (cls._meta.udm_filter, filter_str)
        cls.logger.debug("Getting %s UDM object by filter: %s", cls.__name__, filter_str)
        objs = udm_modules.lookup(
            cls._meta.udm_module,
            None,
            lo,
            scope="sub",
            base=base or ucr.get("ldap/base"),
            filter=str(filter_str),
            superordinate=superordinate,
        )

        if len(objs) == 0:
            return None
        if len(objs) > 1:
            raise MultipleObjectsError(objs=objs)
        obj = objs[0]
        obj.open()
        validate(obj, cls.logger)
        return obj

    @classmethod
    def get_first_udm_obj(cls, lo, filter_str, superordinate=None):
        # type: (LoType, str, Optional[Union[str, UdmObject]]) -> UdmObject
        """
        Returns the first UDM object of class cls._meta.udm_module that
        matches a given filter
        """
        try:
            return cls.get_only_udm_obj(lo, filter_str, superordinate)
        except MultipleObjectsError as exc:
            obj = exc.objs[0]
            obj.open()
            validate(obj, cls.logger)
            return obj

    @classmethod
    def find_udm_superordinate(cls, dn, lo):  # type: (str, LoType) -> Optional[SuperOrdinateType]
        module = udm_modules.get(cls._meta.udm_module)
        return udm_objects.get_superordinate(module, None, lo, dn)

    def to_dict(self):  # type: () -> Dict[str, Any]
        """
        Returns a dictionary somewhat representing this instance.
        This dictionary is usually used when sending the instance to
        a browser as JSON.
        By default the attributes are present as well as the dn and
        the udm_module.
        """
        ret = {"$dn$": self.dn, "objectType": self._meta.udm_module}
        for name, attr in iteritems(self._attributes):
            if not attr.internal:
                ret[name] = getattr(self, name)
        return ret

    def __deepcopy__(self, memo):  # type: (Dict[int]) -> UCSSchoolModel
        id_self = id(self)
        if not memo.get(id_self):
            memo[id_self] = self.__class__(**self.to_dict())
        return memo[id_self]

    def _map_func_name_to_code(self, func_name):  # type: (str) -> str
        if func_name == "create":
            return "A"
        elif func_name == "modify":
            return "M"
        elif func_name == "remove":
            return "D"
        elif func_name == "move":
            return "MV"

    def _build_hook_line(self, *args):  # type: (*Any) -> str
        attrs = []
        for arg in args:
            val = arg
            if arg is None:
                val = ""
            if arg is False:
                val = 0
            if arg is True:
                val = 1
            attrs.append(str(val))
        return self.hook_sep_char.join(attrs)


class RoleSupportMixin(object):
    """
    Attribute and methods to handle the `ucsschool_roles` / `ucsschoolRoles`
    attribute.
    """

    ucsschool_roles = Roles(_("Roles"), aka=["Roles"])  # type: List[str]

    default_roles = []  # type: List[str]
    _school_in_name = False
    _school_in_name_prefix = False

    def get_schools(self):  # type: () -> Set[str]
        return set(getattr(self, "schools", []) + [self.school])

    def get_schools_from_udm_obj(self, udm_obj):  # type: (UdmObject) -> List[str]
        if self._school_in_name:
            return [udm_obj.info["name"]]
        elif self._school_in_name_prefix:
            try:
                return [udm_obj.info["name"].split("-", 1)[0]]
            except KeyError:
                return []
        else:
            try:
                return udm_obj.info["school"]
            except KeyError as exc:
                self.logger.exception(
                    "KeyError in RoleSupportMixin.get_schools_from_udm_obj(%r): %s", udm_obj, exc
                )
                raise

    @property
    def roles_as_dicts(self):  # type: () -> List[Dict[str, str]]
        """Get :py:attr:`self.ucsschool_roles` as a dict."""
        res = []
        for role in self.ucsschool_roles:
            m = Roles.syntax.regex.match(role)
            if m:
                res.append(m.groupdict())
        return res

    @roles_as_dicts.setter
    def roles_as_dicts(self, roles):  # type: (Iterable[Dict[str, str]]) -> None
        """
        Take dict from :py:attr:`roles_as_dicts` and write to
        :py:attr:`self.ucsschool_roles`.
        """
        self.ucsschool_roles = ["{role}:{context_type}:{context}".format(**role) for role in roles]

    def do_move_roles(self, udm_obj, lo, old_school, new_school):
        # type: (UdmObject, LoType, str, str) -> None
        old_roles = list(self.ucsschool_roles)
        # remove all roles of old school
        roles = [role for role in self.roles_as_dicts if role["context"] != old_school]
        # only add role(s) if object has no roles in new school
        if all(role["context"] != new_school for role in roles):
            # add only role(s) of current Python class in new school
            roles.extend(
                [
                    {"context": new_school, "context_type": "school", "role": role}
                    for role in self.default_roles
                ]
            )
        self.roles_as_dicts = roles
        if old_roles != self.ucsschool_roles:
            self.logger.info("Updating roles: %r -> %r...", old_roles, self.ucsschool_roles)
            # cannot use do_modify() here, as it would delete the old object
            lo.modify(self.dn, [("ucsschoolRole", old_roles, self.ucsschool_roles)])

    def validate_roles(self, lo):  # type: (LoType) -> None
        # for now different roles in different schools are not supported
        schools = self.get_schools()
        for role in self.roles_as_dicts:
            if role["context_type"] != "school" or self._meta.udm_module.startswith(
                "computers/domaincontroller_"
            ):
                # check only context_type == 'school' for now
                # DCs have roles for all schools they handle, but have no 'schools' attribute
                continue
            if role["context"] != "-" and role["context"] not in schools:
                self.add_error(
                    "ucsschool_roles",
                    _(
                        "Context {role}:{context_type}:{context} is not allowed for {dn}. Object is not "
                        "in that school."
                    ).format(dn=self.dn, **role),
                )

    def create_without_hooks_roles(self, lo):  # type: (LoType) -> None
        """
        Run by py:meth:`create_without_hooks()` before py:meth:`validate()`
        (and thus before py:meth:`do_create()`).
        """
        roles = self.roles_as_dicts
        if self.default_roles and not any([role["context"] for role in roles if role["context"] != "-"]):
            schools = self.get_schools()
            self.ucsschool_roles += [
                create_ucsschool_role_string(role, school)
                for role in self.default_roles
                for school in schools
            ]

    def update_ucsschool_roles(self, lo):  # type: (LoType) -> None
        """
        Run by py:meth:`modify_without_hooks()` before py:meth:`validate()`.

        Add :py:attr:`ucsschool_roles` entries of `context_type=school` to
        object, if it got new/additional school(s) and object has no role(s)
        in those yet.

        Delete :py:attr:`ucsschool_roles` entries of `context_type=school` of
        object, if it was removed from school(s).
        """
        roles = self.roles_as_dicts
        old_schools = set(role["context"] for role in roles if role["context"] != "-")
        cur_schools = set(self.get_schools())
        new_schools = cur_schools - old_schools
        removed_schools = old_schools - cur_schools
        for new_school in new_schools:
            # only add role(s) if object has no roles in new school
            if any(role["context"] == new_school for role in roles):
                continue
            # add only role(s) of current Python class in new school
            roles.extend(
                {"context": new_school, "context_type": "school", "role": role}
                for role in self.default_roles
            )
        for role in deepcopy(roles):
            if role["context_type"] == "school" and role["context"] in removed_schools:
                roles.remove(role)
        if new_schools or removed_schools:
            self.roles_as_dicts = roles
