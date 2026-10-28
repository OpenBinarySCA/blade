import os

from ....interface import *
from ....log import *

class SImgElement(LocalFileSystemElementImpl):
    pass

class SImgUnpacker(Unpacker):
    logger = getLogger('SImgUnpacker')
    @property
    def name(self) -> str:
        return 'SImgUnpacker'
        
    def byte_signatures(self):
        return b'\x3A\xFF\x26\xED'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'\x3A\xFF\x26\xED')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from .simg_reader import extract

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                temp_img_path = os.path.join(temp_dir, 'simg.img')
                
                with elem.open_stream() as stream:
                    with open(temp_img_path, 'wb+')  as f_out:
                        extract(stream, f_out)
                    yield SImgElement('simg-data', temp_img_path, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

            
