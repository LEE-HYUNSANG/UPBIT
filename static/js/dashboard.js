// WebSocket 연결
const socket = io();

// 페이지 로드 시 초기 데이터 로드
document.addEventListener('DOMContentLoaded', () => {
    updateData();
    // 5초마다 데이터 업데이트
    setInterval(updateData, 5000);
});

// 데이터 업데이트 함수
async function updateData() {
    try {
        console.log('Starting updateData');
        
        // 잔고 및 보유 코인 정보 조회
        const balanceResponse = await fetch('/api/balance');
        const holdingsResponse = await fetch('/api/holdings');
        const monitoredResponse = await fetch('/api/monitored');

        console.log('API Responses:', {
            balance: balanceResponse.ok,
            holdings: holdingsResponse.ok,
            monitored: monitoredResponse.ok
        });

        if (!balanceResponse.ok || !holdingsResponse.ok || !monitoredResponse.ok) {
            throw new Error('API 요청 실패');
        }

        const balanceData = await balanceResponse.json();
        const holdingsData = await holdingsResponse.json();
        const monitoredData = await monitoredResponse.json();

        console.log('Received data:', {
            balance: balanceData,
            holdings: holdingsData,
            monitored: monitoredData
        });

        // 잔고 및 수익 정보 업데이트
        updateBalanceInfo(balanceData);
        
        // 보유 코인 정보 업데이트
        updateHoldings(holdingsData);
        
        // 모니터링 정보 업데이트
        if (monitoredData.status === 'success') {
            console.log('Updating monitoring with coins:', monitoredData.data.coins);
            updateMonitoring(monitoredData.data.coins);
        } else {
            console.error('Monitored data status not success:', monitoredData);
        }

    } catch (error) {
        console.error('데이터 업데이트 실패:', error);
    }
}

// 잔고 및 수익 정보 업데이트
function updateBalanceInfo(data) {
    const balanceElement = document.getElementById('current-balance');
    const profitElement = document.getElementById('current-profit');
    const profitPercentElement = document.getElementById('profit-percentage');

    if (balanceElement && profitElement && profitPercentElement) {
        balanceElement.textContent = formatNumber(data.balance);
        profitElement.textContent = formatNumber(data.total_profit);
        profitPercentElement.textContent = data.profit_percentage.toFixed(2);

        // 수익/손실에 따른 색상 변경
        profitElement.className = data.total_profit >= 0 ? 'text-success' : 'text-danger';
        profitPercentElement.className = data.profit_percentage >= 0 ? 'text-success' : 'text-danger';
    }
}

