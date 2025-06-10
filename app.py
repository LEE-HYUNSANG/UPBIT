from flask import Flask, render_template, jsonify, request
from flask_socketio import emit
from extensions import socketio
import logging
from logging.handlers import RotatingFileHandler
import json
import os
from dotenv import load_dotenv
from config.logging_config import setup_logging
from datetime import datetime
from core.market_analyzer import MarketAnalyzer
from core.constants import DEFAULT_COIN_SELECTION
from pathlib import Path

# 환경 변수 로드
load_dotenv()

# 로거 설정
logger = setup_logging()

# 기본 설정값 정의
DEFAULT_SETTINGS = {
    "trade_settings": {
        "base_amount": 10000,
        "max_positions": 5,
        **DEFAULT_COIN_SELECTION,
        "use_stop_loss": True,
        "stop_loss": 5,
        "use_take_profit": True,
        "take_profit": 10
    },
    "indicators": {
        "rsi_period": 14,
        "rsi_oversold": 30,
        "trend_filter_on": True,
        "use_golden_cross": True,
        "min_slope": 0.1
    },
    "notifications": {
        "trade_alert": True,
        "error_alert": True,
        "status_alert": True
    }
}

app = Flask(__name__)
socketio.init_app(app)

# MarketAnalyzer 초기화
try:
    config_path = str(Path(__file__).parent / 'config.json')
    market_analyzer = MarketAnalyzer(config_path=config_path)
    logger.info("MarketAnalyzer 초기화 성공")
except Exception as e:
    logger.error(f"MarketAnalyzer 초기화 실패: {str(e)}")
    market_analyzer = None

# 텔레그램 알림 초기화
try:
    from core.telegram_notifier import TelegramNotifier
    telegram_notifier = TelegramNotifier()
    if telegram_notifier.is_enabled():
        logger.info("텔레그램 알림 초기화 성공")
    else:
        logger.warning("텔레그램 알림이 비활성화되어 있습니다.")
except Exception as e:
    logger.error(f"텔레그램 알림 초기화 실패: {str(e)}")
    telegram_notifier = None

