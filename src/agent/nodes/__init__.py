"""Processing nodes for different programming languages."""

from .cobol_node import cobol_node
from .vb6_node import vb6_node
from .fortran_node import fortran_node
from .generic_node import generic_node

__all__ = ["cobol_node", "vb6_node", "fortran_node", "generic_node"]
