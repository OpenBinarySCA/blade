import os

from ...interface import *
from ...log import *

class FITImageElement(LocalFileSystemElementImpl):
    pass

class FITImageUnpacker(Unpacker):
    logger = getLogger('FITImageUnpacker')
    @property
    def name(self) -> str:
        return 'FITImageUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)

    def byte_signatures(self):
        return b'\xD0\x0D\xFE\xED' # same as Linux DTB (Device Tree Blob)

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        from . import uboot
        with elem.open_stream() as stream:
            raw_data = stream.read(1024*1024)
            try:
                img = uboot.parse_itb(raw_data)
                return True
            except Exception as exc:
                return False

    def extract(self, context: ExtractorContext, elem: ExtractorElement):

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
        
                with elem.open_stream() as stream:
                    self._extract_to_dir(stream, temp_dir)
                for name in os.listdir(temp_dir):
                    yield FITImageElement(name, os.path.join(temp_dir, name), scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, stream, output_dir):
        from . import uboot
        raw_data = stream.read()

        img = uboot.parse_itb(raw_data)

        its, images = img.to_its()

        with open(os.path.join(output_dir, '_meta.its'), 'w') as f:
            f.write(its)

        for name, data in images.items():
            with open(os.path.join(output_dir, name), 'wb') as f:
                f.write(data)

        with open(os.path.join(output_dir, 'info.txt'), 'w') as f:
            f.write(img.info())
