from typing import Dict, Callable
from .object import SBOLObject

# Global store for builder methods. Custom SBOL classes
# register their builders in this store
BUILDER_REGISTER: Dict[str, Callable[[str, str], SBOLObject]] = {}
