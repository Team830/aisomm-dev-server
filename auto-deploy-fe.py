#!/usr/bin/env python3
"""
前端项目自动部署脚本

用法: python3 auto-deploy-fe.py --conf <config-file> [--skip]
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


def nginx_deploy(logger: Logger, deploy_dir: str, deploy_dir_name: str, 
                 web_name: str, resource_dir: Optional[str] = None):
    """执行 nginx 部署（切换 dist 目录并重启 nginx）"""
    deploy_target = os.path.join(deploy_dir, deploy_dir_name)
    web_dir = os.path.join(deploy_dir, web_name)
    
    logger.info(f"🚀 Starting {web_name} nginx deployment")
    
    # 检查源目录是否存在
    if not os.path.isdir(deploy_target):
        logger.error(f"Source directory not found: {deploy_target}")
        return False
    
    # 如果 web_name != deploy_dir_name，需要重命名
    if web_name != deploy_dir_name:
        # 备份旧的部署
        if os.path.isdir(web_dir):
            backup_dir = f"{deploy_dir}/{web_name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            logger.info(f"💾 Backing up old deployment to: {backup_dir}")
            shutil.move(web_dir, backup_dir)
        
        # 切换目录
        logger.info(f"📁 Switching to new deployment: {deploy_target} -> {web_dir}")
        shutil.move(deploy_target, web_dir)
        
        # 恢复 resources 目录
        if resource_dir and os.path.isdir(resource_dir):
            logger.info("📂 Restoring resources directory")
            resources_target = os.path.join(web_dir, 'resources')
            if os.path.exists(resources_target):
                shutil.rmtree(resources_target)
            shutil.copytree(resource_dir, resources_target)
    else:
        # 备份旧的部署
        if os.path.isdir(web_dir):
            backup_dir = f"{deploy_dir}/{web_name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            logger.info(f"💾 Backing up old deployment to: {backup_dir}")
            shutil.move(web_dir, backup_dir)
        
        # 切换目录
        logger.info("📁 Switching to new deployment")
        shutil.move(deploy_target, web_dir)
        
        # 恢复 resources 目录
        if resource_dir and os.path.isdir(resource_dir):
            logger.info("📂 Restoring resources directory")
            resources_target = os.path.join(web_dir, 'resources')
            if os.path.exists(resources_target):
                shutil.rmtree(resources_target)
            shutil.copytree(resource_dir, resources_target)
    
    # 重启 nginx
    logger.info("🔄 Restarting nginx...")
    code, stdout, stderr = run_command(['sudo', '/usr/sbin/service', 'nginx', 'restart'])
    if code == 0:
        logger.info("✅ Nginx restarted successfully")
    else:
        logger.error(f"❌ Failed to restart nginx: {stderr}")
        return False
    
    logger.info(f"🎉 {web_name} deployment completed successfully")
    return True


def main():
    parser = argparse.ArgumentParser(description='前端项目自动部署脚本')
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
    required_vars = ['PROJECT_DIR', 'BRANCH', 'NPM_PATH', 'BUILD_CMD', 'SOURCE_DIR', 'DEPLOY_DIR', 'DEPLOY_DIR_NAME']
    for var in required_vars:
        if var not in config or not config[var]:
            print(f"❌ 配置文件缺少必需变量: {var}")
            sys.exit(1)
    
    # 设置变量
    project_dir = config['PROJECT_DIR']
    branch = config['BRANCH']
    npm_path = config['NPM_PATH']
    build_cmd = config['BUILD_CMD']
    source_dir = config['SOURCE_DIR']
    deploy_dir = config['DEPLOY_DIR']
    deploy_dir_name = config['DEPLOY_DIR_NAME']
    
    log_dir = config.get('LOG_DIR', '/tmp/deploy-logs')
    web_name = config.get('WEB_NAME', deploy_dir_name)
    resource_dir = config.get('RESOURCE_DIR')
    remote_enabled = config.get('REMOTE_ENABLED', 'false') == 'true'
    deploy_script = config.get('DEPLOY_SCRIPT')
    
    config_name = os.path.splitext(os.path.basename(conf_file))[0]
    log_file = config.get('LOG_FILE', f"{log_dir}/fe-{config_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log")
    
    # 远程服务器配置
    remote_host = config.get('REMOTE_HOST', 'www.xuxiaoye.com')
    remote_user = config.get('REMOTE_USER', 'root')
    
    logger = Logger(log_file)
    
    # 验证目录和命令
    if not os.path.isdir(project_dir):
        logger.error(f"项目目录不存在: {project_dir}")
        sys.exit(1)
    
    if not os.path.isfile(npm_path):
        logger.error(f"npm 路径无效或不可执行: {npm_path}")
        sys.exit(1)
    
    if not os.path.isdir(deploy_dir):
        logger.error(f"部署目录不存在: {deploy_dir}")
        sys.exit(1)
    
    # 显示项目信息
    print("=" * 40)
    print(f"🚀 开始部署: {config.get('PROJECT_NAME', 'Unknown Project')}")
    print("=" * 40)
    print(f"配置文件: {conf_file}")
    print(f"项目目录: {project_dir}")
    print(f"分支: {branch}")
    print(f"NPM 路径: {npm_path}")
    print(f"构建命令: {build_cmd}")
    print(f"部署目标: {deploy_dir}/{deploy_dir_name}")
    print(f"Web 目录: {deploy_dir}/{web_name}")
    if resource_dir:
        print(f"资源目录: {resource_dir}")
    print(f"远程部署: {remote_enabled}")
    if remote_enabled:
        print(f"远程主机: {remote_user}@{remote_host}")
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
        
        # 安装依赖
        logger.info("📦 Installing dependencies...")
        code, stdout, stderr = run_command([npm_path, 'install'], cwd=project_dir)
        with open(log_file, 'a') as f:
            f.write(stdout)
            if stderr:
                f.write(stderr)
        
        # 构建
        logger.info(f"🔨 Building with: {npm_path} run {build_cmd}")
        code, stdout, stderr = run_command([npm_path, 'run', build_cmd], cwd=project_dir)
        with open(log_file, 'a') as f:
            f.write(stdout)
            if stderr:
                f.write(stderr)
        
        if code != 0:
            logger.error("❌ Build failed")
            sys.exit(1)
        logger.info("✅ Build completed")
        
        # 检查源目录是否存在
        full_source_dir = os.path.join(project_dir, source_dir)
        if not os.path.isdir(full_source_dir):
            logger.error(f"❌ 编译输出目录不存在: {full_source_dir}")
            sys.exit(1)
        
        # 部署到本地
        deploy_target = os.path.join(deploy_dir, deploy_dir_name)
        logger.info(f"📦 Copying to: {deploy_target}")
        
        # 如果存在，先删除旧的
        if os.path.isdir(deploy_target):
            shutil.rmtree(deploy_target)
        
        # 复制新构建
        shutil.copytree(full_source_dir, deploy_target)
        
        # 执行本地部署（切换 nginx 目录并重启）
        if web_name != deploy_dir_name or resource_dir:
            logger.info("🔧 Executing nginx deployment...")
            if nginx_deploy(logger, deploy_dir, deploy_dir_name, web_name, resource_dir):
                logger.info("✅ Nginx deployment completed successfully")
            else:
                logger.warn("⚠️  Nginx deployment failed (non-critical)")
        
        # 远程部署
        if remote_enabled:
            logger.info(f"☁️  Uploading to remote server: {remote_user}@{remote_host}")
            
            web_dir = os.path.join(deploy_dir, web_name)
            remote_target = f"{remote_user}@{remote_host}:{deploy_dir}/"
            code, _, _ = run_command(['scp', '-r', web_dir, remote_target])
            
            if code == 0:
                logger.info("✅ Uploaded to remote server")
                
                # 触发远程部署脚本
                if deploy_script:
                    remote_script_path = f"{deploy_dir}/{deploy_script}"
                    logger.info(f"🔧 Triggering remote deploy script: {remote_script_path}")
                    run_command(['ssh', f"{remote_user}@{remote_host}", f"sh {remote_script_path}"])
                
                logger.info("✅ Remote server updated")
            else:
                logger.error("❌ Failed to upload to remote server")
        
        deploy_success = True
        logger.info("🎉 Deploy finished successfully")
    else:
        # 没变化，静默退出
        logger.info(f"ℹ️  no change on {branch} (use --skip to force build)")
    
    sys.exit(0)


if __name__ == '__main__':
    main()