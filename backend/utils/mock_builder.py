import frappe
from frappe import _
from frappe.types import DF

import random
from typing import Any, Dict


class MockBuilder:
	"""mock builder dengan utility methods"""

	def __init__(self, doctype, seq: int|None=None):
		self._rand = seq if seq is not None else random.randint(0, 9999)
		self._rand_hex = f"{seq or self._rand:06X}"

		self.doctype = doctype
		self._data = {"doctype": doctype}
		self._children = {}	 # {fieldname: [rows]}

	def with_field(self, fieldname: str, value: Any):
		"""set any field"""
		self._data[fieldname] = value
		return self

	def with_fields(self, **kwargs):
		"""set multiple fields at once"""
		self._data.update(kwargs)
		return self

	def add_child(self, fieldname: str, child_data: Dict[str, Any]):
		"""add child table row"""
		if fieldname not in self._children:
			self._children[fieldname] = []
		self._children[fieldname].append(child_data)
		return self

	def build(self, insert: DF.Check=1, submit: DF.Check=0):
		"""build the document"""
		doc = frappe.get_doc(self._data)

		# Add child table rows
		for fieldname, rows in self._children.items():
			for row in rows:
				doc.append(fieldname, row)

		if insert:
			doc.insert(ignore_permissions=True)
			if submit and doc.docstatus == 0:
				doc.submit()

		return doc

	def build_dict(self):
		"""return as dict without inserting"""
		return self._data.copy()

