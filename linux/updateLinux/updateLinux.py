#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
import argparse
from typing import List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/system_update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemUpdater:
    def __init__(self, full_upgrade: bool = False, clean: bool = False):
        self.full_upgrade = full_upgrade
        self.clean = clean
        self.distrib_id = self._get_distribution()

    def _run_command(self, cmd: List[str]) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stdout

    def _get_distribution(self) -> str:
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release') as f:
                for line in f:
                    if line.startswith('ID='):
                        return line.strip().split('=')[1].strip('"')
        return 'unknown'

    def _apt_update(self) -> bool:
        success, output = self._run_command(['apt', 'update'])
        if not success:
            logger.error(f"Ошибка apt update:\n{output}")
        return success

    def _apt_upgrade(self) -> bool:
        cmd = ['apt', 'upgrade', '-y']
        if self.full_upgrade:
            cmd = ['apt', 'full-upgrade', '-y']
        
        success, output = self._run_command(cmd)
        if not success:
            logger.error(f"Ошибка apt upgrade:\n{output}")
        return success

    def _apt_clean(self) -> bool:
        commands = [
            ['apt', 'autoremove', '-y'],
            ['apt', 'clean'],
            ['rm', '-rf', '/var/lib/apt/lists/*']
        ]
        
        for cmd in commands:
            success, output = self._run_command(cmd)
            if not success:
                logger.error(f"Ошибка очистки:\n{output}")
                return False
        return True

    def _dnf_upgrade(self) -> bool:
        commands = [
            ['dnf', 'upgrade', '-y'],
            ['dnf', 'autoremove', '-y'] if self.clean else None,
            ['dnf', 'clean', 'all'] if self.clean else None
        ]
        
        for cmd in filter(None, commands):
            success, output = self._run_command(cmd)
            if not success:
                logger.error(f"Ошибка dnf:\n{output}")
                return False
        return True

    def _yum_upgrade(self) -> bool:
        commands = [
            ['yum', 'update', '-y'],
            ['yum', 'clean', 'all'] if self.clean else None
        ]
        
        for cmd in filter(None, commands):
            success, output = self._run_command(cmd)
            if not success:
                logger.error(f"Ошибка yum:\n{output}")
                return False
        return True

    def run(self) -> bool:
        logger.info(f"Обнаружен дистрибутив: {self.distrib_id}")
        
        try:
            if self.distrib_id in ('debian', 'ubuntu', 'linuxmint'):
                if not self._apt_update():
                    return False
                if not self._apt_upgrade():
                    return False
                if self.clean and not self._apt_clean():
                    return False
            
            elif self.distrib_id in ('fedora', 'centos', 'rhel'):
                if not (self._dnf_upgrade() if 'fedora' in self.distrib_id else self._yum_upgrade()):
                    return False
            
            else:
                logger.error("Неподдерживаемый дистрибутив")
                return False
            
            logger.info("Система успешно обновлена!")
            return True
            
        except Exception as e:
            logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
            return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Скрипт обновления Linux")
    parser.add_argument("--full", action="store_true", help="Полное обновление (full-upgrade для APT)")
    parser.add_argument("--clean", action="store_true", help="Очистка кеша пакетов после обновления")
    args = parser.parse_args()

    updater = SystemUpdater(full_upgrade=args.full, clean=args.clean)
    sys.exit(0 if updater.run() else 1)