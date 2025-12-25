import json
import frappe
from frappe.tests.utils import FrappeTestCase

from backend.utils.mock_request import MockRequest


class TestMockRequest(FrappeTestCase):
	"""Unit tests for the MockRequest builder"""

	def test_with_data_auto_encodes_dict(self):
		"""Verify that with_data() automatically encodes a dictionary into bytes"""
		data = {"key": "value", "number": 123}
		request = MockRequest().with_data(data).build()

		self.assertIsInstance(request.data, bytes)
		decoded = json.loads(request.data.decode("utf-8"))
		self.assertEqual(decoded, data)

	def test_with_raw_data_accepts_bytes(self):
		"""Verify that with_raw_data() accepts raw bytes directly"""
		raw_bytes = b"raw binary data"
		request = MockRequest().with_raw_data(raw_bytes).build()

		self.assertEqual(request.data, raw_bytes)

	def test_with_method_sets_http_method(self):
		"""Verify that with_method() correctly sets the HTTP method"""
		request = MockRequest().with_method("POST").build()
		self.assertEqual(request.method, "POST")

		# Verify case-insensitive method handling
		request2 = MockRequest().with_method("get").build()
		self.assertEqual(request2.method, "GET")

	def test_with_header_sets_single_header(self):
		"""Verify that with_header() sets a single HTTP header"""
		request = MockRequest() \
			.with_header("Authorization", "Bearer token123") \
			.build()

		self.assertEqual(request.headers.get("Authorization"), "Bearer token123")

	def test_with_headers_sets_multiple_headers(self):
		"""Verify that with_headers() sets multiple HTTP headers at once"""
		headers = {
			"Content-Type": "application/json",
			"X-Custom-Header": "custom-value"
		}
		request = MockRequest().with_headers(headers).build()

		self.assertEqual(request.headers.get("Content-Type"), "application/json")
		self.assertEqual(request.headers.get("X-Custom-Header"), "custom-value")

	def test_with_args_sets_query_parameters(self):
		"""Verify that with_args() sets query string parameters"""
		request = MockRequest() \
			.with_args(page=1, limit=10, search="test") \
			.build()

		# Frappe parses query_string into request.args
		self.assertIn("page", request.args)
		self.assertIn("limit", request.args)
		self.assertIn("search", request.args)

	def test_with_form_sets_form_data(self):
		"""Verify that with_form() sets form-encoded request data"""
		request = MockRequest() \
			.with_form(username="john", password="secret") \
			.build()

		# Form data populates request.form
		self.assertEqual(request.form.get("username"), "john")
		self.assertEqual(request.form.get("password"), "secret")

	def test_chaining_multiple_methods(self):
		"""Verify that multiple builder methods can be chained together"""
		request = MockRequest() \
			.with_method("POST") \
			.with_data({"name": "Test"}) \
			.with_header("Authorization", "Bearer xyz") \
			.with_args(debug="true") \
			.build()

		self.assertEqual(request.method, "POST")
		self.assertIsNotNone(request.data)
		self.assertEqual(request.headers.get("Authorization"), "Bearer xyz")
		self.assertIn("debug", request.args)

	def test_attach_to_frappe_sets_frappe_request(self):
		"""Test build() sets frappe.local.request"""
		original_request = getattr(frappe.local, 'request', None)

		try:
			MockRequest() \
				.with_data({"test": "data"}) \
				.build()

			self.assertIsNotNone(frappe.local.request)
			self.assertIsNotNone(frappe.local.request.data)

			decoded = json.loads(frappe.local.request.data.decode("utf-8"))
			self.assertEqual(decoded["test"], "data")

		finally:
			# Cleanup
			if original_request is not None:
				frappe.local.request = original_request
			else:
				if hasattr(frappe.local, 'request'):
					delattr(frappe.local, 'request')

	def test_attach_to_frappe_returns_request(self):
		"""Test build() returns request object"""
		request = MockRequest().with_method("GET").build()

		self.assertIsNotNone(request)
		self.assertEqual(request.method, "GET")

	def test_default_values(self):
		"""Verify default request values when no builder methods are applied"""
		request = MockRequest().build()

		self.assertEqual(request.data, b'')
		self.assertEqual(request.method, "GET")

	def test_complex_nested_data(self):
		"""Verify with_data() correctly handles complex nested dictionaries and lists"""
		complex_data = {
			"user": {
				"name": "John Doe",
				"roles": ["admin", "user"]
			},
			"items": [
				{"id": 1, "name": "Item 1"},
				{"id": 2, "name": "Item 2"}
			]
		}
		request = MockRequest().with_data(complex_data).build()

		decoded = json.loads(request.data.decode("utf-8"))
		self.assertEqual(decoded["user"]["name"], "John Doe")
		self.assertEqual(len(decoded["items"]), 2)
		self.assertEqual(decoded["items"][0]["id"], 1)

	def test_multiple_headers_cumulative(self):
		"""Verify that multiple header setters are applied cumulatively"""
		request = MockRequest() \
			.with_header("X-Header-1", "value1") \
			.with_header("X-Header-2", "value2") \
			.with_headers({"X-Header-3": "value3"}) \
			.build()

		self.assertEqual(request.headers.get("X-Header-1"), "value1")
		self.assertEqual(request.headers.get("X-Header-2"), "value2")
		self.assertEqual(request.headers.get("X-Header-3"), "value3")

	def test_multiple_args_cumulative(self):
		"""Verify that multiple with_args() calls are applied cumulatively"""
		request = MockRequest() \
			.with_args(param1="a", param2="b") \
			.with_args(param3="c") \
			.build()

		self.assertIn("param1", request.args)
		self.assertIn("param2", request.args)
		self.assertIn("param3", request.args)

	def test_empty_data_dict(self):
		"""Verify that with_data() correctly handles an empty dictionary"""
		request = MockRequest().with_data({}).build()

		self.assertIsNotNone(request.data)
		decoded = json.loads(request.data.decode("utf-8"))
		self.assertEqual(decoded, {})

	def test_special_characters_in_data(self):
		"""Verify that JSON encoding supports special characters and Unicode"""
		data = {
			"text": "Hello \"World\"",
			"unicode": "テスト 🎉",
			"newline": "line1\nline2"
		}
		request = MockRequest().with_data(data).build()

		decoded = json.loads(request.data.decode("utf-8"))
		self.assertEqual(decoded["text"], "Hello \"World\"")
		self.assertEqual(decoded["unicode"], "テスト 🎉")
		self.assertEqual(decoded["newline"], "line1\nline2")

	def test_form_data_takes_priority_over_raw_data(self):
		"""Verify that with_form() takes priority when both form and data are set"""
		request = MockRequest() \
			.with_data({"json": "data"}) \
			.with_form(username="test") \
			.build()

		# Form should take priority
		self.assertEqual(request.form.get("username"), "test")
		# Data should not be the JSON we set
		self.assertNotEqual(request.data, b'{"json": "data"}')
