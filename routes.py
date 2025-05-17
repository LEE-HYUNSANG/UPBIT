from flask import jsonify, request, Blueprint, render_template
import json
import os
from datetime import datetime
from core.market_analyzer import MarketAnalyzer
from core.upbit_api import UpbitAPI
from core.telegram_notifier import TelegramNotifier
import logging
import socketio
import asyncio
from flask_socketio import SocketIO

# 설정 파일 경로
SETTINGS_FILE = 'config/settings.json'

# 기본 설정값 정의
DEFAULT_SETTINGS = {
    "version": "1.0.0",
    "trading": {
        "enabled": True,
        "investment_amount": 10000,
        "max_coins": 5,
        "coin_selection": {
            "min_price": 700,
            "max_price": 23000,
            "top_volume_count": 20,
            "excluded_coins": ["KRW-ETHW", "KRW-ETHF", "KRW-XCORE", "KRW-GAS"],
            "buy_price_type": "market",
            "sell_price_type": "market"
        }
    },
    "signals": {
        "enabled": False,
        "buy_conditions": {
            "bull": {
                "rsi": 40,
                "sigma": 1.8,
                "vol_prev": 1.5,
                "vol_ma": 1.2,
                "slope": 0.12
            },
            "range": {
                "rsi": 35,
                "sigma": 2.0,
                "vol_prev": 2.0,
                "vol_ma": 1.5,
                "slope": 0.10
            },
            "bear": {
                "rsi": 30,
                "sigma": 2.2,
                "vol_prev": 2.5,
                "vol_ma": 1.8,
                "slope": 0.08
            },
            "enabled": {
                "trend_filter": True,
                "golden_cross": True,
                "rsi": True,
                "bollinger": True,
                "volume_surge": True
            }
        },
        "sell_conditions": {
            "stop_loss": {
                "enabled": True,
                "threshold": -2.5,       # 고정 손절 -2.5%
                "trailing_stop": 0.5     # 추적 손절 0.5%
            },
            "take_profit": {
                "enabled": True,
                "threshold": 2.0,        # 목표 수익 2.0%
                "trailing_profit": 1.0    # 추적 익절 1.0%
            },
            "dead_cross": {
                "enabled": True          # SMA 5/20 데드크로스 & 기울기 ≤ -0.1
            },
            "rsi": {
                "enabled": True,
                "threshold": 60          # RSI ≥ 60 2캔들 연속
            },
            "bollinger": {
                "enabled": True          # BB(20, 2.0) 상단선 돌파
            }
        }
    },
    "notifications": {
        "trade": {
            "start": True,
            "complete": True,
            "profit_loss": True
        },
        "system": {
            "error": True,
            "daily_summary": True,
            "signal": True
        }
    }
}

analyzer = MarketAnalyzer()
api = Blueprint('api', __name__)
logger = logging.getLogger('routes')
upbit = UpbitAPI()

# 텔레그램 알림 초기화
try:
    telegram = TelegramNotifier()
except Exception as e:
    logger.error(f"텔레그램 알림 초기화 실패: {str(e)}")
    telegram = None

def send_telegram_notification(message_type, **kwargs):
    """텔레그램 알림 전송"""
    if not telegram:
        return
        
    try:
        if message_type == 'trade':
            asyncio.run(telegram.notify_trade(**kwargs))
        elif message_type == 'error':
            asyncio.run(telegram.notify_error(**kwargs))
        elif message_type == 'system':
            asyncio.run(telegram.notify_system_metrics(**kwargs))
    except Exception as e:
        logger.error(f"텔레그램 알림 전송 실패: {str(e)}")

def load_settings():
    """
    설정을 로드합니다.
    1. settings.json 파일이 있으면 해당 설정을 사용
    2. 파일이 없으면 default_settings.py의 기본값 사용
    """
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        # 파일이 없는 경우 기본 설정을 저장하고 반환
        save_settings(DEFAULT_SETTINGS.copy())
        return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"설정 로드 중 오류 발생: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """
    설정을 파일에 저장합니다.
    저장된 설정은 이후 기본값으로 사용됩니다.
    """
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"설정 저장 중 오류 발생: {e}")
        return False

@api.route('/api/settings', methods=['GET'])
def get_settings():
    """설정 조회 API"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = DEFAULT_SETTINGS
            save_settings(settings)
        return jsonify(settings)
    except Exception as e:
        logging.error(f'설정 조회 중 오류 발생: {str(e)}', exc_info=True)
        return jsonify({'error': '설정을 불러오는 중 오류가 발생했습니다.'}), 500

