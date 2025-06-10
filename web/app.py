from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json
import sys
import os
from datetime import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.market_analyzer import MarketAnalyzer
from core.config_manager import ConfigManager
import threading
import time
from core.trading_logic import TradingLogic
from config.default_settings import DEFAULT_SETTINGS  # 기본 설정 불러오기
from core.constants import DEFAULT_COIN_SELECTION

# .env 파일 로드
load_dotenv()

app = Flask(__name__, 
    template_folder='../templates',
    static_folder='../static'
)
app.config['SECRET_KEY'] = 'secret!'

# Socket.IO 초기화
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=None,  # 자동으로 최적의 모드 선택
    logger=True,
    engineio_logger=True
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 설정 파일 경로 설정
config_path = str(Path(__file__).parent.parent / 'config.json')
logger.info(f"설정 파일 경로: {config_path}")

# 인스턴스 생성
try:
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # MarketAnalyzer 초기화 전에 설정 검증
    market_analyzer = MarketAnalyzer(config_path=config_path)
    market_analyzer.update_config(config)  # 설정 업데이트
    market_analyzer.is_running = False  # 초기 상태는 중지
    logger.info("MarketAnalyzer와 ConfigManager 초기화 완료 (중지 상태)")
except Exception as e:
    logger.error(f"초기화 중 오류 발생: {str(e)}")
    raise

# 거래봇 상태
bot_status = {
    'is_running': False,
    'holdings': {},
    'monitored_coins': [],
    'last_update': None
}

trading_logic = None

# 설정 파일 경로
CONFIG_FILE = 'config.json'

