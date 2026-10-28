import os
import tempfile
import shutil

from .element import ExtractorElement
from .context import ExtractorContext

class ExtractorScope:
    def __init__(self, *, unpacker, context: ExtractorContext, elem: ExtractorElement) -> None:
        self._context = context
        self._unpacker = unpacker
        self._elem = elem
        self._should_skip = False
        self._injected_exception = None
        self._temp_dir = None
        self._qualsep = ':'
        self._nesting_level = (elem.scope.nesting_level + 1) if elem else 0

    @property
    def qualsep(self):
        return self._qualsep

    @property
    def unpacker(self):
        return self._unpacker

    @property
    def elem(self):
        return self._elem
    
    @property
    def nesting_level(self):
        return self._nesting_level

    def __enter__(self):
        name = self._unpacker.name if self._unpacker else None
        self._context.enter_unpacker(name)
        return self

    def __exit__(self, type, value, trace):
        name = self._unpacker.name if self._unpacker else None
        self._context.leave_unpacker(name)
        if self._temp_dir:
            try:
                if os.path.exists(self._temp_dir):
                    shutil.rmtree(self._temp_dir)
            except OSError as exc:
                self._unpacker.logger.warn(f'<extract> delete tmp dir failed. {str(exc)}. path={self._temp_dir}')
            
    def skip(self):
        self._should_skip = True

    @property
    def should_skip(self):
        if self._injected_exception:
            raise self._injected_exception
        return self._should_skip
    
    # only for debugging and tests 
    def _inject_exception(self, exc):
        self._injected_exception = exc

    @property
    def temp_dir(self):
        if self._temp_dir == None:
            self._temp_dir = tempfile.mkdtemp(
                prefix = self._unpacker.name + '-', 
                dir    = self._context.temp_dir
            )
        return self._temp_dir
    
    def mkdtemp(self, prefix=None, suffix=None):
        return tempfile.mkdtemp(prefix=prefix, suffix=suffix, dir=self.temp_dir)

    def mkstemp(self, prefix=None, suffix=None):
        fd, filename = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=self.temp_dir)
        os.close(fd)
        return filename
