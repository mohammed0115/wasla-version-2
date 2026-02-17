# Apps Module Refactoring Guide

## Overview

The `apps/` directory has been safely refactored to follow Clean Architecture principles with proper module organization, import patterns, and documentation.

**Refactoring Goals:**
✓ Clear separation of concerns (Domain, Application, Infrastructure, Presentation)  
✓ Proper module exports for easier imports  
✓ Consistent import patterns across the module  
✓ Comprehensive module documentation  
✓ Django best practices (AppConfig, migrations, models)  

---

## Directory Structure

```
apps/
├── __init__.py                    # Package marker with module documentation
└── visual_search/                 # Visual search app
    ├── __init__.py               # App-level documentation
    ├── apps.py                   # Django AppConfig (VisualSearchConfig)
    ├── models.py                 # Re-exports from infrastructure.models
    ├── domain/                   # Domain Layer (Business Logic)
    │   ├── __init__.py          # Exports: InvalidImageError, NoResultsFoundError, VisualSearchError
    │   ├── entities.py          # Core entities
    │   ├── errors.py            # Custom exception classes
    │   └── value_objects.py      # Immutable value objects
    ├── application/              # Application Layer (Use Cases & DTOs)
    │   ├── __init__.py          # Module documentation
    │   ├── dto/                 # Data Transfer Objects
    │   │   ├── __init__.py      # Exports: VisualSearchQueryDTO, ResponseDTO, ResultDTO
    │   │   └── visual_search_dto.py
    │   ├── usecases/            # Business use cases orchestration
    │   │   ├── __init__.py      # Exports: VisualSearchUseCase
    │   │   └── visual_search_usecase.py
    │   ├── services/            # Application services
    │   │   ├── __init__.py      # Exports: ImageProcessor, EmbeddingService
    │   │   ├── image_processor.py
    │   │   └── embedding_service.py
    │   └── interfaces/          # Ports (abstract interfaces)
    │       ├── __init__.py      # Exports: VisualSearchRepositoryPort
    │       └── repository_port.py
    ├── infrastructure/           # Infrastructure Layer (Django Integration)
    │   ├── __init__.py          # Exports: ProductEmbedding, DjangoVisualSearchRepository
    │   ├── models.py            # Django ORM models
    │   └── repositories/        # Repository implementations
    │       ├── __init__.py      # Exports: DjangoVisualSearchRepository
    │       └── django_visual_search_repository.py
    ├── presentation/             # Presentation Layer (Views & APIs)
    │   ├── __init__.py          # Module documentation
    │   ├── views.py             # Traditional Django template views
    │   ├── api_views.py         # Django REST Framework views
    │   ├── serializers.py       # DRF serializers for request/response
    │   ├── urls.py              # Web URL routing
    │   └── api_urls.py          # API URL routing
    ├── migrations/              # Django database migrations
    └── tests/                   # Test suite for the app
```

---

## Import Patterns - Before & After

### ❌ Old Pattern (Inconsistent)
```python
# Long absolute imports
from apps.visual_search.infrastructure.models import ProductEmbedding
from apps.visual_search.application.usecases.visual_search_usecase import VisualSearchUseCase

# No clear module exports
import apps.visual_search.domain.errors
```

### ✅ New Pattern (Clean & Consistent)
```python
# Short, clear imports using __all__ exports
from apps.visual_search.models import ProductEmbedding
from apps.visual_search.application.usecases import VisualSearchUseCase
from apps.visual_search.domain import InvalidImageError, NoResultsFoundError

# Or direct layer imports
from apps.visual_search.infrastructure import DjangoVisualSearchRepository
from apps.visual_search.application.dto import VisualSearchQueryDTO
```

---

## Module Export System

### What's `__all__`?

The `__all__` variable in `__init__.py` files explicitly declares which names are public exports from a module.

