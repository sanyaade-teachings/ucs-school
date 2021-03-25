# Copyright 2020-2021 Univention GmbH
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

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from ldap.filter import escape_filter_chars
from pydantic import validator

from ucsschool.lib.create_ou import create_ou
from ucsschool.lib.models.school import School
from ucsschool.lib.models.utils import env_or_ucr
from udm_rest_client import UDM

from ..opa import OPAClient
from ..token_auth import oauth2_scheme
from .base import APIAttributesMixin, LibModelHelperMixin, udm_ctx

router = APIRouter()


@lru_cache(maxsize=1)
def get_logger() -> logging.Logger:
    return logging.getLogger(__name__)


# not subclassing 'UcsSchoolBaseModel' because that has a 'school' attribute


class SchoolCreateModel(LibModelHelperMixin):
    name: str
    display_name: str = None
    administrative_servers: List[str] = []
    class_share_file_server: str = None
    dc_name: str = None
    dc_name_administrative: str = None
    educational_servers: List[str] = []
    home_share_file_server: str = None

    class Config(LibModelHelperMixin.Config):
        lib_class = School

    @validator("name", check_fields=False)
    def check_name(cls, value: str) -> str:
        cls.Config.lib_class.name.validate(value)
        return value

    # TODO: validate all attributes


class SchoolModel(SchoolCreateModel, APIAttributesMixin):

    _dn2name: Dict[str, str] = {}

    class Config(SchoolCreateModel.Config):
        ...

    @classmethod
    async def _from_lib_model_kwargs(cls, obj: School, request: Request, udm: UDM) -> Dict[str, Any]:
        kwargs = await super()._from_lib_model_kwargs(obj, request, udm)
        kwargs["url"] = cls.scheme_and_quote(request.url_for("get", school_name=kwargs["name"]))
        kwargs["administrative_servers"] = [
            await cls.computer_dn2name(udm, dn) for dn in obj.administrative_servers
        ]
        kwargs["class_share_file_server"] = await cls.computer_dn2name(udm, obj.class_share_file_server)
        kwargs["educational_servers"] = [
            await cls.computer_dn2name(udm, dn) for dn in obj.educational_servers
        ]
        kwargs["home_share_file_server"] = await cls.computer_dn2name(udm, obj.home_share_file_server)
        return kwargs

    @classmethod
    async def computer_dn2name(cls, udm: UDM, dn: str) -> Optional[str]:
        if not dn:
            return None
        if dn not in cls._dn2name:
            obj = await udm.obj_by_dn(dn)
            cls._dn2name[dn] = obj.props.name
        return cls._dn2name[dn]


@router.get("/", response_model=List[SchoolModel])
async def search(
    request: Request,
    name_filter: str = Query(
        None,
        alias="name",
        description="List schools with this name. '*' can be used for an " "inexact search. (optional)",
        title="name",
    ),
    logger: logging.Logger = Depends(get_logger),
    udm: UDM = Depends(udm_ctx),
    token: str = Depends(oauth2_scheme),
) -> List[SchoolModel]:
    """
    Search for schools (OUs).

    The **name** parameter is optional and supports the use of ``*`` for wildcard
    searches. No other properties can be used to filter.
    """
    logger.debug("Searching for schools with: name_filter=%r", name_filter)
    if not await OPAClient.instance().check_policy_true(
        policy="schools",
        token=token,
        request=dict(method="GET", path=["schools"]),
        target={},
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to list schools.",
        )
    if name_filter:
        filter_str = "ou={}".format(escape_filter_chars(name_filter).replace(r"\2a", "*"))
    else:
        filter_str = None
    schools = await School.get_all(udm, filter_str=filter_str)
    return [await SchoolModel.from_lib_model(school, request, udm) for school in schools]


@router.get("/{school_name}", response_model=SchoolModel)
async def get(
    request: Request,
    school_name: str = Query(
        None,
        alias="name",
        description="School (OU) with this name.",
        title="name",
    ),
    udm: UDM = Depends(udm_ctx),
    token: str = Depends(oauth2_scheme),
) -> SchoolModel:
    """
    Fetch a specific school (OU).

    - **name**: name of the school (**required**)
    """
    if not await OPAClient.instance().check_policy_true(
        policy="schools",
        token=token,
        request=dict(method="GET", path=["schools", school_name]),
        target={},
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to list schools.",
        )
    school = await School.from_dn(School(name=school_name).dn, None, udm)
    return await SchoolModel.from_lib_model(school, request, udm)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=SchoolModel)
async def create(
    school: SchoolCreateModel,
    request: Request,
    alter_dhcpd_base: Optional[bool] = None,
    udm: UDM = Depends(udm_ctx),
    logger: logging.Logger = Depends(get_logger),
    token: str = Depends(oauth2_scheme),
) -> SchoolModel:
    """
    Create a school (OU) with all the information:

    - **name**: name of the school class (**required**)
    - **display_name**: full name (**required**)
    - **dc_name**: host name of educational DC (optional)
    - **dc_name_administrative**: host name of administrative DC (optional)
    - **class_share_file_server**: host name of domain controller for the class shares (optional)
    - **home_share_file_server**: host name of domain controller for the home shares (optional)
    """
    if not await OPAClient.instance().check_policy_true(
        policy="schools",
        token=token,
        request=dict(method="POST", path=["schools"]),
        target={},
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to create schools.",
        )
    school_obj: School = await school.as_lib_model(request)
    if await school_obj.exists(udm):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="School exists.")
    try:
        await create_ou(
            ou_name=school.name,
            display_name=school.display_name,
            edu_name=school.dc_name,
            admin_name=school.dc_name_administrative,
            share_name=school.home_share_file_server or school.class_share_file_server,
            lo=udm,
            baseDN=env_or_ucr("ldap/base"),
            hostname=env_or_ucr("ldap/master"),
            is_single_master=env_or_ucr("ucsschool/singlemaster"),
            alter_dhcpd_base=alter_dhcpd_base,
        )
    except Exception as exc:
        error_msg = f"Failed to create school {school_obj.name!r}: {exc}"
        logger.exception(error_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    school_obj = await School.from_dn(school_obj.dn, school_obj.name, udm)
    return await SchoolModel.from_lib_model(school_obj, request, udm)