import hashlib
import inspect
import json
import threading
from copy import deepcopy
from functools import wraps
from typing import Any, Union, get_args, get_origin

import frappe

from backend.utils.exceptions import BaseAPIException, InternalServerException


# =================================
# Base Request Class
# =================================
class BaseRequest:
	"""Base class untuk semua request DTOs"""

	def __init__(self, **kwargs):
		for key, value in kwargs.items():
			setattr(self, key, value)

	def __repr__(self):
		attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
		return f"{self.__class__.__name__}({attrs})"


# =================================
# Type Inspector
# =================================
class TypeInspector:
	"""Handles type introspection and metadata extraction"""

	def __init__(self):
		self._cache: dict[type, tuple] = {}
		self._lock = threading.RLock()  # Thread-safe cache access

	def is_optional(self, field_type) -> bool:
		"""Check if field is Optional (Union with None)"""
		origin = get_origin(field_type)
		if origin is None:
			return False

		# Fix: Use proper type checking instead of string comparison
		try:
			# Python 3.10+ has types.UnionType for X | Y syntax
			import types

			if origin is Union or (hasattr(types, "UnionType") and isinstance(field_type, types.UnionType)):
				return type(None) in get_args(field_type)
		except ImportError:
			# Fallback for older Python versions
			if origin is Union:
				return type(None) in get_args(field_type)

		return False

	def get_actual_type(self, field_type):
		"""Extract actual type from Optional field (Optional[int] -> int)"""
		origin = get_origin(field_type)

		try:
			import types

			is_union = origin is Union or (
				hasattr(types, "UnionType") and isinstance(field_type, types.UnionType)
			)
		except ImportError:
			is_union = origin is Union

		if is_union:
			args = get_args(field_type)
			non_none_types = [arg for arg in args if arg is not type(None)]
			return non_none_types[0] if non_none_types else field_type

		return field_type

	def get_type_name(self, target_type: type) -> str:
		"""Get safe type name for error messages"""
		return getattr(target_type, "__name__", getattr(target_type, "_name", str(target_type)))

	def get_field_metadata(self, dto_class: type[BaseRequest]) -> tuple[list[str], list[str], dict, dict]:
		"""
		Extract and cache field metadata from DTO class (Thread-safe)
		Returns: (required_fields, optional_fields, type_hints, default_values)
		"""
		with self._lock:
			if dto_class in self._cache:
				return self._cache[dto_class]

			type_hints = {}
			defaults = {}

			# Collect from all classes in MRO (child overrides parent)
			for cls in reversed(dto_class.__mro__):
				if hasattr(cls, "__annotations__"):
					type_hints.update(cls.__annotations__)

					# Collect default values with deep copy for mutable types
					for field_name in cls.__annotations__:
						if hasattr(cls, field_name):
							default_value = getattr(cls, field_name)
							if not callable(default_value) and not field_name.startswith("_"):
								# Deep copy mutable defaults to avoid shared state
								if isinstance(default_value, (list, dict, set)):
									defaults[field_name] = deepcopy(default_value)
								else:
									defaults[field_name] = default_value

			# Separate required and optional fields
			required_fields = []
			optional_fields = []

			for field_name, field_type in type_hints.items():
				if field_name in defaults or self.is_optional(field_type):
					optional_fields.append(field_name)
				else:
					required_fields.append(field_name)

			result = (required_fields, optional_fields, type_hints, defaults)
			self._cache[dto_class] = result
			return result


