document.addEventListener('DOMContentLoaded', function() {
    // 요소
    const logContainer = document.getElementById('logContainer');
    const logLevel = document.getElementById('logLevel');
    const searchLog = document.getElementById('searchLog');
    const refreshLog = document.getElementById('refreshLog');
    const autoScroll = document.getElementById('autoScroll');
    
    // 초기 로그 로드
    loadLogs();
    
    // 자동 새로고침 설정
    let autoRefresh = setInterval(loadLogs, 5000);
    
    // 필터 변경 시 로그 필터링
    logLevel.addEventListener('change', filterLogs);
    searchLog.addEventListener('input', filterLogs);
    
    // 새로고침 버튼
    refreshLog.addEventListener('click', loadLogs);
    
    // 자동 스크롤 토글
    autoScroll.addEventListener('change', function() {
        if (this.checked) {
            scrollToBottom();
        }
    });
});

// 로그 로드
async function loadLogs() {
    try {
        const response = await fetch('/api/logs');
        const result = await response.json();
        
        if (result.status === 'success') {
            displayLogs(result.data.logs);
        } else {
            console.error('로그 로드 실패:', result.message);
        }
    } catch (error) {
        console.error('로그 로드 중 오류:', error);
    }
}

// 로그 표시
function displayLogs(logs) {
    const logContainer = document.getElementById('logContainer');
    const wasScrolledToBottom = isScrolledToBottom();
    
    // 로그 파싱 및 표시
    logs.forEach(log => {
        const logEntry = document.createElement('pre');
        logEntry.className = 'log-entry';
        
        // 로그 레벨에 따른 스타일 적용
        if (log.includes('[INFO]')) {
            logEntry.classList.add('log-info');
        } else if (log.includes('[WARNING]')) {
            logEntry.classList.add('log-warning');
        } else if (log.includes('[ERROR]')) {
            logEntry.classList.add('log-error');
        } else if (log.includes('[DEBUG]')) {
            logEntry.classList.add('log-debug');
        }
        
        logEntry.textContent = log;
        logContainer.appendChild(logEntry);
    });
    
    // 자동 스크롤이 활성화되어 있고, 이전에 맨 아래였다면 스크롤
    if (document.getElementById('autoScroll').checked && wasScrolledToBottom) {
        scrollToBottom();
    }
}

// 로그 필터링
function filterLogs() {
    const level = document.getElementById('logLevel').value;
    const search = document.getElementById('searchLog').value.toLowerCase();
    const logEntries = document.querySelectorAll('.log-entry');
    
    logEntries.forEach(entry => {
        const text = entry.textContent.toLowerCase();
        let show = true;
        
        // 레벨 필터
        if (level !== 'all') {
            const hasLevel = text.includes(`[${level.toUpperCase()}]`);
            show = show && hasLevel;
        }
        
        // 검색어 필터
        if (search) {
            show = show && text.includes(search);
        }
        
        entry.style.display = show ? '' : 'none';
    });
}

// 스크롤이 맨 아래인지 확인
function isScrolledToBottom() {
    const logContainer = document.getElementById('logContainer');
    return Math.abs(logContainer.scrollHeight - logContainer.clientHeight - logContainer.scrollTop) < 1;
}

// 맨 아래로 스크롤
function scrollToBottom() {
    const logContainer = document.getElementById('logContainer');
    logContainer.scrollTop = logContainer.scrollHeight;
} 