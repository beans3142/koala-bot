"""
로깅 유틸리티
"""
import logging
import os
from datetime import datetime

# 로그 디렉토리
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 로그 파일 경로
LOG_FILE = os.path.join(LOG_DIR, f'bot_{datetime.now().strftime("%Y%m%d")}.log')

def setup_logger():
    """로거 설정"""
    logger = logging.getLogger('discord_bot')
    logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거
    if logger.handlers:
        logger.handlers.clear()
    
    # 파일 핸들러
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_logger():
    """로거 가져오기"""
    logger = logging.getLogger('discord_bot')
    if not logger.handlers:
        return setup_logger()
    return logger

