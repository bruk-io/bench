"""Adapters: the implementations of :class:`bench.kernel.Kernel`.

One, :mod:`bench.adapters.browser`: the kernel that walks a tree and names every face, driving
Manifold's WASM build by handle out of Pyodide. It imports no modeller - the one it drives,
and the exception a refusal raises, are handed to it by its host - so it runs and is tested in
any Python. This barrel imports nothing; import the adapter by name.
"""

__all__: list[str] = []
