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
from cosinnus_cloud.models import CloudFile
from cosinnus.utils.group import get_cosinnus_group_model

logger = logging.getLogger("cosinnus")


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
    userid: str, display_name: str, email: str
) -> OCSResponse:

    # We don't want the user to receive an email asking the user to set a password, as the
    # login will be done via OAuth, so we just set a random password
    random_password = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
    )
    
    data = {
        "userid": userid,
        "displayName": display_name,
        "email": email,
        "password": random_password,
    }
    res = requests.post(
        f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/ocs/v1.php/cloud/users",
        auth=settings.COSINNUS_CLOUD_NEXTCLOUD_AUTH,
        headers=HEADERS,
        data=data,
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

    if response.data and any(folder['mount_point'] == name for folder in response.data.values()):
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

    
def files_search(folder_id=None, timeout=5, order_by_last_modified=False):
    """ Webdav request that lists all files in order by last modified date for all files from the root of
        the admin user, or from a specified folder.
        @param order_by_last_modified:  should the webdav API sort results by last modified?
            if True, results will be sorted by the actual last modified date, which includes
                files' actual timestampt. so recently uploaded old files will not show as new!
            if False, defaults to id ordering, which makes a nice "newest files" list, but
                ignores changes and edits to documents """
    url = f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/remote.php/dav/"
    
    folder_term = ""
    if folder_id:
        folder_term = f"{folder_id}/"
    
    order_term = ""
    if order_by_last_modified:
        order_term = """\
<d:orderby>
    <d:order>
        <d:prop>
            <d:getlastmodified/>
        </d:prop>
        <d:ascending/>
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
                <d:href>/files/{settings.COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME}/{folder_term}</d:href>
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


def list_group_folder_files(groupfolder_id, user=None):
    """ Returns a list of `CloudFile`s for a given nextcloud GroupFolder id """
    try:
        response_text = files_search(groupfolder_id)
    except Exception as e:
        return []
    file_list = parse_cloud_files_search_response(response_text, user=user)
    return file_list


def list_user_group_folders_files(user):
    """ Returns a list of `CloudFile`s from all GroupFolders of a given user """
    try:
        response_text = files_search(order_by_last_modified=True)
    except Exception as e:
        return []
    
    # get nextcloud groupfolder ids for user's groups
    user_groups = get_cosinnus_group_model().objects.get_for_user(user)
    user_groupfolder_id_list = [urllib.parse.quote(group.nextcloud_group_id) for group in user_groups if group.nextcloud_group_id]
    
    # post-filter search for the file path starting with a groupfolder that the user is part of
    file_list = parse_cloud_files_search_response(
        response_text,
        path_filter=lambda path: any((path.startswith(f"/{groupfolder}/") for groupfolder in user_groupfolder_id_list)),
        user=user
    )
    return file_list


def parse_cloud_files_search_response(response_text, path_filter=None, user=None):
    """ Parses a Webdav endpoint response text into a list of `CloudFile`s
        @param response_text: The requests's response.text
        @param path_filter: If given, a function with path as argument that has to  
            be truthy for each given file to be included in the results
        @param user: If given, attaches the user as "owner" of each of the files
    """
    
    soup = BeautifulSoup(response_text, 'xml')
    content = soup.find('d:multistatus')
    if not content:
        return []
    
    cloud_file_list = []
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
            url = domain + filepath
            filename = urllib.parse.unquote(splits[-1])
            folder_name = urllib.parse.unquote(splits[-2])
            actual_path = filepath.split(f"/dav/files/{settings.COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME}")[1]
            if path_filter is not None and not path_filter(actual_path):
                continue # result did not match the path filter
            root_folder_name = urllib.parse.unquote(actual_path.split('/')[1]) # starts with '/', so take 2nd item
            
            cloud_file_list.append(
                CloudFile(
                    title=filename,
                    url=f"{settings.COSINNUS_CLOUD_NEXTCLOUD_URL}/f/{file_id}",
                    download_url=url,
                    type=None,
                    folder=folder_name,
                    root_folder=root_folder_name,
                    path=actual_path,
                    user=user,
                )
            )
    return cloud_file_list
