import os

from ...interface import *
from ...log import *

class UBImageElement(LocalFileSystemElementImpl):
    pass

class UBImageUnpacker(Unpacker):
    logger = getLogger('UBImageUnpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from ubireader.ubi import ubi
        from ubireader.ubi.defines import UBI_EC_HDR_MAGIC
        from ubireader.ubi_io import ubi_file, leb_virtual_file
        from ubireader.utils import guess_filetype, guess_start_offset, guess_peb_size

    @property
    def name(self) -> str:
        return 'UBImageUnpacker'
        
    def byte_signatures(self):
        return b'UBI#'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'UBI#')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from ...utils import copy_stream_to_file

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                temp_input_file = os.path.join(temp_dir, 'img.ubi')
                temp_output_dir = os.path.join(temp_dir, 'output')
                os.mkdir(temp_output_dir)
                with elem.open_stream() as stream:
                    copy_stream_to_file(stream, temp_input_file)
                
                self._extract_to_dir(temp_input_file, temp_output_dir)
                for name in os.listdir(temp_output_dir):
                    yield UBImageElement(name, os.path.join(temp_output_dir, name), scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)
    
    def _extract_to_dir(self, path, output_dir):
        from ubireader.ubi import ubi
        from ubireader.ubi.defines import UBI_EC_HDR_MAGIC
        from ubireader.ubi_io import ubi_file, leb_virtual_file
        from ubireader.utils import guess_filetype, guess_start_offset, guess_peb_size
        block_size = guess_peb_size(path)
        start_offset = guess_start_offset(path)
        end_offset = None
        # Create file object.
        ufile_obj = ubi_file(path, block_size, start_offset, end_offset)

        # Create UBI object
        ubi_obj = ubi(ufile_obj)
        
        # Loop through found images in file.
        for image in ubi_obj.images:
            # Loop through image volumes
            for volume in image.volumes:
                vol_outpath = os.path.join(output_dir, '%s_vol-%s.img' % (image.image_seq, volume))
                with open(vol_outpath, 'wb+') as f:
                    # Loop through and write volume block data (LEB) to file.
                    for block in image.volumes[volume].reader(ubi_obj):
                        f.write(block)