// 보유 코인 정보 업데이트
function updateHoldings(holdings) {
    const tbody = document.getElementById('holdings-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    Object.values(holdings).forEach(coin => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${coin.market}</td>
            <td>${formatNumber(coin.current_price)}</td>
            <td>${formatNumber(coin.average_price)}</td>
            <td>${coin.quantity.toFixed(8)}</td>
            <td>${formatNumber(coin.total_value)}</td>
            <td class="${coin.profit_rate >= 0 ? 'text-success' : 'text-danger'}">
                ${coin.profit_rate.toFixed(2)}%
            </td>
            <td>
                <span class="status-badge ${getStatusClass(coin.status)}">
                    ${coin.status}
                </span>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// 모니터링 정보 업데이트
function updateMonitoring(coins) {
    console.log('updateMonitoring called with coins:', coins);
    
    const tbody = document.getElementById('monitoring-body');
    if (!tbody) {
        console.error('monitoring-body element not found');
        return;
    }

    tbody.innerHTML = '';
    
    if (!coins || coins.length === 0) {
        console.warn('No coins data received');
        tbody.innerHTML = '<tr><td colspan="9" class="text-center">모니터링 중인 코인이 없습니다.</td></tr>';
        return;
    }

    coins.forEach(coin => {
        console.log('Processing coin:', coin);
        const tr = document.createElement('tr');
        const indicators = coin.indicators || {};
        const values = coin.values || {};
        
        console.log('Coin indicators:', indicators);
        console.log('Coin values:', values);
        
        // 각 지표의 값과 상태를 표시하는 함수
        const formatIndicatorWithValue = (isTrue, value) => {
            console.log('formatIndicatorWithValue:', { isTrue, value });
            const symbol = isTrue ? '○' : '×';
            const badge = isTrue ? 'bg-success' : 'bg-secondary';
            const displayValue = value !== undefined ? 
                ` (${typeof value === 'number' ? value.toFixed(2) : value})` : '';
            return `<span class="badge ${badge}">${symbol}${displayValue}</span>`;
        };

        tr.innerHTML = `
            <td>${coin.name || 'undefined'}</td>
            <td>${coin.market || 'undefined'}</td>
            <td class="text-center">${formatIndicatorWithValue(indicators.trend_filter, values.ema50)}</td>
            <td class="text-center">${formatIndicatorWithValue(indicators.golden_cross, values.sma5_slope)}</td>
            <td class="text-center">${formatIndicatorWithValue(indicators.rsi_oversold, values.rsi14)}</td>
            <td class="text-center">${formatIndicatorWithValue(indicators.bollinger_break, values.bb_lower)}</td>
            <td class="text-center">${formatIndicatorWithValue(indicators.volume_surge, values.volume)}</td>
            <td>
                <span class="badge ${getStatusBadgeClass(coin.status)}">
                    ${coin.status || 'undefined'}
                </span>
            </td>
            <td class="text-center">
                <button class="btn btn-sm btn-success buy-btn" 
                        data-market="${coin.market}"
                        data-name="${coin.name || ''}"
                        data-price="${coin.current_price || 0}">
                    매수
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // 매수 버튼 이벤트 핸들러 등록
    document.querySelectorAll('.buy-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const market = this.dataset.market;
            const name = this.dataset.name;
            const price = parseFloat(this.dataset.price);
            console.log('Buy button clicked:', { market, name, price });
            showBuyModal(market, name, price);
        });
    });
}

// 매수 모달 표시
function showBuyModal(market, name, price) {
    document.getElementById('selectedCoin').textContent = `${name} (${market})`;
    document.getElementById('currentPrice').textContent = formatPrice(price);
    
    const modal = new bootstrap.Modal(document.getElementById('buyModal'));
    modal.show();
    
    // 매수 확인 버튼 이벤트 핸들러
    document.getElementById('confirmBuy').onclick = function() {
        const amount = document.getElementById('buyAmount').value;
        if (amount < 5000) {
            alert('최소 매수 금액은 5,000원입니다.');
            return;
        }
        
        // 매수 요청 전송
        socket.emit('buy_market_order', {
            market: market,
            price: amount
        });
        
        modal.hide();
    };
}

// 새로고침 버튼 이벤트 핸들러
document.getElementById('refreshMonitoring').addEventListener('click', function() {
    this.disabled = true;
    this.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> 새로고침 중...';
    
    updateData().finally(() => {
        this.disabled = false;
        this.innerHTML = '<i class="fas fa-sync-alt"></i> 새로고침';
    });
});

// 매수 결과 처리
socket.on('buy_result', function(data) {
    if (data.status === 'success') {
        showNotification('매수 주문이 성공적으로 체결되었습니다.', 'success');
        updateData();  // 데이터 갱신
    } else {
        showNotification(`매수 실패: ${data.message}`, 'error');
    }
});

// 알림 표시 함수
function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    document.body.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', function() {
        document.body.removeChild(toast);
    });
}

// 숫자 포맷팅 (1000단위 콤마)
function formatNumber(number) {
    return new Intl.NumberFormat('ko-KR').format(Math.round(number));
}

// 상태에 따른 클래스 반환
function getStatusClass(status) {
    switch (status) {
        case '높은 수익':
        case '수익':
            return 'status-profit';
        case '소폭 손실':
            return 'status-small-loss';
        case '손실':
            return 'status-loss';
        default:
            return '';
    }
}

// 매수 조건 상태에 따른 클래스 반환
function getConditionClass(condition) {
    return condition ? 'text-success' : 'text-danger';
}

// 매수 조건 포맷팅
function formatCondition(condition) {
    return condition ? '충족' : '미충족';
}

// 가격 포맷팅 함수
function formatPrice(price) {
    return new Intl.NumberFormat('ko-KR', {
        style: 'currency',
        currency: 'KRW'
    }).format(price);
}

// 지표 포맷팅 함수
function formatIndicator(value, label) {
    if (value === undefined || value === null) return '-';
    return value ? 
        `<span class="badge bg-success">○ ${label}</span>` : 
        `<span class="badge bg-secondary">× ${label}</span>`;
}

// 상태 배지 클래스 반환 함수
function getStatusBadgeClass(status) {
    switch(status) {
        case '매수 대기':
            return 'bg-warning';
        case '매수 가능':
            return 'bg-success';
        case '매수 진행중':
            return 'bg-primary';
        case '매수 완료':
            return 'bg-info';
        default:
            return 'bg-secondary';
    }
}

// WebSocket 이벤트 핸들러
socket.on('update', (data) => {
    if (data.type === 'balance') {
        updateBalanceInfo(data.data);
    } else if (data.type === 'holdings') {
        updateHoldings(data.data);
    } else if (data.type === 'monitoring') {
        updateMonitoring(data.data);
    }
});

// 봇 상태 업데이트 처리
socket.on('bot_status', function(data) {
    // 봇 상태 표시
    const botStatus = document.getElementById('bot-status');
    if (botStatus) {
        botStatus.innerHTML = `<span class="badge ${data.status ? 'bg-success' : 'bg-secondary'}">
            ${data.status ? '실행 중' : '중지됨'}
        </span>`;
    }

    // 마지막 업데이트 시간
    const lastUpdate = document.getElementById('last-update');
    if (lastUpdate && data.last_update) {
        lastUpdate.textContent = data.last_update;
    }

    // 시장 상태
    const marketStatus = document.getElementById('market-status');
    if (marketStatus && data.market_condition) {
        const condition = data.market_condition;
        const confidence = data.market_confidence;
        const emoji = condition === 'BULL' ? '📈' : condition === 'BEAR' ? '📉' : '➡️';
        marketStatus.innerHTML = `${emoji} ${condition} <small>(${(confidence * 100).toFixed(1)}%)</small>`;
    }

    // 모니터링 현황
    const monitoringStatus = document.getElementById('monitoring-status');
    if (monitoringStatus) {
        monitoringStatus.textContent = `${data.monitored_count} / ${data.total_markets}`;
    }

    // 버튼 상태 업데이트
    const startButton = document.getElementById('start-bot');
    const stopButton = document.getElementById('stop-bot');
    if (startButton) startButton.disabled = data.status;
    if (stopButton) stopButton.disabled = !data.status;
}); 