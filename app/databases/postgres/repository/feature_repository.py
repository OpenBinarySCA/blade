"""
Feature Repository - 特征数据 CRUD 操作
"""
import hashlib
from typing import List, Optional, Dict, Set

from loguru import logger
from sqlalchemy.dialects.postgresql import insert

from ..postgres import session_generator
from ..entities import (
    StringFeature, FunctionNameFeature,
    ProjectFeature as DBProjectFeature, FileFeature as DBFileFeature, FileMeta,
    StringToLibrary, FunctionNameToLibrary,
    StringToProject, FunctionNameToProject,
    StringToFile, FunctionNameToFile,
)


def compute_hash(value: str) -> str:
    """计算字符串的 SHA256 哈希值"""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


# ============ String Feature ============

def get_or_create_string_feature(string_value: str) -> StringFeature:
    """获取或创建字符串特征"""
    string_hash = compute_hash(string_value)
    with session_generator() as session:
        existing = session.query(StringFeature).filter(
            StringFeature.string_hash == string_hash
        ).first()
        if existing:
            return existing

        new_feature = StringFeature(
            string_value=string_value,
            string_hash=string_hash
        )
        session.add(new_feature)
        session.commit()
        session.refresh(new_feature)
        return new_feature


def bulk_get_or_create_strings(strings: List[str]) -> Dict[str, int]:
    """
    批量获取或创建字符串特征
    返回: {string_value: feature_id}
    """
    if not strings:
        return {}

    # 去重
    unique_strings = list(set(strings))
    hash_to_string = {compute_hash(s): s for s in unique_strings}
    hashes = list(hash_to_string.keys())

    result = {}

    with session_generator() as session:
        # 查询已存在的
        existing = session.query(StringFeature).filter(
            StringFeature.string_hash.in_(hashes)
        ).all()

        existing_hashes = set()
        for sf in existing:
            result[hash_to_string[sf.string_hash]] = sf.id
            existing_hashes.add(sf.string_hash)

        # 插入不存在的
        new_hashes = set(hashes) - existing_hashes
        if new_hashes:
            new_features = [
                StringFeature(
                    string_value=hash_to_string[h],
                    string_hash=h
                )
                for h in new_hashes
            ]
            session.add_all(new_features)
            session.commit()

            # 获取新插入的 ID
            for nf in new_features:
                session.refresh(nf)
                result[nf.string_value] = nf.id

    return result


# ============ Function Name Feature ============

def get_or_create_function_name_feature(function_name: str) -> FunctionNameFeature:
    """获取或创建函数名特征"""
    function_hash = compute_hash(function_name)
    with session_generator() as session:
        existing = session.query(FunctionNameFeature).filter(
            FunctionNameFeature.function_hash == function_hash
        ).first()
        if existing:
            return existing

        new_feature = FunctionNameFeature(
            function_name=function_name,
            function_hash=function_hash
        )
        session.add(new_feature)
        session.commit()
        session.refresh(new_feature)
        return new_feature


def bulk_get_or_create_function_names(function_names: List[str]) -> Dict[str, int]:
    """
    批量获取或创建函数名特征
    返回: {function_name: feature_id}
    """
    if not function_names:
        return {}

    # 去重
    unique_names = list(set(function_names))
    hash_to_name = {compute_hash(n): n for n in unique_names}
    hashes = list(hash_to_name.keys())

    result = {}

    with session_generator() as session:
        # 查询已存在的
        existing = session.query(FunctionNameFeature).filter(
            FunctionNameFeature.function_hash.in_(hashes)
        ).all()

        existing_hashes = set()
        for fn in existing:
            result[hash_to_name[fn.function_hash]] = fn.id
            existing_hashes.add(fn.function_hash)

        # 插入不存在的
        new_hashes = set(hashes) - existing_hashes
        if new_hashes:
            new_features = [
                FunctionNameFeature(
                    function_name=hash_to_name[h],
                    function_hash=h
                )
                for h in new_hashes
            ]
            session.add_all(new_features)
            session.commit()

            # 获取新插入的 ID
            for nf in new_features:
                session.refresh(nf)
                result[nf.function_name] = nf.id

    return result