def load_config():
    """설정 파일 로드"""
    try:
        logger.info("설정 파일 로드 시작...")
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
        logger.info(f"설정 파일 경로: {config_path}")
        
        # 설정 파일 존재 여부 확인
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info("설정 파일 로드 성공")
                
                # 필수 섹션 확인 및 보완
                required_sections = ['trading', 'signals', 'notifications', 'market_analysis', 'buy_score']
                default_config = get_default_config()
                
                for section in required_sections:
                    if section not in config:
                        logger.warning(f"필수 섹션 누락: {section}, 기본값으로 보완합니다.")
                        config[section] = default_config[section]
                
                return config
            except json.JSONDecodeError as e:
                logger.error(f"설정 파일 JSON 파싱 오류: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"설정 파일 읽기 오류: {str(e)}")
                return None
        else:
            logger.warning("설정 파일이 없습니다. 기본 설정을 생성합니다.")
            default_config = get_default_config()
            
            # 설정 파일 디렉토리 생성
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # 기본 설정 저장
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                logger.info("기본 설정 파일 생성 완료")
                return default_config
            except Exception as e:
                logger.error(f"기본 설정 파일 생성 실패: {str(e)}")
                return None
                
    except Exception as e:
        logger.error(f"설정 파일 로드 중 오류 발생: {str(e)}")
        return None

def save_config(config):
    """설정 파일 저장"""
    try:
        config_path = os.path.abspath('config.json')
        logger.info(f"설정 파일 저장 경로: {config_path}")
        
        # 임시 파일에 먼저 저장
        temp_path = config_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info("임시 파일에 설정 저장 완료")
        
        # 성공적으로 저장되면 원본 파일 교체
        os.replace(temp_path, config_path)
        logger.info(f"설정 파일 저장 완료: {config_path}")
    except Exception as e:
        logger.error(f"설정 파일 저장 중 오류 발생: {str(e)}")
        raise

def get_default_config():
    """기본 설정값 반환"""
    # 기본 설정 모듈에서 값을 복사하여 반환한다.
    return DEFAULT_SETTINGS.copy()

def validate_config(config):
    """설정 유효성 검사"""
    validation_errors = []
    try:
        logger.info("설정 유효성 검사 시작...")
        
        # 필수 섹션 확인
        required_sections = ['version', 'trading', 'signals', 'notifications', 'market_analysis', 'buy_score']
        for section in required_sections:
            if section not in config:
                error_msg = f"[오류] 필수 섹션 누락: {section}"
                validation_errors.append(error_msg)
                logger.error(error_msg)
                continue
            else:
                logger.info(f"[정상] 섹션 확인: {section}")

        # 버전 검사
        if not isinstance(config.get('version'), str):
            validation_errors.append("[오류] version은 문자열이어야 합니다.")

        # 거래 설정 검증
        trading = config.get('trading', {})
        if not isinstance(trading.get('enabled'), bool):
            validation_errors.append("[오류] trading.enabled는 boolean이어야 합니다.")
        
        if not isinstance(trading.get('investment_amount', 0), (int, float)) or trading['investment_amount'] <= 0:
            validation_errors.append("[오류] investment_amount는 양수여야 합니다.")
        
        if not isinstance(trading.get('max_coins', 0), int) or trading['max_coins'] <= 0:
            validation_errors.append("[오류] max_coins는 양의 정수여야 합니다.")
            
        # 코인 선택 설정 검증
        coin_selection = trading.get('coin_selection', {})
        if not isinstance(coin_selection.get('min_price', 0), (int, float)) or coin_selection['min_price'] < 0:
            validation_errors.append("[오류] min_price는 0 이상이어야 합니다.")
            
        if not isinstance(coin_selection.get('max_price', 0), (int, float)) or coin_selection['max_price'] <= coin_selection['min_price']:
            validation_errors.append("[오류] max_price는 min_price보다 커야 합니다.")

        for key in ['min_volume_24h', 'min_volume_1h', 'min_tick_ratio']:
            if not isinstance(coin_selection.get(key, 0), (int, float)) or coin_selection[key] < 0:
                validation_errors.append(f"[오류] {key}는 0 이상 숫자여야 합니다.")

        if not isinstance(coin_selection.get('excluded_coins', []), list):
            validation_errors.append("[오류] excluded_coins는 리스트여야 합니다.")

        # 신호 설정 검증
        signals = config.get('signals', {})
        if not isinstance(signals.get('enabled'), bool):
            validation_errors.append("[오류] signals.enabled는 boolean이어야 합니다.")
            
        # 매수/매도 조건 검증
        for condition_type in ['buy_conditions', 'sell_conditions']:
            conditions = signals.get(condition_type, {})
            if not isinstance(conditions.get('enabled'), bool):
                validation_errors.append(f"[오류] {condition_type}.enabled는 boolean이어야 합니다.")
                
            # RSI 설정 검증
            rsi = conditions.get('rsi', {})
            if rsi.get('enabled', False):
                if not isinstance(rsi.get('threshold'), (int, float)):
                    validation_errors.append(f"[오류] {condition_type}.rsi.threshold는 숫자여야 합니다.")
                    
            # 볼린저 밴드 설정 검증
            bollinger = conditions.get('bollinger', {})
            if bollinger.get('enabled', False):
                if not isinstance(bollinger.get('threshold'), (int, float)):
                    validation_errors.append(f"[오류] {condition_type}.bollinger.threshold는 숫자여야 합니다.")

        # 알림 설정 검증
        notifications = config.get('notifications', {})
        for category in ['trade', 'system']:
            category_settings = notifications.get(category, {})
            for key in category_settings:
                if not isinstance(category_settings[key], bool):
                    validation_errors.append(f"[오류] notifications.{category}.{key}는 boolean이어야 합니다.")

        # 시장 분석 설정 검증
        market_analysis = config.get('market_analysis', {})
        weights = market_analysis.get('weights', {})
        if sum(weights.values()) != 1.0:
            validation_errors.append("[오류] market_analysis.weights의 합은 1.0이어야 합니다.")
            
        check_interval = market_analysis.get('check_interval_minutes', 0)
        if not isinstance(check_interval, int) or check_interval <= 0:
            validation_errors.append("[오류] check_interval_minutes는 양의 정수여야 합니다.")

        if validation_errors:
            logger.error("설정 유효성 검사 실패")
            logger.error("발견된 오류:")
            for error in validation_errors:
                logger.error(f"  - {error}")
            return False, validation_errors
        
        logger.info("설정 유효성 검사 완료: 모든 설정이 유효함")
        return True, []
        
    except Exception as e:
        error_msg = f"설정 검증 중 예외 발생: {str(e)}"
        logger.error(error_msg)
        validation_errors.append(error_msg)
        return False, validation_errors

def config_equals(config1, config2):
    """설정 비교"""
    try:
        if set(config1.keys()) != set(config2.keys()):
            return False
            
        for key in config1:
            if isinstance(config1[key], dict):
                if not config_equals(config1[key], config2[key]):
                    return False
            elif config1[key] != config2[key]:
                return False
                
        return True
    except Exception:
        return False

@app.route('/')
def index():
    """통합된 메인 페이지"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/settings')
def settings():
    """설정 페이지"""
    return render_template('settings.html')

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """설정 조회 API"""
    try:
        logger.info("설정 조회 요청 받음")
        settings = market_analyzer.get_settings()
        
        if not settings:
            logger.info("기존 설정 파일이 없어 기본 설정을 사용합니다.")
            settings = get_default_config()
            market_analyzer.save_settings(settings)
        
        return jsonify({
            'success': True,
            'data': settings
        })
    except Exception as e:
        logger.error(f"설정 조회 중 오류 발생: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """설정 저장 API"""
    try:
        logger.info("[정보] 설정 저장 요청 받음")
        new_settings = request.json
        
        if not new_settings:
            return jsonify({
                'success': False,
                'error': '설정 데이터가 비어있습니다.'
            }), 400

        # 기존 설정과 병합하여 전체 설정 생성
        def deep_merge(src, updates):
            for k, v in updates.items():
                if isinstance(v, dict) and isinstance(src.get(k), dict):
                    src[k] = deep_merge(src.get(k, {}), v)
                else:
                    src[k] = v
            return src

        current_settings = config_manager.get_config()
        merged_settings = deep_merge(json.loads(json.dumps(current_settings)), new_settings)

        # 설정 유효성 검사
        valid, errors = validate_config(merged_settings)
        if not valid:
            return jsonify({
                'success': False,
                'error': '유효하지 않은 설정값입니다.',
                'validation_errors': errors
            }), 400
            
        # 설정 저장
        try:
            config_manager.update_config(new_settings)
            market_analyzer.update_config(config_manager.get_config())
            return jsonify({
                'success': True,
                'message': '설정이 성공적으로 저장되었습니다.'
            })
        except Exception:
            return jsonify({
                'success': False,
                'error': '설정 저장에 실패했습니다.'
            }), 500
            
    except Exception as e:
        logger.error(f"[오류] 설정 저장 중 오류 발생: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/buy_settings', methods=['GET'])
def get_buy_settings():
    """매수 주문 설정 조회"""
    try:
        settings = market_analyzer.get_buy_settings()
        return jsonify({'success': True, 'data': settings})
    except Exception as e:
        logger.error(f"매수 설정 조회 오류: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/buy_settings', methods=['POST'])
def save_buy_settings():
    """매수 주문 설정 저장"""
    try:
        settings = request.json
        if not settings:
            return jsonify({'success': False, 'error': '데이터가 비어있습니다.'}), 400
        if market_analyzer.save_buy_settings(settings):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '매수 설정 저장 실패'}), 500
    except Exception as e:
        logger.error(f"매수 설정 저장 오류: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sell_settings', methods=['GET'])
def get_sell_settings():
    """매도 주문 설정 조회"""
    try:
        settings = market_analyzer.get_sell_settings()
        return jsonify({'success': True, 'data': settings})
    except Exception as e:
        logger.error(f"매도 설정 조회 오류: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sell_settings', methods=['POST'])
def save_sell_settings():
    """매도 주문 설정 저장"""
    try:
        settings = request.json
        if not settings:
            return jsonify({'success': False, 'error': '데이터가 비어있습니다.'}), 400
        if market_analyzer.save_sell_settings(settings):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': '매도 설정 저장 실패'}), 500
    except Exception as e:
        logger.error(f"매도 설정 저장 오류: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/holdings', methods=['GET'])
def get_holdings():
    """현재 보유 중인 코인 정보 조회"""
    try:
        holdings = market_analyzer.get_holdings()
        return jsonify({
            'status': 'success',
            'data': holdings
        })
    except Exception as e:
        logger.error(f"보유 코인 조회 중 오류 발생: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

def update_holdings():
    """보유 코인 정보 업데이트"""
    try:
        holdings = market_analyzer.get_holdings()
        if holdings:
            socketio.emit('holdings_update', {
                'holdings': holdings,
                'timestamp': datetime.now().isoformat()
            })
            logger.info("보유 코인 정보 업데이트 완료")
    except Exception as e:
        logger.error(f"보유 코인 정보 업데이트 실패: {str(e)}")

def start_holdings_monitor():
    """보유 코인 모니터링 시작"""
    if not bot_status['is_running']:
        return
        
    try:
        update_holdings()
        socketio.start_background_task(target=holdings_monitor)
        logger.info("보유 코인 모니터링 시작")
    except Exception as e:
        logger.error(f"보유 코인 모니터링 시작 실패: {str(e)}")

def holdings_monitor():
    """보유 코인 모니터링 작업"""
    while bot_status['is_running']:
        try:
            update_holdings()
            socketio.sleep(10)  # 10초마다 업데이트
        except Exception as e:
            logger.error(f"보유 코인 모니터링 중 오류 발생: {str(e)}")
            socketio.sleep(5)

def start_monitoring():
    """모니터링 시작"""
    try:
        if not bot_status['is_running']:
            logger.info("모니터링 시작")
            bot_status['is_running'] = True
            socketio.start_background_task(target=monitor_market)
    except Exception as e:
        logger.error(f"모니터링 시작 중 오류 발생: {str(e)}")

def monitor_market():
    """시장 모니터링 작업"""
    while True:  # 항상 실행 상태 유지
        try:
            if bot_status['is_running']:
                # 봇이 실행 중일 때만 계좌/보유코인 정보 업데이트 (1분 주기)
                holdings = market_analyzer.get_holdings()
                if holdings is None:
                    holdings = {}
                bot_status['holdings'] = holdings
                
                # 클라이언트에 업데이트 전송
                socketio.emit('holdings_update', {
                    'holdings': list(holdings.values()),
                    'timestamp': datetime.now().isoformat()
                })
                
                socketio.sleep(market_analyzer.update_interval)  # 1분 대기
            else:
                # 중지 상태일 때는 모니터링 코인만 업데이트 (20초 주기)
                try:
                    monitored_coins = market_analyzer.get_monitored_coins()
                    if monitored_coins:
                        socketio.emit('monitored_coins_update', {
                            'coins': monitored_coins,
                            'timestamp': datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.warning(f"모니터링 코인 업데이트 실패: {str(e)}")
                
                socketio.sleep(market_analyzer.monitoring_interval)  # 20초 대기
            
        except Exception as e:
            logger.error(f"모니터링 중 오류 발생: {str(e)}")
            socketio.sleep(5)  # 오류 발생 시 5초 대기

@socketio.on('connect')
def handle_connect(auth=None):
    """소켓 연결 이벤트 핸들러"""
    try:
        logger.info('Client connected')
        emit('notification', {
            'type': 'success',
            'message': '서버에 연결되었습니다.'
        })
        
        # 현재 봇 상태 전송
        emit('bot_status', {
            'status': bot_status['is_running'],
            'message': '실행 중' if bot_status['is_running'] else '중지됨'
        })
        
    except Exception as e:
        logger.error(f"연결 처리 중 오류 발생: {str(e)}")
        emit('notification', {
            'type': 'error',
            'message': f'연결 중 오류가 발생했습니다: {str(e)}'
        })

@socketio.on('disconnect')
def handle_disconnect():
    """소켓 연결 해제 이벤트 핸들러"""
    logger.info('Client disconnected')

@socketio.on('start_bot')
def handle_start_bot():
    """거래봇 시작"""
    try:
        logger.info("거래봇 시작 시도")
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
            emit('notification', {
                'type': 'error',
                'message': error_msg
            })
            return
        
        # 거래봇 시작
        if market_analyzer.start():
            bot_status['is_running'] = True
            logger.info("거래봇 시작됨")
            
            # 상태 업데이트 브로드캐스트
            socketio.emit('bot_status', {
                'status': True,
                'message': '실행 중'
            }, broadcast=True)
            
            # 성공 알림
            emit('notification', {
                'type': 'success',
                'message': '거래봇이 성공적으로 시작되었습니다.'
            })
            
            # 초기 데이터 전송
            holdings = market_analyzer.get_holdings()
            if holdings:
                socketio.emit('holdings_update', {
                    'holdings': list(holdings.values())
                }, broadcast=True)
        else:
            emit('notification', {
                'type': 'error',
                'message': '거래봇 시작에 실패했습니다.'
            })
            
    except Exception as e:
        error_msg = f"거래봇 시작 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        emit('notification', {
            'type': 'error',
            'message': error_msg
        })
        bot_status['is_running'] = False

@socketio.on('stop_bot')
def handle_stop_bot():
    """거래봇 중지"""
    try:
        logger.info("거래봇 중지 시도")
        emit('notification', {
            'type': 'info',
            'message': '거래봇을 중지하는 중...'
        })
        
        if market_analyzer.stop():
            bot_status['is_running'] = False
            logger.info("거래봇 중지됨")
            
            # 상태 업데이트 브로드캐스트
            socketio.emit('bot_status', {
                'status': False,
                'message': '중지됨'
            }, broadcast=True)
            
            # 성공 알림
            emit('notification', {
                'type': 'success',
                'message': '거래봇이 성공적으로 중지되었습니다.'
            })
        else:
            emit('notification', {
                'type': 'error',
                'message': '거래봇 중지에 실패했습니다.'
            })
            
    except Exception as e:
        error_msg = f"거래봇 중지 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        emit('notification', {
            'type': 'error',
            'message': error_msg
        })

@socketio.on('get_monitored_coins')
def handle_get_monitored_coins():
    """모니터링 중인 코인 목록 조회"""
    try:
        coins = market_analyzer.get_monitored_coins()
        emit('monitored_coins', {'coins': coins})
    except Exception as e:
        error_msg = f"코인 목록 조회 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        emit('error', {'message': error_msg})

@socketio.on('select_coin')
def handle_select_coin(data):
    """코인 선택"""
    try:
        market = data['market']
        # 선택된 코인에 대한 상세 데이터 전송
        coin_data = market_analyzer.get_coin_data(market)
        emit('market_update', coin_data)
        
        # 매수/매도 신호 계산 및 전송
        signals = market_analyzer.calculate_signals(market)
        emit('trade_signals', signals)
    except Exception as e:
        error_msg = f"코인 선택 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        emit('error', {'message': error_msg})

def emit_market_update(market_data):
    """실시간 시장 데이터 전송"""
    try:
        socketio.emit('market_update', market_data)
        
        # 매수/매도 신호 계산 및 전송
        signals = market_analyzer.calculate_signals(market_data['market'])
        socketio.emit('trade_signals', signals)

        # 보유 코인 및 수익 현황 업데이트
        if market_data['market'] in bot_status['holdings']:
            holding = bot_status['holdings'][market_data['market']]
            holding['current_price'] = market_data['trade_price']
            holding['profit_percentage'] = ((market_data['trade_price'] - holding['avg_price']) / holding['avg_price']) * 100
            socketio.emit('holdings_update', {'holdings': list(bot_status['holdings'].values())})
    except Exception as e:
        logger.error(f"시장 데이터 업데이트 중 오류 발생: {str(e)}")

@socketio.on('request_initial_data')
def handle_initial_data():
    """초기 데이터 전송"""
    try:
        # 보유 코인 정보
        holdings = market_analyzer.get_holdings() or {}
        
        # 봇 상태
        emit('bot_status', {
            'status': bot_status['is_running'],
            'message': '실행 중' if bot_status['is_running'] else '중지됨',
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # 보유 코인 정보
        emit('holdings_update', {
            'holdings': list(holdings.values()) if holdings else []
        })
        
        # 모니터링 중인 코인 정보
        monitored_coins = market_analyzer.get_monitored_coins()
        if monitored_coins:
            coin_data = []
            for market in monitored_coins:
                info = market_analyzer.get_market_info(market)
                if info:
                    coin_data.append({
                        'market': market,
                        'current_price': info.get('trade_price', 0),
                        'change_rate': info.get('signed_change_rate', 0) * 100,
                        'volume': info.get('acc_trade_volume_24h', 0),
                        'status': '모니터링 중'
                    })
            
            emit('monitored_coins_update', {
                'coins': coin_data
            })
            
    except Exception as e:
        logger.error(f"초기 데이터 전송 중 오류 발생: {str(e)}")
        emit('error', {'message': str(e)})

def send_holdings_update():
    holdings = market_analyzer.get_holdings()
    balance = market_analyzer.get_balance()
    emit('holdings_update', {'holdings': holdings, 'balance': balance})

def send_monitoring_update():
    """모니터링 업데이트를 클라이언트에 전송"""
    try:
        # 시장 상태 조회
        market_condition, confidence = market_analyzer.analyze_market_condition()
        
        # 모니터링 중인 코인 정보 조회
        monitored_coins = market_analyzer.get_monitored_markets()
        coin_data = []
        
        for market in monitored_coins:
            try:
                market_info = market_analyzer.get_market_info(market)
                if market_info:
                    # 시장 점수 계산
                    score = market_analyzer.calculate_market_score(
                        trend_strength=market_info.get('signed_change_rate', 0),
                        volatility=market_info.get('acc_trade_price_24h', 0) / market_info.get('acc_trade_price', 1),
                        volume_ratio=market_info.get('acc_trade_volume_24h', 0) / market_info.get('acc_trade_volume', 1),
                        market_dominance=market_info.get('market_cap', 0) / market_info.get('total_market_cap', 1)
                    )
                    
                    coin_data.append({
                        'market': market,
                        'current_price': market_info.get('trade_price', 0),
                        'change_rate': market_info.get('signed_change_rate', 0) * 100,
                        'volume': market_info.get('acc_trade_volume_24h', 0),
                        'market_score': score
                    })
            except Exception as e:
                logger.error(f"{market} 데이터 처리 중 오류: {str(e)}")
        
        # 분석 결과 전송
        socketio.emit('market_analysis', {
            'market_condition': market_condition,
            'confidence': confidence,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'coins': coin_data
        }, broadcast=True)
        
    except Exception as e:
        logger.error(f"모니터링 업데이트 중 오류 발생: {str(e)}")

def background_updates():
    """백그라운드에서 주기적으로 업데이트 수행"""
    while True:
        try:
            if bot_status['is_running']:
                # 봇 실행 중에는 시장 분석 데이터를 주기적으로 전송
                send_monitoring_update()
            else:
                # 봇이 중지된 경우에도 모니터링 코인 목록을 갱신하여 전송
                monitored_coins = market_analyzer.get_monitored_coins()
                socketio.emit('monitored_coins_update', {
                    'coins': monitored_coins,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

            time.sleep(20)  # 20초마다 업데이트
        except Exception as e:
            logger.error(f"백그라운드 업데이트 중 오류 발생: {str(e)}")
            time.sleep(5)  # 오류 발생 시 5초 대기 후 재시도

@socketio.on('sell_coin')
def handle_sell_coin(data):
    """개별 코인 시장가 매도"""
    try:
        market = data['market']
        logger.info(f"코인 매도 요청: {market}")
        result = market_analyzer.sell_market_order(market)
        
        if result['success']:
            emit('success', {'message': f"{market} 매도 주문이 완료되었습니다."})
            # 보유 코인 정보 업데이트
            holdings = market_analyzer.get_holdings()
            emit('holdings_update', {'holdings': holdings})
        else:
            emit('error', {'message': f"매도 실패: {result['error']}"})
    except Exception as e:
        error_msg = f"매도 처리 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        emit('error', {'message': error_msg})

@socketio.on('sell_all_coins')
def handle_sell_all_coins():
    """보유한 모든 코인 시장가 매도"""
    try:
        logger.info("전체 코인 매도 요청")
        result = market_analyzer.sell_all_market_order()
        
        if result['success']:
            emit('success', {'message': "모든 코인 매도 주문이 완료되었습니다."})
            # 보유 코인 정보 업데이트
            holdings = market_analyzer.get_holdings()
            emit('holdings_update', {'holdings': holdings})
        else:
            emit('error', {'message': f"매도 실패: {result['error']}"})
    except Exception as e:
        error_msg = f"전체 매도 처리 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        emit('error', {'message': error_msg})

@app.route('/api/bot/init', methods=['GET'])
def init_bot_status():
    """웹 진입 시 초기 상태를 설정합니다."""
    try:
        # 기본적으로 중지 상태로 시작
        bot_status['is_running'] = False
        market_analyzer.stop()
        
        # 모니터링 주기 설정
        market_analyzer.monitoring_interval = 20  # 모니터링 주기 20초
        market_analyzer.update_interval = 60     # 계좌/보유코인 업데이트 주기 60초
        
        # 초기 설정 로드 및 검증
        current_settings = market_analyzer.get_settings()
        if not current_settings:
            current_settings = DEFAULT_SETTINGS.copy()
            market_analyzer.save_settings(current_settings)
            logger.info("기본 설정이 적용되었습니다.")
        
        # 초기 상태 반환
        return jsonify({
            'status': 'success',
            'message': '봇이 중지 상태로 초기화되었습니다.',
            'is_running': False,
            'settings': current_settings
        })
        
    except Exception as e:
        logger.error(f"초기화 중 오류 발생: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'초기화 중 오류 발생: {str(e)}'
        }), 500

def validate_settings_structure(settings):
    """설정 구조의 유효성을 검사하고 누락된 섹션을 보완합니다."""
    try:
        # 기본 설정 복사
        validated_settings = DEFAULT_SETTINGS.copy()
        
        # 받은 설정을 재귀적으로 병합
        def merge_settings(default, new):
            for key, value in new.items():
                if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                    merge_settings(default[key], value)
                else:
                    default[key] = value
        
        merge_settings(validated_settings, settings)
        return validated_settings
        
    except Exception as e:
        logger.error(f'Settings validation error: {str(e)}', exc_info=True)
        return None

def send_notification(message: str, notification_type: str = 'info'):
    """알림 전송 헬퍼 함수"""
    try:
        socketio.emit('notification', {
            'type': notification_type,
            'message': message
        }, broadcast=True)
        logger.info(f"알림 전송: [{notification_type}] {message}")
    except Exception as e:
        logger.error(f"알림 전송 실패: {str(e)}")

@app.route('/api/monitored', methods=['GET'])
def get_monitored_coins():
    """모니터링 중인 코인 목록 조회 API"""
    try:
        logger.info("모니터링 코인 목록 조회 API 호출")
        coins = market_analyzer.get_monitored_coins()
        logger.debug(f"모니터링 코인 데이터: {json.dumps(coins, ensure_ascii=False)}")
        
        response = {
            'status': 'success',
            'data': {
                'coins': coins,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        logger.info(f"모니터링 코인 {len(coins)}개 응답")
        return jsonify(response)
        
    except Exception as e:
        error_msg = f"모니터링 코인 목록 조회 실패: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg
        }), 500

if __name__ == '__main__':
    try:
        # 초기 상태 설정
        bot_status['is_running'] = False
        market_analyzer.stop()  # 확실하게 중지 상태로 시작
        
        # 백그라운드 스레드 시작
        update_thread = threading.Thread(target=background_updates)
        update_thread.daemon = True
        update_thread.start()
        
        # 서버 시작
        logger.info("서버 시작...")
        socketio.run(
            app,
            debug=True,
            host='0.0.0.0',
            port=5000,
            use_reloader=False,
            allow_unsafe_werkzeug=True  # 개발 환경에서만 사용
        )
    except Exception as e:
        logger.error(f"서버 시작 중 오류 발생: {str(e)}") 