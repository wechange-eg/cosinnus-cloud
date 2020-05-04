import logging
import secrets
import string

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from typing import Mapping, Sequence

import requests
from cosinnus.conf import settings
from cosinnus.models.group import CosinnusPortal
from bs4 import BeautifulSoup
import urllib

logger = logging.getLogger("cosinnus")

# should the webdav API sort results by last modified?
# if True, results will be sorted by the actual last modified date, which includes
#     files' actual timestampt. so recently uploaded old files will not show as new!
# if False, defaults to id ordering, which makes a nice "newest files" list, but
#     ignores changes and edits to documents
WEBDAV_API_ORDER_BY_LAST_MODIFIED = False


class OCSResponse:
    def __init__(self, json):
        self.json = json

    @property
    def status(self) -> str:
        return self.json["ocs"]["meta"]["status"]

    @property
    def statuscode(self) -> int:
        return int(self.json["ocs"]["meta"]["statuscode"])

    @property
    def message(self) -> str:
        return self.json["ocs"]["meta"]["message"]

    @property
    def data(self) -> Mapping[str, object]:
        return self.json["ocs"]["data"]

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


HEADERS = {"OCS-APIRequest": "true", "Accept": "application/json"}
WEBDAV_HEADERS = {"Content-Type": "text/xml"}


def _response_or_raise(requests_response: requests.Response):
    if not requests_response.ok:
        logger.error(
            "Got HTTP result %s from nextcloud, text: %s",
            requests_response,
            requests_response.text,
        )
        requests_response.raise_for_status()
    try:
        response_json = requests_response.json()
    except:
        raise OCSException(-1, requests_response.text)
    response = OCSResponse(response_json)
    if response.ok:
        return response
    else:
        raise OCSException(response.statuscode, response.message)
    
def _webdav_response_or_raise(requests_response: requests.Response):
    if not requests_response.ok:
        logger.error(
            "Got Webdav HTTP result %s from nextcloud, text: %s",
            requests_response,
            requests_response.text,
        )
        requests_response.raise_for_status()
    return requests_response.text


def create_user(
    userid: str, display_name: str, email: str, groups: Sequence[str]
) -> OCSResponse:

    # We don't want the user to receive an email asking the user to set a password, as the
    # login will be done via OAuth, so we just set a random password
    random_password = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
    )

    res = requests.post(
        f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users",
        auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
        headers=HEADERS,
        data={
            "userid": userid,
            "displayName": display_name,
            "email": email,
            "groups": groups,
            "password": random_password,
        },
    )
    return _response_or_raise(res)

def disable_user(userid: str) -> OCSResponse:
    return _response_or_raise(
        requests.put(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users/{quote(userid)}/disable",
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            headers=HEADERS,
        )
    )
    
def enable_user(userid: str) -> OCSResponse:
    return _response_or_raise(
        requests.put(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users/{quote(userid)}/enable",
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            headers=HEADERS,
        )
    )

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
    try:
        return _response_or_raise(
            requests.post(
                f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/groups",
                auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
                headers=HEADERS,
                data={"groupid": groupid},
            )
        )
    except OCSException as e:
        if e.statuscode == 102:
            logger.warning("group [%s] already exists, doing nothing", groupid)
            return None
        raise
        


def create_group_folder(name: str, group_id: str, raise_on_existing_name=True) -> None:
    # First, check whether the name is already taken (workaround for bug in groupfolders)
    response = _response_or_raise(
        requests.get(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/apps/groupfolders/folders",
            headers=HEADERS,
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
        )
    )

    if any(folder['mount_point'] == name for folder in response.data.values()):
        if raise_on_existing_name:
            raise ValueError("A groupfolder with that name already exists")
        else:
            logger.warning("group folder [%s] already exists, doing nothing", name)
            return
    response = _response_or_raise(
        requests.post(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/apps/groupfolders/folders",
            headers=HEADERS,
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            data={"mountpoint": name},
        )
    )

    folder_id = response.data["id"]

    return _response_or_raise(
        requests.post(
            f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/apps/groupfolders/folders/{folder_id}/groups",
            headers=HEADERS,
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            data={"group": group_id},
        )
    )
    
    
def group_folder_files_search(groupfolder_id, timeout=5):
    """ Webdav request that lists all files in order by last modified date """
    url = f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/remote.php/dav/"
    order_term = ""
    if WEBDAV_API_ORDER_BY_LAST_MODIFIED:
        order_term = """\
<d:orderby>
    <d:order>
        <d:prop>
            <d:getlastmodified/>
        </d:prop>
        <d:descending/>
    </d:order>
</d:orderby>"""
    
    body = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
    <d:basicsearch>
        <d:select>
            <d:prop>
                <d:displayname/>
                <oc:fileid/>
            </d:prop>
        </d:select>
        <d:from>
            <d:scope>
                <d:href>/files/{settings.COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME}/{groupfolder_id}/</d:href>
                <d:depth>infinity</d:depth>
            </d:scope>
        </d:from>
        <d:where>
            <d:gte>
                <d:prop>
                    <oc:size/>
                </d:prop>
                <d:literal>0</d:literal>
            </d:gte>
        </d:where>
        {order_term}
    </d:basicsearch>
</d:searchrequest>"""
    return _webdav_response_or_raise(
        requests.request(
            method='SEARCH',
            url=url,
            auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
            headers=WEBDAV_HEADERS,
            timeout=timeout,
            data=body,
        )
    )

def list_group_folder_files(groupfolder_id):
    """ Returns a tupled list of [filename, folder-name, file-id, download-url] to """
    try:
        response_text = group_folder_files_search(groupfolder_id)
    except Exception as e:
        return []
    
    soup = BeautifulSoup(response_text, 'xml')
    content = soup.find('d:multistatus')
    if not content:
        return []
    
    file_list = []
    domain = CosinnusPortal.get_current().get_domain()
    
    all_responses = content.find_all('d:response') 
    # since nextcloud seemingly ignores the last-modified sorting, reverse the list,
    # at least then it is sorted by IDs (last created)
    all_responses = reversed(all_responses)
    for search_result in all_responses:
        filepath = search_result.find('d:href').get_text()
        if filepath:
            if filepath.endswith('/'):
                continue # result is a folder
            splits = filepath.split('/')
            id_pointer = search_result.find('oc:fileid')
            file_id = id_pointer and id_pointer.get_text() or None
            file_list.append([
                urllib.parse.unquote(splits[-1]),
                urllib.parse.unquote(splits[-2]), 
                file_id, 
                domain + filepath
            ])
    return file_list
        