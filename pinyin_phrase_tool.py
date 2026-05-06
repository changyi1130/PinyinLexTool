"""
微软拼音自定义短语管理工具
Author: CodeGeeX
功能：导入、导出、备份、管理微软拼音输入法的自定义短语
"""
import os
import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional

# 常量定义
LEX_FILE = os.path.join(os.getenv('APPDATA'), r'Microsoft\InputMethod\Chs\ChsPinyinEUDPv1.lex')
PADDED_ENCODING = 'utf-16le'
HEADER_LEN = 16 + 4
PHRASE_64PCNT_POS = HEADER_LEN
TOTAL_BYTES_POS = HEADER_LEN + 4
PHRASE_CNT_POS = HEADER_LEN + 8
PHRASE_SEPARATOR_BYTES = b'\x00\x00'
PHRASE_SEPARATOR_SIZE = len(PHRASE_SEPARATOR_BYTES)
PHRASE_LEN_FIRST_POS = PHRASE_CNT_POS + 40

# 文件头常量
HEADER_BYTES = bytes('mschxudp', encoding='ascii')
HEADER_BYTES = HEADER_BYTES + bytes('\x02\x60\x01\x00', PADDED_ENCODING)
phrase_fixed_last_bytes = b'\xA5\x2C'

# 验证规则
PINYIN_MAX_LEN = 32
PHRASE_MAX_LEN = 64
PINYIN_PATTERN = re.compile(r'^[a-z]{1,' + str(PINYIN_MAX_LEN) + r'}$')


def read_bytes(position, length=1):
    """从指定位置读取字节"""
    with open(LEX_FILE, 'rb+') as file:
        file.seek(position)
        return file.read(length)


def replace_bytes(position, value):
    """替换指定位置的字节"""
    with open(LEX_FILE, 'rb+') as file:
        file.seek(position)
        data = file.read()
        file.seek(position)
        file.write(value + data[len(value):])


def bytes2int(data):
    """将字节转换为整数"""
    return int.from_bytes(data, byteorder='little')


def int2bytes(data, length=1):
    """将整数转换为字节"""
    return int.to_bytes(data, length=length, byteorder='little')


def padded_bytes(s):
    """将字符串转换为填充后的字节"""

    def padded_byte(c):
        b = bytes(c, PADDED_ENCODING)
        return b + b'\x00' if len(b) == 1 else b

    return b''.join([padded_byte(c) for c in s])


def get_phrase_header(header_pinyin_len, index):
    """
    生成短语头部（固定 16 字节）
    结构: magic(4) + pinyin_len(2) + index(4) + flags(4) + suffix(2)
    """
    return (b'\x10\x00\x10\x00' + int2bytes(header_pinyin_len, 2)
            + int2bytes(index, 4) + b'\x06\x00\x00\x00'
            + phrase_fixed_last_bytes)