# ============ Project Feature ============

def create_project_feature(source_code_id: int, project_data: dict) -> DBProjectFeature:
    """创建项目特征"""
    with session_generator() as session:
        project_feature = DBProjectFeature(
            id=source_code_id,  # 使用 source_code_id 作为主键
            name=project_data.get('name'),
            project_size_mb=project_data.get('project_size_mb'),
            total_src_file=project_data.get('total_src_file'),
            failed_src_file=project_data.get('failed_src_file'),
            exception_src_file=project_data.get('exception_src_file'),
            function_count=project_data.get('function_count'),
            distinct_string_count=project_data.get('distinct_string_count'),
            extraction_succeed=project_data.get('extraction_succeed', True),
            extraction_log=project_data.get('extraction_log'),
        )
        session.add(project_feature)
        session.commit()
        session.refresh(project_feature)
        return project_feature


def get_project_feature(source_code_id: int) -> Optional[DBProjectFeature]:
    """获取项目特征"""
    with session_generator() as session:
        return session.query(DBProjectFeature).filter(
            DBProjectFeature.id == source_code_id
        ).first()


# ============ File Feature ============

def get_or_create_file_feature(file_data: dict) -> DBFileFeature:
    """获取或创建文件特征（基于 sha256 去重）"""
    file_sha256 = file_data.get('sha256')

    with session_generator() as session:
        existing = session.query(DBFileFeature).filter(
            DBFileFeature.file_sha256 == file_sha256
        ).first()
        if existing:
            return existing

        file_feature = DBFileFeature(
            file_sha256=file_sha256,
            name=file_data.get('name'),
            extension=file_data.get('extension'),
            file_size_kb=file_data.get('file_size_kb'),
            function_num=file_data.get('function_num'),
            distinct_string_num=file_data.get('distinct_string_num'),
            global_strings=file_data.get('global_strings', []),
            extraction_succeed=file_data.get('extraction_succeed', True),
            extraction_log=file_data.get('extraction_log'),
        )
        session.add(file_feature)
        session.commit()
        session.refresh(file_feature)
        return file_feature


def create_file_meta(project_id: int, file_feature_id: int, path: str, file_sha256: str) -> FileMeta:
    """创建文件元数据（关联项目和文件）"""
    with session_generator() as session:
        file_meta = FileMeta(
            project_feature_id=project_id,
            file_feature_id=file_feature_id,
            path=path,
            file_sha256=file_sha256,
        )
        session.add(file_meta)
        session.commit()
        session.refresh(file_meta)
        return file_meta


# ============ 关联关系 ============

def add_strings_to_library(string_ids: List[int], library_id: int):
    """批量添加字符串到库的关联"""
    if not string_ids:
        return

    with session_generator() as session:
        # 使用 INSERT ... ON CONFLICT DO NOTHING
        for string_id in string_ids:
            stmt = insert(StringToLibrary).values(
                string_id=string_id,
                library_id=library_id
            ).on_conflict_do_nothing(
                constraint='uix_string_library'
            )
            session.execute(stmt)
        session.commit()


def add_function_names_to_library(function_name_ids: List[int], library_id: int):
    """批量添加函数名到库的关联"""
    if not function_name_ids:
        return

    with session_generator() as session:
        for fn_id in function_name_ids:
            stmt = insert(FunctionNameToLibrary).values(
                function_name_id=fn_id,
                library_id=library_id
            ).on_conflict_do_nothing(
                constraint='uix_function_name_library'
            )
            session.execute(stmt)
        session.commit()


def add_strings_to_project(string_ids: List[int], project_id: int):
    """批量添加字符串到项目的关联"""
    if not string_ids:
        return

    with session_generator() as session:
        for string_id in string_ids:
            stmt = insert(StringToProject).values(
                string_id=string_id,
                project_id=project_id
            ).on_conflict_do_nothing(
                constraint='uix_string_project'
            )
            session.execute(stmt)
        session.commit()


