import os
import sys
import shutil
import subprocess
from pathlib import Path


# ============================================================
# MAA 自动同步 + 本地编译脚本
#
# 核心原则：
# 1. 接受官方 origin/dev-v2 的所有更新
# 2. 保留 no-popup 分支自己的修改
# 3. 编译前将用户 config 完整备份到内存
# 4. 编译完成后恢复用户 config
# 5. 编译失败也尝试恢复用户 config
# 6. 发生 Git 冲突时停止，不自动覆盖
#
# 与原 BAT 的区别：
# - 不再创建磁盘上的 config 备份目录
# - config 直接保存到 Python 内存
# - 恢复时恢复原始字节内容
# ============================================================


# ============================================================
# 0. 基础路径
# ============================================================

PROJECT_DIR = Path(r"C:\Users\MX\Desktop\MAA\MaaAssistantArknights")

# Debug config
CONFIG_DIR = PROJECT_DIR / "build" / "bin" / "Debug" / "config"

# Git 代理
GIT_PROXY = "http://127.0.0.1:20122"

# Visual Studio
VS_ROOT = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community")

# VsDevCmd
VSDEVCMD = VS_ROOT / "Common7" / "Tools" / "VsDevCmd.bat"

# CMake
CMAKE = (
    VS_ROOT
    / "Common7"
    / "IDE"
    / "CommonExtensions"
    / "Microsoft"
    / "CMake"
    / "CMake"
    / "bin"
    / "cmake.exe"
)


# ============================================================
# 全局状态
# ============================================================

# 是否已经进入编译阶段
BUILD_STAGE_STARTED = False

# Git 代理是否已经设置
GIT_PROXY_ENABLED = False

# config 的内存备份
#
# 格式：
# {
#     "相对路径": bytes,
#     ...
# }
#
# 例如：
# {
#     "gui.json": b"...",
#     "tasks\\xxx.json": b"..."
# }
#
CONFIG_BACKUP = None

# config 原目录是否存在
CONFIG_DIR_EXISTED = False


# ============================================================
# 通用函数
# ============================================================


def pause():
    input("\n按 Enter 键退出...")


def run_command(args, cwd=None):
    """
    执行普通命令。
    实时显示程序输出。
    """
    print()

    result = subprocess.run(args, cwd=str(cwd) if cwd else None)

    return result.returncode


def run_git(*args):
    """
    执行 Git 命令。
    """
    return run_command(["git", *args], cwd=PROJECT_DIR)


