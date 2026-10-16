# This Python file uses the following encoding: utf-8
#
# Copyright 2017 Google Inc. All rights reserved.
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

"""Tests for the addressvalidation module."""

import json

import responses

import googlemaps
from . import TestCase


class AddressValidationTest(TestCase):
    def setUp(self):
        self.key = "AIzaSyD_sJl0qMA65CYHMBokVfMNA7AKyt5ERYs"
        self.client = googlemaps.Client(self.key)

    def test_enable_usps_cass_serialization(self):
        address = {
            "addressLines": ["1600 Amphitheatre Parkway"],
            "regionCode": "US",
            "locality": "Mountain View",
        }
        cases = [
            ({}, {"address": address}),
            ({"enableUspsCass": True}, {
                "address": address, "enableUspsCass": True,
            }),
            ({"enableUspsCass": False}, {
                "address": address, "enableUspsCass": False,
            }),
        ]
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                with responses.RequestsMock() as http:
                    http.add(
                        responses.POST,
                        "https://addressvalidation.googleapis.com/v1:validateAddress",
                        json={"result": {}},
                        status=200,
                    )

                    self.client.addressvalidation(
                        address["addressLines"],
                        regionCode=address["regionCode"],
                        locality=address["locality"],
                        **kwargs
                    )

                    body = json.loads(http.calls[0].request.body)
                    self.assertEqual(expected, body)