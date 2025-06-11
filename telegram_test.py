import sys
from core.telegram_notifier import TelegramNotifier

if __name__ == "__main__":
    try:
        notifier = TelegramNotifier()
    except Exception as e:
        print(f"텔레그램 설정 오류: {e}")
        sys.exit(1)

    print("텔레그램 테스트 메시지를 전송합니다...")
    success = notifier.send_message_sync("✅ 텔레그램 설정이 정상입니다.")
    if success:
        print("메시지 전송 성공")
    else:
        print("메시지 전송 실패")
