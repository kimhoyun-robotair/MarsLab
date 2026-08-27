class Path:
    pathString: str

class AssetPath:
    path: str
    def __bool__(self) -> bool: ...
    def __len__(self) -> int: ...

class ValueTypeName: ...

class _ValueTypeNames:
    Asset: ValueTypeName

ValueTypeNames: _ValueTypeNames

class Layer:
    realPath: str
    @classmethod
    def FindOrOpen(cls, path: str) -> Layer | None: ...
    def GetExternalReferences(self) -> tuple[str, ...]: ...

class PropertySpec:
    layer: Layer
