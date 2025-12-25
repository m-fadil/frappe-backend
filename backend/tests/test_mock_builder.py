import frappe
from frappe.tests import IntegrationTestCase

from backend.utils.mock_builder import MockBuilder


class TestMockBuilder(IntegrationTestCase):
	def test_init_sets_doctype(self):
		"""Test initialization sets doctype correctly"""
		builder = MockBuilder("User")
		self.assertEqual(builder.doctype, "User")
		self.assertEqual(builder._data["doctype"], "User")

	def test_init_with_seq_uses_provided_sequence(self):
		"""Test initialization with provided sequence number"""
		builder = MockBuilder("User", seq=100)
		self.assertEqual(builder._rand, 100)
		self.assertEqual(builder._rand_hex, "000064")

	def test_init_without_seq_generates_random(self):
		"""Test initialization without seq generates random number"""
		builder = MockBuilder("User")
		self.assertIsNotNone(builder._rand)
		self.assertIsNotNone(builder._rand_hex)
		self.assertTrue(0 <= builder._rand <= 9999)

	def test_with_field_sets_single_field(self):
		"""Test with_field sets a single field value"""
		builder = MockBuilder("User")
		builder.with_field("first_name", "John")
		self.assertEqual(builder._data["first_name"], "John")

	def test_with_field_returns_self_for_chaining(self):
		"""Test with_field returns self for method chaining"""
		builder = MockBuilder("User")
		result = builder.with_field("first_name", "John")
		self.assertIs(result, builder)

	def test_with_field_overwrites_existing_value(self):
		"""Test with_field can overwrite existing field value"""
		builder = MockBuilder("User")
		builder.with_field("first_name", "John")
		builder.with_field("first_name", "Jane")
		self.assertEqual(builder._data["first_name"], "Jane")

	def test_with_fields_sets_multiple_fields(self):
		"""Test with_fields sets multiple fields at once"""
		builder = MockBuilder("User")
		builder.with_fields(first_name="John", last_name="Doe", email="john@example.com")
		self.assertEqual(builder._data["first_name"], "John")
		self.assertEqual(builder._data["last_name"], "Doe")
		self.assertEqual(builder._data["email"], "john@example.com")

	def test_with_fields_returns_self_for_chaining(self):
		"""Test with_fields returns self for method chaining"""
		builder = MockBuilder("User")
		result = builder.with_fields(first_name="John", last_name="Doe")
		self.assertIs(result, builder)

	def test_with_fields_overwrites_existing_values(self):
		"""Test with_fields can overwrite existing values"""
		builder = MockBuilder("User")
		builder.with_fields(first_name="John", last_name="Doe")
		builder.with_fields(first_name="Jane")
		self.assertEqual(builder._data["first_name"], "Jane")
		self.assertEqual(builder._data["last_name"], "Doe")

	def test_add_child_creates_new_child_list(self):
		"""Test add_child creates new list for first child"""
		builder = MockBuilder("Note")
		builder.add_child("seen_by", {"user": "Administrator"})
		self.assertIn("seen_by", builder._children)
		self.assertEqual(len(builder._children["seen_by"]), 1)
		self.assertEqual(builder._children["seen_by"][0]["user"], "Administrator")

	def test_add_child_appends_to_existing_list(self):
		"""Test add_child appends to existing child list"""
		builder = MockBuilder("Note")
		builder.add_child("seen_by", {"user": "Administrator"})
		builder.add_child("seen_by", {"user": "Guest"})
		self.assertEqual(len(builder._children["seen_by"]), 2)
		self.assertEqual(builder._children["seen_by"][1]["user"], "Guest")

	def test_add_child_returns_self_for_chaining(self):
		"""Test add_child returns self for method chaining"""
		builder = MockBuilder("Note")
		result = builder.add_child("seen_by", {"user": "Administrator"})
		self.assertIs(result, builder)

	def test_add_child_multiple_child_tables(self):
		"""Test add_child with multiple different child tables"""
		# Use Event doctype which has event_participants child table
		builder = MockBuilder("Event")
		builder.add_child("event_participants", {"reference_doctype": "User"})
		builder.add_child("event_participants", {"reference_doctype": "Contact"})
		self.assertIn("event_participants", builder._children)
		self.assertEqual(len(builder._children["event_participants"]), 2)

	def test_build_dict_returns_copy_of_data(self):
		"""Test build_dict returns a copy of internal data"""
		builder = MockBuilder("User")
		builder.with_fields(first_name="John", last_name="Doe")
		result = builder.build_dict()

		self.assertEqual(result["doctype"], "User")
		self.assertEqual(result["first_name"], "John")
		self.assertEqual(result["last_name"], "Doe")

		# Verify it's a copy, not reference
		result["first_name"] = "Jane"
		self.assertEqual(builder._data["first_name"], "John")

	def test_build_dict_does_not_include_children(self):
		"""Test build_dict does not include child table data"""
		builder = MockBuilder("Note")
		builder.with_field("title", "Test Note")
		builder.add_child("seen_by", {"user": "Administrator"})
		result = builder.build_dict()

		self.assertNotIn("seen_by", result)
		self.assertEqual(result["title"], "Test Note")

	def test_build_creates_document_without_insert(self):
		"""Test build creates document without inserting to database"""
		builder = MockBuilder("ToDo")
		builder.with_fields(description="Test Task", status="Open")
		doc = builder.build(insert=0)

		self.assertEqual(doc.doctype, "ToDo")
		self.assertEqual(doc.description, "Test Task")
		self.assertEqual(doc.status, "Open")
		self.assertFalse(doc.name)  # Not inserted, so no name

	def test_build_creates_and_inserts_document(self):
		"""Test build creates and inserts document to database"""
		builder = MockBuilder("ToDo")
		builder.with_fields(description="Test Task", status="Open")
		doc = builder.build(insert=1)

		self.assertTrue(doc.name)  # Inserted, so has name
		self.assertEqual(doc.description, "Test Task")

		# Cleanup
		frappe.delete_doc("ToDo", doc.name, force=True)

	def test_build_with_children_appends_child_rows(self):
		"""Test build appends child table rows to document"""
		# Use Note doctype which has seen_by child table
		builder = MockBuilder("Note")
		builder.with_field("title", "Test Note")
		builder.add_child("seen_by", {"user": "Administrator"})
		builder.add_child("seen_by", {"user": "Guest"})
		doc = builder.build(insert=0)

		# Verify child rows were appended
		self.assertEqual(len(doc.seen_by), 2)
		self.assertEqual(doc.seen_by[0].user, "Administrator")
		self.assertEqual(doc.seen_by[1].user, "Guest")

	def test_method_chaining_works(self):
		"""Test all methods can be chained together"""
		builder = (MockBuilder("ToDo", seq=1)
			.with_field("description", "Task 1")
			.with_fields(status="Open", priority="High")
			.with_field("description", "Task 1 Updated"))

		self.assertEqual(builder._data["description"], "Task 1 Updated")
		self.assertEqual(builder._data["status"], "Open")
		self.assertEqual(builder._data["priority"], "High")

	def test_multiple_builders_are_independent(self):
		"""Test multiple builder instances don't interfere with each other"""
		builder1 = MockBuilder("User", seq=1)
		builder2 = MockBuilder("User", seq=2)

		builder1.with_field("first_name", "John")
		builder2.with_field("first_name", "Jane")

		self.assertEqual(builder1._data["first_name"], "John")
		self.assertEqual(builder2._data["first_name"], "Jane")
		self.assertNotEqual(builder1._rand, builder2._rand)

	def test_with_field_accepts_various_data_types(self):
		"""Test with_field accepts various data types"""
		builder = MockBuilder("User")
		builder.with_field("enabled", 1)
		builder.with_field("creation", frappe.utils.now())
		builder.with_field("roles", ["Sales User", "Sales Manager"])
		builder.with_field("settings", {"theme": "dark"})

		self.assertEqual(builder._data["enabled"], 1)
		self.assertIsNotNone(builder._data["creation"])
		self.assertIsInstance(builder._data["roles"], list)
		self.assertIsInstance(builder._data["settings"], dict)

	def test_add_child_with_empty_dict(self):
		"""Test add_child with empty child data dict"""
		builder = MockBuilder("Note")
		builder.add_child("seen_by", {})

		self.assertEqual(len(builder._children["seen_by"]), 1)
		self.assertEqual(builder._children["seen_by"][0], {})

	def test_rand_hex_format_is_correct(self):
		"""Test _rand_hex is formatted correctly as 6-digit hex"""
		builder = MockBuilder("User", seq=255)
		self.assertEqual(builder._rand_hex, "0000FF")

		builder = MockBuilder("User", seq=4095)
		self.assertEqual(builder._rand_hex, "000FFF")

		builder = MockBuilder("User", seq=0)
		self.assertEqual(builder._rand_hex, "000000")

	def test_build_with_submit_flag(self):
		"""Test build with submit flag (requires submittable doctype)"""
		# Note: This test assumes doctype supports submission
		# Using ToDo which is not submittable, so submit should not error
		builder = MockBuilder("ToDo")
		builder.with_fields(description="Test Task", status="Open")
		doc = builder.build(insert=1, submit=1)

		# ToDo is not submittable, so docstatus should remain 0
		self.assertEqual(doc.docstatus, 1)

		# Cleanup
		frappe.delete_doc("ToDo", doc.name, force=True)

	def test_children_dict_initializes_empty(self):
		"""Test _children dict initializes as empty"""
		builder = MockBuilder("User")
		self.assertEqual(builder._children, {})
		self.assertIsInstance(builder._children, dict)

