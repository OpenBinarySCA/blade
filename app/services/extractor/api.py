import typing
from .core import ExtractorEngine
from .element import ExtractorElement


def extract_iter(
        path: str, 
        sigs:      typing.Union[bytes, typing.List[bytes], None] = None, 
        filetypes: typing.Union[str,   typing.List[str],   None] = None,
        temp_dir: str = None,
        ignore_error: bool = False,
        nounpack_filetypes = None,
        output_filetypes = None,
        stats: dict = None,
        max_nesting_level: typing.Union[int, None] = None,
        output_filter: typing.Callable[[ExtractorElement], bool] = None,
        unpack_filter: typing.Callable[[ExtractorElement], bool] = None,
        ) -> typing.Iterable[ExtractorElement]:
    extractor = ExtractorEngine()
    extractor.initialize(temp_dir=temp_dir)
    try:
        yield from extractor.extract(
            path, 
            bytesigs=sigs, 
            filetypes=filetypes, 
            ignore_error=ignore_error, 
            nounpack_filetypes=nounpack_filetypes,
            output_filetypes=output_filetypes,
            stats = stats,
            max_nesting_level = max_nesting_level,
            output_filter = output_filter,
            unpack_filter = unpack_filter,
        )
    finally:
        extractor.deinitialize()