@api.route('/api/settings', methods=['POST'])
def save_settings_api():
    """설정 저장 API"""
    try:
        settings = request.get_json()
        save_settings(settings)
        socketio.emit('settings_updated', settings)
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f'설정 저장 중 오류 발생: {str(e)}', exc_info=True)
        return jsonify({'error': '설정을 저장하는 중 오류가 발생했습니다.'}), 500

@api.route('/api/settings/reset', methods=['POST'])
def reset_settings():
    """설정 초기화 API"""
    try:
        save_settings(DEFAULT_SETTINGS)
        socketio.emit('settings_updated', DEFAULT_SETTINGS)
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f'설정 초기화 중 오류 발생: {str(e)}', exc_info=True)
        return jsonify({'error': '설정을 초기화하는 중 오류가 발생했습니다.'}), 500

@api.route('/api/bot/status', methods=['GET'])
def get_bot_status():
    """봇 상태 조회"""
    try:
        # 업비트 API 연결 상태 확인
        account = upbit.get_account()
        is_connected = account is not None
        
        # 봇 상태 정보 구성
        status = {
            'is_running': analyzer.is_running,  # 실제 실행 상태 반영
            'is_connected': is_connected,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': '정상 작동 중' if analyzer.is_running else '중지됨'
        }
        
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        logger.error(f"봇 상태 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'봇 상태 조회 실패: {str(e)}'
        }), 500