def git_proxy_cleanup():
    """
    清理当前仓库 Git 代理。
    """
    global GIT_PROXY_ENABLED

    if not GIT_PROXY_ENABLED:
        return

    print()
    print("[*] 清理当前仓库 Git 代理配置，恢复默认...")

    subprocess.run(
        ["git", "config", "--unset", "http.proxy"],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        ["git", "config", "--unset", "https.proxy"],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    GIT_PROXY_ENABLED = False


# ============================================================
# config 内存备份
# ============================================================


def backup_config_to_memory():
    """
    将整个 Debug config 目录完整读取到内存。

    不创建任何备份文件。
    不修改原 config。
    """

    global CONFIG_BACKUP
    global CONFIG_DIR_EXISTED

    print()
    print("=========================================")
    print("      正在备份 MAA 用户配置")
    print("=========================================")
    print()

    print("[*] 原始配置目录：")
    print(CONFIG_DIR)

    if not CONFIG_DIR.exists():
        print()
        print("[警告] 未找到 Debug config 目录：")
        print(CONFIG_DIR)
        print()
        print("[*] 没有可备份的用户配置。")
        print("[*] 将继续执行后续步骤。")

        CONFIG_DIR_EXISTED = False
        CONFIG_BACKUP = {}

        return True

    CONFIG_DIR_EXISTED = True
    CONFIG_BACKUP = {}

    print()
    print("[*] 正在将用户配置读取到内存...")

    try:
        for path in CONFIG_DIR.rglob("*"):
            if path.is_file():
                relative_path = path.relative_to(CONFIG_DIR)

                # 保存原始 bytes
                CONFIG_BACKUP[relative_path] = path.read_bytes()

        print(f"[*] 用户配置备份完成！共保存 {len(CONFIG_BACKUP)} 个文件。")

        # 显示总大小
        total_size = sum(len(data) for data in CONFIG_BACKUP.values())

        print(f"[*] 内存备份大小：{total_size:,} bytes ({total_size / 1024:.2f} KB)")

        return True

    except Exception as e:
        print()
        print("=========================================")
        print("      [错误] 配置备份失败！")
        print("=========================================")
        print()
        print(f"错误：{e}")

        CONFIG_BACKUP = None

        return False


def restore_config_from_memory():
    """
    从内存中的原始备份恢复 config。

    恢复策略：
    1. 删除当前整个 config 目录
    2. 如果原来存在 config，则重新创建
    3. 写回原来的所有文件

    这样可以确保：
    - 编译过程中新增的文件被删除
    - 原来删除的文件被恢复
    - 文件内容恢复为原始 bytes
    """

    global CONFIG_BACKUP
    global CONFIG_DIR_EXISTED

    print()
    print("[*] 正在从内存备份恢复用户配置...")

    if CONFIG_BACKUP is None:
        print("[警告] 内存中没有配置备份！")
        print("[警告] 用户配置没有恢复。")
        return False

    try:
        # 原来不存在 config
        if not CONFIG_DIR_EXISTED:
            if CONFIG_DIR.exists():
                print("[*] 原 config 目录原本不存在。")
                print("[*] 正在删除编译过程中产生的 config...")

                shutil.rmtree(CONFIG_DIR)

            print("[*] 用户配置恢复完成！")
            return True

        # 删除当前 config
        if CONFIG_DIR.exists():
            shutil.rmtree(CONFIG_DIR)

        # 重新创建
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # 写回原始文件
        for relative_path, data in CONFIG_BACKUP.items():
            target = CONFIG_DIR / relative_path

            target.parent.mkdir(parents=True, exist_ok=True)

            target.write_bytes(data)

        print("[*] 用户配置恢复完成！")

        return True

    except Exception as e:
        print()
        print("=========================================")
        print("      [警告] 用户配置恢复失败！")
        print("=========================================")
        print()
        print(f"错误：{e}")

        return False


# ============================================================
# Git 部分
# ============================================================


def merge_upstream():
    """只自动处理已知的指引删除冲突，其余冲突保留现场。"""
    run_git("config", "rerere.enabled", "true")
    if run_git("merge", "origin/dev-v2", "--no-edit") == 0:
        return True
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    import re

    for name in result.stdout.splitlines():
        path = PROJECT_DIR / name
        if name in (
            "src/MaaWpfGui/Models/GuideDemoTaskItem.cs",
            "src/MaaWpfGui/Views/UserControl/GuideUserControl.xaml",
        ):
            # 仅在本分支确实删除该文件时保留删除。
            exists = subprocess.run(
                ["git", "cat-file", "-e", "HEAD:" + name],
                cwd=PROJECT_DIR,
                capture_output=True,
            )
            if exists.returncode != 0:
                run_git("rm", "--", name)
        elif name == "src/maa-cli":
            sha = subprocess.check_output(
                ["git", "rev-parse", "origin/dev-v2:" + name],
                cwd=PROJECT_DIR,
                text=True,
            ).strip()
            run_git("update-index", "--cacheinfo", "160000," + sha + "," + name)
        elif name == "src/MaaWpfGui/ViewModels/UI/SettingsViewModel.cs" or (
            name.startswith("src/MaaWpfGui/Res/Localizations/")
            and name.endswith(".xaml")
        ):
            data = path.read_bytes()
            pattern = (
                rb"^<<<<<<< HEAD\r?\n(.*?)^=======\r?\n(.*?)^>>>>>>> [^\r\n]+\r?\n"
            )
            safe = True

            def resolve(match):
                nonlocal safe
                ours, theirs = match.group(1), match.group(2)
                if ours.strip() or b"Guide" not in theirs:
                    safe = False
                    return match.group(0)
                return ours

            fixed = re.sub(pattern, resolve, data, flags=re.M | re.S)
            if safe and b"<<<<<<<" not in fixed:
                path.write_bytes(fixed)
                run_git("add", "--", name)
    remaining = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=U"], cwd=PROJECT_DIR, text=True
    )
    if remaining.strip():
        print("需要人工检查的新冲突：", remaining)
        return False
    if run_git("diff", "--cached", "--check") != 0:
        return False
    return run_git("commit", "--no-edit") == 0


