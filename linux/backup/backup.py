#!/usr/bin/env python3
import os
import shutil
import datetime
import logging
import argparse
import sys
import yaml
from typing import Dict, Any

DEFAULT_CONFIG_PATH = "/etc/backup_config.yaml"

def load_config(config_path: str) -> Dict[str, Any]:
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        required_fields = ['backup_root', 'min_free_space_gb', 'max_backups']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Отсутствует обязательное поле: {field}")
        
        config.setdefault('source_dir', None)
        config.setdefault('log_level', 'INFO')
        config.setdefault('max_logs', 5)
        
        return config
    except Exception as e:
        raise RuntimeError(f"Ошибка загрузки конфига: {str(e)}")

class BackupManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backup_dir = os.path.join(config['backup_root'], "backup_files")
        self.log_dir = os.path.join(config['backup_root'], "logs")
        self.log_file = os.path.join(self.log_dir, "backup.log")
        self.setup_logging()

    def setup_logging(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

        log_level = getattr(logging, self.config['log_level'].upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def cleanup_old_files(self, directory: str, extension: str, max_files: int):
        try:
            files = sorted(
                [os.path.join(directory, f) for f in os.listdir(directory) 
                 if f.endswith(extension)],
                key=os.path.getmtime
            )
            if len(files) > max_files:
                for old_file in files[:-max_files]:
                    os.remove(old_file)
                    self.logger.info(f"Удалён старый файл: {os.path.basename(old_file)}")
        except Exception as e:
            self.logger.error(f"Ошибка очистки файлов: {str(e)}")

    def check_disk_space(self) -> bool:
        stat = shutil.disk_usage(self.config['backup_root'])
        free_space_gb = stat.free / (1024 ** 3)
        if free_space_gb < self.config['min_free_space_gb']:
            self.logger.error(
                f"Недостаточно места! Свободно: {free_space_gb:.2f}GB, "
                f"требуется: {self.config['min_free_space_gb']}GB"
            )
            return False
        return True

    def run_backup(self, source_dir: str):
        try:
            self.logger.info("=== Начало процесса бэкапирования ===")
            
            if not self.check_disk_space():
                raise RuntimeError("Недостаточно места на диске")

            if not os.path.exists(source_dir):
                raise FileNotFoundError(f"Исходная директория не существует: {source_dir}")

            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir, exist_ok=True)
                self.logger.info(f"Создана директория для бэкапов: {self.backup_dir}")

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{os.path.basename(source_dir)}_{timestamp}.tar.gz"
            backup_path = os.path.join(self.backup_dir, backup_name)

            self.logger.info(f"Создание бэкапа: {backup_path}")
            shutil.make_archive(
                base_name=os.path.join(self.backup_dir, f"backup_{os.path.basename(source_dir)}_{timestamp}"),
                format='gztar',
                root_dir=os.path.dirname(source_dir),
                base_dir=os.path.basename(source_dir)
            )

            self.cleanup_old_files(self.backup_dir, '.tar.gz', self.config['max_backups'])
            self.cleanup_old_files(self.log_dir, '.log', self.config['max_logs'])
            
            self.logger.info(f"Бэкап успешно создан: {backup_path}")
            return 0

        except Exception as e:
            self.logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
            return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Скрипт резервного копирования")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH, 
                       help="Путь к конфигурационному файлу")
    parser.add_argument("-s", "--source", help="Переопределить исходную директорию из конфига")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        if args.source:
            config['source_dir'] = args.source
        
        if not config['source_dir']:
            raise ValueError("Не указана исходная директория (ни в конфиге, ни в аргументах)")

        manager = BackupManager(config)
        sys.exit(manager.run_backup(config['source_dir']))
    
    except Exception as e:
        print(f"Ошибка инициализации: {str(e)}", file=sys.stderr)
        sys.exit(1)