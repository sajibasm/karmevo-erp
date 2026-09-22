"""Module system (ADR-0009): installed modules and dependencies."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from erp.core.controller import Controller


@dataclass(frozen=True)
class ModuleManifest:
    """Declared by each module in erp/modules/<key>/module.py."""

    key: str
    name: str
    depends_on: tuple[str, ...] = ()
    core: bool = False  # always enabled; can never be disabled
    controllers: tuple[type[Controller], ...] = field(default=(), compare=False, repr=False)


class ModuleCatalogError(ValueError):
    pass


class ModuleCatalog:
    """Every module installed in this build, validated as a DAG."""

    def __init__(self, manifests: Iterable[ModuleManifest]) -> None:
        self._modules: dict[str, ModuleManifest] = {}
        for manifest in manifests:
            if manifest.key in self._modules:
                raise ModuleCatalogError(f"duplicate module key {manifest.key!r}")
            self._modules[manifest.key] = manifest
        for manifest in self._modules.values():
            self._validate_dependencies(manifest)
        self._order = self._topological_order()

    def __iter__(self) -> Iterator[ModuleManifest]:
        return (self._modules[key] for key in self._order)

    def get(self, key: str) -> ModuleManifest:
        try:
            return self._modules[key]
        except KeyError:
            raise ModuleCatalogError(f"unknown module {key!r}") from None

    def core_keys(self) -> frozenset[str]:
        return frozenset(k for k, m in self._modules.items() if m.core)

    def dependencies(self, key: str) -> list[str]:
        """Transitive dependencies of `key`, in enable order."""
        needed: set[str] = set()
        stack = list(self.get(key).depends_on)
        while stack:
            dependency = stack.pop()
            if dependency not in needed:
                needed.add(dependency)
                stack.extend(self._modules[dependency].depends_on)
        return [k for k in self._order if k in needed]

    def dependents(self, key: str) -> list[str]:
        """Modules depending on `key`, transitively, in enable order."""
        self.get(key)
        return [k for k in self._order if key in self.dependencies(k)]

    def _validate_dependencies(self, manifest: ModuleManifest) -> None:
        for dependency in manifest.depends_on:
            if dependency not in self._modules:
                raise ModuleCatalogError(
                    f"{manifest.key!r} depends on unknown module {dependency!r}"
                )
            if manifest.core and not self._modules[dependency].core:
                raise ModuleCatalogError(
                    f"core module {manifest.key!r} cannot depend on optional module {dependency!r}"
                )

    def _topological_order(self) -> list[str]:
        remaining = {k: set(m.depends_on) for k, m in self._modules.items()}
        order: list[str] = []
        while remaining:
            ready = sorted(k for k, deps in remaining.items() if not deps)
            if not ready:
                raise ModuleCatalogError(f"dependency cycle among {sorted(remaining)}")
            for key in ready:
                order.append(key)
                del remaining[key]
            for deps in remaining.values():
                deps.difference_update(ready)
        return order