def git_sync():
    global GIT_PROXY_ENABLED

    # --------------------------------------------------------
    # 0. 开启代理
    # --------------------------------------------------------

    print()
    print("[0/8] 开启 Sing-box 代理 (端口: 20122)...")

    result = run_git("config", "http.proxy", GIT_PROXY)

    if result != 0:
        return False

    result = run_git("config", "https.proxy", GIT_PROXY)

    if result != 0:
        return False

    GIT_PROXY_ENABLED = True

    # --------------------------------------------------------
    # 1. 拉取官方代码
    # --------------------------------------------------------

    print()
    print("[1/8] 正在拉取官方 origin 远程仓库最新变动...")

    if run_git("fetch", "origin") != 0:
        return False

    # --------------------------------------------------------
    # 2. 切换 no-popup
    # --------------------------------------------------------

    print()
    print("[2/8] 切换至免弹窗分支 no-popup...")

    if run_git("checkout", "no-popup") != 0:
        return False

    # --------------------------------------------------------
    # 2.5 检查本地修改
    # --------------------------------------------------------

    print()
    print("[2.5/8] 检查 no-popup 本地修改...")

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )

    if status.returncode != 0:
        return False

    if status.stdout.strip():
        print()
        print("[*] 检测到 no-popup 存在本地修改。")
        print("[*] 正在自动保存本地修改到 Git...")

        if run_git("add", "-u") != 0:
            return False

        if run_git("commit", "-m", "Preserve local no-popup modifications") != 0:
            return False

        print("[*] 本地 no-popup 修改已安全保存。")

    else:
        print("[*] 未发现需要保存的本地修改。")

    # --------------------------------------------------------
    # 3. 合并官方 dev-v2
    # --------------------------------------------------------

    print()
    print("[3/8] 合并官方 dev-v2 代码到 no-popup...")

    if not merge_upstream():
        return False

    # --------------------------------------------------------
    # 4. 推送 no-popup
    # --------------------------------------------------------

    print()
    print("[4/8] 推送更新后的 no-popup 到你的 GitHub (myfork)...")

    if run_git("push", "myfork", "no-popup") != 0:
        return False

    # --------------------------------------------------------
    # 5. 同步 dev-v2
    # --------------------------------------------------------

    print()
    print("[5/8] 同步本地与 GitHub 的 dev-v2 分支...")

    if run_git("checkout", "dev-v2") != 0:
        return False

    print()
    print("[*] 合并官方 origin/dev-v2...")

    if run_git("merge", "origin/dev-v2", "--no-edit") != 0:
        return False

    print()
    print("[*] 推送 dev-v2 到你的 GitHub (myfork)...")

    if run_git("push", "myfork", "dev-v2") != 0:
        return False

    # --------------------------------------------------------
    # 6. 切换回 no-popup
    # --------------------------------------------------------

    print()
    print("[6/8] 切换回工作分支 no-popup...")

    if run_git("checkout", "no-popup") != 0:
        return False

    if run_git("submodule", "update", "--init", "--recursive") != 0:
        return False
    return True


# ============================================================
# Visual Studio / CMake
# ============================================================


def run_vs_cmake(command):
    """
    在同一个 cmd.exe 进程中加载 VsDevCmd，
    然后执行 CMake。
    """

    cmd = f'call "{VSDEVCMD}" && {command}'

    result = subprocess.run(cmd, cwd=str(PROJECT_DIR), shell=True)

    return result.returncode