```python
# apps/visual_search/application/usecases/__init__.py
from .visual_search_usecase import VisualSearchUseCase

__all__ = ["VisualSearchUseCase"]  # Only this is considered "public"
```

### Benefits

✓ **Clear API**: Anyone importing knows exactly what's available  
✓ **IDE Support**: Better autocomplete and type hints  
✓ **Refactoring Safety**: Changing internal files doesn't break imports  
✓ **Documentation**: Self-documenting public interfaces  
✓ **Quality Assurance**: Explicit about what other modules depend on  

### Usage in Views

```python
# apps/visual_search/presentation/api_views.py

# Clean imports leveraging __all__ exports
from apps.visual_search.application.usecases import VisualSearchUseCase
from apps.visual_search.application.dto import VisualSearchQueryDTO
from apps.visual_search.domain import InvalidImageError
from apps.visual_search.infrastructure import DjangoVisualSearchRepository
```

---

## Layer Responsibilities

### Domain Layer (`domain/`)
**Framework-Independent Business Logic**

```python
# domain/errors.py
class InvalidImageError(VisualSearchError):
    """Raised when image validation fails"""

# domain/entities.py
@dataclass
class ProductEmbedding:
    """Core domain entity - not a Django model"""
```

✓ No Django imports  
✓ Pure business logic  
✓ Highly testable  
✓ Reusable in any context  

### Application Layer (`application/`)
**Use Cases & Orchestration**

```python
# application/usecases/visual_search_usecase.py
class VisualSearchUseCase:
    """Orchestrates visual search business logic"""
    
    def __init__(self, repository: VisualSearchRepositoryPort):
        self.repository = repository  # Dependency injection
    
    def run(self, query: VisualSearchQueryDTO) -> VisualSearchResponseDTO:
        # Clean business logic without infrastructure details
```

✓ No Django models directly  
✓ Depends on domain and interfaces  
✓ Framework-agnostic  
✓ Testable with mock repositories  

### Infrastructure Layer (`infrastructure/`)
**Django-Specific Implementation**

```python
# infrastructure/models.py
class ProductEmbedding(models.Model):
    """Django ORM model for database persistence"""
    store_id = models.IntegerField(db_index=True)

# infrastructure/repositories/django_visual_search_repository.py
class DjangoVisualSearchRepository:
    """Implements VisualSearchRepositoryPort using Django ORM"""
```

✓ Django-specific code  
✓ Implements abstract ports  
✓ Handles data persistence  
✓ Can be swapped for different implementations  

### Presentation Layer (`presentation/`)
**User-Facing Views & APIs**

```python
# presentation/api_views.py
class VisualSearchAPIView(APIView):
    """REST API endpoint for visual search"""
    
    def post(self, request):
        # Use case orchestration happens here
        use_case = VisualSearchUseCase(repository=repo)
        result = use_case.run(query)
```

✓ Request/response handling  
✓ Serialization/deserialization  
✓ API routes  
✓ User feedback and errors  

---

## Configuration in Django

### 1. INSTALLED_APPS (`config/settings.py`)

```python
INSTALLED_APPS = [
    # ...
    "apps.visual_search.apps.VisualSearchConfig",  # Proper app config
    # ...
]
```

✓ Uses AppConfig (best practice)  
✓ Allows app-level customization  
✓ Clear app initialization  

### 2. URL Routing (`config/urls.py`)

```python
urlpatterns = [
    # Web views
    path("", include(("apps.visual_search.presentation.urls", "visual_search"), 
                     namespace="visual_search")),
    
    # API endpoints
    path("api/", include(("apps.visual_search.presentation.api_urls", "visual_search_api"), 
                         namespace="visual_search_api")),
]
```

### 3. Django Migrations

Migrations are handled automatically when using:
```bash
python manage.py makemigrations
python manage.py migrate
```

The `ProductEmbedding` model in `infrastructure/models.py` is automatically discovered via the app config.

---

## Best Practices for Development

