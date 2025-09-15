import logging as logger
import time

import aiohttp
import requests
from hamcrest import assert_that
from utils import json_decoder, json_encoder
from utils import NluAPIEndpoints as NLUEp


class NluAPIFramework(object):
    def __init__(self, organisation_id, base_url):
        self.organization_id = organisation_id

        self.request_headers = {
            'Inin-Organization-Id': self.organization_id,
            'Content-Type': 'application/json'
        }

        self.base_url = base_url


    def show_domain_details(self, domain_id):

        """This method shows the details of a domain given its id"""

        response_json = requests.get(self.base_url + NLUEp.domain(self.organization_id,
                                                                  domain_id), headers=self.request_headers)

        response_content = json_decoder(response_json.content)

        return response_json, response_content

    def list_domain_versions_for_domain(self, domain_id, include_utterances=False):

        """This method lists all the domain versions available per domain """

        response_json = requests.get(
            self.base_url + NLUEp.domain_versions(self.organization_id, domain_id, include_utterances),
            headers=self.request_headers
        )
        response_content = json_decoder(response_json.content)

        return response_json, response_content

    def show_domain_version_details(self, domain_id, version_id, include_utterances=False):

        """This method shows the details of a domain version given a version id"""

        response_json = requests.get(
            self.base_url + NLUEp.domain_version(self.organization_id, domain_id, version_id, include_utterances),
            headers=self.request_headers
        )
        response_content = json_decoder(response_json.content)

        return response_json, response_content

if __name__ == '__main__':
    nlu_api = NluAPIFramework('3893d439-310d-47fe-a218-93823ad044a5', 'https://language-understanding-service.prv-use1-ai.dev-pure.cloud')
    version_deets = nlu_api.show_domain_version_details('11e87964-c188-4626-98f1-462a472d07af', 'b586e69c-50c0-49ad-82a0-9719a10aa612')
    print(nlu_api.show_domain_version_details('11e87964-c188-4626-98f1-462a472d07af', 'b586e69c-50c0-49ad-82a0-9719a10aa612'))

