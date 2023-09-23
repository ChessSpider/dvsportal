# -*- coding: utf-8 -*-
"""Asynchronous Python client for the DVSPortal API."""
import asyncio
import base64
import json
import re
import socket

from datetime import datetime, timedelta
from functools import reduce
from typing import Dict, Optional, List,Optional,Union

import aiohttp
import async_timeout
from yarl import URL

from .__version__ import __version__
from .const import API_BASE_URI
from .exceptions import (
    DVSPortalAuthError,
    DVSPortalConnectionError,
    DVSPortalError,
)


class DVSPortal:
    """Main class for handling connections with DVSPortal."""

    def __init__(
        self,
        api_host: str,
        identifier: str,
        password: str,
        loop=None,
        request_timeout: int = 10,
        session=None,
        user_agent: str = None,
    ):
        """Initialize connection with DVSPortal."""
        self._loop = loop
        self._session = session
        self._close_session = False

        self.api_host = api_host
        self._identifier = identifier
        self._password = password

        self.request_timeout = request_timeout
        self.user_agent = user_agent

        self._token = None

        if self._loop is None:
            self._loop = asyncio.get_event_loop()

        if self._session is None:
            self._session = aiohttp.ClientSession(loop=self._loop)
            self._close_session = True

        if self.user_agent is None:
            self.user_agent = "PythonDVSPortal/{}".format(__version__)
        
        self.balance: Optional[float] = None
        self.unit_price: Optional[float] = None
        self.active_reservations: List[Dict[str, Optional[Union[datetime, str, int, float]]]] = []
        self.license_plates: Dict[str, str] = {}
        self.default_type_id: Optional[int] = None
        self.default_code: Optional[str] = None

    async def _request(self, uri: str, method: str = "POST", json={}, headers={}):
        """Handle a request to DVSPortal."""
        url = URL.build(
            scheme="https", host=self.api_host, port=443, path=API_BASE_URI
        ).join(URL(uri))

        default_headers = {
            "User-Agent": self.user_agent,
        }

        try:
            with async_timeout.timeout(self.request_timeout):
                response = await self._session.request(
                    method, url, json=json, headers={**default_headers, **headers}, ssl=True
                )
        except asyncio.TimeoutError as exception:
            raise DVSPortalConnectionError(
                "Timeout occurred while connecting to DVSPortal API."
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise DVSPortalConnectionError(
                "Error occurred while communicating with DVSPortal."
            ) from exception

        content_type = response.headers.get("Content-Type", "")

        if not content_type.startswith("application/json"):
            response_text = await response.text()
            raise DVSPortalError(
                response.status, {"message": response_text}
            )

        response_json = await response.json()
        if (response.status // 100) in [4, 5] or "ErrorMessage" in response_json:
            raise DVSPortalError(
                response.status, response_json
            )

        return response_json

    async def token(self) -> Optional[int]:
        """Return token."""
        if self._token is None:
            response = await self._request(
                "login",
                json={
                    "identifier": self._identifier,
                    "loginMethod": "Pas",
                    "password": self._password,
                    "permitMediaTypeID": 1}
            )
            self._token = response["Token"]
        return self._token

    async def authorization_header(self):
        await self.token()
        return {
            "Authorization": "Token " + str(base64.b64encode(self._token.encode("utf-8")), "utf-8")
        }

    async def update(self) -> None:
        """Fetch data from DVSPortal."""
        await self.token()

        authorization_header = await self.authorization_header()
        response = await self._request(
            "login/getbase",
            headers=authorization_header
        )
        

        if len(response["Permits"]) > 1:
            raise Exception("More than one zonal code found")
        elif len(response["Permits"]) == 0 :
            raise Exception("No zonal code found")

        if response["Permits"]:
            self.default_type_id = response["Permits"][0]["PermitMedias"][0].get("TypeID")
            self.default_code = response["Permits"][0]["PermitMedias"][0].get("Code")


        # get the first permit media (assuming there is at least one)
        permit_media = response["Permits"][0]["PermitMedias"][0] if response["Permits"] else {}

        self.balance = {
            'balance': permit_media.get("Balance"),
            'remaining_upgrades': permit_media.get('RemainingUpgrades'),
            'remaining_downgrades': permit_media.get('RemainingDowngrades')
        }
        self.unit_price = response["Permits"][0].get("UnitPrice")
        self.active_reservations = {
            reservation["LicensePlate"].get("Value"): {
                "reservation_id": reservation.get("ReservationID"),
                "valid_from": reservation.get("ValidFrom"),
                "valid_until": reservation.get("ValidUntil"),
                "license_plate": reservation["LicensePlate"].get("Value"),
                "units": reservation.get("Units"),
                "cost": reservation.get("Units") * self.unit_price if self.unit_price and reservation.get("Units") is not None else None,
            }
            for reservation in permit_media.get("ActiveReservations", {})
        }
        
        history_license_plates = [item["LicensePlate"]["Value"] for item in permit_media.get("History", {}).get("Reservations", {}).get("Items", [])]
        self.known_license_plates = set(list(self.active_reservations.keys()) + history_license_plates)


    async def end_reservation(self,*, reservation_id, type_id=None, code=None):
        """Ends reservation"""
        if type_id is None:
            type_id = self.default_type_id
        if code is None:
            code = self.default_code
        authorization_header = await self.authorization_header()

        return await self._request(
            "reservation/end",
            headers=authorization_header,
            json={
                "ReservationID": reservation_id,
                "permitMediaTypeID": type_id,
                "permitMediaCode": code
            }
        )

    async def create_reservation(
        self, 
        license_plate_value=None, 
        license_plate_name=None, 
        type_id=None, 
        code=None, 
        date_from: Optional[datetime] = None, 
        date_until: Optional[datetime] = None
    ):
        if type_id is None:
            type_id = self.default_type_id
        if code is None:
            code = self.default_code
        if date_from is None:
            date_from = datetime.now()
        
        request_data = {
            "DateFrom": date_from.isoformat(),
            "LicensePlate": {
                "Value": license_plate_value,
                "Name": license_plate_name
            },
            "permitMediaTypeID": type_id,
            "permitMediaCode": code
        }
        
        if date_until:
            request_data["DateUntil"] = date_until.isoformat()

        authorization_header = await self.authorization_header()

        return await self._request(
            "reservation/create",
            headers=authorization_header,
            json=request_data
        )

    async def close(self) -> None:
        """Close open client session."""
        if self._close_session:
            await self._session.close()

    async def __aenter__(self) -> "DVSPortal":
        """Async enter."""
        return self

    async def __aexit__(self, *exc_info) -> None:
        """Async exit."""
        await self.close()