# 로깅 설정
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler(
    'logs/trading.log',
    maxBytes=1024 * 1024,  # 1MB
    backupCount=10,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# 설정 파일 경로
SETTINGS_FILE = str(Path(__file__).parent / 'config' / 'settings.json')

# 봇 상태 관리를 위한 전역 변수
bot_status = {
    'is_running': False,
    'last_update': None,
    'error': None
}

# 봇 상태 업데이트 함수
def update_bot_status(status, message=None, error=None):
    """봇 상태를 업데이트하고 클라이언트에 알림을 보냅니다."""
    bot_status['is_running'] = status
    bot_status['last_update'] = datetime.now().isoformat()
    bot_status['error'] = error

    # 클라이언트에 상태 업데이트 전송
    socketio.emit('bot_status', {
        'status': status,
        'message': message or ('실행 중' if status else '중지됨'),
        'error': error,
        'last_update': bot_status['last_update']
    }, include_self=True)

    # 에러가 있는 경우 알림 전송
    if error:
        socketio.emit('notification', {
            'type': 'error',
            'message': f'오류 발생: {error}'
        }, include_self=True)

def ensure_config_dir():
    """설정 파일 디렉토리가 존재하는지 확인하고 없으면 생성합니다."""
    config_dir = os.path.dirname(SETTINGS_FILE)
    if config_dir:  # 디렉토리 경로가 비어있지 않은 경우에만 생성
        os.makedirs(config_dir, exist_ok=True)
        logger.info(f'설정 파일 디렉토리 생성: {config_dir}')

def load_settings():
    """설정 파일을 로드합니다."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                logger.info('설정 파일 로드 성공')
                return settings
        logger.info('설정 파일이 없어 기본 설정을 생성합니다.')
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    except Exception as e:
        logger.error(f'설정 로드 중 오류 발생: {str(e)}')
        return DEFAULT_SETTINGS

def save_settings(settings):
    """설정을 파일에 저장합니다."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        logger.info('설정 저장 성공')
        return True
    except Exception as e:
        logger.error(f'설정 저장 중 오류 발생: {str(e)}')
        return False

def start_monitoring():
    """모니터링 시작"""
    try:
        if not bot_status['is_running']:
            logger.info("모니터링 시작")
            bot_status['is_running'] = True
            socketio.start_background_task(target=monitor_market)
            socketio.start_background_task(target=monitor_account)
    except Exception as e:
        logger.error(f"모니터링 시작 중 오류 발생: {str(e)}")

def monitor_account():
    """계좌 정보 모니터링"""
    while True:
        try:
            if bot_status['is_running'] and market_analyzer:
                # 계좌 잔고 조회
                balance = market_analyzer.get_balance()
                socketio.emit('balance_update', balance, include_self=True)
                
                # 보유 코인 조회
                holdings = market_analyzer.get_holdings()
                if holdings:
                    socketio.emit('holdings_update', {
                        'holdings': list(holdings.values())
                    }, include_self=True)
                
            socketio.sleep(10)  # 10초마다 업데이트
            
        except Exception as e:
            logger.error(f"계좌 모니터링 중 오류 발생: {str(e)}")
            socketio.sleep(5)

def monitor_market():
    """시장 모니터링 작업"""
    while True:
        try:
            if bot_status['is_running'] and market_analyzer:
                # 모니터링 코인 정보 업데이트
                monitored_coins = market_analyzer.get_monitored_coins()
                socketio.emit('monitored_coins_update', {
                    'coins': monitored_coins,
                    'timestamp': datetime.now().isoformat()
                }, include_self=True)
                
            socketio.sleep(market_analyzer.monitoring_interval if market_analyzer else 20)
            
        except Exception as e:
            logger.error(f"시장 모니터링 중 오류 발생: {str(e)}")
            socketio.sleep(5)

# Socket.IO 이벤트 핸들러
@socketio.on('connect')
def handle_connect(auth=None):
    """소켓 연결 이벤트 핸들러"""
    try:
        logger.debug('Client connected')
        emit('notification', {
            'type': 'success',
            'message': '서버에 연결되었습니다.'
        })
        
        # 현재 봇 상태 전송
        emit('bot_status', {
            'status': bot_status['is_running'],
            'message': '실행 중' if bot_status['is_running'] else '중지됨'
        })
        
        # 초기 데이터 전송
        if market_analyzer:
            # 계좌 잔고 조회
            balance = market_analyzer.get_balance()
            emit('balance_update', balance)
            
            # 보유 코인 조회
            holdings = market_analyzer.get_holdings()
            if holdings:
                emit('holdings_update', {
                    'holdings': list(holdings.values())
                })
            
            # 모니터링 코인 조회
            monitored_coins = market_analyzer.get_monitored_coins()
            emit('monitored_coins_update', {
                'coins': monitored_coins,
                'timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"연결 처리 중 오류 발생: {str(e)}")
        emit('notification', {
            'type': 'error',
            'message': f'연결 중 오류가 발생했습니다: {str(e)}'
        })

@socketio.on('disconnect')
def handle_disconnect():
    """클라이언트 연결 해제 시 호출됩니다."""
    logger.debug('Client disconnected')

@socketio.on('settings_changed')
def handle_settings_changed(settings):
    """클라이언트에서 설정이 변경되었을 때 호출됩니다."""
    logger.info('설정 변경: %s', json.dumps(settings, indent=2, ensure_ascii=False))
    if save_settings(settings):
        # 다른 클라이언트들에게 변경사항 전파
        emit('settings_updated', settings, broadcast=True)
    else:
        # 저장 실패 시 에러 전송
        emit('settings_error', {'message': '설정 저장에 실패했습니다.'})

def send_telegram_message(message: str):
    """텔레그램 메시지 전송"""
    try:
        if telegram_notifier and telegram_notifier.is_enabled():
            telegram_notifier.send_message_sync(message)
            logger.info(f"텔레그램 알림 전송 성공: {message}")
        else:
            logger.warning("텔레그램 알림이 비활성화되어 있습니다.")
    except Exception as e:
        logger.error(f"텔레그램 알림 전송 실패: {str(e)}")

@socketio.on('start_bot')
def handle_start_bot(data=None):
    """거래봇 시작"""
    try:
        logger.info("거래봇 시작 시도")
        
        if not market_analyzer:
            error_msg = "MarketAnalyzer가 초기화되지 않았습니다."
            logger.error(error_msg)
            update_bot_status(False, error=error_msg)
            return
            
        emit('notification', {
            'type': 'info',
            'message': '거래봇을 시작하는 중...'
        })
        
        # API 키 확인
        access_key = os.getenv('UPBIT_ACCESS_KEY')
        secret_key = os.getenv('UPBIT_SECRET_KEY')
        
        if not access_key or not secret_key:
            error_msg = "Upbit API 키가 설정되지 않았습니다. .env 파일을 확인해주세요."
            logger.error(error_msg)
            update_bot_status(False, error=error_msg)
            return
        
        # 거래봇 시작
        if market_analyzer.start():
            update_bot_status(True, '실행 중')
            logger.info("거래봇 시작됨")
            
            # 모니터링 시작
            start_monitoring()
            
            # 성공 알림
            emit('notification', {
                'type': 'success',
                'message': '거래봇이 성공적으로 시작되었습니다.'
            })
            
            # 텔레그램 알림 전송
            send_telegram_message("거래봇이 시작되었습니다. 모니터링을 시작합니다.")
            
            # 초기 데이터 전송
            balance = market_analyzer.get_balance()
            if balance:
                socketio.emit('balance_update', balance, include_self=True)
            
            holdings = market_analyzer.get_holdings()
            if holdings:
                socketio.emit('holdings_update', {
                    'holdings': list(holdings.values())
                }, include_self=True)
            
        else:
            error_msg = '거래봇 시작에 실패했습니다.'
            update_bot_status(False, error=error_msg)
            send_telegram_message("거래봇 시작 실패")
            
    except Exception as e:
        error_msg = f"거래봇 시작 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        update_bot_status(False, error=error_msg)
        send_telegram_message(f"오류 발생: {error_msg}")

@socketio.on('stop_bot')
def handle_stop_bot(data=None):
    """거래봇 중지"""
    try:
        logger.info("거래봇 중지 시도")
        
        if not market_analyzer:
            error_msg = "MarketAnalyzer가 초기화되지 않았습니다."
            logger.error(error_msg)
            update_bot_status(True, error=error_msg)
            return
            
        emit('notification', {
            'type': 'info',
            'message': '거래봇을 중지하는 중...'
        })
        
        if market_analyzer.stop():
            update_bot_status(False, '중지됨')
            logger.info("거래봇 중지됨")
            
            # 성공 알림
            emit('notification', {
                'type': 'success',
                'message': '거래봇이 성공적으로 중지되었습니다.'
            })
        else:
            error_msg = '거래봇 중지에 실패했습니다.'
            update_bot_status(True, error=error_msg)
            
    except Exception as e:
        error_msg = f"거래봇 중지 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        update_bot_status(True, error=error_msg)

@socketio.on('market_buy')
def handle_market_buy(data):
    """시장가 매수 처리"""
    try:
        market = data['market']
        logger.info(f"시장가 매수 요청: {market}")
        
        if not market_analyzer:
            error_msg = "MarketAnalyzer가 초기화되지 않았습니다."
            logger.error(error_msg)
            emit('market_buy_result', {
                'success': False,
                'error': error_msg
            })
            return
            
        result = market_analyzer.market_buy(market)
        
        if result['success']:
            emit('market_buy_result', {
                'success': True,
                'message': f"{market} 매수 주문이 완료되었습니다."
            })
            # 보유 코인 정보 업데이트
            holdings = market_analyzer.get_holdings()
            socketio.emit('holdings_update', {
                'holdings': list(holdings.values()) if holdings else []
            }, include_self=True)
        else:
            emit('market_buy_result', {
                'success': False,
                'error': result.get('error', '매수 실패')
            })
            
    except Exception as e:
        error_msg = f"매수 처리 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        emit('market_buy_result', {
            'success': False,
            'error': error_msg
        })

# API 블루프린트 등록
from routes import api
app.register_blueprint(api)

@app.route('/')
def index():
    logger.info('홈 페이지 접속')
    return render_template('index.html')

@app.route('/settings')
def settings():
    logger.info('설정 페이지 접속')
    return render_template('settings.html')

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """현재 설정을 반환합니다."""
    try:
        logger.info('설정 로드 요청 받음')
        settings = load_settings()
        if not settings:
            logger.error('설정을 로드할 수 없습니다.')
            return jsonify({
                'status': 'error',
                'message': '설정을 로드할 수 없습니다.'
            }), 500
            
        logger.info('설정 로드 성공')
        return jsonify({
            'status': 'success',
            'data': settings
        })
    except Exception as e:
        logger.error(f'설정 로드 중 오류: {str(e)}', exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'설정 로드 중 오류 발생: {str(e)}'
        }), 500

@app.route('/save_settings', methods=['POST'])
def save_settings_endpoint():
    try:
        settings = request.get_json()
        if save_settings(settings):
            # 설정 변경을 모든 클라이언트에 전송
            socketio.emit('settings_updated', settings)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '설정 저장 실패'})
    except Exception as e:
        logger.error(f"설정 저장 중 오류: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/load_settings', methods=['GET'])
def load_settings_endpoint():
    try:
        settings = load_settings()
        return jsonify(settings)
    except Exception as e:
        logger.error(f"설정 로드 중 오류: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    logger.info('서버 시작')
    try:
        socketio.run(app, debug=True, host='0.0.0.0')
    except Exception as e:
        logger.error(f'서버 실행 중 오류 발생: {str(e)}')
    finally:
        logger.info('서버 종료') 