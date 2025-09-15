import json
import logging as logger
from enum import Enum

API_VERSION = "v1"


class NluAPIEndpoints:
    organizations = f"/{API_VERSION}/organizations"

    @classmethod
    def domains(cls, organization_id):
        return f"{cls.organizations}/{organization_id}/domains"

    @classmethod
    def domain(cls, organization_id, domain_id):
        return f"{cls.domains(organization_id)}/{domain_id}"

    @classmethod
    def domain_versions(cls, organization_id, domain_id, include_utterances=False):
        query_parameter = "?includeUtterances=true" if include_utterances else ""
        return f"{cls.domain(organization_id, domain_id)}/versions" + query_parameter

    @classmethod
    def domain_version(cls, organization_id, domain_id, version_id, include_utterances=False):
        query_parameter = "?includeUtterances=true" if include_utterances else ""
        return f"{cls.domain_versions(organization_id, domain_id)}/{version_id}" + query_parameter


def json_decoder(data):
    try:
        return json.loads(data)
    except Exception:
        logger.exception(f"Error while decoding data: {data}")
        return data


def json_encoder(data):
    try:
        return json.dumps(data)
    except Exception:
        logger.exception(f"Error while encoding data: {data}")
        raise