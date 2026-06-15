#!/usr/bin/env python3
"""
一键部署所有服务脚本

按顺序部署: TAdmin FE -> xuxiaoye FE NX -> LaChaine FE -> LaChaine BE
支持 crontab 定时任务运行
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from typing import List, Tuple, Dict


class Colors:
    """终端颜色支持"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'
    
    @classmethod
    def is_tty(cls) -> bool:
        return sys.stdout.isatty()


class Logger:
    """日志记录器"""
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.log_dir = os.path.dirname(log_file)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 初始化主日志文件
        with open(self.log_file, 'a') as f:
            f.write("=" * 40 + "\n")
            f.write(f"Deploy started at {datetime.now().strftime('%Y%m%d-%H%M%S')}\n")
            f.write("=" * 40 + "\n")
    
    def _format(self, level: str, message: str) -> str:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"[{timestamp}] [{level}] {message}"
    
    def _write(self, level: str, message: str):
        formatted = self._format(level, message)
        with open(self.log_file, 'a') as f:
            f.write(formatted + '\n')
        
        use_color = Colors.is_tty()
        if use_color:
            if level == "SECTION":
                print(f"\n{Colors.BLUE}{'=' * 40}{Colors.NC}")
                print(f"{Colors.BLUE}  {message}{Colors.NC}")
                print(f"{Colors.BLUE}{'=' * 40}{Colors.NC}\n")
            else:
                color = {
                    'INFO': Colors.GREEN,
                    'WARN': Colors.YELLOW,
                    'ERROR': Colors.RED,
                }.get(level, '')
                print(f"{color}{formatted}{Colors.NC}")
        else:
            print(formatted)
    
    def info(self, message: str):
        self._write('INFO', message)
    
    def warn(self, message: str):
        self._write('WARN', message)
    
    def error(self, message: str):
        self._write('ERROR', message)
    
    def section(self, message: str):
        self._write('SECTION', message)
    
    def finish(self, success_count: int, failed_count: int):
        with open(self.log_file, 'a') as f:
            f.write("=" * 40 + "\n")
            f.write(f"Deploy finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Status: SUCCESS={success_count}, FAILED={failed_count}\n")
            f.write("=" * 40 + "\n")


def run_command(cmd: list, cwd: str = None, capture: bool = False) -> tuple:
    """执行命令"""
    try:
        if capture:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, cwd=cwd)
            return result.returncode, '', ''
    except Exception as e:
        return 1, '', str(e)


def deploy_service(name: str, script: str, config: str, logger: Logger, log_dir: str, timestamp: str) -> bool:
    """部署单个服务"""
    log_file = os.path.join(log_dir, f"{name.replace(' ', '-')}-{timestamp}.log")
    service_log = os.path.join(log_dir, f"{name.replace(' ', '-')}-latest.log")
    
    logger.info(f"🔄 Starting {name}...")
    
    # 执行部署并捕获结果
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    config_path = f"./config/{config}"
    
    code, stdout, stderr = run_command(
        ['python3', script_path, '--conf', config_path],
        capture=True
    )
    
    # 写入日志
    with open(log_file, 'w') as f:
        f.write(stdout)
        if stderr:
            f.write(stderr)
    
    # 更新每个服务的最新日志链接
    shutil.copy(log_file, service_log)
    
    if code == 0:
        logger.info(f"✅ {name} deployed successfully")
        print()
        return True
    else:
        logger.error(f"❌ {name} deployment failed")
        print()
        return False


def main():
    # 配置
    project_dir = os.path.dirname(os.path.abspath(__file__))
    branch = "release"
    log_dir = "/tmp/deploy-logs"
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    
    # 日志文件
    main_log = os.path.join(log_dir, f"deploy-all-{timestamp}.log")
    latest_log = os.path.join(log_dir, "deploy-all-latest.log")
    
    logger = Logger(main_log)
    
    # 切换到项目目录
    os.chdir(project_dir)
    
    # 拉取最新脚本
    logger.info("📥 Pulling latest scripts...")
    code, stdout, stderr = run_command(['git', 'pull', 'origin', branch], cwd=project_dir, capture=True)
    for line in stdout.strip().split('\n'):
        if line:
            logger.info(f"  {line}")
    for line in stderr.strip().split('\n'):
        if line:
            logger.info(f"  {line}")
    
    # 显示标题
    logger.section(f"🚀 全量部署开始 - {timestamp}")
    
    # 部署服务列表
    services = [
        ("LaChaine FE", "auto-deploy-fe.py", "lachaine-fe.conf"),
         ("LaChaine Admin FE", "auto-deploy-fe.py", "lachaine-admin-fe.conf"),
        ("LaChaine BE", "auto-deploy-be.py", "lachaine-be.conf"),
    ]
    
    # 部署结果
    results: Dict[str, bool] = {}
    success = 0
    failed = 0
    
    print()
    
    for name, script, config in services:
        if deploy_service(name, script, config, logger, log_dir, timestamp):
            results[name] = True
            success += 1
        else:
            results[name] = False
            failed += 1
    
    # 显示部署结果汇总
    print()
    logger.section("📊 部署结果汇总")
    
    summary = f"""
=========================================
总服务数: {len(services)}
成功:     {success}
失败:     {failed}
=========================================
"""
    print(summary)
    with open(main_log, 'a') as f:
        f.write(summary)
    
    for name, status in results.items():
        status_icon = "✅" if status else "❌"
        line = f"  {status_icon} {name}"
        print(line)
        with open(main_log, 'a') as f:
            f.write(line + '\n')
    
    print()
    print(f"📁 日志目录: {log_dir}")
    print(f"📝 主日志: {main_log}")
    print(f"📝 最新日志: {latest_log}")
    print()
    
    # 复制主日志到最新
    shutil.copy(main_log, latest_log)
    
    # 写入结束标记
    logger.finish(success, failed)
    
    if failed == 0:
        logger.info("🎉 All services deployed successfully!")
        sys.exit(0)
    else:
        logger.warn("⚠️  Some services failed to deploy. Please check the logs.")
        sys.exit(1)


if __name__ == '__main__':
    main()