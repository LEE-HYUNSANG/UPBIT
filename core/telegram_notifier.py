"""
텔레그램 알림 모듈
이 모듈은 거래 시스템의 주요 이벤트를 텔레그램으로 알림을 보내는 기능을 제공합니다.

주요 기능:
- 시스템 상태 모니터링 (5분 간격)
- 거래 실행 알림 (매수/매도)
- 수익/손실 알림
- 에러 및 경고 알림
- 일일 성과 보고
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv
from pathlib import Path
import logging
import requests

dotenv_path = Path(__file__).resolve().parents[1] / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    load_dotenv()

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    텔레그램 알림을 담당하는 클래스
    
    거래 시스템의 주요 이벤트를 텔레그램으로 전송하여
    실시간으로 거래 상황을 모니터링할 수 있게 합니다.
    """
    
    def __init__(self, config: dict = None):
        """
        텔레그램 알림 초기화
        
        Args:
            config (dict, optional): 시스템 설정
        """
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.config = config or {}
        
        if not self.bot_token or not self.chat_id:
            logger.error("텔레그램 API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            raise ValueError("텔레그램 설정이 없습니다.")
            
        self.bot = Bot(token=self.bot_token)
        self.last_heartbeat = datetime.now()
        self.last_activity = datetime.now()
        self.last_activity_type = "시스템 시작"
        self.system_running = False
        self.monitoring_task = None
        self.activity_check_task = None
        
    async def start_monitoring(self):
        """시스템 상태 모니터링 시작"""
        self.system_running = True
        self.last_heartbeat = datetime.now()
        self.last_activity = datetime.now()
        self.monitoring_task = asyncio.create_task(self._monitor_system_status())
        self.activity_check_task = asyncio.create_task(self._check_activity_status())
        await self.notify_system_start()
        
    async def stop_monitoring(self, reason: str = "정상 종료"):
        """
        시스템 상태 모니터링 종료
        
        Args:
            reason (str): 종료 사유
        """
        self.system_running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.activity_check_task:
            self.activity_check_task.cancel()
        await self.notify_system_stop(reason)
        
    async def update_heartbeat(self):
        """시스템 활성 상태 업데이트"""
        self.last_heartbeat = datetime.now()
        
    async def update_activity(self, activity_type: str):
        """
        시스템 활동 상태 업데이트
        
        Args:
            activity_type (str): 활동 유형 (예: "매수", "매도", "모니터링" 등)
        """
        self.last_activity = datetime.now()
        self.last_activity_type = activity_type
        # 활동이 발생하면 하트비트도 함께 갱신하여
        # 모니터링 루프가 비정상 종료로 오인하지 않도록 한다
        self.last_heartbeat = datetime.now()
        
    async def _monitor_system_status(self):
        """시스템 상태 주기적 모니터링 (5분 간격)"""
        while self.system_running:
            await asyncio.sleep(300)  # 5분 간격
            if datetime.now() - self.last_heartbeat > timedelta(minutes=5):
                await self.notify_system_stop("비정상 종료 감지 - 하트비트 없음")
                self.system_running = False
                break
        
    async def _check_activity_status(self):
        """시스템 활동 상태 체크 (5분 간격)"""
        while self.system_running:
            await asyncio.sleep(300)  # 5분 간격
            
            # 마지막 활동으로부터 경과 시간
            elapsed_time = datetime.now() - self.last_activity
            
            # 현재 시스템 상태 요약
            await self.notify_activity_status(elapsed_time)
            
    async def notify_activity_status(self, elapsed_time: timedelta):
        """
        시스템 활동 상태 알림
        
        Args:
            elapsed_time (timedelta): 마지막 활동으로부터 경과 시간
        """
        minutes = elapsed_time.total_seconds() / 60
        
        message = "🔄 <b>시스템 상태 체크</b>\n\n"
        message += f"⏱ 마지막 활동: {minutes:.1f}분 전\n"
        message += f"📝 활동 내용: {self.last_activity_type}\n"
        
        # 현재 시간이 거래 시간인지 확인
        current_time = datetime.now().time()
        if self.config and 'trading' in self.config:
            trading_hours = self.config['trading'].get('trading_hours', {})
            start_time = datetime.strptime(trading_hours.get('start', '09:00'), '%H:%M').time()
            end_time = datetime.strptime(trading_hours.get('end', '23:00'), '%H:%M').time()
            
            if start_time <= current_time <= end_time:
                message += "⏰ 거래 시간 중\n"
            else:
                message += "💤 거래 시간 외\n"
                
        # 시스템 리소스 사용량 추가
        try:
            import psutil
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.Process().memory_percent()
            message += f"\n🖥 시스템 리소스:\n"
            message += f"- CPU: {cpu_percent:.1f}%\n"
            message += f"- 메모리: {memory_percent:.1f}%"
        except ImportError:
            pass
            
        await self.send_message(message)
        
    async def send_message(self, message: str):
        """
        텔레그램으로 메시지 전송
        
        Args:
            message (str): 전송할 메시지
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"텔레그램 메시지 전송 성공: {message[:50]}...")
        except TelegramError as e:
            logger.error(f"텔레그램 메시지 전송 실패: {str(e)}")
        finally:
            # 메시지를 전송할 때마다 하트비트를 갱신하여
            # 주기적인 모니터링에서 정상 동작으로 판단하게 한다
            self.last_heartbeat = datetime.now()
            
    async def notify_system_start(self):
        """시스템 시작 알림"""
        message = "🟢 <b>자동매매 시스템 시작</b>\n\n"
        
        if self.config:
            message += "📋 시스템 설정:\n"
            message += f"- 기본 주문금액: {self.config['trading']['base_order_amount']:,}원\n"
            message += f"- 최대 포지션: {self.config['trading']['max_positions']}개\n"
            message += f"- 일일 손실한도: {self.config['risk_management']['system']['max_daily_loss']:,}원\n"
            
        message += f"\n⏰ 시작 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await self.send_message(message)
        
    async def notify_system_stop(self, reason: str):
        """
        시스템 종료 알림
        
        Args:
            reason (str): 종료 사유
        """
        message = "🔴 <b>자동매매 시스템 종료</b>\n\n"
        message += f"📝 종료 사유: {reason}\n"
        message += f"⏰ 종료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await self.send_message(message)
            
    async def notify_trade(self, action: str, market: str, price: float, 
                         volume: float, profit: Optional[float] = None,
                         reason: str = None):
        """
        거래 실행 알림
        
        Args:
            action (str): 거래 유형 (매수/매도)
            market (str): 거래 마켓 코드
            price (float): 거래 가격
            volume (float): 거래량
            profit (float, optional): 실현 수익률 (%)
            reason (str, optional): 거래 사유
        """
        await self.update_activity(f"{action} - {market}")
        
        emoji = "🔵" if action == "매수" else "🔴"
        message = f"{emoji} <b>{action}</b>\n"
        message += f"마켓: {market}\n"
        message += f"가격: {price:,.0f}원\n"
        message += f"수량: {volume:.8f}\n"
        message += f"금액: {(price * volume):,.0f}원\n"
        
        if profit is not None:
            emoji = "📈" if profit > 0 else "📉"
            message += f"수익률: {emoji} {profit:.2f}%\n"
            
        if reason:
            message += f"사유: {reason}"
            
        await self.send_message(message)
        
    async def notify_error(self, error_msg: str, critical: bool = False):
        """
        에러 발생 알림
        
        Args:
            error_msg (str): 에러 메시지
            critical (bool): 심각한 에러 여부
        """
        emoji = "🚨" if critical else "⚠️"
        message = f"{emoji} <b>{'심각한 ' if critical else ''}에러 발생</b>\n{error_msg}"
        await self.send_message(message)
        
    async def notify_daily_summary(self, metrics: dict):
        """
        일일 성과 요약 알림
        
        Args:
            metrics (dict): 성과 지표 정보를 담은 딕셔너리
        """
        message = "📊 <b>일일 거래 성과</b>\n\n"
        
        # 주요 지표 추가
        if 'total_profit' in metrics:
            profit = metrics['total_profit']
            emoji = "📈" if profit > 0 else "📉"
            message += f"총 수익: {emoji} {profit:,.0f}원\n"
            
        if 'win_rate' in metrics:
            message += f"승률: {metrics['win_rate']:.1f}%\n"
            
        if 'total_trades' in metrics:
            message += f"총 거래: {metrics['total_trades']}회\n"
            
        if 'max_drawdown' in metrics:
            message += f"최대 손실폭: {metrics['max_drawdown']:.1f}%\n"
            
        if 'profit_factor' in metrics:
            message += f"수익 팩터: {metrics['profit_factor']:.2f}\n"
            
        if 'average_profit' in metrics:
            avg_profit = metrics['average_profit']
            emoji = "📈" if avg_profit > 0 else "📉"
            message += f"평균 수익: {emoji} {avg_profit:,.0f}원\n"
            
        await self.send_message(message)
        
    async def notify_risk_alert(self, risk_type: str, details: str, level: str = "주의"):
        """
        위험 관리 알림
        
        Args:
            risk_type (str): 위험 유형
            details (str): 세부 내용
            level (str): 경고 수준 (주의/경고/심각)
        """
        emoji_map = {
            "주의": "⚠️",
            "경고": "🚨",
            "심각": "❌"
        }
        emoji = emoji_map.get(level, "⚠️")
        
        message = f"{emoji} <b>위험 관리 알림</b>\n"
        message += f"수준: {level}\n"
        message += f"유형: {risk_type}\n"
        message += f"내용: {details}"
        
        await self.send_message(message)
        
    async def notify_market_status(self, market_data: Dict):
        """
        시장 상태 알림
        
        Args:
            market_data (Dict): 시장 데이터 정보
        """
        message = "🌐 <b>시장 상태 업데이트</b>\n\n"
        
        # 거래량 상위 코인
        if 'top_volume' in market_data:
            message += "📊 거래량 상위:\n"
            for coin in market_data['top_volume'][:5]:
                message += f"- {coin['market']}: {coin['volume']:,.0f}원\n"
                
        # 가격 변동 큰 코인
        if 'price_change' in market_data:
            message += "\n📈 가격 변동 상위:\n"
            for coin in market_data['price_change'][:5]:
                emoji = "🔺" if coin['change'] > 0 else "🔻"
                message += f"- {coin['market']}: {emoji}{abs(coin['change']):.2f}%\n"
                
        await self.send_message(message)
        
    async def notify_position_update(self, positions: Dict):
        """
        포지션 상태 업데이트 알림
        
        Args:
            positions (Dict): 현재 보유 포지션 정보
        """
        if not positions:
            return
            
        message = "📍 <b>포지션 현황</b>\n\n"
        
        total_profit = 0
        for market, pos in positions.items():
            profit_percent = pos.get('profit_percent', 0)
            emoji = "📈" if profit_percent > 0 else "📉"
            message += f"{market}:\n"
            message += f"- 평가손익: {emoji} {profit_percent:.2f}%\n"
            message += f"- 보유량: {pos['volume']:.8f}\n"
            total_profit += pos.get('unrealized_profit', 0)
            
        message += f"\n총 평가손익: {'📈' if total_profit > 0 else '📉'} {total_profit:,.0f}원"
        await self.send_message(message)
        
    async def notify_system_metrics(self, metrics: Dict):
        """
        시스템 메트릭 알림
        
        Args:
            metrics (Dict): 시스템 성능 지표
        """
        message = "🔧 <b>시스템 상태</b>\n\n"
        
        if 'cpu_usage' in metrics:
            message += f"CPU 사용률: {metrics['cpu_usage']:.1f}%\n"
        if 'memory_usage' in metrics:
            message += f"메모리 사용률: {metrics['memory_usage']:.1f}%\n"
        if 'api_calls' in metrics:
            message += f"API 호출 수: {metrics['api_calls']}회\n"
        if 'response_time' in metrics:
            message += f"평균 응답시간: {metrics['response_time']:.2f}ms\n"
            
        await self.send_message(message)
        
    async def notify_market_analysis(self, market: str, analysis: Dict):
        """
        시장 분석 결과 알림
        
        Args:
            market (str): 마켓 코드
            analysis (Dict): 분석 결과
        """
        await self.update_activity(f"시장 분석 - {market}")
        
        message = f"📊 <b>{market} 시장 분석</b>\n\n"
        
        # 기술적 지표
        if 'indicators' in analysis:
            message += "📈 기술적 지표:\n"
            indicators = analysis['indicators']
            if 'rsi' in indicators:
                message += f"- RSI: {indicators['rsi']:.2f}\n"
            if 'macd' in indicators:
                message += f"- MACD: {indicators['macd']:.2f}\n"
            if 'volume_ma' in indicators:
                message += f"- 거래량 MA: {indicators['volume_ma']:,.0f}\n"
                
        # 추세 분석
        if 'trend' in analysis:
            trend = analysis['trend']
            emoji = "📈" if trend['direction'] == "상승" else "📉"
            message += f"\n{emoji} 추세:\n"
            message += f"- 방향: {trend['direction']}\n"
            message += f"- 강도: {trend['strength']}\n"
            
                
        await self.send_message(message)
        
    async def notify_risk_status(self, risk_metrics: Dict):
        """
        위험 관리 상태 알림
        
        Args:
            risk_metrics (Dict): 위험 관리 지표
        """
        await self.update_activity("위험 관리 상태 체크")
        
        message = "⚠️ <b>위험 관리 상태</b>\n\n"
        
        # 일일 손실 현황
        if 'daily_loss' in risk_metrics:
            daily_loss = risk_metrics['daily_loss']
            max_daily_loss = risk_metrics.get('max_daily_loss', 0)
            loss_percentage = (daily_loss / max_daily_loss * 100) if max_daily_loss else 0
            
            message += "💰 일일 손실 현황:\n"
            message += f"- 현재 손실: {daily_loss:,.0f}원\n"
            message += f"- 한도 대비: {loss_percentage:.1f}%\n"
            
        # 연속 손실
        if 'consecutive_losses' in risk_metrics:
            message += f"\n📉 연속 손실: {risk_metrics['consecutive_losses']}회\n"
            
        # 포지션 위험도
        if 'position_risk' in risk_metrics:
            pos_risk = risk_metrics['position_risk']
            message += f"\n📊 포지션 위험도:\n"
            message += f"- 총 노출도: {pos_risk.get('exposure', 0):.1f}%\n"
            message += f"- 최대 손실 위험: {pos_risk.get('max_loss_risk', 0):.1f}%\n"
            
        await self.send_message(message)
        
    async def send_trade_alert(self, trade_type, coin, price, amount):
        """거래 알림을 전송합니다."""
        message = f"🔔 <b>거래 알림</b>\n"
        message += f"유형: {'매수' if trade_type == 'buy' else '매도'}\n"
        message += f"코인: {coin}\n"
        message += f"가격: {price:,} KRW\n"
        message += f"수량: {amount:.8f}"
        
        await self.send_message(message)
        
    async def send_error_alert(self, error_message):
        """에러 알림을 전송합니다."""
        message = f"⚠️ <b>에러 발생</b>\n{error_message}"
        await self.send_message(message)
        
    async def send_system_status(self, status_message):
        """시스템 상태 알림을 전송합니다."""
        message = f"ℹ️ <b>시스템 상태</b>\n{status_message}"
        await self.send_message(message)
        
    def is_enabled(self) -> bool:
        """텔레그램 알림 활성화 여부 확인"""
        return bool(self.bot_token and self.chat_id)

    def send_message_sync(self, message: str):
        """동기 방식으로 메시지 전송"""
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                data={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            response.raise_for_status()
            logger.info(f"텔레그램 메시지 전송 성공: {message[:50]}...")
            return True
        except requests.RequestException as e:
            logger.error(f"텔레그램 메시지 전송 실패: {str(e)}")
            return False

    def send_trade_alert_sync(self, trade_type: str, coin: str, price: float, amount: float):
        """동기 방식으로 거래 알림 전송"""
        message = f"💰 <b>거래 알림</b>\n\n"
        message += f"유형: {trade_type}\n"
        message += f"코인: {coin}\n"
        message += f"가격: {price:,.0f}원\n"
        message += f"수량: {amount:.8f}\n"
        message += f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self.send_message_sync(message)

    def send_error_alert_sync(self, error_message: str):
        """동기 방식으로 에러 알림 전송"""
        message = f"⚠️ <b>에러 발생</b>\n\n{error_message}"
        return self.send_message_sync(message)

    def send_system_status_sync(self, status_message: str):
        """동기 방식으로 시스템 상태 알림 전송"""
        message = f"ℹ️ <b>시스템 상태</b>\n\n{status_message}"
        return self.send_message_sync(message) 