### ✅ DO

1. **Use clean imports**
   ```python
   from apps.visual_search.application.usecases import VisualSearchUseCase
   ```

2. **Leverage __all__ exports**
   ```python
   # When adding new classes, update __init__.py
   from .new_module import NewClass
   __all__ = ["ExistingClass", "NewClass"]
   ```

3. **Keep layers independent**
   ```python
   # ✓ GOOD: Presentation depends on Application
   from apps.visual_search.application.usecases import VisualSearchUseCase
   
   # ✓ GOOD: Application depends on Domain and Interfaces
   from apps.visual_search.domain import InvalidImageError
   from apps.visual_search.application.interfaces import VisualSearchRepositoryPort
   ```

4. **Add docstrings to __init__.py files**
   ```python
   """
   Presentation Layer
   
   Handles user-facing views and API endpoints.
   """
   ```

5. **Test in isolation**
   ```python
   # Test use case with mock repository (no Django)
   def test_visual_search():
       mock_repo = MockRepository()
       use_case = VisualSearchUseCase(repository=mock_repo)
       result = use_case.run(query)
   ```

### ❌ DON'T

1. **Don't create circular imports**
   ```python
   # ✗ BAD: Infrastructure shouldn't import from Presentation
   # This could create circular dependencies
   ```

2. **Don't skip __all__ exports**
   ```python
   # ✗ BAD: No explicit public API
   # Users have to know internal structure
   ```

3. **Don't put domain logic in views**
   ```python
   # ✗ BAD: Business logic in presentation
   # Hard to test, not reusable
   ```

4. **Don't skip layer responsibilities**
   ```python
   # ✗ BAD: Putting Django ORM in domain
   from django.db import models  # Wrong layer!
   ```

5. **Don't hardcode repository in use case**
   ```python
   # ✗ BAD: Not dependency-injected
   class VisualSearchUseCase:
       def __init__(self):
           self.repo = DjangoVisualSearchRepository()  # Tight coupling!
   ```

---

## Adding New Features

### Example: Adding a New Service Class

1. Create the service file:
   ```python
   # apps/visual_search/application/services/new_service.py
   class NewService:
       """Description of what this service does"""
   ```

2. Update the services `__init__.py`:
   ```python
   # apps/visual_search/application/services/__init__.py
   from .image_processor import ImageProcessor
   from .embedding_service import EmbeddingService
   from .new_service import NewService  # Add this
   
   __all__ = ["ImageProcessor", "EmbeddingService", "NewService"]
   ```

3. Import in use cases:
   ```python
   # apps/visual_search/application/usecases/visual_search_usecase.py
   from apps.visual_search.application.services import NewService
   ```

### Example: Adding a New Domain Entity

1. Create the entity in domain layer:
   ```python
   # apps/visual_search/domain/entities.py
   @dataclass
   class NewEntity:
       """Description"""
   ```

2. No need to update `domain/__init__.py` unless it's an error class

3. Use in application layer:
   ```python
   from apps.visual_search.domain.entities import NewEntity
   ```

---

## Migration Guide for Existing Code

### For Code Inside Apps Module

```python
# Old way
from apps.visual_search.presentation.views import visual_search_view

# New way (same, but now it's cleaner via exports)
from apps.visual_search.presentation.views import visual_search_view
```

### For Code Outside Apps Module

```python
# In other apps, use cleaner imports:
from apps.visual_search.models import ProductEmbedding
from apps.visual_search.infrastructure import DjangoVisualSearchRepository

# Instead of
from apps.visual_search.infrastructure.models import ProductEmbedding
from apps.visual_search.infrastructure.repositories.django_visual_search_repository import DjangoVisualSearchRepository
```

---

## Testing Strategy

### Unit Tests (Domain & Application)

