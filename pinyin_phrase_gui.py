import os
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext
import subprocess
import threading

# 导入原工具的核心函数
from pinyin_phrase_tool import (
    import_phrases, export_phrases, list_phrases, backup_lex_file,
    LEX_FILE, read_existing_phrases
)

# 修改 list_phrases 使其返回字符串而非直接打印
def get_phrases_text():
    """获取当前短语的文本表示"""
    phrase_list = read_existing_phrases()
    if not phrase_list:
        return "没有自定义短语"
    lines = [f"共 {len(phrase_list)} 条自定义短语：\n"]
    for _, pinyin_bytes, header, phrase_bytes in phrase_list:
        try:
            index = int.from_bytes(header[6:10], byteorder='little')
            pinyin = pinyin_bytes.decode('utf-16le').rstrip('\x00')
            phrase = phrase_bytes.decode('utf-16le').rstrip('\x00')
            lines.append(f"{pinyin:6} {index:8} {phrase}")
        except Exception:
            continue
    return '\n'.join(lines)


def open_phrases_txt():
    """用默认应用打开或创建 phrases.txt"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    txt_path = os.path.join(base_dir, "phrases.txt")
    if not os.path.exists(txt_path):
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write("# 自定义短语文件\n# 格式：拼音 序号 短语\n")
        except Exception as e:
            messagebox.showerror("错误", f"无法创建 phrases.txt：{e}")
            return
    try:
        if sys.platform == "win32":
            os.startfile(txt_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", txt_path])
        else:
            subprocess.run(["xdg-open", txt_path])
    except Exception as e:
        messagebox.showerror("错误", f"无法打开文件：{e}")


def show_about():
    messagebox.showinfo("关于", "拼音短语管理工具\n版本：0.0.1\n\n管理微软拼音自定义短语")


class PhraseToolGUI:
    def __init__(self, root):
        self.root = root
        root.title("拼音短语工具")
        root.geometry("550x400")
        root.resizable(False, False)

        # 标题
        tk.Label(root, text="微软拼音自定义短语管理工具", font=("微软雅黑", 14, "bold")).pack(pady=10)

        # 按钮框架（第一行）
        btn_frame1 = tk.Frame(root)
        btn_frame1.pack(pady=5)
        tk.Button(btn_frame1, text="导入短语", command=self.import_action, width=15).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame1, text="导出短语", command=self.export_action, width=15).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame1, text="列出短语", command=self.list_action, width=15).grid(row=0, column=2, padx=5)

        # 按钮框架（第二行）
        btn_frame2 = tk.Frame(root)
        btn_frame2.pack(pady=5)
        tk.Button(btn_frame2, text="备份词库", command=self.backup_action, width=15).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame2, text="编辑 phrases.txt", command=open_phrases_txt, width=15).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame2, text="关于", command=show_about, width=15).grid(row=0, column=2, padx=5)

        # 日志/结果显示区域
        self.result_text = scrolledtext.ScrolledText(root, height=12, font=("Consolas", 9))
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 底部标签
        self.status_label = tk.Label(root, text="就绪", anchor=tk.W, fg="gray")
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        # 底部可编辑标签（用户自定义文本）
        self.user_label = tk.Label(root, text="❤小知安~❤", fg="gray", anchor=tk.E)
        self.user_label.pack(side=tk.RIGHT, padx=10, pady=5)

        # 初始显示短语列表
        self.update_phrase_display()

    def update_phrase_display(self):
        """刷新短语显示区域"""
        text = get_phrases_text()
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, text)

    def import_action(self):
        # 获取 exe 所在目录（或程序所在目录）
        if getattr(sys, 'frozen', False):
            # 打包后的 exe 路径
            exe_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境下的程序目录
            exe_dir = os.path.dirname(os.path.abspath(__file__))
        
        file_path = os.path.join(exe_dir, "phrases.txt")
        
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"找不到文件：{file_path}")
            return
        try:
            # 在新线程中执行，避免阻塞 GUI
            threading.Thread(target=self._do_import, args=(file_path,), daemon=True).start()
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _do_import(self, file_path):
        try:
            result = import_phrases(file_path, force=False, dry_run=False)
            self.root.after(0, self._import_done, result)
        except Exception as e:
            self.root.after(0, messagebox.showerror, "导入失败", str(e))

    def _import_done(self, result):
        self.status_label.config(text=f"导入完成：{result['imported']} 成功，{result['skipped']} 跳过")
        self.update_phrase_display()
        messagebox.showinfo("导入完成", f"导入完成！\n成功：{result['imported']}\n跳过：{result['skipped']}")

    def export_action(self):
        # 获取 exe 所在目录（或程序所在目录）
        if getattr(sys, 'frozen', False):
            # 打包后的 exe 路径
            exe_dir = os.path.dirname(sys.executable)
        else:
            # 开发环境下的程序目录
            exe_dir = os.path.dirname(os.path.abspath(__file__))
        
        file_path = os.path.join(exe_dir, "backup.txt")
        
        try:
            success = export_phrases(file_path)
            if success:
                self.status_label.config(text=f"短语已导出到 {os.path.basename(file_path)}")
                messagebox.showinfo("导出成功", f"短语已导出到：{file_path}")
            else:
                messagebox.showerror("导出失败", "没有可导出的短语或写入失败")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def list_action(self):
        self.update_phrase_display()
        self.status_label.config(text="已刷新短语列表")

    def backup_action(self):
        backup_path = backup_lex_file()
        if backup_path:
            self.status_label.config(text=f"备份成功：{os.path.basename(backup_path)}")
            messagebox.showinfo("备份成功", f"词库已备份至：\n{backup_path}")
        else:
            messagebox.showerror("备份失败", "找不到词库文件，请确认您已添加过自定义短语")


def main():
    root = tk.Tk()
    PhraseToolGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()