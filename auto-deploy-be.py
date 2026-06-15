#!/usr/bin/env python3
"""
后端 Java 项目自动部署脚本

用法: python3 auto-deploy-be.py --conf <config-file> [--skip]
"""

import argparse
import os
import sys
import subprocess
import shutil
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


class Colors:
    """终端颜色支持"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'
    
    @classmethod
    def is_tty(cls) -> bool:
        return sys.stdout.isatty()


def parse_config(config_file: str) -> Dict[str, Any]:
    """解析配置文件"""
    config = {}
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue
            # 解析 KEY="value" 或 KEY=value 格式
            match = re.match(r'^(\w+)=["\']?([^"\']*)["\']?$', line)
            if match:
                key, value = match.groups()
                config[key] = value
    return config


class Logger:
    """日志记录器"""
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.log_dir = os.path.dirname(log_file)
        os.makedirs(self.log_dir, exist_ok=True)
        
    def _format(self, level: str, message: str) -> str:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"[{timestamp}] [{level}] {message}"
    
    def _write(self, level: str, message: str):
        formatted = self._format(level, message)
        with open(self.log_file, 'a') as f:
            f.write(formatted + '\n')
        
        use_color = Colors.is_tty()
        if use_color:
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


def run_command(cmd: list, cwd: Optional[str] = None, capture: bool = False) -> tuple:
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


def main():
    parser = argparse.ArgumentParser(description='后端 Java 项目自动部署脚本')
    parser.add_argument('--conf', required=True, help='配置文件路径')
    parser.add_argument('--skip', action='store_true', help='跳过 Git commit 比较，直接编译')
    args = parser.parse_args()
    
    conf_file = args.conf
    skip_git_check = args.skip
    
    # 验证配置文件
    if not os.path.exists(conf_file):
        print(f"❌ 配置文件不存在: {conf_file}")
        sys.exit(1)
    
    # 加载配置
    config = parse_config(conf_file)
    
    # 验证必需变量
    required_vars = ['PROJECT_DIR', 'BRANCH', 'JAR_NAME', 'DEPLOY_DIR', 'STOP_SCRIPT', 'START_SCRIPT']
    for var in required_vars:
        if var not in config or not config[var]:
            print(f"❌ 配置文件缺少必需变量: {var}")
            sys.exit(1)
    
    # 设置变量
    project_dir = config['PROJECT_DIR']
    branch = config['BRANCH']
    jar_name = config['JAR_NAME']
    deploy_dir = config['DEPLOY_DIR']
    stop_script = config['STOP_SCRIPT']
    start_script = config['START_SCRIPT']
    
    skip_tests = config.get('SKIP_TESTS', 'true') == 'true'
    mvn_path = config.get('MVN_PATH', 'mvn')
    remote_enabled = config.get('REMOTE_ENABLED', 'false') == 'true'
    log_dir = config.get('LOG_DIR', '/tmp/deploy-logs')
    
    config_name = os.path.splitext(os.path.basename(conf_file))[0]
    log_file = config.get('LOG_FILE', f"{log_dir}/be-{config_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log")
    
    # 远程服务器配置
    remote_host = config.get('REMOTE_HOST', 'www.xuxiaoye.com')
    remote_user = config.get('REMOTE_USER', 'root')
    remote_deploy_dir = config.get('REMOTE_DEPLOY_DIR', '/project')
    
    logger = Logger(log_file)
    
    # 验证目录和命令
    if not os.path.isdir(project_dir):
        logger.error(f"项目目录不存在: {project_dir}")
        sys.exit(1)
    
    if not os.path.isdir(deploy_dir):
        logger.error(f"部署目录不存在: {deploy_dir}")
        sys.exit(1)
    
    # 检查 mvn 命令
    code, _, _ = run_command([mvn_path, '--version'], capture=True)
    if code != 0:
        logger.error(f"mvn 命令不可用: {mvn_path}")
        sys.exit(1)
    
    # 显示项目信息
    print("=" * 40)
    print(f"🚀 开始部署: {config.get('PROJECT_NAME', 'Unknown Project')}")
    print("=" * 40)
    print(f"配置文件: {conf_file}")
    print(f"项目目录: {project_dir}")
    print(f"分支: {branch}")
    print(f"JAR 文件: {jar_name}")
    print(f"部署目录: {deploy_dir}")
    print(f"停止脚本: {stop_script}")
    print(f"启动脚本: {start_script}")
    print(f"跳过测试: {skip_tests}")
    print(f"Maven 路径: {mvn_path}")
    print(f"远程部署: {remote_enabled}")
    if remote_enabled:
        print(f"远程主机: {remote_user}@{remote_host}:{remote_deploy_dir}")
    if skip_git_check:
        print("强制编译: 启用 (跳过 Git 检查)")
    print(f"日志文件: {log_file}")
    print("=" * 40)
    
    # Git 检查
    if skip_git_check:
        local = "skip"
        remote = "force"
    else:
        run_command(['git', 'fetch', 'origin', branch], cwd=project_dir)
        code, local, _ = run_command(['git', 'rev-parse', 'HEAD'], cwd=project_dir, capture=True)
        code, remote, _ = run_command(['git', 'rev-parse', f'origin/{branch}'], cwd=project_dir, capture=True)
        local = local.strip()
        remote = remote.strip()
    
    deploy_success = False
    
    # 比较和部署
    if skip_git_check or local != remote:
        if skip_git_check:
            logger.info("⏭️  Skipping Git check, force build enabled")
            run_command(['git', 'fetch', 'origin', branch], cwd=project_dir)
        else:
            logger.info(f"🔔 New commit detected on {branch}")
        
        # 拉取代码
        run_command(['git', 'reset', '--hard', f'origin/{branch}'], cwd=project_dir)
        run_command(['git', 'clean', '-fd'], cwd=project_dir)
        logger.info("✅ Code updated")
        
        # 构建
        mvn_cmd = [mvn_path, 'clean', 'install']
        if skip_tests:
            mvn_cmd.append('-Dmaven.test.skip=true')
        
        logger.info(f"🔨 Building with: {' '.join(mvn_cmd)}")
        code, stdout, stderr = run_command(mvn_cmd, cwd=project_dir)
        with open(log_file, 'a') as f:
            f.write(stdout)
            if stderr:
                f.write(stderr)
        
        if code != 0:
            logger.error("❌ Build failed")
            sys.exit(1)
        logger.info("✅ Build completed")
        
        # 检查 JAR 文件
        target_jar = os.path.join(project_dir, 'target', jar_name)
        if not os.path.exists(target_jar):
            logger.error(f"❌ JAR 文件不存在: {target_jar}")
            sys.exit(1)
        
        # 部署 JAR 文件
        logger.info(f"📦 Copying JAR to: {deploy_dir}/{jar_name}")
        shutil.copy(target_jar, os.path.join(deploy_dir, jar_name))
        
        # 进入部署目录
        os.chdir(deploy_dir)
        
        # 停止旧服务
        stop_script_path = os.path.join(deploy_dir, stop_script)
        if os.path.exists(stop_script_path):
            logger.info(f"⛔ Stopping service: {stop_script}")
            os.chmod(stop_script_path, 0o755)
            run_command(['sh', stop_script], cwd=deploy_dir)
            time.sleep(2)
        else:
            logger.warn(f"⚠️  Stop script not found: {stop_script}")
        
        # 启动新服务
        start_script_path = os.path.join(deploy_dir, start_script)
        if not os.path.exists(start_script_path):
            logger.error(f"❌ Start script not found: {start_script}")
            sys.exit(1)
        
        logger.info(f"🚀 Starting service: {start_script}")
        os.chmod(start_script_path, 0o755)
        
        # 使用 nohup 后台启动
        with open('auto.log', 'a') as log_f:
            subprocess.Popen(
                ['sh', start_script],
                cwd=deploy_dir,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        
        # 验证服务启动
        time.sleep(3)
        code, stdout, _ = run_command(['pgrep', '-f', jar_name], capture=True)
        if code == 0:
            logger.info("✅ Service started successfully")
            deploy_success = True
        else:
            logger.warn(f"⚠️  Service may not have started. Check logs: {deploy_dir}/auto.log")
        
        # 远程部署
        if remote_enabled:
            logger.info(f"☁️  Uploading to remote server: {remote_user}@{remote_host}")
            
            remote_target = f"{remote_user}@{remote_host}:{remote_deploy_dir}/target/"
            code, _, _ = run_command(['scp', f"{deploy_dir}/{jar_name}", remote_target])
            
            if code == 0:
                logger.info("✅ JAR uploaded to remote server")
                
                # 远程停止服务
                logger.info("⛔ Stopping remote service")
                ssh_stop = f"cd {remote_deploy_dir} && sh {stop_script}"
                run_command(['ssh', f"{remote_user}@{remote_host}", ssh_stop])
                time.sleep(2)
                
                # 远程启动服务
                logger.info("🚀 Starting remote service")
                ssh_start = f"cd {remote_deploy_dir} && sh {start_script}"
                run_command(['ssh', f"{remote_user}@{remote_host}", ssh_start])
                
                logger.info("✅ Remote server updated")
            else:
                logger.error("❌ Failed to upload to remote server")
        
        logger.info("🎉 Deploy finished")
    else:
        # 没变化，静默退出
        logger.info(f"ℹ️  no change on {branch} (use --skip to force build)")
    
    sys.exit(0)


if __name__ == '__main__':
    main()