document.addEventListener('DOMContentLoaded', function() {
    // 필터 요소
    const typeFilter = document.getElementById('typeFilter');
    const coinFilter = document.getElementById('coinFilter');
    const startDate = document.getElementById('startDate');
    const endDate = document.getElementById('endDate');
    const applyFilter = document.getElementById('applyFilter');
    
    // 페이지네이션 설정
    let currentPage = 1;
    const itemsPerPage = 20;
    
    // 초기 데이터 로드
    loadTradeHistory();
    loadCoinList();
    
    // 필터 적용
    applyFilter.addEventListener('click', function() {
        currentPage = 1;
        loadTradeHistory();
    });
    
    // 날짜 필터 초기값 설정
    const today = new Date();
    const lastMonth = new Date();
    lastMonth.setMonth(lastMonth.getMonth() - 1);
    
    startDate.value = formatDate(lastMonth);
    endDate.value = formatDate(today);
});

// 거래내역 로드
async function loadTradeHistory() {
    try {
        // 필터 값 가져오기
        const type = document.getElementById('typeFilter').value;
        const coin = document.getElementById('coinFilter').value;
        const start = document.getElementById('startDate').value;
        const end = document.getElementById('endDate').value;
        
        // API 호출
        const response = await fetch(`/api/history?type=${type}&coin=${coin}&start=${start}&end=${end}`);
        const result = await response.json();
        
        if (result.status === 'success') {
            displayTradeHistory(result.data);
        } else {
            Swal.fire({
                icon: 'error',
                title: '거래내역 로드 실패',
                text: result.message || '거래내역을 불러오는데 실패했습니다.'
            });
        }
    } catch (error) {
        console.error('거래내역 로드 중 오류:', error);
        Swal.fire({
            icon: 'error',
            title: '오류',
            text: '거래내역을 불러오는 중 오류가 발생했습니다.'
        });
    }
}

// 코인 목록 로드
async function loadCoinList() {
    try {
        const response = await fetch('/api/monitored');
        const result = await response.json();
        
        if (result.status === 'success') {
            const coinFilter = document.getElementById('coinFilter');
            const coins = result.data.coins;
            
            // 코인 옵션 추가
            coins.forEach(coin => {
                const option = document.createElement('option');
                option.value = coin.market;
                option.textContent = coin.korean_name;
                coinFilter.appendChild(option);
            });
        }
    } catch (error) {
        console.error('코인 목록 로드 중 오류:', error);
    }
}

// 거래내역 표시
function displayTradeHistory(trades) {
    const tbody = document.getElementById('tradeHistory');
    tbody.innerHTML = '';
    
    trades.forEach(trade => {
        const tr = document.createElement('tr');
        
        // 시간
        const time = document.createElement('td');
        time.textContent = formatDateTime(trade.timestamp);
        tr.appendChild(time);
        
        // 코인
        const coin = document.createElement('td');
        coin.textContent = trade.market;
        tr.appendChild(coin);
        
        // 유형
        const type = document.createElement('td');
        type.textContent = trade.type === 'buy' ? '매수' : '매도';
        type.className = trade.type === 'buy' ? 'text-danger' : 'text-primary';
        tr.appendChild(type);
        
        // 가격
        const price = document.createElement('td');
        price.textContent = formatNumber(trade.price) + '원';
        tr.appendChild(price);
        
        // 수량
        const volume = document.createElement('td');
        volume.textContent = formatNumber(trade.volume, 8);
        tr.appendChild(volume);
        
        // 총액
        const total = document.createElement('td');
        total.textContent = formatNumber(trade.price * trade.volume) + '원';
        tr.appendChild(total);
        
        // 수익률
        const profit = document.createElement('td');
        if (trade.profit_rate) {
            profit.textContent = trade.profit_rate.toFixed(2) + '%';
            profit.className = trade.profit_rate >= 0 ? 'text-success' : 'text-danger';
        } else {
            profit.textContent = '-';
        }
        tr.appendChild(profit);
        
        // 상태
        const status = document.createElement('td');
        status.textContent = trade.status === 'done' ? '완료' : '대기';
        status.className = trade.status === 'done' ? 'text-success' : 'text-warning';
        tr.appendChild(status);
        
        tbody.appendChild(tr);
    });
    
    // 데이터가 없는 경우
    if (trades.length === 0) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 8;
        td.textContent = '거래내역이 없습니다.';
        td.className = 'text-center';
        tr.appendChild(td);
        tbody.appendChild(tr);
    }
}

// 날짜 포맷
function formatDate(date) {
    return date.toISOString().split('T')[0];
}

// 날짜시간 포맷
function formatDateTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// 숫자 포맷
function formatNumber(number, decimals = 0) {
    return number.toLocaleString('ko-KR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
} 