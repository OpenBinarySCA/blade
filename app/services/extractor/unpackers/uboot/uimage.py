import os

from ...interface import *
from ...log import *

class UImageElement(LocalFileSystemElementImpl):
    pass

class UImageUnpacker(Unpacker):
    logger = getLogger('UImageUnpacker')
    @property
    def name(self) -> str:
        return 'UImageUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)

    def byte_signatures(self):
        return b'\x27\x05\x19\x56'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'\x27\x05\x19\x56')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
            
                with elem.open_stream() as stream:
                    self._extract_to_dir(stream, temp_dir)
                for name in os.listdir(temp_dir):
                    yield UImageElement(name, os.path.join(temp_dir, name), scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, stream, output_dir):
        from . import uboot
        def get_file_ext(img):
            ext = ('bin', 'gz', 'bz2', 'lzma', 'lzo', 'lz4')
            return ext[img.header.compression]

        raw_data = stream.read()

        img = uboot.parse_img(raw_data)

        if img.header.image_type == uboot.EnumImageType.MULTI:
            n = 0
            for simg in img:
                with open(os.path.join(output_dir, 'image_{0:02d}.bin'.format(n)), 'wb') as f:
                    f.write(simg.export())
                n += 1
        elif img.header.image_type == uboot.EnumImageType.SCRIPT:
            with open(os.path.join(output_dir, 'script.txt'), 'w') as f:
                f.write(img.store())

        else:
            with open(os.path.join(output_dir, 'image.' + get_file_ext(img)), 'wb') as f:
                f.write(img.data)

        with open(os.path.join(output_dir, 'info.txt'), 'w') as f:
            f.write(img.info())
