from apps.accounts.permissions import HasRole
from apps.accounts.roles import Role

# Who may import (enforced in views; tested in tests/test_imports.py).
IMPORT_ROLES = (Role.ADMIN, Role.SALES, Role.SERVICE)
CanImport = HasRole(*IMPORT_ROLES)
CanManageApiKeys = HasRole(Role.ADMIN)
