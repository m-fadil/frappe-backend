import frappe


class BaseAPIException(frappe.ValidationError):
	"""Base class untuk semua custom exceptions"""

	_status_code = 500
	_title = "Error"
	_message = "An error occurred"

	def __init__(self, message=None, title=None, errors=None, **kwargs):
		self.message = message or self._message
		self.title = title or self._title
		self.errors = errors or []

		# Set response langsung ke frappe.local.response
		frappe.clear_messages()
		frappe.local.response["http_status_code"] = self._status_code
		frappe.local.response["title"] = self.title
		frappe.local.response["detail"] = self.message
		frappe.local.response["errors"] = self.errors

		# Tambahkan extra data jika ada
		for key, value in kwargs.items():
			frappe.local.response[key] = value

		# Clear default frappe messages
		frappe.local.response.pop("_server_messages", None)
		frappe.local.response.pop("server_messages", None)
		frappe.local.response.pop("exc_type", None)
		frappe.local.response.pop("exc", None)

		super().__init__(self.message)


# 4xx Client Errors
class BadRequestException(BaseAPIException):
	"""400 Bad Request"""

	_status_code = 400
	_title = "Bad Request"
	_message = "The request could not be understood or was missing required parameters"


class UnauthorizedException(BaseAPIException):
	"""401 Unauthorized"""

	_status_code = 401
	_title = "Unauthorized"
	_message = "Authentication is required and has failed or has not been provided"


class ForbiddenException(BaseAPIException):
	"""403 Forbidden"""

	_status_code = 403
	_title = "Forbidden"
	_message = "You don't have permission to access this resource"


class NotFoundException(BaseAPIException):
	"""404 Not Found"""

	_status_code = 404
	_title = "Not Found"
	_message = "The requested resource was not found"


class MethodNotAllowedException(BaseAPIException):
	"""405 Method Not Allowed"""

	_status_code = 405
	_title = "Method Not Allowed"
	_message = "The HTTP method is not allowed for this endpoint"


class ConflictException(BaseAPIException):
	"""409 Conflict"""

	_status_code = 409
	_title = "Conflict"
	_message = "The request conflicts with the current state of the resource"


class ValidationException(BaseAPIException):
	"""422 Unprocessable Entity"""

	_status_code = 422
	_title = "Validation Error"
	_message = "The request data failed validation"


class TooManyRequestsException(BaseAPIException):
	"""429 Too Many Requests"""

	_status_code = 429
	_title = "Too Many Requests"
	_message = "You have exceeded the rate limit"


# 5xx Server Errors
class InternalServerException(BaseAPIException):
	"""500 Internal Server Error"""

	_status_code = 500
	_title = "Internal Server Error"
	_message = "An unexpected error occurred on the server"


class NotImplementedException(BaseAPIException):
	"""501 Not Implemented"""

	_status_code = 501
	_title = "Not Implemented"
	_message = "This functionality is not yet implemented"


class ServiceUnavailableException(BaseAPIException):
	"""503 Service Unavailable"""

	_status_code = 503
	_title = "Service Unavailable"
	_message = "The service is temporarily unavailable"


# Business Logic Exceptions
class AlreadyExistsException(ConflictException):
	"""Resource already exists"""

	_title = "Already Exists"
	_message = "The resource already exists"


class InvalidStateException(BadRequestException):
	"""Invalid state for operation"""

	_title = "Invalid State"
	_message = "The resource is in an invalid state for this operation"


class ExpiredException(BadRequestException):
	"""Resource has expired"""

	_title = "Expired"
	_message = "The resource or token has expired"


class DuplicateException(ConflictException):
	"""Duplicate entry"""

	_title = "Duplicate Entry"
	_message = "A duplicate entry was detected"
