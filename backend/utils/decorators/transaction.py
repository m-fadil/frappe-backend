from functools import wraps

import frappe


def with_transaction(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		try:
			frappe.db.begin()
			result = func(*args, **kwargs)

			if not frappe.flags.in_test:
				frappe.db.commit()

			return result
		except Exception:
			frappe.db.rollback()
			raise

	return wrapper
