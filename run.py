from web.app import app, socketio
import requests
from requests.exceptions import RequestException, Timeout
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        logger.info("웹 서버 시작...")
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    except Exception as e:
        logger.error(f"서버 실행 중 오류 발생: {str(e)}")

def get_market_index_data(self, force_update: bool = False):
    # 캐시 사용으로 API 호출 최소화
    if not force_update and self._is_cache_valid(self.market_cache['last_update']):
        return self.market_cache['prices'], self.market_cache['volumes'] 

def analyze_market_condition(self):
    logger.info("시장 상황 분석 시작")
    # 상세한 로그 추가
    logger.debug(f"분석 지표: 추세={trend:.2f}, 변동성={volatility:.2f}") 

def validate_config(self, config):
    # 설정값 범위 검증 추가
    if config['investment_amount'] <= 0:
        raise ValueError("투자금액은 0보다 커야 합니다")
    if not (0 < config['stop_loss'] < 100):
        raise ValueError("손절 비율이 올바르지 않습니다") 