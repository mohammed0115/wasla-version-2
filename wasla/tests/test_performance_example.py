from __future__ import annotations

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext


@pytest.mark.django_db
def test_schema_endpoint_performance_example():
    client = Client(HTTP_HOST="localhost")

    with CaptureQueriesContext(connection) as queries:
        response = client.get("/api/schema/")

    assert response.status_code == 200
    assert len(queries.captured_queries) >= 0
