"""
데이터베이스 백업 스크립트
다른 PC로 데이터를 옮기거나 백업할 때 사용
"""
import os
import shutil
from datetime import datetime

def backup_database():
    """데이터베이스 파일을 백업"""
    db_file = 'bot_data.db'
    json_file = 'data.json'
    
    if not os.path.exists(db_file) and not os.path.exists(json_file):
        print("❌ 백업할 데이터 파일이 없습니다.")
        return
    
    # 백업 폴더 생성
    backup_dir = 'backups'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 타임스탬프 추가한 백업 파일명
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if os.path.exists(db_file):
        backup_name = f'bot_data_backup_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(db_file, backup_path)
        print(f"✅ 데이터베이스 백업 완료: {backup_path}")
    
    if os.path.exists(json_file):
        backup_name = f'data_backup_{timestamp}.json'
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(json_file, backup_path)
        print(f"✅ JSON 데이터 백업 완료: {backup_path}")

def restore_database(backup_file):
    """백업 파일에서 데이터베이스 복원"""
    if not os.path.exists(backup_file):
        print(f"❌ 백업 파일을 찾을 수 없습니다: {backup_file}")
        return
    
    if backup_file.endswith('.db'):
        target = 'bot_data.db'
    elif backup_file.endswith('.json'):
        target = 'data.json'
    else:
        print("❌ 지원하지 않는 파일 형식입니다. (.db 또는 .json)")
        return
    
    # 기존 파일 백업 (덮어쓰기 전)
    if os.path.exists(target):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        old_backup = f'{target}.old_{timestamp}'
        shutil.copy2(target, old_backup)
        print(f"⚠️ 기존 파일을 백업했습니다: {old_backup}")
    
    shutil.copy2(backup_file, target)
    print(f"✅ 데이터 복원 완료: {target}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # 복원 모드
        restore_database(sys.argv[1])
    else:
        # 백업 모드
        backup_database()
        print("\n💡 사용법:")
        print("  백업: python backup_data.py")
        print("  복원: python backup_data.py <백업파일경로>")

