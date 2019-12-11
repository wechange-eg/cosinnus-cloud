import logging
import secrets
import string

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from typing import Mapping, Sequence

import requests

logger = logging.getLogger('cosinnus')

class OCSResponse:

    def __init__(self, json):
        self.json = json

    @property
    def status(self) -> str:
        return self.json['ocs']['meta']['status']

    @property
    def statuscode(self) -> int:
        return int(self.json['ocs']['meta']['statuscode'])

    @property
    def message(self) -> str:
        return self.json['ocs']['meta']['message']

    @property
    def data(self) -> Mapping[str, object]:
        return self.json['ocs']['data']

    @property
    def ok(self):
        """True iff the status is 'ok'"""
        return self.status == "ok"

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"<OCSResponse status={self.status} statuscode={self.statuscode} data={self.data}>"

    def __str__(self):
        return str(self.json)
    
class OCSException(RuntimeError):
    
    def __init__(self, statuscode, message):
        #super().__init__(message)
        self.message = message
        self.statuscode = statuscode

    def __repr__(self):
        return f"OCSException({self.statuscode}, {self.message!r})"

    def __str__(self):
        return f"Statuscode {self.statuscode} ({self.message})"

# FIXME
PREFIX = "http://pratchett/nextcloud"
AUTH = ("admin", "admin")

HEADERS = {
    "OCS-APIRequest": "true",
    "Accept": "application/json"
}


def _response_or_raise(requests_response: requests.Response):
    if not requests_response.ok:
        logger.error("Got HTTP result %s from nextcloud", requests_response)
        requests_response.raise_for_status()
    response = OCSResponse(requests_response.json())
    if response.ok:
        return response
    else:
        raise OCSException(response.statuscode, response.message)


def create_user(userid: str, display_name: str, email: str, groups: Sequence[str]) -> OCSResponse:
    
    # We don't want the user to receive an email asking him to set a password, as the
    # login will be done via OAuth, so we just set a random password
    random_password = ''.join(secrets.choice(string.ascii_letters + string.punctuation + string.digits) for _ in range(32))
    
    res = requests.post(
        f"{PREFIX}/ocs/v1.php/cloud/users", 
        auth=AUTH,
        headers=HEADERS,
        data={
            "userid": userid,
            "displayName": display_name,
            "email": email,
            "groups": groups,
            "password": random_password
        })
    return _response_or_raise(res)


def delete_user(userid: str) -> OCSResponse:
    return _response_or_raise(
        requests.delete(f"{PREFIX}/ocs/v1.php/cloud/users/{quote(userid)}", auth=AUTH, headers=HEADERS)
    )


def add_user_to_group(userid: str, groupid: str) -> OCSResponse:
    return _response_or_raise(
        requests.post(f"{PREFIX}/ocs/v1.php/cloud/users/{quote(userid)}/groups", auth=AUTH, headers=HEADERS, data={"groupid": groupid})
    )


def remove_user_from_group(userid: str, groupid: str) -> OCSResponse:
    return _response_or_raise(
        requests.delete(f"{PREFIX}/ocs/v1.php/cloud/users/{quote(userid)}/groups", auth=AUTH, headers=HEADERS, data={"groupid": groupid})
    )


def create_group(name: str) -> OCSResponse:
    return _response_or_raise(
        requests.post(f"{PREFIX}/ocs/v1.php/cloud/groups", auth=AUTH, headers=HEADERS, data={"groupid": name})
    )

