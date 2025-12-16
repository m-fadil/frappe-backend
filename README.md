# Backend - Frappe Developer Toolkit

Developer toolkit providing decorators, DTO validation, and request parsing for building structured APIs in Frappe

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app backend
```

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/backend
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

## Documentation

### Request Validator & Exception Handler

#### Validator.py

##### Overview
A comprehensive request validation and type conversion system for Frappe applications with automatic DTO (Data Transfer Object) validation.

##### Features
- Automatic type conversion and validation
- Required and optional field handling
- Default value support
- Thread-safe caching
- Comprehensive error messages
- JSON parsing with normalization

##### Basic Usage

###### 1. Define Request DTO

```python
from backend.utils.validator import BaseRequest

class CreateUserRequest(BaseRequest):
    # Required fields
    username: str
    email: str
    age: int

    # Optional fields with type hints
    phone: str | None = None
    is_active: bool = True
    tags: list = []
    metadata: dict = {}
```

###### 2. Apply Validator Decorator

```python
import frappe
from backend.utils.validator import validate
from backend.utils.exceptions import BadRequestException

@frappe.whitelist()
@validate(CreateUserRequest)
def create_user(body: CreateUserRequest):
    # Access validated and type-converted data
    user = frappe.new_doc("User")
    user.username = body.username
    user.email = body.email
    user.age = body.age
    user.is_active = body.is_active
    user.insert()

    return {"message": "User created successfully"}
```

###### 3. Request Examples

```python
# Valid request - all required fields present
POST /api/method/create_user
{
    "username": "john_doe",
    "email": "john@example.com",
    "age": "25",  # Auto-converted to int
    "is_active": "true"  # Auto-converted to bool
}

# Invalid request - missing required field
POST /api/method/create_user
{
    "username": "john_doe"
}
# Response: "Missing required fields: email, age"

# Invalid request - empty required field
POST /api/method/create_user
{
    "username": "",
    "email": "john@example.com",
    "age": 25
}
# Response: "username: Cannot be empty or whitespace"
```

##### Supported Type Conversions

| Type | Conversion Examples |
|------|-------------------|
| `str` | Any value to string |
| `int` | `"123"` → `123`, `"123.45"` → `123` |
| `float` | `"123.45"` → `123.45` |
| `bool` | `"true"`, `"1"`, `"yes"` → `True` |
| `list` | `"[1,2,3]"` → `[1,2,3]`, `"a,b,c"` → `["a","b","c"]` |
| `dict` | `'{"key":"value"}'` → `{"key":"value"}` |

##### Advanced Features

###### Nested DTOs

```python
class AddressRequest(BaseRequest):
    street: str
    city: str
    postal_code: str

class UserWithAddressRequest(BaseRequest):
    username: str
    email: str
    address: dict  # Will accept JSON string or dict
```

###### Optional Fields with Union Types

```python
class UpdateUserRequest(BaseRequest):
    user_id: str
    username: str | None = None
    email: str | None = None
    age: int | None = None
```

###### List and Dict Handling

```python
class BulkCreateRequest(BaseRequest):
    users: list  # Accepts JSON array string or list
    metadata: dict  # Accepts JSON object string or dict
```

#### Exceptions.py

##### Overview
Standardized HTTP exception classes for consistent API error responses in Frappe applications.

##### Features
- HTTP-compliant status codes
- Structured error responses
- Automatic response formatting
- Support for additional error details

##### Exception Hierarchy

###### Client Errors (4xx)

```python
from backend.utils.exceptions import (
    BadRequestException,       # 400
    UnauthorizedException,     # 401
    ForbiddenException,        # 403
    NotFoundException,         # 404
    MethodNotAllowedException, # 405
    ConflictException,         # 409
    ValidationException,       # 422
    TooManyRequestsException   # 429
)
```

###### Server Errors (5xx)

```python
from backend.utils.exceptions import (
    InternalServerException,    # 500
    NotImplementedException,    # 501
    ServiceUnavailableException # 503
)
```

###### Business Logic Exceptions

```python
from backend.utils.exceptions import (
    AlreadyExistsException,  # 409 - Resource already exists
    InvalidStateException,   # 400 - Invalid state for operation
    ExpiredException,        # 400 - Resource/token expired
    DuplicateException       # 409 - Duplicate entry
)
```

##### Usage Examples

###### Basic Exception Throwing

```python
@frappe.whitelist()
def get_user(user_id):
    user = frappe.get_doc("User", user_id)

    if not user:
        raise NotFoundException(
            message=f"User with ID {user_id} not found"
        )

    return user
```

###### Custom Error Message and Title

```python
@frappe.whitelist()
def delete_user(user_id):
    user = frappe.get_doc("User", user_id)

    if user.has_active_sessions:
        raise ConflictException(
            title="Cannot Delete User",
            message="User has active sessions. Please logout first."
        )

    user.delete()
```

###### With Additional Error Details

```python
@frappe.whitelist()
@validate(CreateUserRequest)
def create_user(body: CreateUserRequest):
    existing_user = frappe.db.exists("User", {"email": body.email})

    if existing_user:
        raise AlreadyExistsException(
            message="User with this email already exists",
            errors=[
                {"field": "email", "message": "Email already registered"}
            ],
            existing_user_id=existing_user
        )
```

###### Validation Errors

```python
@frappe.whitelist()
def update_user_age(user_id, age):
    if age < 0 or age > 150:
        raise ValidationException(
            message="Invalid age provided",
            errors=[
                {"field": "age", "message": "Age must be between 0 and 150"}
            ]
        )
```

##### Error Response Format

All exceptions produce standardized JSON responses:

```json
{
    "http_status_code": 404,
    "title": "Not Found",
    "detail": "User with ID 123 not found",
    "errors": [],
    "existing_user_id": "USR-0001"
}
```

##### Integration with Validator

```python
from backend.utils.validator import validate, BaseRequest
from backend.utils.exceptions import NotFoundException, ValidationException

class GetUserRequest(BaseRequest):
    user_id: str

@frappe.whitelist()
@validate(GetUserRequest)
def get_user(body: GetUserRequest):
    if not frappe.db.exists("User", body.user_id):
        raise NotFoundException(
            message=f"User {body.user_id} not found"
        )

    user = frappe.get_doc("User", body.user_id)
    return user.as_dict()
```

## CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

## License

mit
