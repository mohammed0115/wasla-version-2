from ..models import Customer


class CustomerService:
    @staticmethod
    def create_customer(
        email: str,
        full_name: str,
        store_id: int = 1,
        group: str = "retail",
        is_active: bool = True,
    ):
        if Customer.objects.filter(store_id=store_id, email=email).exists():
            raise ValueError("Customer already exists")
        return Customer.objects.create(
            store_id=store_id,
            email=email,
            full_name=full_name,
            group=group,
            is_active=is_active,
        )
