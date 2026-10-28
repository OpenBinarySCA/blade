import dataclasses
import json
import sys
import traceback
from dataclasses import asdict, fields
from dataclasses import dataclass
from typing import Dict, Type, Any, Union, get_origin, get_args
from typing import List

from environs import Env
from loguru import logger

env = Env()
env.read_env()
logger.remove()
logger.add(sys.stderr, level="INFO")


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
            elif isinstance(value, dict):
                # 处理字典类型的序列化
                serialized_dict = {}
                for key, val in value.items():
                    if hasattr(val, 'customer_serialize'):
                        serialized_dict[key] = val.customer_serialize()
                    elif isinstance(val, list) and val and hasattr(val[0], 'customer_serialize'):
                        serialized_dict[key] = [item.customer_serialize() for item in val]
                    else:
                        serialized_dict[key] = val
                serialized_data[field.name] = serialized_dict
        return serialized_data

    @classmethod
    def init_from_dict(cls: Type['Serializable'], data: Dict[str, Any]) -> 'Serializable':
        init_args = {}
        for field in fields(cls):
            try:
                field_value = data.get(field.name)

                # 如果字段值为None，直接使用默认值
                if field_value is None:
                    init_args[field.name] = field_value
                    continue

                # 获取类型信息
                field_type = field.type
                origin_type = get_origin(field_type)
                type_args = get_args(field_type)

                # 处理直接的自定义类
                if hasattr(field_type, 'init_from_dict') and isinstance(field_value, dict):
                    init_args[field.name] = field_type.init_from_dict(field_value)

                # 处理 List[CustomClass] 类型
                elif (origin_type is list and
                      isinstance(field_value, list) and
                      type_args and
                      hasattr(type_args[0], 'init_from_dict') and
                      all(isinstance(i, dict) for i in field_value if i is not None)):
                    init_args[field.name] = [type_args[0].init_from_dict(item) for item in field_value if
                                             item is not None]

                # 处理 Dict[str, List[CustomClass]] 类型
                elif (origin_type is dict and
                      isinstance(field_value, dict) and
                      len(type_args) >= 2):

                    value_type = type_args[1]  # 获取字典值的类型
                    value_origin = get_origin(value_type)
                    value_args = get_args(value_type)

                    # 如果字典值是 List[CustomClass] 类型
                    if (value_origin is list and
                            value_args and
                            hasattr(value_args[0], 'init_from_dict')):
                        processed_dict = {}
                        for key, value_list in field_value.items():
                            if isinstance(value_list, list):
                                processed_dict[key] = [value_args[0].init_from_dict(item)
                                                       for item in value_list
                                                       if isinstance(item, dict)]
                            else:
                                processed_dict[key] = value_list
                        init_args[field.name] = processed_dict

                    # 如果字典值是直接的自定义类 Dict[str, CustomClass]
                    elif hasattr(value_type, 'init_from_dict'):
                        processed_dict = {}
                        for key, value_item in field_value.items():
                            if isinstance(value_item, dict):
                                processed_dict[key] = value_type.init_from_dict(value_item)
                            else:
                                processed_dict[key] = value_item
                        init_args[field.name] = processed_dict

                    else:
                        # 普通字典，直接赋值
                        init_args[field.name] = field_value

                # 处理 Union 类型（包括 Optional）
                elif origin_type is Union:
                    # 尝试按照Union中的每个类型进行初始化
                    initialized = False
                    for union_type in type_args:
                        if union_type is type(None):  # 跳过 None 类型
                            continue
                        try:
                            if hasattr(union_type, 'init_from_dict') and isinstance(field_value, dict):
                                init_args[field.name] = union_type.init_from_dict(field_value)
                                initialized = True
                                break
                        except:
                            continue

                    if not initialized:
                        init_args[field.name] = field_value

                else:
                    # 其他情况，直接赋值
                    init_args[field.name] = field_value

            except Exception as e:
                logger.error(f"Error in {cls.__name__}, field: {field.name}, type: {field.type}")
                logger.error(f"Field value: {field_value}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise e

        return cls(**init_args)





@dataclass
class Library(Serializable):
    # meta
    name: str
    version: str
    description: str = ""
    # 字符串或列表
    license: Union[str, List[str]] = ""  # e.g., "MIT", ["MIT", "Apache-2.0"]
    homepage: str = ""
    url: str = ""
    topics: List[str] = dataclasses.field(default_factory=list)

    def __hash__(self):
        return hash((self.name, self.version))

    def __eq__(self, other):
        if not isinstance(other, Library):
            return NotImplemented
        return self.name == other.name and self.version == other.version

@dataclass
class LibraryReuse(Serializable):

    # library
    library:Library

    # reuse
    is_real_used: bool = True  # Whether the library is actually used in the binary
    link_type: str = "shared"  # e.g., "static", "shared"
    level: str = 1  # e.g., "local", "global"
    reuse_paths: List[str] = dataclasses.field(default_factory=list)  # Paths to the reused libraries
    has_tc: bool = False  # 是否有测试用例覆盖

@dataclass
class CompileConfig(Serializable):
    conan_version:str
    profile:str

@dataclass
class Binary(Serializable):
    # meta
    name: str
    type: str  # e.g., "bin", "lib"
    rel_path:str # 相对路径
    file_size_kb: float
    sha256: str

    # under what tpl dir
    tpl_name: str

    def __hash__(self):
        return hash((self.tpl_name, self.name, self.sha256))
    def __eq__(self, other):
        if not isinstance(other, Binary):
            return NotImplemented
        return (self.tpl_name == other.tpl_name and
                self.name == other.name and
                self.sha256 == other.sha256)

@dataclass
class TestBinarySuiteStat(Serializable):
    total_reused_library:int
    total_binaries:int
    bin_binaries: int  # Number of binary files
    lib_binaries: int

@dataclass
class TestBinarySuite(Serializable):
    # stat
    stat: TestBinarySuiteStat = None

    # compile config
    compile_config: CompileConfig = None  # Compile configuration, e.g., "Release", "Debug"

    # reused_libraries
    library_reuses: List[LibraryReuse] = dataclasses.field(default_factory=list)

    # binaries
    binaries: Dict[str, List[Binary]] = dataclasses.field(default_factory=list)


@dataclass
class TestSoftware(Serializable):
    # library meta
    source_library: Library  # The source library for this test case

    test_binary_suites: List[TestBinarySuite] = dataclasses.field(default_factory=list)  # List of test binary suites


@dataclass
class Benchmark(Serializable):
    name: str
    version: str
    test_software: List[TestSoftware] = dataclasses.field(default_factory=list)

    def stat(self):
        """
        生成面向论文的详细benchmark统计报告
        """
        print("=" * 80)
        print(f"CONAN LIBRARY BENCHMARK - 数据集统计报告")
        print("=" * 80)

        # ===== 1. 总体概览 =====
        print("\n📊 总体概览")
        print("-" * 50)

        # 基础统计
        total_software = len(self.test_software)
        total_profiles = len(set(
            suite.compile_config.profile
            for ts in self.test_software
            for suite in ts.test_binary_suites
        ))

        # 统计所有第三方库
        all_dependencies = set()
        real_dependencies = set()
        real_dependencies_with_tc = set()  # 有测试用例的真实使用库
        for ts in self.test_software:
            for suite in ts.test_binary_suites:
                for reuse in suite.library_reuses:
                    all_dependencies.add((reuse.library.name, reuse.library.version))
                    if reuse.is_real_used:
                        real_dependencies.add((reuse.library.name, reuse.library.version))
                        if reuse.has_tc:
                            real_dependencies_with_tc.add((reuse.library.name, reuse.library.version))

        # 统计所有二进制文件
        total_binaries = sum(
            len(binaries)
            for ts in self.test_software
            for suite in ts.test_binary_suites
            for binaries in suite.binaries.values()
        )

        # 改为只用 sha256 去重
        unique_binaries = set(
            binary.sha256
            for ts in self.test_software
            for suite in ts.test_binary_suites
            for binaries in suite.binaries.values()
            for binary in binaries
        )

        # 按类型统计二进制文件（去重前）
        total_bin_files = sum(
            1 for ts in self.test_software
            for suite in ts.test_binary_suites
            for binaries in suite.binaries.values()
            for binary in binaries
            if binary.type == 'bin'
        )
        total_lib_files = sum(
            1 for ts in self.test_software
            for suite in ts.test_binary_suites
            for binaries in suite.binaries.values()
            for binary in binaries
            if binary.type == 'lib'
        )

        # 按类型统计二进制文件（去重后）- 改为只用 sha256 去重
        unique_bin_files = len(set(
            binary.sha256
            for ts in self.test_software
            for suite in ts.test_binary_suites
            for binaries in suite.binaries.values()
            for binary in binaries
            if binary.type == 'bin'
        ))
        unique_lib_files = len(set(
            binary.sha256
            for ts in self.test_software
            for suite in ts.test_binary_suites
            for binaries in suite.binaries.values()
            for binary in binaries
            if binary.type == 'lib'
        ))

        # 统计profile间的二进制文件重叠情况
        profiles = sorted(set(
            suite.compile_config.profile
            for ts in self.test_software
            for suite in ts.test_binary_suites
        ))

        # 构建每个profile的二进制文件集合 - 改为只用 sha256
        profile_binaries = {}
        for profile in profiles:
            profile_binaries[profile] = set()
            for ts in self.test_software:
                for suite in ts.test_binary_suites:
                    if suite.compile_config.profile == profile:
                        for binaries in suite.binaries.values():
                            for binary in binaries:
                                profile_binaries[profile].add(binary.sha256)

        # 计算独有和共享文件
        all_profile_binaries = set()
        for profile_bins in profile_binaries.values():
            all_profile_binaries.update(profile_bins)

        shared_binaries = set()
        unique_to_profile = {}
        for profile in profiles:
            unique_to_profile[profile] = profile_binaries[profile].copy()

        # 找出共享文件
        for binary_sha256 in all_profile_binaries:
            count = sum(1 for profile_bins in profile_binaries.values() if binary_sha256 in profile_bins)
            if count > 1:
                shared_binaries.add(binary_sha256)
                for profile in profiles:
                    if binary_sha256 in unique_to_profile[profile]:
                        unique_to_profile[profile].remove(binary_sha256)

        # 编译成功率统计
        software_compile_success = {}
        for ts in self.test_software:
            software_name = ts.source_library.name
            if software_name not in software_compile_success:
                software_compile_success[software_name] = set()
            for suite in ts.test_binary_suites:
                software_compile_success[software_name].add(suite.compile_config.profile)

        full_success = sum(1 for profiles_set in software_compile_success.values()
                           if len(profiles_set) == len(profiles))
        partial_success = len(software_compile_success) - full_success

        print(f"源软件数量: {total_software}")
        print(f"编译配置数: {total_profiles}")
        print(f"编译成功率统计:")
        print(f"  - 全平台编译成功: {full_success} 个软件")
        print(f"  - 部分平台编译成功: {partial_success} 个软件")
        print(
            f"  - 平均每软件支持平台数: {sum(len(profiles_set) for profiles_set in software_compile_success.values()) / len(software_compile_success):.1f}")
        print(f"涉及第三方库总数: {len(all_dependencies)}")
        print(f"实际使用的第三方库数: {len(real_dependencies)}")
        print(
            f"有测试用例覆盖的第三方库数: {len(real_dependencies_with_tc)} ({len(real_dependencies_with_tc) / len(real_dependencies) * 100:.1f}%)")
        print(f"二进制文件总数: {total_binaries:,}")
        print(f"  - 可执行文件(bin): {total_bin_files:,}")
        print(f"  - 库文件(lib): {total_lib_files:,}")
        print(f"去重后二进制文件数: {len(unique_binaries):,}")
        print(f"  - 可执行文件(bin): {unique_bin_files:,}")
        print(f"  - 库文件(lib): {unique_lib_files:,}")
        print(f"跨profile文件分布:")
        print(f"  - 共享文件数: {len(shared_binaries)} ({len(shared_binaries) / len(unique_binaries) * 100:.1f}%)")
        for profile in profiles:
            print(f"  - {profile} 独有文件数: {len(unique_to_profile[profile])}")

        # ===== 2. 编译配置详情 =====
        print(f"\n🔧 编译配置详情")
        print("-" * 50)

        # 分析架构和编译器
        architectures = set()
        compilers = set()
        for profile in profiles:
            parts = profile.split('-')
            if len(parts) >= 2:
                arch = parts[0]  # arm_64, x86_64
                compiler = parts[1]  # gcc, clang
                architectures.add(arch)
                compilers.add(compiler)

        print(f"支持架构: {', '.join(sorted(architectures))}")
        print(f"支持编译器: {', '.join(sorted(compilers))}")
        print(f"编译配置列表:")
        for i, profile in enumerate(profiles, 1):
            print(f"  {i}. {profile}")

        # ===== 3. 各编译配置统计详情 =====
        print(f"\n📋 各编译配置统计详情")
        print("-" * 50)

        profile_stats = {}
        for profile in profiles:
            # 统计该profile下的数据
            profile_software = set()
            profile_dependencies = set()
            profile_real_dependencies = set()
            profile_real_dependencies_with_tc = set()  # 该profile下有测试用例的库
            profile_binaries = []

            for ts in self.test_software:
                for suite in ts.test_binary_suites:
                    if suite.compile_config.profile == profile:
                        profile_software.add(ts.source_library.name)

                        # 统计依赖
                        for reuse in suite.library_reuses:
                            profile_dependencies.add((reuse.library.name, reuse.library.version))
                            if reuse.is_real_used:
                                profile_real_dependencies.add((reuse.library.name, reuse.library.version))
                                if reuse.has_tc:
                                    profile_real_dependencies_with_tc.add((reuse.library.name, reuse.library.version))

                        # 统计二进制文件
                        for binaries in suite.binaries.values():
                            profile_binaries.extend(binaries)

            # 去重后的二进制文件 - 改为只用 sha256
            profile_unique_binaries = set(
                binary.sha256 for binary in profile_binaries
            )

            # 按类型统计（去重前）
            bin_count = len([b for b in profile_binaries if b.type == 'bin'])
            lib_count = len([b for b in profile_binaries if b.type == 'lib'])

            # 按类型统计（去重后）- 改为只用 sha256
            unique_bin_count = len(set(b.sha256 for b in profile_binaries if b.type == 'bin'))
            unique_lib_count = len(set(b.sha256 for b in profile_binaries if b.type == 'lib'))

            profile_stats[profile] = {
                'software_count': len(profile_software),
                'total_deps': len(profile_dependencies),
                'real_deps': len(profile_real_dependencies),
                'real_deps_with_tc': len(profile_real_dependencies_with_tc),
                'total_binaries': len(profile_binaries),
                'unique_binaries': len(profile_unique_binaries),
                'bin_files': bin_count,
                'lib_files': lib_count,
                'unique_bin_files': unique_bin_count,
                'unique_lib_files': unique_lib_count
            }

            print(f"\n{profile}:")
            print(f"  成功编译软件数: {len(profile_software)}")
            print(f"  涉及第三方库总数: {len(profile_dependencies)}")
            print(f"  实际使用第三方库数: {len(profile_real_dependencies)}")
            print(
                f"  有测试用例覆盖的第三方库数: {len(profile_real_dependencies_with_tc)} ({len(profile_real_dependencies_with_tc) / len(profile_real_dependencies) * 100:.1f}%)")
            print(f"  二进制文件总数: {len(profile_binaries):,}")
            print(f"    - 可执行文件(bin): {bin_count:,}")
            print(f"    - 库文件(lib): {lib_count:,}")
            print(f"  去重后二进制文件数: {len(profile_unique_binaries):,}")
            print(f"    - 可执行文件(bin): {unique_bin_count:,}")
            print(f"    - 库文件(lib): {unique_lib_count:,}")

        # ===== 4. 存储空间统计 =====
        print(f"\n💾 存储空间统计")
        print("-" * 50)

        total_size_kb = sum(
            binary.file_size_kb
            for ts in self.test_software
            for suite in ts.test_binary_suites
            for binaries in suite.binaries.values()
            for binary in binaries
        )

        # 计算去重后的文件大小 - 改为只用 sha256
        unique_binary_sizes = {}
        for ts in self.test_software:
            for suite in ts.test_binary_suites:
                for binaries in suite.binaries.values():
                    for binary in binaries:
                        if binary.sha256 not in unique_binary_sizes:
                            unique_binary_sizes[binary.sha256] = binary.file_size_kb

        unique_total_size_kb = sum(unique_binary_sizes.values())

        print(
            f"总存储空间: {total_size_kb:,.2f} KB ({total_size_kb / 1024:.2f} MB, {total_size_kb / 1024 / 1024:.2f} GB)")
        print(
            f"去重后存储空间: {unique_total_size_kb:,.2f} KB ({unique_total_size_kb / 1024:.2f} MB, {unique_total_size_kb / 1024 / 1024:.2f} GB)")
        print(f"空间节省率: {(1 - unique_total_size_kb / total_size_kb) * 100:.1f}%")
        print(f"平均文件大小: {total_size_kb / total_binaries:.2f} KB")
        print(f"去重后平均文件大小: {unique_total_size_kb / len(unique_binaries):.2f} KB")

        # ===== 5. 软件来源Topic分析 =====
        print(f"\n📚 软件来源Topic分析")
        print("-" * 50)

        # 统计所有topic
        all_topics = []
        for ts in self.test_software:
            if ts.source_library.topics:
                all_topics.extend(ts.source_library.topics)

        # 统计topic频率
        from collections import Counter
        topic_counter = Counter(all_topics)

        print(f"Topic种类总数: {len(topic_counter)}")
        print(f"包含topic信息的软件数: {sum(1 for ts in self.test_software if ts.source_library.topics)}")

        if topic_counter:
            print(f"最常见的Topic (前10个):")
            for i, (topic, count) in enumerate(topic_counter.most_common(10), 1):
                print(f"  {i:2d}. {topic}: {count} 个软件")
        else:
            print("  未发现topic信息")

        # ===== 6. 第三方库覆盖度分析 =====
        print(f"\n🔍 第三方库覆盖度分析")
        print("-" * 50)

        # 统计第三方库在各profile中的出现频率
        lib_profile_count = {}

        for ts in self.test_software:
            for suite in ts.test_binary_suites:
                profile = suite.compile_config.profile
                for reuse in suite.library_reuses:
                    if reuse.is_real_used:
                        lib_key = (reuse.library.name, reuse.library.version)
                        if lib_key not in lib_profile_count:
                            lib_profile_count[lib_key] = set()
                        lib_profile_count[lib_key].add(profile)

        # 按覆盖度分类
        coverage_stats = {i: 0 for i in range(1, len(profiles) + 1)}
        for lib_key, lib_profiles in lib_profile_count.items():
            coverage_stats[len(lib_profiles)] += 1

        print(f"第三方库跨平台覆盖度:")
        for profile_count, lib_count in coverage_stats.items():
            if lib_count > 0:
                print(f"  在{profile_count}个平台中使用: {lib_count} 个库")

        # ===== 7. 论文数据摘要 =====
        print(f"\n📄 论文数据摘要")
        print("-" * 50)

        # 计算总的尝试编译数量（假设是从1700个软件中选择的）
        attempted_software = 1700  # 这个数字可以作为参数传入
        success_rate = (full_success + partial_success) / attempted_software * 100 if attempted_software > 0 else 0

        print(f"本数据集基于Conan包管理器构建。Conan作为C/C++生态系统中广泛使用的包管理器，")
        print(f"提供了丰富的第三方库资源和标准化的构建配方。我们从Conan仓库中选取了{attempted_software}个")
        print(f"活跃的开源软件项目，涵盖{len(architectures)}种CPU架构({', '.join(sorted(architectures))})和")
        print(f"{len(compilers)}种主流编译器({', '.join(sorted(compilers))})，构成{total_profiles}种编译配置。")
        print(f"经过自动化编译流程，成功编译{total_software}个软件项目(成功率{success_rate:.1f}%)，")
        print(f"其中{full_success}个项目实现全平台编译成功，{partial_success}个项目部分平台编译成功。")
        print()
        print(f"编译过程共生成{total_binaries:,}个二进制文件，去重后为{len(unique_binaries):,}个唯一文件，")
        print(f"总存储空间{unique_total_size_kb / 1024 / 1024:.1f}GB。数据集涵盖{len(real_dependencies)}个")
        print(f"不同的第三方库依赖关系。基于Conan的构建配方(conanfile)、CMake配置文件、")
        print(f"Makefile以及源码分析，我们采用多源交叉验证的方法，人工标注了")
        print(f"{sum(len(suite.library_reuses) for ts in self.test_software for suite in ts.test_binary_suites):,}条")
        print(f"库复用关系作为Ground Truth，其中{len(real_dependencies_with_tc)}个库具有测试用例覆盖，")
        print(f"为SCA工具的准确性评估提供了可靠的基准数据。")

        print("=" * 80)

    def check_suspicious_shared_files(self):
        """
        检查可疑的跨profile共享文件，特别是跨架构的共享文件
        """
        print("=" * 60)
        print("可疑文件检查报告")
        print("=" * 60)

        # 构建二进制文件到profile的映射
        binary_to_profiles = {}
        binary_details = {}  # 存储文件的详细信息

        for ts in self.test_software:
            for suite in ts.test_binary_suites:
                profile = suite.compile_config.profile
                for binaries in suite.binaries.values():
                    for binary in binaries:
                        binary_key = (binary.name, binary.sha256)

                        if binary_key not in binary_to_profiles:
                            binary_to_profiles[binary_key] = set()
                            binary_details[binary_key] = {
                                'type': binary.type,
                                'size_kb': binary.file_size_kb,
                                'rel_path': binary.rel_path,
                                'tpl_name': binary.tpl_name,
                                'profiles': []
                            }

                        binary_to_profiles[binary_key].add(profile)
                        if profile not in binary_details[binary_key]['profiles']:
                            binary_details[binary_key]['profiles'].append(profile)

        total_profiles = len(set(profile for profiles in binary_to_profiles.values() for profile in profiles))

        # 1. 检查跨所有profile的共享文件（最可疑）
        fully_shared = [(binary_key, profiles) for binary_key, profiles in binary_to_profiles.items()
                        if len(profiles) == total_profiles]

        print(f"\n1. 跨所有架构共享的文件 ({len(fully_shared)} 个) - 极度可疑:")
        print("-" * 50)
        for i, (binary_key, profiles) in enumerate(fully_shared[:30]):  # 显示前30个
            name, sha256 = binary_key
            details = binary_details[binary_key]
            print(f"{i + 1:2d}. {name}")
            print(f"    SHA256: {sha256}")
            print(f"    类型: {details['type']}")
            print(f"    大小: {details['size_kb']} KB")
            print(f"    相对路径: {details['rel_path']}")
            print(f"    模板名: {details['tpl_name']}")
            print(f"    出现在: {sorted(list(profiles))}")
            print()

        if len(fully_shared) > 30:
            print(f"    ... 还有 {len(fully_shared) - 30} 个文件未显示")
            print()

        # 2. 检查跨ARM64和x86_64的共享文件
        cross_arch_shared = []
        for binary_key, profiles in binary_to_profiles.items():
            has_arm = any('arm_64' in profile for profile in profiles)
            has_x86 = any('x86_64' in profile for profile in profiles)
            if has_arm and has_x86:
                cross_arch_shared.append((binary_key, profiles))

        print(f"\n2. 跨ARM64和x86_64架构的共享文件 ({len(cross_arch_shared)} 个) - 高度可疑:")
        print("-" * 50)
        for i, (binary_key, profiles) in enumerate(cross_arch_shared[:20]):  # 显示前20个
            name, sha256 = binary_key
            details = binary_details[binary_key]
            print(f"{i + 1:2d}. {name}")
            print(f"    类型: {details['type']}, 大小: {details['size_kb']} KB")
            print(f"    路径: {details['rel_path']}")
            print(f"    出现在: {sorted(list(profiles))}")
            print()

        # 3. 检查同架构不同编译器的共享文件 (x86_64 clang vs gcc)
        same_arch_shared = []
        for binary_key, profiles in binary_to_profiles.items():
            profiles_list = list(profiles)
            # 检查是否只在x86_64的clang和gcc之间共享
            if (len(profiles_list) == 2 and
                    'x86_64-clang-release-shared' in profiles_list and
                    'x86_64-gcc-release-shared' in profiles_list):
                same_arch_shared.append((binary_key, profiles))

        print(f"\n3. x86_64架构下clang和gcc共享的文件 ({len(same_arch_shared)} 个):")
        print("-" * 50)
        for i, (binary_key, profiles) in enumerate(same_arch_shared):  # 显示全部
            name, sha256 = binary_key
            details = binary_details[binary_key]
            print(f"{i + 1:2d}. {name}")
            print(f"    SHA256: {sha256}")
            print(f"    类型: {details['type']}, 大小: {details['size_kb']} KB")
            print(f"    路径: {details['rel_path']}")
            print(f"    模板名: {details['tpl_name']}")
            print()

        # 3. 按文件扩展名和特征分析可疑度
        print(f"\n3. 按文件特征分析:")
        print("-" * 50)

        suspicious_patterns = {
            'zero_size': [],
            'very_small': [],  # < 1KB
            'text_extensions': [],
            'config_like': [],
            'no_extension': []
        }

        for binary_key, profiles in binary_to_profiles.items():
            if len(profiles) > 1:  # 只看共享文件
                name, sha256 = binary_key
                details = binary_details[binary_key]
                size = details['size_kb']

                if size == 0:
                    suspicious_patterns['zero_size'].append((binary_key, details))
                elif size < 1:
                    suspicious_patterns['very_small'].append((binary_key, details))

                # 检查文件扩展名
                if '.' in name:
                    ext = name.split('.')[-1].lower()
                    if ext in ['txt', 'cfg', 'conf', 'ini', 'xml', 'json', 'yml', 'yaml', 'md', 'rst']:
                        suspicious_patterns['text_extensions'].append((binary_key, details))
                    elif ext in ['config', 'properties', 'settings']:
                        suspicious_patterns['config_like'].append((binary_key, details))
                else:
                    suspicious_patterns['no_extension'].append((binary_key, details))

        for pattern, files in suspicious_patterns.items():
            if files:
                print(f"\n{pattern.replace('_', ' ').title()} ({len(files)} 个):")
                for binary_key, details in files[:10]:  # 只显示前10个
                    name, sha256 = binary_key
                    profiles = binary_to_profiles[binary_key]
                    print(f"  - {name} ({details['size_kb']} KB) -> {len(profiles)} profiles")
                if len(files) > 10:
                    print(f"  ... 还有 {len(files) - 10} 个")

        # 4. 统计总结
        print(f"\n4. 总结:")
        print("-" * 50)
        total_shared = sum(1 for profiles in binary_to_profiles.values() if len(profiles) > 1)
        print(f"总共享文件数: {total_shared}")
        print(f"跨所有架构共享: {len(fully_shared)} ({len(fully_shared) / total_shared * 100:.1f}%)")
        print(f"跨ARM64+x86_64共享: {len(cross_arch_shared)} ({len(cross_arch_shared) / total_shared * 100:.1f}%)")

        # 按大小分布
        size_ranges = {'0KB': 0, '0-1KB': 0, '1-10KB': 0, '10-100KB': 0, '100KB+': 0}
        for binary_key, profiles in binary_to_profiles.items():
            if len(profiles) > 1:
                size = binary_details[binary_key]['size_kb']
                if size == 0:
                    size_ranges['0KB'] += 1
                elif size < 1:
                    size_ranges['0-1KB'] += 1
                elif size < 10:
                    size_ranges['1-10KB'] += 1
                elif size < 100:
                    size_ranges['10-100KB'] += 1
                else:
                    size_ranges['100KB+'] += 1

        print(f"\n共享文件大小分布:")
        for range_name, count in size_ranges.items():
            if count > 0:
                print(f"  {range_name}: {count} 个 ({count / total_shared * 100:.1f}%)")

        print("=" * 60)

# ===== 新增数据结构用于评估 =====

@dataclass
class DetectedLibrary(Serializable):
    """检测到的库（聚合版本）"""
    name: str
    version: str = None
    confidence: float = 0.0
    identify_methods: List[str] = dataclasses.field(default_factory=list)
    source_binaries: List[str] = dataclasses.field(default_factory=list)  # 来源二进制文件名
    is_reasonable: bool = True
    is_redundant: bool = False
    description: str = ""


@dataclass
class ProgramAnalysisResult(Serializable):
    """程序级别的检测结果"""
    program_id: str  # 程序标识: f"{source_lib_name}_{version}_{compile_config}"
    source_library: Library  # 源程序库信息
    compile_config: CompileConfig  # 编译配置
    
    # 检测的二进制文件列表
    analyzed_binaries: List[Binary] = dataclasses.field(default_factory=list)
    
    # 聚合后的检测结果
    detected_libraries: List[DetectedLibrary] = dataclasses.field(default_factory=list)
    
    # 分析数据汇总
    total_analysis_duration: float = 0.0
    total_file_size_kb: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    
    # 原始二进制检测结果（用于消融实验）
    binary_analysis_results: List = dataclasses.field(default_factory=list)  # List[AnalysisResult]


@dataclass 
class ProgramAnalysisResultCheck(Serializable):
    """程序级别的结果验证"""
    program_id: str
    source_library_name: str
    compile_config: str
    
    # Ground Truth (只包含is_real_used=True的库)
    ground_truth_lib_names: List[str] = dataclasses.field(default_factory=list)
    
    # 检测结果
    detected_lib_names: List[str] = dataclasses.field(default_factory=list)
    
    # 评估结果
    has_fn: bool = False  # 是否有漏报
    has_fp: bool = False  # 是否有误报
    tp_lib_names: List[str] = dataclasses.field(default_factory=list)
    fp_lib_names: List[str] = dataclasses.field(default_factory=list) 
    fn_lib_names: List[str] = dataclasses.field(default_factory=list)
    
    # 统计信息
    total_binaries_analyzed: int = 0
    total_file_size_kb: float = 0.0


@dataclass
class ConanBenchmarkMeta(Serializable):
    """Conan Benchmark 元数据"""
    name: str
    version: str
    test_software_num: int
    test_program_suites_num: int
    covered_library_num: int
    total_binaries: int


@dataclass
class ConanEvaluationConfig(Serializable):
    """Conan评估配置"""
    benchmark_file: str
    benchmark_data_dir: str  # conan_libs_builder_output目录
    
    # LLM配置
    llm_provider: str = 'openai'
    llm_model_id: str = 'gpt-4o'
    input_token_price_per_1M: float = 2.0
    output_token_price_per_1M: float = 8.0
    
    # 处理配置
    concurrency: int = 3
    
    # 测试用例筛选
    min_reused_lib_num: int = 3  # 最少包含的真实使用库数量
    target_software_names: List[str] = dataclasses.field(default_factory=list)  # 指定测试的软件名称，空表示全部
    target_compile_configs: List[str] = dataclasses.field(default_factory=list)  # 指定编译配置，空表示全部
    
    # 测试用例切片
    slice_start: int = 0
    slice_end: int = -1


@dataclass
class ConanEvaluationReport(Serializable):
    """Conan评估报告"""
    start_at: str = None
    finished_at: str = None
    evaluation_config: ConanEvaluationConfig = None
    benchmark_meta: ConanBenchmarkMeta = None
    
    # 评估结果
    program_analysis_results: List[ProgramAnalysisResult] = dataclasses.field(default_factory=list)
    program_results_check: List[ProgramAnalysisResultCheck] = dataclasses.field(default_factory=list)
    
    # 研究问题数据（需要导入原有的ResearchQuestionData）
    research_question_data: Dict = None  # ResearchQuestionData类型，这里用Dict避免循环导入
    
    # 软件上下文（如果分析的话）
    software_context: Dict = None  # SoftwareContext类型，这里用Dict避免循环导入
    
    # 原始benchmark数据
    benchmark: Benchmark = None

    def dump(self, file_path):
        """保存报告到文件"""
        data = self.customer_serialize()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # 生成简化版本报告
        simple_report = self.get_simple_report()
        simple_report_save_path = file_path.replace('.json', '_simple.json')
        with open(simple_report_save_path, 'w', encoding='utf-8') as f:
            json.dump(simple_report.customer_serialize(), f, indent=4, ensure_ascii=False)

    @classmethod
    def load_from_file(cls, file_path: str) -> 'ConanEvaluationReport':
        """从文件加载报告"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.init_from_dict(data)

    def get_simple_report(self):
        """生成简化版报告"""
        simple_report = SimpleConanEvaluationReport(
            start_at=self.start_at,
            finished_at=self.finished_at,
            evaluation_config=self.evaluation_config,
            benchmark_meta=self.benchmark_meta,
            research_question_data=self.research_question_data,
            program_results_check=self.program_results_check,
        )
        return simple_report


@dataclass
class SimpleConanEvaluationReport(Serializable):
    """简化版Conan评估报告"""
    start_at: str = None
    finished_at: str = None
    evaluation_config: ConanEvaluationConfig = None
    benchmark_meta: ConanBenchmarkMeta = None
    research_question_data: Dict = None  # ResearchQuestionData类型
    program_results_check: List[ProgramAnalysisResultCheck] = dataclasses.field(default_factory=list)