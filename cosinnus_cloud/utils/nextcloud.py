import logging
import secrets
import string

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from typing import Mapping, Sequence

import requests
from cosinnus.conf import settings

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
        self.message = message
        self.statuscode = statuscode

    def __repr__(self):
        return f"OCSException({self.statuscode}, {self.message!r})"

    def __str__(self):
        return f"Statuscode {self.statuscode} ({self.message})"

HEADERS = {
    "OCS-APIRequest": "true",
    "Accept": "application/json"
}


def _response_or_raise(requests_response: requests.Response):
    if not requests_response.ok:
        logger.error("Got HTTP result %s from nextcloud, text: %s", requests_response, requests_response.text)
        requests_response.raise_for_status()
    response = OCSResponse(requests_response.json())
    if response.ok:
        return response
    else:
        raise OCSException(response.statuscode, response.message)


def create_user(userid: str, display_name: str, email: str, groups: Sequence[str]) -> OCSResponse:
    
    # We don't want the user to receive an email asking the user to set a password, as the
    # login will be done via OAuth, so we just set a random password
    random_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    res = requests.post(
        f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users", 
        auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
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
        requests.delete(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users/{quote(userid)}",
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            headers=HEADERS,
        )
    )


def add_user_to_group(userid: str, groupid: str) -> OCSResponse:
    return _response_or_raise(
        requests.post(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users/{quote(userid)}/groups",
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            headers=HEADERS,
            data={"groupid": groupid},
        )
    )


def remove_user_from_group(userid: str, groupid: str) -> OCSResponse:
    return _response_or_raise(
        requests.delete(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users/{quote(userid)}/groups",
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            headers=HEADERS,
            data={"groupid": groupid},
        )
    )


def create_group(groupid: str) -> OCSResponse:
    return _response_or_raise(
        requests.post(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/groups",
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            headers=HEADERS,
            data={"groupid": groupid}
        )
    )


def create_group_folder(name: str) -> None:
    path = f"/{settings.COSINNUS_CLOUD_NEXTCLOUD_GROUPFOLDER_BASE}/{name}"
    response = requests.request(
        'mkcol',
        f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/remote.php/dav/files/{settings.COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME}{path}",
        auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
    )
    if not response.ok:
        # 405 Method not allowed means that the folder already exists, so we want to continue in that case
        if response.status_code != 405:
            logger.error("got error in DAV call %s", response.text)
            response.raise_for_status()

    return _response_or_raise(
        requests.post(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares",
            headers=HEADERS,
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            data={
                "path": path,
                "shareType": 1,
                "shareWith": name,
            }
        )
    )