def build_release():
    global BUILD_STAGE_STARTED

    BUILD_STAGE_STARTED = True

    # --------------------------------------------------------
    # 7. Visual Studio
    # --------------------------------------------------------

    print()
    print("[7/8] 正在调用 Visual Studio 本地编译 Debug...")

    print()
    print("[*] 加载 Visual Studio 2026 Community 编译环境...")

    if not VSDEVCMD.exists():
        print()
        print("[错误] 找不到 VsDevCmd.bat：")
        print(VSDEVCMD)
        return False

    # --------------------------------------------------------
    # 重新配置 CMake
    # --------------------------------------------------------

    print()
    print("[7/8] 正在重新配置 CMake，扫描新版本源码...")

    cmake_configure = f'"{CMAKE}" -S "{PROJECT_DIR}" -B "{PROJECT_DIR / "build"}"'

    if run_vs_cmake(cmake_configure) != 0:
        return False

    # --------------------------------------------------------
    # 编译 Debug
    # --------------------------------------------------------

    print()
    print("[8/8] 正在编译 Debug...")

    cmake_build = (
        f'"{CMAKE}" --build "{PROJECT_DIR / "build"}" --config Debug --parallel'
    )

    if run_vs_cmake(cmake_build) != 0:
        return False

    return True


# ============================================================
# 主程序
# ============================================================


def main():
    # --------------------------------------------------------
    # 检查项目目录
    # --------------------------------------------------------

    if not PROJECT_DIR.exists():
        print()
        print("[错误] 找不到项目目录：")
        print(PROJECT_DIR)
        pause()
        return 1

    # --------------------------------------------------------
    # 1. 内存备份 config
    # --------------------------------------------------------

    if not backup_config_to_memory():
        pause()
        return 1

    # --------------------------------------------------------
    # 2. Git 同步
    # --------------------------------------------------------

    print()
    print("=========================================")
    print("      开始自动同步 MAA 官方最新代码")
    print("=========================================")

    try:
        if not git_sync():
            git_proxy_cleanup()

            print()
            print("=========================================")
            print("       [错误] Git 操作失败！")
            print()
            print("       Git 冲突或其他 Git 错误")
            print("       已停止，不自动覆盖。")
            print()
            print("       用户 config 仍保持原状态。")
            print("=========================================")
            print()

            pause()
            return 1

        # ----------------------------------------------------
        # Git 成功，清理代理
        # ----------------------------------------------------

        git_proxy_cleanup()

        # ----------------------------------------------------
        # 3. 编译
        # ----------------------------------------------------

        build_success = False

        try:
            build_success = build_release()

        finally:
            # ------------------------------------------------
            # 只要进入过编译阶段，就一定尝试恢复 config
            # ------------------------------------------------

            if BUILD_STAGE_STARTED:
                print()

                if build_success:
                    print("=========================================")
                    print("       Debug 编译成功！")
                    print("=========================================")

                else:
                    print("=========================================")
                    print("       [错误] 本地编译失败！")
                    print("=========================================")

                restore_config_from_memory()

        # ----------------------------------------------------
        # 编译结果
        # ----------------------------------------------------

        if not build_success:
            git_proxy_cleanup()

            print()
            print("=========================================")
            print("       编译失败，但原用户配置")
            print("       已尝试从内存备份恢复。")
            print("=========================================")
            print()

            pause()
            return 1

        # ----------------------------------------------------
        # 全部成功
        # ----------------------------------------------------

        print()
        print("=========================================")
        print("       更新并编译完成！")
        print()
        print("       官方 dev-v2 已同步")
        print("       no-popup 修改已保留")
        print("       Debug 已重新编译")
        print("       用户 config 已从内存恢复")
        print("=========================================")
        print()

        pause()

        return 0

    except KeyboardInterrupt:
        print()
        print()
        print("[警告] 用户中断了脚本。")

        git_proxy_cleanup()

        # 如果已经进入编译阶段，中断时也恢复 config
        if BUILD_STAGE_STARTED:
            print()
            print("[*] 正在尝试恢复用户 config...")
            restore_config_from_memory()

        pause()
        return 1

    except Exception as e:
        print()
        print("=========================================")
        print("       [错误] 脚本发生未处理异常！")
        print("=========================================")
        print()
        print(e)

        git_proxy_cleanup()

        if BUILD_STAGE_STARTED:
            print()
            print("[*] 正在尝试恢复用户 config...")
            restore_config_from_memory()

        pause()
        return 1


if __name__ == "__main__":
    sys.exit(main())
