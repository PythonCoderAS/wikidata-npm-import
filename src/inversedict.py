from typing import (
    Generic,
    Iterator,
    Literal,
    Mapping,
    MutableMapping,
    Tuple,
    TypeVar,
    Union,
    overload,
)

KT = TypeVar("KT")
VT = TypeVar("VT")


class InverseDict(Generic[KT, VT], MutableMapping[KT, VT]):
    """
    A dictionary that has two mappings so that key lookup and value lookup is O(1).
    """

    def __init__(self, existing: Union[Mapping[KT, VT], None] = None):
        self._forward = {}
        self._inverse = {}
        if existing:
            self.update(existing)

    def __contains__(self, item: KT):
        return item in self._forward

    def __setitem__(self, k: KT, v: VT):
        if k in self._forward:
            del self._forward[k]
        self._forward[k] = v
        self._inverse[v] = k

    def __delitem__(self, k: KT):
        del self._inverse[self._forward[k]]
        del self._forward[k]

    def get_value(self, k: KT) -> VT:
        return self._forward[k]

    def get_key(self, v: VT) -> KT:
        return self._inverse[v]

    def __getitem__(self, k: KT) -> VT:
        return self._forward[k]

    def __len__(self) -> int:
        return len(self._forward)

    def __iter__(self) -> Iterator[KT]:
        return iter(self._forward)
