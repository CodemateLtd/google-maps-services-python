#
# Copyright 2020 Google Inc. All rights reserved.
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

"""Tests for the maps module."""

from unittest import mock

import responses

import googlemaps
from . import TestCase

from googlemaps.maps import StaticMapMarker
from googlemaps.maps import StaticMapPath


class MapsTest(TestCase):
    def setUp(self):
        self.key = "AIzaasdf"
        self.client = googlemaps.Client(self.key)

    @responses.activate
    def test_static_map_marker(self):
        marker = StaticMapMarker(
            locations=[{"lat": -33.867486, "lng": 151.206990}, "Sydney"],
            size="small",
            color="blue",
            label="S",
        )

        self.assertEqual(
            "size:small|color:blue|label:S|" "-33.867486,151.20699|Sydney", str(marker)
        )

        with self.assertRaises(ValueError):
            StaticMapMarker(locations=["Sydney"], label="XS")

        self.assertEqual("label:1|Sydney", str(StaticMapMarker(locations=["Sydney"], label="1")))

    @responses.activate
    def test_static_map_path(self):
        path = StaticMapPath(
            points=[{"lat": -33.867486, "lng": 151.206990}, "Sydney"],
            weight=5,
            color="red",
            geodesic=True,
            fillcolor="Red",
        )

        self.assertEqual(
            "weight:5|color:red|fillcolor:Red|"
            "geodesic:True|"
            "-33.867486,151.20699|Sydney",
            str(path),
        )

    def test_download_streams_binary_data_lazily(self):
        url = "https://maps.googleapis.com/maps/api/staticmap"
        image = b"\x89PNG\r\n\x1a\nbinary map\x00\xff"
        path = StaticMapPath(
            points=[(62.107733, -145.541936), "Delta+Junction,AK"],
            weight=5,
            color="red",
        )
        markers = [
            StaticMapMarker(
                locations=[(62.107733, -145.541936)], color="blue", label="S"
            ),
            StaticMapMarker(
                locations=["Delta+Junction,AK"], size="tiny", color="green"
            ),
            StaticMapMarker(
                locations=["Tok,AK"], size="mid", color="0xFFFF00", label="C"
            ),
        ]

        for status in (200, 299):
            with self.subTest(status=status):
                with responses.RequestsMock() as rsps:
                    rsps.add(
                        responses.GET, url, body=image, status=status,
                        content_type="image/png",
                    )
                    chunks = self.client.static_map(
                        size=(400, 400), zoom=6,
                        center=(63.259591, -144.667969),
                        maptype="hybrid", format="png", scale=2,
                        visible=["Tok,AK"], path=path, markers=markers,
                    )
                    response = rsps.calls[0].response
                    self.assertFalse(response._content_consumed)
                    self.assertEqual(0, response.raw.tell())
                    self.assertEqual(image, b"".join(chunks))

    def test_download_rejects_http_errors_without_consuming_body(self):
        url = "https://maps.googleapis.com/maps/api/staticmap"
        errors = (
            (300, "Multiple choices", "text/plain"),
            (400, '{"error": "Invalid request"}', "application/json"),
            (403, "Access denied", "text/plain"),
            (404, "<html>Map not found</html>", "text/html"),
            (429, "Too many requests", "text/plain"),
        )
        for status, body, content_type in errors:
            with self.subTest(status=status):
                with responses.RequestsMock() as rsps:
                    rsps.add(
                        responses.GET, url, body=body, status=status,
                        content_type=content_type,
                    )
                    with self.assertRaises(googlemaps.exceptions.HTTPError) as error:
                        self.client.static_map(
                            size=(400, 400), center=(0, 0), zoom=1
                        )
                    self.assertEqual(status, error.exception.status_code)
                    self.assertEqual(1, len(rsps.calls))
                    response = rsps.calls[0].response
                    self.assertFalse(response._content_consumed)
                    self.assertTrue(response.raw.closed)

    @mock.patch("googlemaps.client.time.sleep")
    def test_download_retries_transient_errors_then_streams_success(self, sleep):
        url = "https://maps.googleapis.com/maps/api/staticmap"
        image = b"\x89PNG\r\n\x1a\nbinary map\x00\xff"
        for status in (500, 503, 504):
            with self.subTest(status=status):
                with responses.RequestsMock() as rsps:
                    rsps.add(responses.GET, url, body="Unavailable", status=status)
                    rsps.add(
                        responses.GET, url, body=image, status=200,
                        content_type="image/png",
                    )
                    chunks = self.client.static_map(
                        size=(400, 400), center=(0, 0), zoom=1
                    )
                    self.assertEqual(2, len(rsps.calls))
                    self.assertFalse(rsps.calls[1].response._content_consumed)
                    self.assertEqual(image, b"".join(chunks))

    @responses.activate
    @mock.patch("googlemaps.client.time.sleep")
    def test_download_retries_503_then_raises_terminal_error(self, sleep):
        url = "https://maps.googleapis.com/maps/api/staticmap"
        responses.add(responses.GET, url, body="Unavailable", status=503)
        responses.add(
            responses.GET, url, body="<html>Map not found</html>", status=404,
            content_type="text/html",
        )
        with self.assertRaises(googlemaps.exceptions.HTTPError) as error:
            self.client.static_map(size=(400, 400), center=(0, 0), zoom=1)

        self.assertEqual(404, error.exception.status_code)
        self.assertEqual(2, len(responses.calls))
        response = responses.calls[1].response
        self.assertFalse(response._content_consumed)
        self.assertTrue(response.raw.closed)

    @responses.activate
    def test_download_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            self.client.static_map(size=(400, 400))

        with self.assertRaises(ValueError):
            self.client.static_map(
                size=(400, 400), center=(63.259591, -144.667969), zoom=6, format="test"
            )

        with self.assertRaises(ValueError):
            self.client.static_map(
                size=(400, 400), center=(63.259591, -144.667969), zoom=6, maptype="test"
            )
