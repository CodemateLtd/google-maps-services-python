#
# Copyright 2022 Google Inc. All rights reserved.
#
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
#

"""Performs requests to the Google Maps Address Validation API."""
from googlemaps import exceptions


_ADDRESSVALIDATION_BASE_URL = "https://addressvalidation.googleapis.com"


def _addressvalidation_extract(response):
    """Extracts an Address Validation response, raising API or HTTP errors."""
    if 200 <= response.status_code < 300:
        return response.json()

    try:
        body = response.json()
    except ValueError:
        raise exceptions.HTTPError(response.status_code)

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            status = error.get("status")
            if isinstance(status, str) and status:
                raise exceptions.ApiError(status, error.get("message"))

    raise exceptions.HTTPError(response.status_code)


def _addressvalidation_feedback_extract(response):
    """Extract feedback without parsing an empty successful response."""
    if 200 <= response.status_code < 300:
        return {}
    return _addressvalidation_extract(response)


def addressvalidation(client, addressLines, regionCode=None , locality=None, enableUspsCass=None):
    """
    The Google Maps Address Validation API returns a verification of an address
    See https://developers.google.com/maps/documentation/address-validation/overview
    request must include parameters below.
    :param addressLines: The address to validate
    :type addressLines: array 
    :param regionCode: (optional) The country code
    :type regionCode: string  
    :param locality: (optional) Restrict to a locality, ie:Mountain View
    :type locality: string
    :param enableUspsCass For the "US" and "PR" regions only, you can optionally enable the Coding Accuracy Support System (CASS) from the United States Postal Service (USPS)
    :type locality: boolean
    """

    params = {
        "address":{
            "addressLines": addressLines
        }
    }

    if regionCode is not None:
        params["address"]["regionCode"] = regionCode

    if locality is not None:
        params["address"]["locality"] = locality

    if enableUspsCass is not False or enableUspsCass is not None:
        params["enableUspsCass"] = enableUspsCass

    return client._request("/v1:validateAddress", {},  # No GET params
                           base_url=_ADDRESSVALIDATION_BASE_URL,
                           extract_body=_addressvalidation_extract,
                           post_json=params)


def addressvalidation_feedback(client, response_id, conclusion):
    """Provide the final outcome of an address validation sequence.

    Send feedback once, after the transaction concludes. Use the response ID
    from the first validation response, not a later attempt in the sequence.
    See https://developers.google.com/maps/documentation/address-validation/reference/rest/v1/TopLevel/provideValidationFeedback.

    :param response_id: The ``responseId`` from the first validation response.
    :type response_id: str

    :param conclusion: One of ``VALIDATED_VERSION_USED``, ``USER_VERSION_USED``,
        ``UNVALIDATED_VERSION_USED``, or ``UNUSED``.
    :type conclusion: str

    :raises ValueError: If the response ID is not a nonempty string or the
        conclusion is not supported.
    :raises googlemaps.exceptions.ApiError: If the API returns a structured error.
    :raises googlemaps.exceptions.HTTPError: If an unsuccessful response does
        not contain a structured API error.

    :returns: An empty dictionary on success.
    :rtype: dict
    """
    if not isinstance(response_id, str) or not response_id:
        raise ValueError("response_id must be a nonempty string")
    if conclusion not in (
        "VALIDATED_VERSION_USED", "USER_VERSION_USED",
        "UNVALIDATED_VERSION_USED", "UNUSED",
    ):
        raise ValueError("conclusion must be a supported validation conclusion")

    return client._request(
        "/v1:provideValidationFeedback", {},
        base_url=_ADDRESSVALIDATION_BASE_URL,
        extract_body=_addressvalidation_feedback_extract,
        post_json={"responseId": response_id, "conclusion": conclusion},
    )
    