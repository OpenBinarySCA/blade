import dataclasses
import enum
from dataclasses import asdict, fields
from dataclasses import dataclass
from typing import Any, Type
from typing import Dict
from typing import List


@dataclass
class Serializable:
    def customer_serialize(self) -> Dict[str, Any]:
        serialized_data = asdict(self)
        for field in fields(self):
            value = getattr(self, field.name)
            if hasattr(value, 'customer_serialize'):
                serialized_data[field.name] = value.customer_serialize()
            elif isinstance(value, list) and value and hasattr(value[0], 'customer_serialize'):
                serialized_data[field.name] = [item.customer_serialize() for item in value]
        return serialized_data

    @classmethod
    def init_from_dict(cls: Type['Serializable'], data: Dict[str, Any]) -> 'Serializable':

        init_args = {}
        for field in fields(cls):
            try:
                field_value = data.get(field.name)
                if hasattr(field.type, 'init_from_dict') and isinstance(field_value, dict):
                    init_args[field.name] = field.type.init_from_dict(field_value)
                elif (isinstance(field_value, list) and
                      field.type.__args__ and
                      hasattr(field.type.__args__[0], 'init_from_dict') and
                      all(isinstance(i, dict) for i in field_value)):
                    init_args[field.name] = [field.type.__args__[0].init_from_dict(item) for item in field_value]
                else:
                    init_args[field.name] = field_value
            except Exception as e:
                print(cls.__name__, field.name, field.type)
                raise e
        return cls(**init_args)

class NodeType(enum.Enum):
    function_declarator = "function_declarator"  # 函数声明
    function_definition = "function_definition"  # 函数定义
    pointer_declarator = "pointer_declarator"  # 指针声明

    @classmethod
    def get_function_node_values(cls):
        return {
            cls.function_declarator.value,
            cls.function_definition.value,
            cls.pointer_declarator.value
        }


@dataclass
class FunctionFeature(Serializable):
    name: str
    start_line: int
    end_line: int
    file_path: str
    distinct_string_num: int
    function_calls: List[str]
    string_literals: List[str]
    source_codes: List[str]


@dataclass
class FileFeature(Serializable):
    name: str
    extension: str
    path: str
    file_size_kb: float
    sha256:str

    function_num: int
    distinct_string_num: int

    extraction_succeed: bool = True
    extraction_log: str = ""

    functions: List[FunctionFeature] = dataclasses.field(default_factory=list)
    global_strings: List[str] = dataclasses.field(default_factory=list)
    may_missed_function_names: List[str] = dataclasses.field(default_factory=list)


    def use_relative_file_path(self, base_path: str):
        base_path = str(base_path)
        self.path = self.path.replace(base_path, "")
        for function in self.functions:
            function.file_path = function.file_path.replace(base_path, "")

    def get_strings(self):
        string_set = set(self.global_strings)
        for function in self.functions:
            string_set.update(function.string_literals)

        return list(string_set)

    def get_function_names(self):
        """
        获取文件中所有的函数名，包括全局字符串中的函数名和函数特征中的函数名
        处理：如果函数名以 * 开头，则去掉 *，并去除首尾空格

        :return:
        """
        function_names = set()

        # 处理全局字符串中的函数名
        for func_name in self.may_missed_function_names:
            if func_name.startswith("*"):
                func_name = func_name[1:]
            function_names.add(func_name.strip())

        # 处理函数特征中的函数名
        for function in self.functions:
            func_name = function.name
            if func_name.startswith("*"):
                func_name = func_name[1:]
            function_names.add(func_name.strip())

        return list(function_names)
@dataclass
class ProjectFeature(Serializable):
    name: str
    project_size_mb: float

    # statistics
    total_src_file: int = 0  # 所有的源代码文件数量，无论提取成功失败
    failed_src_file: int = 0  # 提取失败的文件数量
    exception_src_file: int = 0  # 提取时发生异常的文件数量, 成功了，但是有记录异常日志

    function_count: int = 0  # 提取到的函数数量
    distinct_string_count: int = 0  # 提取到的字符串去重后的数量

    extraction_succeed: bool = True
    extraction_log: str = ""

    file_features: List[FileFeature] = dataclasses.field(default_factory=list)

    def __repr__(self):
        return f"project name: {self.name}, c/cpp file count: {len(self.file_features)}, c/cpp file size: {self.project_size_mb} mb."

