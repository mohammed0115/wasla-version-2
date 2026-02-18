"""
APPS Module - Container for reusable Django applications

This module contains independent, reusable Django apps with clean architecture patterns.
Each app follows domain-driven design with clear separation of concerns:

- domain/ : Business logic and entities
- application/ : Use cases and business rules orchestration
- infrastructure/ : Django models, repositories, and external integrations
- presentation/ : Views, serializers, and URL routing

Apps in this module:
- visual_search: Image-based product search functionality
"""
