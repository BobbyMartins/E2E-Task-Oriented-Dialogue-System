import json
import requests
import logging as logger
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from base64 import b64encode


class AuthAPIEndpoints:
    token = "/oauth/token"


def create_token():
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    client_id = "751a8c8c-5814-454e-9b02-047518b75f58"
    client_secret = "E1BgGoptoshovvlL0yf0MjsjWL1rSMqmkLVE0HuvPOg"
    base64_token = b64encode(f"{client_id}:{client_secret}".encode("ascii"))
    headers['Authorization'] = b"Basic %b" % base64_token

    retry_strategy = Retry(
        total=1,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)

    try:
        response_json = http.post("https://login.inindca.com" + AuthAPIEndpoints.token,
                                  headers=headers,
                                  data={
                                      'grant_type': 'client_credentials',
                                  })
        response_content = json.loads(response_json.content)
        return response_json, response_content

    except requests.exceptions.RetryError:
        logger.info("Authorization failed!")
        raise


class AuthAPIFramework(object):

    def __init__(self):
        pass