```python
# apps/visual_search/tests/test_use_case.py
from apps.visual_search.application.usecases import VisualSearchUseCase
from apps.visual_search.domain import InvalidImageError

def test_visual_search_with_invalid_image():
    mock_repo = MockRepository()
    use_case = VisualSearchUseCase(mock_repo)
    
    with pytest.raises(InvalidImageError):
        use_case.run(invalid_query)
```

### Integration Tests (Infrastructure)

```python
# apps/visual_search/tests/test_repository.py
from apps.visual_search.infrastructure import DjangoVisualSearchRepository, ProductEmbedding

def test_repository_finds_products(db):
    repo = DjangoVisualSearchRepository()
    products = repo.find_similar_products(...)
    assert len(products) > 0
```

### API Tests (Presentation)

```python
# apps/visual_search/tests/test_api_views.py
from django.test import Client

def test_visual_search_api(client, db):
    response = client.post('/api/visual-search/', {...})
    assert response.status_code == 200
```

---

## Module Documentation

Each `__init__.py` file now includes:
- Purpose of the layer/module
- Key classes and functions
- How to import from this module
- Example usage

Example:
```python
"""
Presentation Layer

Handles user-facing views and API endpoints:
- views.py: Django template views for web interface
- api_views.py: DRF API views for REST endpoints
- serializers.py: DRF serializers for request/response validation

Quick Import:
    from apps.visual_search.presentation import views
    from apps.visual_search.presentation.api_views import VisualSearchAPIView
"""
```

---

## Performance & Optimization

### Tree Shaking
Because we use explicit `__all__`, unused imports can be identified:

```python
# apps/visual_search/application/__init__.py
__all__ = [
    "VisualSearchUseCase",
    "ImageProcessor",  # If not used, can be removed
]
```

### Lazy Loading (Advanced)
For large modules, you can use lazy imports:

```python
def __getattr__(name):
    if name == "HeavyClass":
        from .heavy_module import HeavyClass
        return HeavyClass
    raise AttributeError(f"Module has no attribute {name}")
```

---

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'visual_search'`

**Solution**: Always use full path from `wasla/` directory:
```python
# ✗ Wrong
from visual_search.models import ProductEmbedding

# ✓ Correct
from apps.visual_search.models import ProductEmbedding
```

### Circular Imports

**Problem**: `ImportError: cannot import name 'X'` during startup

**Solution**: Check layer dependencies:
- Domain → (nothing)
- Application → Domain + Interfaces
- Infrastructure → Domain + Application Interfaces
- Presentation → All layers

**Fix**: Change imports if they violate this order.

### Missing Exports

**Problem**: Can't import a class that exists

**Solution**: Ensure it's in the module's `__all__`:
```python
# apps/visual_search/application/services/__init__.py
from .new_service import NewService

__all__ = ["ImageProcessor", "EmbeddingService", "NewService"]  # Add here
```

---

## Future Refactoring Ideas

1. **Move `apps/` to top-level package** if it grows significantly
2. **Create plugin system** for additional search algorithms
3. **Add caching layer** for embedding vectors
4. **Implement event sourcing** for audit trails
5. **Separate read/write models** (CQRS pattern)

---

## References

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Django App Design Guide](https://docs.djangoproject.com/en/stable/ref/core-packages/)
- [Python Packaging Best Practices](https://packaging.python.org/)
- [DRF Serializers Documentation](https://www.django-rest-framework.org/api-guide/serializers/)

---

## Refactoring Checklist (Safe Refactoring)

- ✅ Added comprehensive __init__.py files with exports
- ✅ Added docstrings explaining each layer
- ✅ Verified all imports still work
- ✅ No breaking changes to public API
- ✅ All Django configurations unchanged
- ✅ Database migrations unaffected
- ✅ Tests remain functional
- ✅ Created this guide for team reference

---

## Contact & Support

For questions about the refactoring or module structure:
1. Check this guide first
2. Review the __init__.py docstrings in relevant modules
3. Look at examples in presentation layer
4. Ask team lead or architect
