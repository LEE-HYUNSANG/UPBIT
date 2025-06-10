// 소켓 연결 설정
const socket = io();

// DOM 요소
const botStatus = document.getElementById('bot-status');
const startBotButton = document.getElementById('toggleBot');
if (startBotButton) {
    startBotButton.disabled = true;
}
const monitoredCoinsTable = document.getElementById('monitored-coins');
const holdingsTable = document.getElementById('holdingsTableBody');
const statusIndicator = document.getElementById('botStatus');
const marketConditionDiv = document.getElementById('marketCondition');
const marketConfidence = document.getElementById('marketConfidence');
const lastUpdate = document.getElementById('lastUpdate');

// 수익 현황 요소
const totalProfit = document.getElementById('total-profit');
const profitPercentage = document.getElementById('profit-percentage');
const totalInvestment = document.getElementById('total-investment');
const totalCoins = document.getElementById('total-coins');

// 알림 표시 함수
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.style.position = 'fixed';
    alertDiv.style.top = '20px';
    alertDiv.style.right = '20px';
    alertDiv.style.zIndex = '1050';
    alertDiv.style.minWidth = '300px';
    alertDiv.style.boxShadow = '0 0.5rem 1rem rgba(0, 0, 0, 0.15)';
    
    alertDiv.innerHTML = `
        <strong>${type === 'danger' ? '오류' : '알림'}</strong>: ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // 5초 후 자동으로 사라지게 설정
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

let monitoredCoins = new Map();
let holdings = new Map();

// 거래봇 상태 업데이트
function updateBotStatus(isRunning) {
    const status = isRunning ? '실행 중' : '중지됨';
    const buttonText = isRunning ? '중지' : '시작';
    const statusClass = isRunning ? 'text-success' : 'text-danger';
    
    statusIndicator.textContent = status;
    statusIndicator.className = statusClass;
    startBotButton.textContent = buttonText;
    startBotButton.className = `btn ${isRunning ? 'btn-danger' : 'btn-primary'}`;

    // 수익 현황 업데이트
    if (isRunning) {
        totalProfit.textContent = new Intl.NumberFormat('ko-KR', { 
            style: 'currency', 
            currency: 'KRW' 
        }).format(data.total_profit);
        
        profitPercentage.textContent = `${data.profit_percentage.toFixed(2)}%`;
        profitPercentage.className = data.profit_percentage >= 0 ? 'text-success' : 'text-danger';
        
        totalInvestment.textContent = new Intl.NumberFormat('ko-KR', { 
            style: 'currency', 
            currency: 'KRW' 
        }).format(data.total_investment);
        
        if (data.holdings) {
            totalCoins.textContent = `${data.holdings.length}개`;
            updateHoldings(data.holdings);
        }
    }
}

// 보유 코인 목록 업데이트
function updateHoldings(holdingsList) {
    holdings.clear();
    
    // 데이터가 없는 경우 처리
    if (!holdingsList || holdingsList.length === 0) {
        holdingsTable.innerHTML = `
            <tr>
                <td colspan="8" class="text-center">보유 중인 코인이 없습니다.</td>
            </tr>
        `;
        return;
    }
    
    holdingsTable.innerHTML = holdingsList.map(holding => {
        holdings.set(holding.market, holding);
        const profitClass = holding.profit_rate >= 0 ? 'text-success' : 'text-danger';
        
        // 숫자 포맷팅
        const formatNumber = (num) => {
            return new Intl.NumberFormat('ko-KR', {
                style: 'currency',
                currency: 'KRW'
            }).format(num);
        };
        
        return `
            <tr>
                <td>${holding.market}</td>
                <td>${formatNumber(holding.current_price)}</td>
                <td>${formatNumber(holding.avg_price)}</td>
                <td>${formatNumber(holding.balance, 8)}</td>
                <td>${formatNumber(holding.total_value)}</td>
                <td class="${profitClass}">${formatNumber(holding.profit_loss, 2)}%</td>
                <td>${holding.status || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="sellCoin('${holding.market}')">매도</button>
                </td>
            </tr>
        `;
    }).join('');
}

// 모니터링 코인 목록 업데이트
function updateMonitoredCoins(coins) {
    monitoredCoins.clear();
    const tableBody = document.getElementById('monitoredCoinsTableBody');
    
    // 데이터가 없는 경우 처리
    if (!coins || coins.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center">모니터링 중인 코인이 없습니다.</td>
            </tr>
        `;
        return;
    }
    
    tableBody.innerHTML = coins.map(coin => {
        monitoredCoins.set(coin.market, coin);
        
        // 신호 표시 함수
        const signalMark = (value, signal_value) => {
            if (signal_value === undefined) return '×';
            return value ? `○ (${signal_value})` : `× (${signal_value})`;
        };
        
        // 숫자 포맷팅
        const formatNumber = (num) => {
            if (typeof num === 'number') {
                return num.toLocaleString('ko-KR');
            }
            return num || '-';
        };
        
        const formatPercent = (num) => {
            if (typeof num === 'number') {
                return `${num.toFixed(2)}%`;
            }
            return '-';
        };
        
        return `
            <tr>
                <td>${coin.name || coin.market}</td>
                <td>${coin.market}</td>
                <td>${signalMark(coin.indicators?.trend_filter, formatPercent(coin.values?.slope))}</td>
                <td>${signalMark(coin.indicators?.golden_cross, formatPercent(coin.values?.sma5))}</td>
                <td>${signalMark(coin.indicators?.rsi_oversold, formatNumber(coin.values?.rsi))}</td>
                <td>${signalMark(coin.indicators?.bollinger_break, formatNumber(coin.values?.bb_lower))}</td>
                <td>${signalMark(coin.indicators?.volume_surge, formatNumber(coin.values?.volume_ratio))}</td>
                <td><span class="badge bg-info">${coin.status || '모니터링'}</span></td>
                <td>
                    <button class="btn btn-sm btn-success" onclick="marketBuy('${coin.market}')">
                        매수
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// 소켓 이벤트 리스너
socket.on('connect', () => {
    console.log('서버에 연결되었습니다.');
    showNotification('서버에 연결되었습니다.', 'success');
});

socket.on('disconnect', () => {
    console.log('서버와의 연결이 끊어졌습니다.');
    showNotification('서버와의 연결이 끊어졌습니다. 페이지를 새로고침해주세요.', 'danger');
    updateBotStatus(false);
});

socket.on('bot_status', (data) => {
    console.log('봇 상태 업데이트:', data);
    updateBotStatus(data.status);
});

socket.on('error', (data) => {
    console.error('에러 발생:', data.message);
    showNotification(data.message, 'danger');
});

socket.on('success', (data) => {
    console.log('성공:', data.message);
    showNotification(data.message, 'success');
});

socket.on('market_analysis', (data) => {
    console.log('시장 분석 데이터:', data);
    updateMarketAnalysis(data);
});

socket.on('holdings_update', (data) => {
    console.log('보유 코인 업데이트:', data);
    if (data && data.holdings) {
        updateHoldings(data.holdings);
    }
});

// 시장 분석 결과 업데이트 함수
function updateMarketAnalysis(data) {
    marketConditionDiv.textContent = data.market_condition || '-';
    marketConfidence.textContent = data.confidence ? `${(data.confidence * 100).toFixed(2)}%` : '-';
    lastUpdate.textContent = data.timestamp || '-';
}

// 숫자 포맷팅 함수
function formatNumber(number, decimals = 0) {
    if (typeof number !== 'number') {
        number = parseFloat(number) || 0;
    }
    return number.toLocaleString('ko-KR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

// 코인 매도 함수
function sellCoin(market) {
    if (confirm(`${market}을(를) 매도하시겠습니까?`)) {
        socket.emit('sell_coin', { market });
    }
}

// 시작/중지 버튼은 비활성화되어 있습니다.

// 페이지 로드 시 초기 데이터 요청
socket.emit('request_initial_data');

// 봇 컨트롤 버튼 이벤트 리스너
document.addEventListener('DOMContentLoaded', function() {
    // 설정 버튼
    document.getElementById('settingsBtn').addEventListener('click', function() {
        window.location.href = '/settings';
    });

    // 거래내역 버튼
    document.getElementById('historyBtn').addEventListener('click', function() {
        window.location.href = '/history';
    });

    // 로그 버튼
    document.getElementById('logsBtn').addEventListener('click', function() {
        window.location.href = '/logs';
    });
});