import json
from typing import Any
from urllib.parse import urlencode


class MockRequest:
	"""Builder utility for mocking frappe.request in test scenarios"""

	def __init__(self):
		self._data: bytes | None = None
		self._method: str = "GET"
		self._headers: dict[str, str] = {}
		self._args: dict[str, Any] = {}
		self._form: dict[str, Any] = {}

	def with_data(self, data: dict[str, Any]):
		"""Set request.data by automatically encoding a dictionary into bytes"""
		self._data = json.dumps(data).encode("utf-8")
		return self

	def with_raw_data(self, data: bytes):
		"""Set request.data directly using raw bytes"""
		self._data = data
		return self

	def with_method(self, method: str):
		"""Set the HTTP method (e.g. GET, POST, etc.)"""
		self._method = method.upper()
		return self

	def with_header(self, key: str, value: str):
		"""Set a single HTTP header"""
		self._headers[key] = value
		return self

	def with_headers(self, headers: dict[str, str]):
		"""Set multiple HTTP headers at once"""
		self._headers.update(headers)
		return self

	def with_args(self, **kwargs):
		"""Set query string parameters (GET parameters)"""
		self._args.update(kwargs)
		return self

	def with_form(self, **kwargs):
		"""Set form-encoded request payload (POST form data)"""
		self._form.update(kwargs)
		return self

	def build(self):
		"""Build and return a mock request object"""
		import frappe
		from frappe.utils import set_request

		kwargs = {
			'method': self._method,
			'headers': self._headers,
		}

		if self._form:
			kwargs['data'] = self._form
		elif self._data is not None:
			kwargs['data'] = self._data

		if self._args:
			kwargs['query_string'] = urlencode(self._args)

		set_request(**kwargs)

		return frappe.local.request
