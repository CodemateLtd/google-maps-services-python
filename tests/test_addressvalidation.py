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


class AddressValidationFeedbackTest(TestCase):
    def setUp(self):
        self.client = googlemaps.Client("AIza-feedback-tests-non-secret")
        self.url = (
            "https://addressvalidation.googleapis.com/v1:provideValidationFeedback"
        )

    def test_feedback_submits_supported_conclusions(self):
        for conclusion in (
            "VALIDATED_VERSION_USED", "USER_VERSION_USED",
            "UNVALIDATED_VERSION_USED", "UNUSED",
        ):
            with self.subTest(conclusion=conclusion):
                with responses.RequestsMock() as http:
                    http.add(
                        responses.POST, self.url, body="", status=200,
                        match=[responses.matchers.json_params_matcher({
                            "responseId": "initial-response-id",
                            "conclusion": conclusion,
                        })],
                    )

                    self.assertEqual({}, self.client.addressvalidation_feedback(
                        "initial-response-id", conclusion
                    ))

    @responses.activate
    def test_feedback_accepts_no_content(self):
        responses.add(responses.POST, self.url, status=204)

        self.assertEqual({}, self.client.addressvalidation_feedback(
            "initial-response-id", "UNUSED"
        ))

    @responses.activate
    def test_feedback_rejects_invalid_response_ids_before_transport(self):
        for response_id in ("", None, 123, []):
            with self.subTest(response_id=response_id):
                with self.assertRaises(ValueError):
                    self.client.addressvalidation_feedback(response_id, "UNUSED")

        self.assertEqual(0, len(responses.calls))

    @responses.activate
    def test_feedback_rejects_invalid_conclusions_before_transport(self):
        for conclusion in (
            "VALIDATION_CONCLUSION_UNSPECIFIED", "UNKNOWN",
            "validated_version_used", None, [],
        ):
            with self.subTest(conclusion=conclusion):
                with self.assertRaises(ValueError):
                    self.client.addressvalidation_feedback(
                        "initial-response-id", conclusion
                    )

        self.assertEqual(0, len(responses.calls))

    @responses.activate
    def test_feedback_raises_structured_api_errors(self):
        responses.add(
            responses.POST, self.url, status=400,
            json={"error": {
                "status": "INVALID_ARGUMENT",
                "message": "The response ID is unknown.",
            }},
        )

        with self.assertRaises(googlemaps.exceptions.ApiError) as error:
            self.client.addressvalidation_feedback("unknown-response-id", "UNUSED")

        self.assertEqual("INVALID_ARGUMENT", error.exception.status)
        self.assertEqual("The response ID is unknown.", error.exception.message)

    @responses.activate
    def test_feedback_raises_http_errors_for_non_json_bodies(self):
        responses.add(
            responses.POST, self.url, status=403,
            body="<html>Access denied</html>", content_type="text/html",
        )

        with self.assertRaises(googlemaps.exceptions.HTTPError) as error:
            self.client.addressvalidation_feedback("initial-response-id", "UNUSED")

        self.assertEqual(403, error.exception.status_code)

    @responses.activate
    def test_feedback_retries_transient_errors_before_extraction(self):
        responses.add(
            responses.POST, self.url, body="Unavailable", status=503,
        )
        responses.add(responses.POST, self.url, body="", status=200)

        with mock.patch("googlemaps.client.time.sleep"):
            self.assertEqual({}, self.client.addressvalidation_feedback(
                "initial-response-id", "USER_VERSION_USED"
            ))

        self.assertEqual([503, 200], [
            call.response.status_code for call in responses.calls
        ])