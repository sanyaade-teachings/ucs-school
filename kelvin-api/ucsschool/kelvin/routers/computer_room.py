# from typing import List
#
# from fastapi import APIRouter, HTTPException, Query
# from pydantic import (
#     BaseModel,
#     Field,
#     HttpUrl,
#     Protocol,
#     PydanticValueError,
#     SecretStr,
#     StrBytes,
#     ValidationError,
#     validator,
# )
# from starlette.status import (
#     HTTP_200_OK,
#     HTTP_201_CREATED,
#     HTTP_204_NO_CONTENT,
#     HTTP_400_BAD_REQUEST,
#     HTTP_401_UNAUTHORIZED,
#     HTTP_404_NOT_FOUND,
# )
#
# from ucsschool.lib.models.group import ComputerRoom
#
# from ..utils import get_logger
#
# logger = get_logger(__name__)
# router = APIRouter()
#
#
# class ComputerRoomModel(UcsSchoolBaseModel):
#     dn: str = None
#     name: str
#     school: HttpUrl
#     description: str = None
#
#
# @router.get("/")
# async def search(
#     name_filter: str = Query(
#         None,
#         title="List rooms with this name. '*' can be used for an inexact search.",
#         min_length=3,
#     ),
#     school_filter: str = Query(
#         None, title="List only rooms in school with this name (not URL). ", min_length=3
#     ),
# ) -> List[ComputerRoomModel]:
#     logger.debug(
#         "Searching for rooms with: name_filter=%r school_filter=%r",
#         name_filter,
#         school_filter,
#     )
#     return [
#         ComputerRoomModel(name="10a", school="https://foo.bar/schools/gsmitte"),
#         ComputerRoomModel(name="8b", school="https://foo.bar/schools/gsmitte"),
#     ]
#
#
# @router.get("/{name}")
# async def get(name: str, school: str) -> ComputerRoomModel:
#     return ComputerRoomModel(name=name, school=f"https://foo.bar/schools/{school}")
#
#
# @router.post("/", status_code=HTTP_201_CREATED)
# async def create(room: ComputerRoomModel) -> ComputerRoomModel:
#     if room.name == "alsoerror":
#         raise HTTPException(
#             status_code=HTTP_400_BAD_REQUEST, detail="Invalid computer room name."
#         )
#     room.dn = "cn=foo,cn=computers,dc=test"
#     return room
#
#
# @router.patch("/{name}", status_code=HTTP_200_OK)
# async def partial_update(name: str, room: ComputerRoomModel) -> ComputerRoomModel:
#     if name != room.name:
#         logger.info("Renaming room from %r to %r.", name, room.name)
#     return room
#
#
# @router.put("/{name}", status_code=HTTP_200_OK)
# async def complete_update(name: str, room: ComputerRoomModel) -> ComputerRoomModel:
#     if name != room.name:
#         logger.info("Renaming room from %r to %r.", name, room.name)
#     return room
#
# @router.delete("/{name}", status_code=HTTP_204_NO_CONTENT)
# async def delete(name: str, request: Request) -> None:
#     async with UDM(**await udm_kwargs()) as udm:
#         sc = await get_lib_obj(udm, ComputerRoom, name, None)
#         if await sc.exists(udm):
#             await sc.remove(udm)
#         else:
#             raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="TODO")
#     return None