# =================================
# type Converter
# =================================
class TypeConverter:
	"""Handles type conversion with caching and error handling"""

	MAX_CACHE_SIZE = 1000  # Prevent unbounded growth

	def __init__(self):
		self._json_cache: dict[str, Any] = {}
		self._type_inspector = TypeInspector()
		self._lock = threading.RLock()  # Thread-safe cache

	def clear_cache(self):
		"""Clear JSON parsing cache"""
		with self._lock:
			self._json_cache.clear()

	def normalize_null_string(self, value: Any) -> Any:
		"""Convert string "null" (case-insensitive) to None"""
		return None if isinstance(value, str) and value.lower() == "null" else value

	def safe_json_parse(self, value: str) -> Any:
		"""Parse JSON string with secure caching using hash"""
		if not isinstance(value, str):
			return None

		# Fix: Use hash instead of prefix to avoid collision
		cache_key = hashlib.md5(value.encode("utf-8")).hexdigest()

		with self._lock:
			if cache_key in self._json_cache:
				return self._json_cache[cache_key]

			# Enforce cache size limit
			if len(self._json_cache) >= self.MAX_CACHE_SIZE:
				# Remove oldest 20% of entries (simple FIFO)
				items_to_remove = list(self._json_cache.keys())[: self.MAX_CACHE_SIZE // 5]
				for key in items_to_remove:
					del self._json_cache[key]

		try:
			result = json.loads(value)
			with self._lock:
				self._json_cache[cache_key] = result
			return result
		except json.JSONDecodeError:
			return None

	def convert_to_int(self, value: Any) -> int | None:
		"""Convert value to integer"""
		if isinstance(value, str):
			value = value.strip()
			# Fix: Check for empty string explicitly, not falsy
			if value == "":
				return None
			if "." in value:
				return int(float(value))
		return int(value)

	def convert_to_float(self, value: Any) -> float | None:
		"""Convert value to float"""
		if isinstance(value, str):
			value = value.strip()
			# Fix: Check for empty string explicitly
			if value == "":
				return None
		return float(value)

	def convert_to_bool(self, value: Any) -> bool:
		"""Convert value to boolean"""
		if isinstance(value, str):
			return value.lower() in ("true", "1", "yes", "on")
		return bool(value)

	def convert_to_list(self, value: Any) -> list:
		"""Convert value to list"""
		if isinstance(value, str):
			parsed = self.safe_json_parse(value)
			if isinstance(parsed, list):
				return parsed
			return [item.strip() for item in value.split(",") if item.strip()]
		elif isinstance(value, list):
			return value
		else:
			return [value]

	def convert_to_dict(self, value: Any) -> dict | Any:
		"""Convert value to dict"""
		if isinstance(value, str):
			parsed = self.safe_json_parse(value)
			if isinstance(parsed, dict):
				return parsed
		elif isinstance(value, dict):
			return value
		return value

	def convert(self, value: Any, target_type: type) -> Any:
		"""Convert value to target type with comprehensive handling"""
		if value is None:
			return None

		# Handle Union types first to extract actual type
		origin = get_origin(target_type)
		if origin is Union:
			args = get_args(target_type)
			non_none_types = [arg for arg in args if arg is not type(None)]
			target_type = non_none_types[0] if non_none_types else target_type
			origin = get_origin(target_type)  # Update origin after unwrapping

		# FIX: E721 - Use `is` for type comparisons
		if origin is list or target_type is list:
			return self.convert_to_list(value)
		elif origin is dict or target_type is dict:
			return self.convert_to_dict(value)

		# Early return if already correct type (safe for non-generic types)
		try:
			if isinstance(value, target_type):
				return value
		except TypeError:
			pass

		# type conversion mapping
		converters = {
			str: lambda v: str(v),
			int: self.convert_to_int,
			float: self.convert_to_float,
			bool: self.convert_to_bool,
		}

		# Try direct converter
		if target_type in converters:
			return converters[target_type](value)

		# Fallback: try direct conversion
		try:
			return target_type(value)
		except (ValueError, TypeError):
			type_name = self._type_inspector.get_type_name(target_type)
			raise ValueError(f"Cannot convert '{value}' to {type_name}")


# =================================
# Request Parser
# =================================
class RequestParser:
	"""Handles request data parsing and normalization"""

	def __init__(self, converter: TypeConverter):
		self.converter = converter

	def parse_request_data(self, kwargs: dict) -> dict:
		"""Parse and normalize request data from frappe.request"""
		try:
			raw_data = frappe.request.data
			if isinstance(raw_data, bytes):
				# Fix: Handle encoding errors gracefully
				try:
					raw_data = raw_data.decode("utf-8")
				except UnicodeDecodeError:
					# Try alternative encodings
					for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
						try:
							raw_data = raw_data.decode(encoding)
							break
						except UnicodeDecodeError:
							continue
					else:
						# Last resort: ignore errors
						raw_data = raw_data.decode("utf-8", errors="ignore")

			data = json.loads(raw_data)

			# Normalize null strings
			normalized_data = {
				key: self.converter.normalize_null_string(value) for key, value in data.items()
			}
			kwargs.update(normalized_data)
		except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
			pass

		return kwargs


# =================================
# Validator
# =================================
class RequestValidator:
	"""Main validator class for request validation and conversion"""

	def __init__(self):
		self.type_inspector = TypeInspector()
		self.converter = TypeConverter()
		self.parser = RequestParser(self.converter)

	def validate_required_fields(
		self, required_fields: list[str], kwargs: dict
	) -> tuple[list[str], dict[str, str]]:
		"""
		Validate required fields presence and emptiness
		Returns: (missing_fields, empty_fields)
		"""
		missing_fields = [f for f in required_fields if f not in kwargs]

		# Fix: Handle whitespace and empty collections
		empty_fields = {}
		for field in required_fields:
			if field in kwargs:
				value = kwargs[field]
				# Check for None, empty string, or whitespace-only string
				if value is None or value == "":
					empty_fields[field] = "Cannot be empty"
				elif isinstance(value, str) and value.strip() == "":
					empty_fields[field] = "Cannot be empty or whitespace"
				elif isinstance(value, (list, dict)) and len(value) == 0:
					empty_fields[field] = "Cannot be empty"

		return missing_fields, empty_fields

	def process_field(self, field: str, value: Any, field_type: type, has_default: bool) -> Any:
		"""Process and convert a single field value"""
		# Fix: Use proper boolean check
		if not has_default and value == "":
			return None

		return self.converter.convert(value, field_type)

	def build_validated_data(
		self,
		required_fields: list[str],
		optional_fields: list[str],
		type_hints: dict[str, type],
		default_values: dict[str, Any],
		kwargs: dict,
	) -> tuple[dict[str, Any], dict[str, str]]:
		"""
		Build validated data dictionary with type conversion
		Returns: (validated_data, conversion_errors)
		"""
		validated_data = {}
		conversion_errors = {}

		# Process required fields
		for field in required_fields:
			if field in kwargs:
				try:
					validated_data[field] = self.converter.convert(kwargs[field], type_hints[field])
				except ValueError as e:
					conversion_errors[field] = str(e)

		# Process optional fields
		for field in optional_fields:
			if field in kwargs and kwargs[field] is not None:
				try:
					has_default = field in default_values
					field_type = self.type_inspector.get_actual_type(type_hints[field])
					converted = self.process_field(field, kwargs[field], field_type, has_default)
					if converted is not None:
						validated_data[field] = converted
				except ValueError as e:
					conversion_errors[field] = str(e)

			# Apply default values (already deep-copied in get_field_metadata)
			elif field not in kwargs and field in default_values:
				try:
					field_type = self.type_inspector.get_actual_type(type_hints[field])
					validated_data[field] = self.converter.convert(default_values[field], field_type)
				except ValueError as e:
					# FIX: RUF010 - Use !s conversion flag instead of str()
					conversion_errors[field] = f"Invalid default value: {e!s}"

		return validated_data, conversion_errors

	def create_dto_instance(
		self, dto_class: type[BaseRequest], validated_data: dict[str, Any]
	) -> BaseRequest:
		"""Create DTO instance from validated data"""
		try:
			return dto_class(**validated_data)
		except TypeError:
			# Fallback: create empty instance and set attributes
			instance = dto_class()
			for key, value in validated_data.items():
				setattr(instance, key, value)
			return instance

	def validate_request(self, dto_class: type[BaseRequest], kwargs: dict) -> BaseRequest:
		"""
		Main validation method
		Returns: Validated DTO instance
		Raises: ValidationError on validation errors
		"""

		# Clear cache for new request
		self.converter.clear_cache()

		# Parse request data
		kwargs = self.parser.parse_request_data(kwargs)

		# Get field metadata
		required_fields, optional_fields, type_hints, default_values = self.type_inspector.get_field_metadata(
			dto_class
		)

		# Validate required fields
		missing_fields, empty_fields = self.validate_required_fields(required_fields, kwargs)

		# Fix: Better error message with field names and proper status code
		if missing_fields:
			frappe.throw(
				msg=f"Missing required fields: {', '.join(missing_fields)}", exc=frappe.ValidationError
			)

		if empty_fields:
			# Format multiple empty fields into readable message
			error_msgs = [f"{field}: {msg}" for field, msg in empty_fields.items()]
			frappe.throw(msg="<br>".join(error_msgs), exc=frappe.ValidationError)

		# Build validated data
		validated_data, conversion_errors = self.build_validated_data(
			required_fields, optional_fields, type_hints, default_values, kwargs
		)

		if conversion_errors:
			# Format conversion errors into readable message
			error_msgs = [f"{field}: {msg}" for field, msg in conversion_errors.items()]
			frappe.throw(msg="<br>".join(error_msgs), exc=frappe.ValidationError)

		# Create and return DTO instance
		return self.create_dto_instance(dto_class, validated_data)


# =================================
# Decorator Factory
# =================================
# Singleton validator instance untuk reuse
_validator_instance = RequestValidator()


def validate(dto_class: type[BaseRequest]):
	"""
	Decorator untuk validasi dan konversi request parameters

	Features:
	- type validation & conversion
	- Required field checking
	- Default value support
	- Optional field handling
	- Comprehensive error messages
	- Thread-safe caching

	Usage: @validate(YourDtoClass)
	"""
	# Pre-fetch metadata saat decorator di-apply
	_validator_instance.type_inspector.get_field_metadata(dto_class)

	def decorator(func):
		# Cache function signature
		sig = inspect.signature(func)
		dto_param_name = None

		# Find parameter with DTO type annotation
		for param_name, param in sig.parameters.items():
			if param.annotation == dto_class:
				dto_param_name = param_name
				break

		# Check if function accepts **kwargs
		has_var_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

		@wraps(func)
		def wrapper(*args, **kwargs):
			try:
				# Validate and get DTO instance
				validated_request = _validator_instance.validate_request(dto_class, kwargs)

				# Inject into function parameters
				if dto_param_name:
					kwargs[dto_param_name] = validated_request
				else:
					kwargs["body"] = validated_request

				# Clean kwargs if the function does not accept **kwargs
				if not has_var_kwargs:
					# Remove all keys except those in the signature
					kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

				# Execute the actual function
				return func(*args, **kwargs)

			except BaseAPIException:
				# Custom exceptions sudah set response di __init__, jangan raise lagi
				# Return None agar frappe pakai response yang sudah di-set
				return

			except frappe.ValidationError as e:
				InternalServerException(message=str(e))
				return

			except Exception as e:
				if isinstance(e, (SystemExit, KeyboardInterrupt)):
					raise

				# Log unexpected errors dan set InternalServerException
				frappe.log_error(title=f"Error in {func.__name__}", message=frappe.get_traceback())
				InternalServerException(message=str(e))
				return

		return wrapper

	return decorator


# =================================
# Public API
# =================================
__all__ = [
	"BaseRequest",
	"RequestParser",
	"RequestValidator",
	"TypeConverter",
	"TypeInspector",
	"validate",
]
