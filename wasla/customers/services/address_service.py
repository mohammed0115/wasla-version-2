
from ..models import Address

class AddressService:
    @staticmethod
    def add_address(customer, line1, city, country, is_default=False):
        if is_default:
            Address.objects.filter(customer=customer, is_default=True).update(is_default=False)
        return Address.objects.create(
            customer=customer,
            line1=line1,
            city=city,
            country=country,
            is_default=is_default
        )
