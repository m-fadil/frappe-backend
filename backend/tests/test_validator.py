# ./tests/test_validator.py

import json

import frappe
from frappe.tests import IntegrationTestCase

from backend.utils.decorators.validator import BaseRequest, validate


# ============================================
# Sample DTO Classes for Testing
# ============================================
class CreateUserRequestDTO(BaseRequest):
	email: str
	first_name: str
	last_name: str | None = None
	age: int | None = None
	is_active: bool = True
	roles: list[str] | None = None


class UpdateProductRequestDTO(BaseRequest):
	product_id: int
	name: str
	price: float
	stock: int = 0
	tags: list[str] = ["tag"]


# ============================================
# Sample Functions with @validate
# ============================================


@validate(CreateUserRequestDTO)
def create_user_handler(body: CreateUserRequestDTO):
	return {
		"email": body.email,
		"first_name": body.first_name,
		"last_name": body.last_name,
		"age": body.age,
		"is_active": body.is_active,
		"roles": body.roles,
	}


@validate(CreateUserRequestDTO)
def create_user_with_error(body: CreateUserRequestDTO):
	raise ValueError("Database connection failed")


@validate(CreateUserRequestDTO)
def create_user_with_frappe_error(body: CreateUserRequestDTO):
	frappe.throw("User already exists", frappe.ValidationError)


@validate(UpdateProductRequestDTO)
def update_product_handler(body: UpdateProductRequestDTO):
	return {
		"product_id": body.product_id,
		"name": body.name,
		"price": body.price,
		"stock": body.stock,
		"tags": body.tags,
	}


# ============================================
# Test Cases
# ============================================


class TestValidatorDecorator(IntegrationTestCase):
	def setUp(self):
		frappe.request = type("Request", (), {})()
		frappe.request.data = None

	def test_valid_request_all_fields(self):
		frappe.request.data = json.dumps(
			{
				"email": "test@example.com",
				"first_name": "John",
				"last_name": "Doe",
				"age": 30,
				"is_active": True,
				"roles": ["admin", "user"],
			}
		).encode("utf-8")

		result = create_user_handler()
		self.assertEqual(result["email"], "test@example.com")
		self.assertEqual(result["first_name"], "John")
		self.assertEqual(result["last_name"], "Doe")
		self.assertEqual(result["age"], 30)
		self.assertTrue(result["is_active"])
		self.assertEqual(result["roles"], ["admin", "user"])

	def test_missing_required_field(self):
		frappe.request.data = json.dumps({"first_name": "John"}).encode("utf-8")

		with self.assertRaises(frappe.ValidationError):
			create_user_handler()

		res = frappe.response
		errors = res["errors"]

		self.assertIn("email", errors)
		self.assertEqual(errors["email"], "Missing required field")

	def test_empty_required_field(self):
		frappe.request.data = json.dumps({"email": "", "first_name": "	  "}).encode("utf-8")

		with self.assertRaises(frappe.ValidationError):
			create_user_handler()

		res = frappe.response
		errors = res["errors"]
		self.assertIn("email", errors)
		self.assertEqual(errors["email"], "Cannot be empty or whitespace")

		self.assertIn("first_name", errors)
		self.assertEqual(errors["first_name"], "Cannot be empty or whitespace")

	def test_conversion_error(self):
		frappe.request.data = json.dumps(
			{"email": "test@example.com", "first_name": "John", "age": "not_a_number"}
		).encode("utf-8")

		with self.assertRaises(frappe.ValidationError):
			create_user_handler()

		res = frappe.response
		errors = res["errors"]
		self.assertIn("age", errors)
		self.assertEqual(errors["age"], "invalid literal for int() with base 10: 'not_a_number'")

	def test_handler_runtime_error(self):
		frappe.request.data = json.dumps({"email": "test@example.com", "first_name": "John"}).encode("utf-8")

		with self.assertRaises(frappe.ValidationError) as ctx:
			create_user_with_error()
		self.assertIn("Database connection failed", str(ctx.exception))

	def test_handler_frappe_error(self):
		frappe.request.data = json.dumps({"email": "test@example.com", "first_name": "John"}).encode("utf-8")

		with self.assertRaises(frappe.ValidationError) as ctx:
			create_user_with_frappe_error()
		self.assertIn("User already exists", str(ctx.exception))

	def test_update_product_handler_defaults(self):
		frappe.request.data = json.dumps({"product_id": 1, "name": "Laptop", "price": 999.99}).encode("utf-8")

		result = update_product_handler()
		self.assertEqual(result["product_id"], 1)
		self.assertEqual(result["name"], "Laptop")
		self.assertEqual(result["price"], 999.99)
		self.assertEqual(result["stock"], 0)
		self.assertEqual(result["tags"], ["tag"])

	def test_parse_request_data_from_frappe_request(self):
		# Simulate raw JSON in frappe.request.data
		frappe.request.data = json.dumps(
			{"email": "raw@example.com", "first_name": "Raw", "age": "25"}
		).encode("utf-8")

		result = create_user_handler()
		self.assertEqual(result["email"], "raw@example.com")
		self.assertEqual(result["first_name"], "Raw")
		self.assertEqual(result["age"], 25)
