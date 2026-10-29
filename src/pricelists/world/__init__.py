"""O mundo fictício: mercado, cadastro da loja, listas dos fornecedores e o gabarito, gerados de uma semente."""
from .build import World, build_world
from .files import write_world

__all__ = ["World", "build_world", "write_world"]
