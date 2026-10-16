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

from datetime import datetime, timedelta
from unittest import mock

import responses

import googlemaps
from . import TestCase


class AddressValidationTest(TestCase):
    def setUp(self):
        self.key = "AIzaSyD_sJl0qMA65CYHMBokVfMNA7AKyt5ERYs"
        self.client = googlemaps.Client(self.key)

    def test_structured_errors(self):
        cases = [
            (400, "INVALID_ARGUMENT"),
            (403, "PERMISSION_DENIED"),
            (404, "NOT_FOUND"),
            (429, "RESOURCE_EXHAUSTED"),
            (502, "INTERNAL"),
        ]
        for status_code, status in cases:
            with self.subTest(status_code=status_code):
                with responses.RequestsMock() as http:
                    http.add(
                        responses.POST,
                        "https://addressvalidation.googleapis.com/v1:validateAddress",
                        json={"error": {
                            "code": status_code,
                            "status": status,
                            "message": "Address validation failed.",
                        }},
                        status=status_code,
                    )

                    with self.assertRaises(googlemaps.exceptions.ApiError) as error:
                        self.client.addressvalidation(["1600 Amphitheatre Parkway"])

                    self.assertEqual(status, error.exception.status)
                    self.assertEqual(
                        "Address validation failed.", error.exception.message
                    )
                    self.assertEqual(1, len(http.calls))

    @responses.activate
    def test_structured_error_without_message(self):
        responses.add(
            responses.POST,
            "https://addressvalidation.googleapis.com/v1:validateAddress",
            json={"error": {"code": 403, "status": "PERMISSION_DENIED"}},
            status=403,
        )

        with self.assertRaises(googlemaps.exceptions.ApiError) as error:
            self.client.addressvalidation(["1600 Amphitheatre Parkway"])

        self.assertEqual("PERMISSION_DENIED", error.exception.status)
        self.assertIsNone(error.exception.message)

    def test_malformed_error_responses(self):
        bodies = [
            "<html>Bad request</html>",
            "[]",
            '{"error": "Bad request"}',
            '{"error": {"message": "Bad request"}}',
        ]
        for body in bodies:
            with self.subTest(body=body):
                with responses.RequestsMock() as http:
                    http.add(
                        responses.POST,
                        "https://addressvalidation.googleapis.com/v1:validateAddress",
                        body=body,
                        status=400,
                    )

                    with self.assertRaises(googlemaps.exceptions.HTTPError) as error:
                        self.client.addressvalidation(["1600 Amphitheatre Parkway"])

                    self.assertEqual(400, error.exception.status_code)

    @responses.activate
    def test_transient_error_retries_before_extraction(self):
        url = "https://addressvalidation.googleapis.com/v1:validateAddress"
        responses.add(responses.POST, url, body="Unavailable", status=503)
        responses.add(
            responses.POST,
            url,
            json={"error": {"status": "PERMISSION_DENIED"}},
            status=403,
        )

        with mock.patch("googlemaps.client.time.sleep"):
            with self.assertRaises(googlemaps.exceptions.ApiError) as error:
                self.client.addressvalidation(["1600 Amphitheatre Parkway"])

        self.assertEqual("PERMISSION_DENIED", error.exception.status)
        self.assertEqual([503, 403], [
            call.response.status_code for call in responses.calls
        ])

    @responses.activate
    def test_transient_error_exhausts_retry_timeout(self):
        responses.add(
            responses.POST,
            "https://addressvalidation.googleapis.com/v1:validateAddress",
            body="Unavailable",
            status=503,
        )
        started = datetime(2026, 1, 1)
        with mock.patch("googlemaps.client.datetime") as clock:
            clock.now.side_effect = [
                started, started, started + timedelta(seconds=61)
            ]
            with self.assertRaises(googlemaps.exceptions.Timeout):
                self.client.addressvalidation(["1600 Amphitheatre Parkway"])

        self.assertEqual(1, len(responses.calls))