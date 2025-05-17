// 전역 변수
let isRunning = false;
let updateTimers = {};

// 로깅 함수
function logToConsole(type, message) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] ${type.toUpperCase()}: ${message}`);
}

// 숫자 포맷팅 함수
function formatNumber(num) {
    return new Intl.NumberFormat('ko-KR').format(num);
}

// 날짜 포맷팅 함수
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString('ko-KR');
}

// API 호출 함수
async function fetchAPI(endpoint, options = {}) {
    try {
        logToConsole('debug', `API 호출: ${endpoint}`);
        const response = await fetch(endpoint, options);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        logToConsole('debug', `API 응답: ${JSON.stringify(data)}`);
        return data;
    } catch (error) {
        logToConsole('error', `API 오류 (${endpoint}): ${error.message}`);
        throw error;
    }
}

// 봇 상태 업데이트
async function updateBotStatus() {
    try {
        const data = await fetchAPI('/api/bot/status');
        
        if (data.status === 'success') {
            isRunning = data.data.is_running;
            const statusText = isRunning ? '실행 중' : '중지됨';
            const buttonText = isRunning ? '중지' : '시작';
            const buttonClass = isRunning ? 'btn-danger' : 'btn-primary';
            
            document.getElementById('botStatus').textContent = statusText;
            const toggleButton = document.getElementById('toggleBot');
            toggleButton.textContent = buttonText;
            toggleButton.className = `btn ${buttonClass}`;
            
            if (data.data.last_update) {
                document.getElementById('lastUpdate').textContent = formatDate(data.data.last_update);
            }
            
            logToConsole('info', `봇 상태 업데이트: ${statusText}`);
        }
    } catch (error) {
        logToConsole('error', '봇 상태 조회 실패');
    }
}

// 시장 상황 업데이트
async function updateMarketStatus() {
    try {
        const data = await fetchAPI('/api/market/status');
        
        if (data.status === 'success') {
            const condition = data.data.condition;
            const confidence = (data.data.confidence * 100).toFixed(1);
            
            const conditionText = 
                condition === 'BULL' ? '상승장' :
                condition === 'BEAR' ? '하락장' : '횡보장';
                
            document.getElementById('marketCondition').textContent = conditionText;
            document.getElementById('marketConfidence').textContent = `${confidence}%`;
            
            logToConsole('info', `시장 상황 업데이트: ${conditionText} (${confidence}%)`);
        }
    } catch (error) {
        logToConsole('error', '시장 상황 조회 실패');
    }
}

// 계좌 정보 업데이트
async function updateBalance() {
    try {
        const data = await fetchAPI('/api/balance');
        
        if (data.status === 'success') {
            const balance = data.data.balance;
            document.getElementById('balance').textContent = 
                formatNumber(balance) + ' KRW';
            
            logToConsole('info', `잔고 업데이트: ${formatNumber(balance)} KRW`);
        }
    } catch (error) {
        logToConsole('error', '잔고 조회 실패');
    }
}

// 보유 코인 업데이트
async function updateHoldings() {
    try {
        const data = await fetchAPI('/api/holdings');
        
        if (data.status === 'success') {
            const holdings = data.data.holdings;
            const tbody = document.getElementById('holdingsTableBody');
            tbody.innerHTML = '';
            
            let totalValue = 0;
            let totalInvestment = 0;
            
            if (Object.keys(holdings).length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="8" class="text-center">보유 중인 코인이 없습니다.</td>
                    </tr>
                `;
                return;
            }
            
            for (const [market, holding] of Object.entries(holdings)) {
                totalValue += holding.total_value;
                totalInvestment += holding.average_price * holding.quantity;
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="coin-symbol">${market}</td>
                    <td>${formatNumber(holding.current_price)}</td>
                    <td>${formatNumber(holding.average_price)}</td>
                    <td>${holding.quantity.toFixed(8)}</td>
                    <td>${formatNumber(holding.total_value)}</td>
                    <td class="${holding.profit_rate >= 0 ? 'profit-positive' : 'profit-negative'}">
                        ${holding.profit_rate.toFixed(2)}%
                    </td>
                    <td>
                        <span class="badge ${getStatusBadgeClass(holding.status)} status-badge">
                            ${holding.status}
                        </span>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="sellCoin('${market}')">
                            매도
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            }
            
            // 총 자산 및 수익률 업데이트
            const balance = parseFloat(document.getElementById('balance').textContent.replace(/[^0-9.-]+/g, ''));
            const totalAsset = balance + totalValue;
            const totalProfitRate = ((totalValue - totalInvestment) / totalInvestment * 100) || 0;
            
            document.getElementById('totalAsset').textContent = formatNumber(totalAsset) + ' KRW';
            document.getElementById('totalProfitRate').textContent = 
                `${totalProfitRate.toFixed(2)}% (${formatNumber(totalValue - totalInvestment)} KRW)`;
            
            logToConsole('info', `보유 코인 업데이트: ${Object.keys(holdings).length}개 코인, 총 평가액: ${formatNumber(totalValue)} KRW`);
        }
    } catch (error) {
        logToConsole('error', '보유 코인 조회 실패');
    }
}

