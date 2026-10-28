import abc
import typing
from .element import ExtractorElement, LocalFileSystemElementImpl
from .context import ExtractorContext
from .scope import ExtractorScope

class Engine(abc.ABC):
    @abc.abstractmethod
    def dispatch(self, context: ExtractorContext, elem: ExtractorElement):
        pass

    @abc.abstractmethod
    def extract(self, path: str, options=None) -> typing.Iterable[ExtractorElement]:
        pass

BYTE_SIGNATURES_FLEXIBLE = '*'
BYTE_SIGNATURES_WILDCARD = '**'

class Unpacker(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def priority(self) -> int:
        return 0

    @property
    @abc.abstractmethod
    def byte_signatures(self):
        raise NotImplementedError()
    
    def initialize(self, engine: Engine) -> None:
        pass
    
    def deinitialize(self) -> None:
        pass

    @abc.abstractmethod
    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        pass

    @abc.abstractmethod
    def extract(self, context: ExtractorContext, elem: ExtractorElement)  -> typing.Iterable[ExtractorElement]:
        pass