def add_function_names_to_project(function_name_ids: List[int], project_id: int):
    """批量添加函数名到项目的关联"""
    if not function_name_ids:
        return

    with session_generator() as session:
        for fn_id in function_name_ids:
            stmt = insert(FunctionNameToProject).values(
                function_name_id=fn_id,
                project_id=project_id
            ).on_conflict_do_nothing(
                constraint='uix_function_name_project'
            )
            session.execute(stmt)
        session.commit()


# ============ 文件级关联关系 ============

def add_strings_to_file(string_ids: List[int], file_id: int):
    """批量添加字符串到文件的关联"""
    if not string_ids:
        return

    with session_generator() as session:
        for string_id in string_ids:
            stmt = insert(StringToFile).values(
                string_id=string_id,
                file_id=file_id
            ).on_conflict_do_nothing(
                constraint='uix_string_file'
            )
            session.execute(stmt)
        session.commit()


def add_function_names_to_file(function_name_ids: List[int], file_id: int):
    """批量添加函数名到文件的关联"""
    if not function_name_ids:
        return

    with session_generator() as session:
        for fn_id in function_name_ids:
            stmt = insert(FunctionNameToFile).values(
                function_name_id=fn_id,
                file_id=file_id
            ).on_conflict_do_nothing(
                constraint='uix_function_name_file'
            )
            session.execute(stmt)
        session.commit()


def bulk_get_or_create_file_features(file_data_list: List[dict]) -> Dict[str, int]:
    """
    批量获取或创建文件特征（基于 sha256 去重）

    Args:
        file_data_list: 文件数据列表，每个元素包含 sha256, name, extension 等

    Returns:
        {sha256: file_feature_id} 映射
    """
    if not file_data_list:
        return {}

    # 按 sha256 去重
    sha256_to_data = {fd['sha256']: fd for fd in file_data_list if fd.get('sha256')}
    sha256_list = list(sha256_to_data.keys())

    result = {}

    with session_generator() as session:
        # 查询已存在的
        existing = session.query(DBFileFeature).filter(
            DBFileFeature.file_sha256.in_(sha256_list)
        ).all()

        existing_sha256s = set()
        for ff in existing:
            result[ff.file_sha256] = ff.id
            existing_sha256s.add(ff.file_sha256)

        # 插入不存在的
        new_sha256s = set(sha256_list) - existing_sha256s
        if new_sha256s:
            new_features = []
            for sha256 in new_sha256s:
                fd = sha256_to_data[sha256]
                new_features.append(DBFileFeature(
                    file_sha256=sha256,
                    name=fd.get('name'),
                    extension=fd.get('extension'),
                    file_size_kb=fd.get('file_size_kb', 0),
                    function_num=fd.get('function_num', 0),
                    distinct_string_num=fd.get('distinct_string_num', 0),
                    global_strings=fd.get('global_strings', []),
                    extraction_succeed=fd.get('extraction_succeed', True),
                    extraction_log=fd.get('extraction_log', ''),
                ))
            session.add_all(new_features)
            session.commit()

            # 获取新插入的 ID
            for nf in new_features:
                session.refresh(nf)
                result[nf.file_sha256] = nf.id

    return result


def bulk_create_file_metas(project_id: int, file_metas_data: List[dict]):
    """
    批量创建文件元数据（关联项目和文件）

    Args:
        project_id: 项目 ID (= source_code_id)
        file_metas_data: 文件元数据列表，每个元素包含 file_feature_id, path, file_sha256
    """
    if not file_metas_data:
        return

    with session_generator() as session:
        for fm_data in file_metas_data:
            # 使用 on_conflict_do_nothing 避免重复插入
            stmt = insert(FileMeta).values(
                project_feature_id=project_id,
                file_feature_id=fm_data['file_feature_id'],
                path=fm_data['path'],
                file_sha256=fm_data['file_sha256'],
            ).on_conflict_do_nothing(
                constraint='uix_file_metas_unique'
            )
            session.execute(stmt)
        session.commit()