@api.route('/api/market/status', methods=['GET'])
def get_market_status():
    """시장 상황 조회"""
    try:
        status = upbit.get_market_status()
        logger.info(f"시장 상황 조회: {status}")
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        logger.error(f"시장 상황 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api.route('/api/balance', methods=['GET'])
def get_balance():
    """계좌 잔고 조회"""
    try:
        accounts = upbit.get_account()
        if not accounts:
            raise Exception("계좌 정보를 가져올 수 없습니다.")
        
        # KRW 잔고 찾기
        krw_account = next((acc for acc in accounts if acc['currency'] == 'KRW'), None)
        balance = float(krw_account['balance']) if krw_account else 0
        
        logger.info(f"잔고 조회: {balance:,.0f}원")
        return jsonify({
            'status': 'success',
            'data': {
                'balance': balance
            }
        })
    except Exception as e:
        logger.error(f"잔고 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api.route('/api/holdings', methods=['GET'])
def get_holdings():
    """보유 코인 조회"""
    try:
        holdings = analyzer.get_holdings()
        
        # 보유 코인 정보 가공
        formatted_holdings = {}
        for holding in holdings:
            formatted_holdings[holding['market']] = {
                'market': holding['market'],
                'currency': holding['currency'],
                'quantity': float(holding['balance']),
                'average_price': float(holding['avg_price']),
                'current_price': float(holding['current_price']),
                'total_value': float(holding['total_value']),
                'profit_rate': float(holding['profit_loss']),
                'status': get_holding_status(float(holding['profit_loss']))
            }
        
        return jsonify({
            'status': 'success',
            'data': {
                'holdings': formatted_holdings
            }
        })
    except Exception as e:
        logger.error(f"보유 코인 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'보유 코인 조회 실패: {str(e)}'
        }), 500

@api.route('/api/monitored', methods=['GET'])
def get_monitored():
    """모니터링 코인 조회"""
    try:
        # 설정에서 필터링 조건 가져오기
        settings = load_settings()
        min_price = settings.get('min_price', 500)
        max_price = settings.get('max_price', 23000)
        
        # 모든 KRW 마켓 정보 조회
        markets = upbit.get_monitored_markets()
        monitored_coins = []
        
        # 각 마켓의 정보 수집
        for market in markets:
            market_code = market['market']
            info = upbit.get_market_info(market_code)
            
            if info:
                # 가격 범위 필터링
                if min_price <= info['trade_price'] <= max_price:
                    # 기술적 지표 계산
                    indicators = analyzer.calculate_indicators(market_code)
                    
                    monitored_coins.append({
                        'market': market_code,
                        'name': market.get('korean_name', market_code),
                        'current_price': info['trade_price'],
                        'change_rate': info['signed_change_rate'] * 100,
                        'trade_volume': info['acc_trade_price_24h'],
                        'indicators': {
                            'trend_15m': indicators.get('trend_15m', False),
                            'golden_cross': indicators.get('golden_cross', False),
                            'rsi_oversold': indicators.get('rsi_oversold', False),
                            'bollinger_band': indicators.get('bollinger_band', False),
                            'volume_surge': indicators.get('volume_surge', False)
                        },
                        'signal_strength': calculate_signal_strength(info, indicators),
                        'status': get_market_status(info, indicators)
                    })
        
        # 거래량 기준으로 정렬
        monitored_coins.sort(key=lambda x: x['trade_volume'], reverse=True)
        
        # 상위 20개만 선택 (또는 설정된 값)
        top_volume = settings.get('top_volume', 20)
        monitored_coins = monitored_coins[:top_volume]
        
        logger.info(f"모니터링 코인 조회: {len(monitored_coins)}개")
        return jsonify({
            'status': 'success',
            'data': {
                'coins': monitored_coins
            }
        })
    except Exception as e:
        logger.error(f"모니터링 코인 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_holding_status(profit_rate):
    """보유 코인 상태 판단"""
    if profit_rate >= 5:
        return '높은 수익'
    elif profit_rate >= 2:
        return '수익'
    elif profit_rate >= -2:
        return '소폭 손실'
    else:
        return '손실'

def calculate_signal_strength(market_info, indicators):
    """매수/매도 신호 강도 계산"""
    try:
        change_rate = market_info['signed_change_rate']
        volume_rate = market_info['acc_trade_volume_24h'] / market_info['acc_trade_volume']
        
        # 신호 강도를 0~1 사이 값으로 정규화
        strength = (abs(change_rate) * 0.7 + min(volume_rate, 2) * 0.3) / 2
        return min(strength, 1.0)
    except:
        return 0.5

def get_market_status(market_info, indicators):
    """시장 상태 판단"""
    try:
        change_rate = market_info['signed_change_rate'] * 100
        if change_rate >= 3:
            return '강력 매수'
        elif change_rate >= 1:
            return '매수'
        elif change_rate <= -3:
            return '매도'
        elif change_rate <= -1:
            return '관망'
        else:
            return '관망'
    except:
        return '관망'

@api.route('/api/trade/sell', methods=['POST'])
def execute_market_sell():
    """시장가 매도 API"""
    try:
        data = request.get_json()
        market = data.get('market')
        
        if not market:
            return jsonify({
                'status': 'error',
                'message': '마켓 코드가 필요합니다.'
            }), 400
            
        success = analyzer._execute_sell(market, reason='수동 매도')
        
        return jsonify({
            'status': 'success' if success else 'error',
            'message': '매도 주문이 실행되었습니다.' if success else '매도 주문 실패'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api.route('/api/bot/start', methods=['POST'])
def start_bot():
    """봇 시작"""
    try:
        analyzer.start()
        if telegram:
            asyncio.run(telegram.notify_system_start())
        return jsonify({
            'status': 'success',
            'message': '봇이 시작되었습니다.'
        })
    except Exception as e:
        logger.error(f"봇 시작 실패: {str(e)}")
        if telegram:
            asyncio.run(telegram.notify_error(str(e)))
        return jsonify({
            'status': 'error',
            'message': f'봇 시작 실패: {str(e)}'
        }), 500

@api.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """봇 중지"""
    try:
        analyzer.stop()
        if telegram:
            asyncio.run(telegram.notify_system_stop("사용자 요청"))
        
        # 상태 업데이트 및 클라이언트에 알림
        socketio.emit('bot_status', {
            'is_running': False,
            'message': '봇이 중지되었습니다.',
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, broadcast=True)
        
        return jsonify({
            'status': 'success',
            'message': '봇이 중지되었습니다.',
            'data': {
                'is_running': False,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        logger.error(f"봇 중지 실패: {str(e)}")
        if telegram:
            asyncio.run(telegram.notify_error(str(e)))
        return jsonify({
            'status': 'error',
            'message': f'봇 중지 실패: {str(e)}'
        }), 500

@api.route('/api/history', methods=['GET'])
def get_trade_history():
    """거래 내역 조회"""
    try:
        history = analyzer.get_trade_history()
        return jsonify({
            'status': 'success',
            'data': history
        })
    except Exception as e:
        logger.error(f"거래 내역 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api.route('/api/logs', methods=['GET'])
def get_logs():
    """로그 조회"""
    try:
        # 로그 파일 경로
        log_file = 'logs/trading.log'
        
        # 파일이 없으면 빈 로그 반환
        if not os.path.exists(log_file):
            return jsonify({
                'status': 'success',
                'data': {
                    'logs': []
                }
            })
        
        # 최근 100줄만 읽기
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.readlines()[-100:]
        
        return jsonify({
            'status': 'success',
            'data': {
                'logs': logs
            }
        })
    except Exception as e:
        logger.error(f"로그 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@api.route('/settings')
def settings_page():
    """설정 페이지 렌더링"""
    return render_template('settings.html')

@api.route('/history')
def history_page():
    """거래내역 페이지 렌더링"""
    return render_template('history.html')

@api.route('/logs')
def logs_page():
    """로그 페이지 렌더링"""
    return render_template('logs.html')

# Socket.IO 초기화
socketio = SocketIO()

def init_app(app):
    # Blueprint 등록
    app.register_blueprint(api)
    
    # Socket.IO 초기화
    socketio.init_app(app)
    
    # 초기 설정 파일 생성
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS) 