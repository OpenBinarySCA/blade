import os

from ....interface import *
from ....log import *

class CrAUElement(LocalFileSystemElementImpl):
    pass

class CrAUUnpacker(Unpacker):
    logger = getLogger('CrAUUnpacker')
    @property
    def name(self) -> str:
        return 'CrAUUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from .dumper import extract
        
    def byte_signatures(self):
        return b'CrAU'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'CrAU')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from .dumper import extract

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                with elem.open_stream() as stream:
                    for name, temp_file in extract(stream, temp_dir, self.logger):
                        if scope.should_skip:
                            break
                        yield CrAUElement(name, temp_file, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

            