// 모니터링 코인 업데이트
async function updateMonitoredCoins() {
    try {
        const data = await fetchAPI('/api/monitored');
        
        if (data.status === 'success') {
            const coins = data.data.coins;
            const tbody = document.getElementById('monitoredTableBody');
            tbody.innerHTML = '';
            
            for (const coin of coins) {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${coin.name}</td>
                    <td class="coin-symbol">${coin.market}</td>
                    <td class="text-center">${formatIndicator(coin.indicators.trend_15m)}</td>
                    <td class="text-center">${formatIndicator(coin.indicators.golden_cross)}</td>
                    <td class="text-center">${formatIndicator(coin.indicators.rsi_oversold)}</td>
                    <td class="text-center">${formatIndicator(coin.indicators.bollinger_band)}</td>
                    <td class="text-center">${formatIndicator(coin.indicators.volume_surge)}</td>
                    <td>
                        <div class="progress">
                            <div class="progress-bar" role="progressbar" 
                                 style="width: ${coin.signal_strength * 100}%">
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge ${getSignalBadgeClass(coin.status)} status-badge">
                            ${coin.status}
                        </span>
                    </td>
                `;
                tbody.appendChild(tr);
            }
            
            logToConsole('info', `모니터링 코인 업데이트: ${coins.length}개 코인`);
        }
    } catch (error) {
        logToConsole('error', '모니터링 코인 조회 실패');
    }
}

// 지표 표시 형식 변환
function formatIndicator(value) {
    return value ? '○' : '×';
}

// 상태에 따른 배지 클래스 반환
function getStatusBadgeClass(status) {
    switch (status) {
        case '높은 수익':
            return 'bg-success';
        case '수익':
            return 'bg-primary';
        case '소폭 손실':
            return 'bg-warning';
        case '손실':
            return 'bg-danger';
        default:
            return 'bg-secondary';
    }
}

// 신호 강도에 따른 배지 클래스 반환
function getSignalBadgeClass(status) {
    switch (status) {
        case '강력 매수':
            return 'bg-success';
        case '매수':
            return 'bg-primary';
        case '관망':
            return 'bg-warning';
        case '매도':
            return 'bg-danger';
        default:
            return 'bg-secondary';
    }
}

// 코인 매도
async function sellCoin(market) {
    try {
        if (!confirm(`${market}을(를) 시장가 매도하시겠습니까?`)) {
            return;
        }
        
        logToConsole('info', `매도 시도: ${market}`);
        
        const data = await fetchAPI('/api/trade/sell', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ market })
        });
        
        alert(data.message);
        
        if (data.status === 'success') {
            logToConsole('info', `매도 성공: ${market}`);
            await Promise.all([
                updateHoldings(),
                updateBalance()
            ]);
        }
    } catch (error) {
        logToConsole('error', `매도 실패: ${error.message}`);
    }
}