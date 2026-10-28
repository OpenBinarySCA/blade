To implement GzipFileWithTrailingGarbage
    1) a gzip.py is copied from python3.8 stdlib, not changed.
    2) monkey patch py38_gzip._GzipReader

