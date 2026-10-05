from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role

# Everyone signed in can look customers up. Most staff add and edit them
# (service writes work orders for them, parts sells to them). Only admin and
# sales can remove one.
CUSTOMER_EDITORS = (Role.ADMIN, Role.SALES, Role.SERVICE, Role.PARTS)
CUSTOMER_REMOVERS = (Role.ADMIN, Role.SALES)

CanEditCustomers = HasRole(*CUSTOMER_EDITORS, read_roles=(Role.READ_ONLY,))
CanRemoveCustomers = HasRole(*CUSTOMER_REMOVERS)