def backup_lex_file():
    """备份原始词库文件"""
    if not os.path.exists(LEX_FILE):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{LEX_FILE}.{timestamp}.bak.lex"

    try:
        shutil.copy2(LEX_FILE, backup_path)
        print(f"已备份原词库文件至: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"备份文件失败: {e}")
        return None


def validate_pinyin(pinyin: str) -> bool:
    """验证拼音是否合法"""
    if not pinyin:
        return False
    # 检查是否以u/v开头
    if pinyin.startswith(('u', 'v')):
        return False
    # 检查长度和格式
    return bool(PINYIN_PATTERN.match(pinyin))


def validate_phrase(phrase: str) -> bool:
    """验证短语是否合法"""
    if not phrase:
        return False
    return len(phrase) <= PHRASE_MAX_LEN


def parse_line(line: str) -> Optional[Tuple[str, int, str]]:
    """解析一行短语文本，返回(拼音, 位置, 短语)或None"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    parts = line.split()
    if len(parts) < 2:
        print(f"警告: 跳过格式错误的行: '{line}'")
        return None

    # 尝试解析位置
    try:
        # 检查第二部分是否为数字
        if parts[1].isdigit() and len(parts) >= 3:
            pinyin = parts[0]
            index = int(parts[1])
            phrase = ' '.join(parts[2:])
        else:
            # 没有位置信息
            pinyin = parts[0]
            index = -1  # 表示需要自动分配
            phrase = ' '.join(parts[1:])
    except Exception as e:
        print(f"警告: 解析行失败 '{line}': {e}")
        return None

    # 验证拼音和短语
    if not validate_pinyin(pinyin):
        print(f"警告: 拼音不合法 '{pinyin}' (行: '{line}')")
        return None

    if not validate_phrase(phrase):
        print(f"警告: 短语过长或为空 (行: '{line}')")
        return None

    return (pinyin, index, phrase)


def read_existing_phrases() -> List[Tuple[bool, bytes, bytes, bytes]]:
    """读取现有短语，返回列表[(is_new, pinyin_bytes, header, phrase_bytes)]
    参考 srf.py 的简洁实现，跳过无法解析的短语。"""
    if not os.path.exists(LEX_FILE):
        return []

    phrase_list = []
    last_phrase_pos = 0
    global phrase_fixed_last_bytes

    try:
        phrase_cnt = bytes2int(read_bytes(PHRASE_CNT_POS, 4))
        if phrase_cnt == 0:
            return []

        phrase_block_first_pos = PHRASE_LEN_FIRST_POS + 4 * (phrase_cnt - 1)
        file_size = os.path.getsize(LEX_FILE)

        for i in range(phrase_cnt):
            if i == phrase_cnt - 1:
                phrase_block_pos = file_size
                phrase_block_len = phrase_block_pos - last_phrase_pos
            else:
                phrase_block_pos = bytes2int(
                    read_bytes(PHRASE_LEN_FIRST_POS + i * 4, 4))
                phrase_block_len = phrase_block_pos - last_phrase_pos

            phrase_block_bytes = read_bytes(
                phrase_block_first_pos + last_phrase_pos, phrase_block_len)
            last_phrase_pos = phrase_block_pos

            try:
                if len(phrase_block_bytes) < 18:
                    continue

                match = re.match(
                    (b'(.+)' + PHRASE_SEPARATOR_BYTES) * 2,
                    phrase_block_bytes[16:])
                if match is None:
                    continue
                pinyin_bytes, phrase_bytes = match.groups()
                phrase_fixed_last_bytes = phrase_block_bytes[14:16]

                if phrase_block_bytes[9:10] == b'\x00':
                    phrase_list.append((False, pinyin_bytes,
                                        phrase_block_bytes[:16], phrase_bytes))
            except Exception:
                continue
    except Exception:
        pass

    return phrase_list


def get_max_index_for_pinyin(phrase_list: List[Tuple[bool, bytes, bytes, bytes]],
                             pinyin_bytes: bytes) -> int:
    """获取指定拼音的最大位置值"""
    max_index = 0
    for _, pb, header, _ in phrase_list:
        if pb == pinyin_bytes:
            # 从header中提取index
            index = bytes2int(header[6:10])
            if index > max_index:
                max_index = index
    return max_index


def import_phrases(file_path: str, force: bool = False, dry_run: bool = False) -> Dict[str, int]:
    """
    导入短语文件
    返回统计信息字典
    """
    stats = {
        'total_lines': 0,
        'imported': 0,
        'skipped': 0,
        'overwritten': 0,
        'errors': 0
    }

    if not os.path.exists(file_path):
        print(f"错误: 文件不存在 '{file_path}'")
        return stats

    # 读取现有短语
    phrase_list = read_existing_phrases()

    # 构建现有短语的字典，便于查找 - 基于拼音+短语组合（忽略索引）
    existing_phrases = {}
    for _, pinyin_bytes, header, phrase_bytes in phrase_list:
        index = bytes2int(header[6:10])
        key = (pinyin_bytes, phrase_bytes)  # 使用拼音+短语作为唯一标识
        existing_phrases[key] = (False, pinyin_bytes, header, phrase_bytes)

    # 读取并解析导入文件
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    stats['total_lines'] = len(lines)

    # 处理每一行
    for line in lines:
        parsed = parse_line(line)
        if not parsed:
            stats['skipped'] += 1
            continue

        pinyin, index, phrase = parsed
        pinyin_bytes = padded_bytes(pinyin)
        phrase_bytes = padded_bytes(phrase)

        # 如果没有指定位置，自动分配
        if index == -1:
            max_index = get_max_index_for_pinyin(phrase_list, pinyin_bytes)
            index = max_index + 1000000
            print(f"自动分配位置: {pinyin} -> {index}")

        # 检查是否已存在 - 基于拼音+短语组合（忽略索引）
        key = (pinyin_bytes, phrase_bytes)
        if key in existing_phrases:
            # 相同的拼音和短语已存在，直接跳过，不询问
            print(f"跳过重复: '{pinyin} {phrase}'（已存在）")
            stats['skipped'] += 1
            continue

        # 添加新短语
        header = get_phrase_header(16 + len(pinyin_bytes) + PHRASE_SEPARATOR_SIZE, index)
        existing_phrases[key] = (True, pinyin_bytes, header, phrase_bytes)
        phrase_list.append((True, pinyin_bytes, header, phrase_bytes))
        stats['imported'] += 1

    # 排序短语列表
    phrase_list.sort(key=lambda x: x[1])

    if dry_run:
        print("\n=== 干运行模式 - 不会实际修改文件 ===")
        print(f"总行数: {stats['total_lines']}")
        print(f"成功导入: {stats['imported']}")
        print(f"跳过: {stats['skipped']}")
        print(f"覆盖: {stats['overwritten']}")
        print(f"错误: {stats['errors']}")
        print(f"最终短语总数: {len(phrase_list)}")
        return stats

    # 备份原文件
    backup_path = backup_lex_file()

    # 写入文件
    write_phrases(phrase_list)

    print("\n导入完成:")
    print(f"总行数: {stats['total_lines']}")
    print(f"成功导入: {stats['imported']}")
    print(f"跳过: {stats['skipped']}")
    print(f"覆盖: {stats['overwritten']}")
    print(f"错误: {stats['errors']}")
    print(f"最终短语总数: {len(phrase_list)}")
    if backup_path:
        print(f"备份文件: {backup_path}")

    print("\n提示: 修改完成后，请重新切换输入法（中/英模式切换一次）或重新登录 Windows 才能看到效果。")

    return stats


def export_phrases(file_path: str) -> bool:
    """导出所有短语到文件"""
    phrase_list = read_existing_phrases()

    if not phrase_list:
        print("没有可导出的短语")
        return False

    try:
        exported_count = 0
        with open(file_path, 'w', encoding='utf-8') as f:
            for _, pinyin_bytes, header, phrase_bytes in phrase_list:
                try:
                    index = bytes2int(header[6:10])
                    pinyin = pinyin_bytes.decode(PADDED_ENCODING).rstrip('\x00')
                    phrase = phrase_bytes.decode(PADDED_ENCODING).rstrip('\x00')
                    f.write(f"{pinyin} {index} {phrase}\n")
                    exported_count += 1
                except Exception as e:
                    print(f"警告: 跳过无法导出的短语: {e}")
                    continue

        print(f"成功导出 {exported_count} 条短语到: {file_path}")
        return True
    except Exception as e:
        print(f"导出失败: {e}")
        return False


def write_phrases(phrase_list: List[Tuple[bool, bytes, bytes, bytes]]):
    """写入短语到词库文件"""
    global phrase_fixed_last_bytes

    # 确保目录存在
    os.makedirs(os.path.dirname(LEX_FILE), exist_ok=True)

    # 初始化文件（如果不存在）
    if not os.path.exists(LEX_FILE):
        with open(LEX_FILE, 'wb') as f:
            f.write(HEADER_BYTES)
            f.write((b'\x40' + b'\x00' * 3) * 3)
            f.write(b'\x00' * 4)
            f.write(b'\x38\xd2\xa3\x65')
            f.write(b'\x00' * 32)

    # 计算所有短语的数据长度
    phrase_data_list = []
    for _, pinyin_bytes, header, phrase_bytes in phrase_list:
        data_bytes = PHRASE_SEPARATOR_BYTES.join([pinyin_bytes, phrase_bytes, b''])
        phrase_data_list.append((header, data_bytes))

    # 写入短语
    tolast_phrase_pos = 0
    # 初始总大小 = 文件头部分 + 位置偏移数组
    phrase_cnt = len(phrase_data_list)
    total_size = PHRASE_LEN_FIRST_POS + 4 * (phrase_cnt - 1)

    with open(LEX_FILE, 'rb+') as file:
        file.seek(PHRASE_LEN_FIRST_POS)
        file.truncate()

        # 写入短语位置偏移
        for i in range(phrase_cnt - 1):
            header, data_bytes = phrase_data_list[i]
            phrase_len = len(header) + len(data_bytes)
            tolast_phrase_pos += phrase_len
            file.write(int2bytes(tolast_phrase_pos, length=4))

        # 写入短语数据
        for header, data_bytes in phrase_data_list:
            file.write(header)
            file.write(data_bytes)
            total_size += len(header) + len(data_bytes)

    # 更新文件头
    replace_bytes(PHRASE_64PCNT_POS, int2bytes(64 + phrase_cnt * 4, length=4))
    replace_bytes(PHRASE_CNT_POS, int2bytes(phrase_cnt, length=4))
    replace_bytes(TOTAL_BYTES_POS, int2bytes(total_size, length=4))


def list_phrases():
    """列出所有短语"""
    phrase_list = read_existing_phrases()

    if not phrase_list:
        print("没有自定义短语")
        return

    print(f"共 {len(phrase_list)} 条自定义短语:\n")

    for _, pinyin_bytes, header, phrase_bytes in phrase_list:
        index = bytes2int(header[6:10])
        pinyin = pinyin_bytes.decode(PADDED_ENCODING).rstrip('\x00')
        phrase = phrase_bytes.decode(PADDED_ENCODING).rstrip('\x00')
        print(f"{pinyin:15} {index:8} {phrase}")


def main():
    parser = argparse.ArgumentParser(description='微软拼音自定义短语管理工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # 导入命令
    import_parser = subparsers.add_parser('import', help='导入短语文件')
    import_parser.add_argument('file', help='要导入的短语文件路径')
    import_parser.add_argument('--force', action='store_true', help='强制覆盖，不询问')
    import_parser.add_argument('--dry-run', action='store_true', help='干运行模式，不实际修改文件')

    # 导出命令
    export_parser = subparsers.add_parser('export', help='导出短语到文件')
    export_parser.add_argument('file', help='导出的短语文件路径')

    # 列出命令
    subparsers.add_parser('list', help='列出所有短语')

    args = parser.parse_args()

    if args.command == 'import':
        import_phrases(args.file, args.force, args.dry_run)
    elif args.command == 'export':
        export_phrases(args.file)
    elif args.command == 'list':
        list_phrases()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
