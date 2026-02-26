from django.http import HttpResponse
from django.urls import path


def _placeholder(_request):
	return HttpResponse("Admin portal")


app_name = "admin_portal"

urlpatterns = [
	path("", _placeholder, name="dashboard"),
	path("login/", _placeholder, name="login"),
	path("logout/", _placeholder, name="logout"),
	path("tenants/", _placeholder, name="tenants"),
	path("stores/", _placeholder, name="stores"),
	path("payments/", _placeholder, name="payments"),
	path("payments/transactions/", _placeholder, name="payment_transactions"),
	path("payments/transactions/create/", _placeholder, name="payment_transaction_create"),
	path("subscriptions/", _placeholder, name="subscriptions"),
	path("settlements/", _placeholder, name="settlements"),
	path("invoices/", _placeholder, name="invoices"),
	path("webhooks/", _placeholder, name="webhooks"),
	path("performance/", _placeholder, name="performance_monitoring"),
]
