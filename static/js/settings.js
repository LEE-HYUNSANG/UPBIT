// DOM 요소
const tradingSettingsForm = document.getElementById('trading-settings-form');
const signalSettingsForm = document.getElementById('signal-settings-form');
const notificationSettingsForm = document.getElementById('notification-settings-form');
const saveButton = document.getElementById('save-settings');
const settingsForm = document.getElementById('settings-form');
const alertModal = new bootstrap.Modal(document.getElementById('alertModal'));
const alertMessage = document.getElementById('alertMessage');

let excludedCoins = [];
let currentSettings = {};

let recommendedSettings = {};

async function loadRecommendedSettings() {
    try {
        const res = await fetch('/api/default_settings');
        const data = await res.json();
        recommendedSettings = data.data || data;
    } catch (e) {
        console.error('기본 설정 로드 실패:', e);
        recommendedSettings = {};
    }
}

// Socket.IO 초기화
const socket = io();

// DOM 요소
const excludedCoinInput = document.getElementById('excluded-coin-input');
const excludedCoinsList = document.getElementById('excluded-coins-list');

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', async () => {
    await loadRecommendedSettings();
    loadSettings();

    // 제외 코인 입력 이벤트
    excludedCoinInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addExcludedCoin();
        }
    });

    // 설정값 변경 이벤트 리스너
    document.querySelectorAll('input, select').forEach(input => {
        input.addEventListener('change', (e) => {
            markSettingsAsChanged(e.target);
        });
    });

});

// 제외 코인 추가
function addExcludedCoin() {
    const input = document.getElementById('excluded-coin-input');
    const coin = input.value.trim().toUpperCase();
    
    if (!coin) {
        showNotification('코인 심볼을 입력해주세요.', 'error');
        return;
    }
    
    if (!coin.startsWith('KRW-')) {
        showNotification('코인 심볼은 KRW-로 시작해야 합니다.', 'error');
        return;
    }
    
    if (excludedCoins.includes(coin)) {
        showNotification('이미 제외 목록에 있는 코인입니다.', 'error');
        return;
    }
    
    excludedCoins.push(coin);
    updateExcludedCoinsList(excludedCoins);
    input.value = '';
    markSettingsAsChanged(input);
}

// 제외 코인 제거
function removeExcludedCoin(coin) {
    excludedCoins = excludedCoins.filter(c => c !== coin);
    updateExcludedCoinsList(excludedCoins);
    markSettingsAsChanged(document.getElementById('excluded-coin-input'));
}

// 제외 코인 목록 업데이트
function updateExcludedCoinsList(coins) {
    excludedCoins = coins;
    const list = document.getElementById('excluded-coins-list');
    list.innerHTML = '';
    
    coins.forEach(coin => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.innerHTML = `
            ${coin}
            <button class="btn btn-sm btn-danger" onclick="removeExcludedCoin('${coin}')">
                <i class="bi bi-x"></i>
            </button>
        `;
        list.appendChild(li);
    });
}

// 설정 변경 표시
function markSettingsAsChanged(element) {
    const card = element.closest('.card');
    const saveButton = card ? card.querySelector('.save-btn') : null;
    if (saveButton) {
        saveButton.classList.add('btn-warning');
        saveButton.classList.remove('btn-primary');
    }
}

// 설정 로드
function mergeDeep(target, source) {
    for (const key in source) {
        if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
            if (!target[key]) target[key] = {};
            mergeDeep(target[key], source[key]);
        } else {
            target[key] = source[key];
        }
    }
    return target;
}

function loadSettings() {
    fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            const settings = data.data || data;
            currentSettings = mergeDeep(JSON.parse(JSON.stringify(recommendedSettings)), settings);
            updateFormValues(currentSettings);
            updateExcludedCoinsList(currentSettings.trading?.coin_selection?.excluded_coins || []);
        })
        .catch(error => {
            console.error('설정을 불러오는 중 오류가 발생했습니다:', error);
            showNotification('설정을 불러오는 중 오류가 발생했습니다.', 'error');
        });
}

// 폼 값 업데이트
function updateFormValues(settings) {
    // 기본 설정
    setValue('trading.investment_amount', settings.trading?.investment_amount);
    setValue('trading.max_coins', settings.trading?.max_coins);
    setValue('trading.min_price', settings.trading?.coin_selection?.min_price);
    setValue('trading.max_price', settings.trading?.coin_selection?.max_price);
    setValue('trading.min_volume_24h', settings.trading?.coin_selection?.min_volume_24h);
    setValue('trading.min_volume_1h', settings.trading?.coin_selection?.min_volume_1h);
    setValue('trading.min_tick_ratio', settings.trading?.coin_selection?.min_tick_ratio);


    // 매수 주문 설정
    const buySet = settings.buy_settings || {};
    setValue('buy_settings.ENTRY_SIZE_INITIAL', buySet.ENTRY_SIZE_INITIAL);
    setValue('buy_settings.LIMIT_WAIT_SEC_1', buySet.LIMIT_WAIT_SEC_1);
    if (document.getElementById('buy_settings.1st_Bid_Price'))
        document.getElementById('buy_settings.1st_Bid_Price').value = buySet['1st_Bid_Price'] || 'BID1';
    setValue('buy_settings.LIMIT_WAIT_SEC_2', buySet.LIMIT_WAIT_SEC_2);
    if (document.getElementById('buy_settings.2nd_Bid_Price'))
        document.getElementById('buy_settings.2nd_Bid_Price').value = buySet['2nd_Bid_Price'] || 'BID1';

    // 매도 설정
    setValue('sell_settings.TP_PCT', settings.sell_settings?.TP_PCT);
    setValue('sell_settings.MINIMUM_TICKS', settings.sell_settings?.MINIMUM_TICKS);

    // 알림 설정
    const notifications = settings.notifications || {};
    setValue('notifications.trade.start', notifications.trade?.start);
    setValue('notifications.trade.complete', notifications.trade?.complete);
    setValue('notifications.trade.profit_loss', notifications.trade?.profit_loss);
    
    setValue('notifications.system.error', notifications.system?.error);
    setValue('notifications.system.daily_summary', notifications.system?.daily_summary);
    setValue('notifications.system.signal', notifications.system?.signal);

    const score = settings.buy_score || {};
    setValue('buy_score.strength_weight', score.strength_weight);
    setValue('buy_score.strength_threshold_low', score.strength_threshold_low);
    setValue('buy_score.strength_threshold', score.strength_threshold);
    setValue('buy_score.volume_spike_weight', score.volume_spike_weight);
    setValue('buy_score.volume_spike_threshold_low', score.volume_spike_threshold_low);
    setValue('buy_score.volume_spike_threshold', score.volume_spike_threshold);
    setValue('buy_score.orderbook_weight', score.orderbook_weight);
    setValue('buy_score.orderbook_threshold', score.orderbook_threshold);
    setValue('buy_score.momentum_weight', score.momentum_weight);
    setValue('buy_score.momentum_threshold', score.momentum_threshold);
    setValue('buy_score.near_high_weight', score.near_high_weight);
    setValue('buy_score.near_high_threshold', score.near_high_threshold);
    setValue('buy_score.trend_reversal_weight', score.trend_reversal_weight);
    setValue('buy_score.williams_weight', score.williams_weight);
    document.getElementById('buy_score.williams_enabled').value = String(score.williams_enabled);
    setValue('buy_score.stochastic_weight', score.stochastic_weight);
    document.getElementById('buy_score.stochastic_enabled').value = String(score.stochastic_enabled);
    setValue('buy_score.macd_weight', score.macd_weight);
    document.getElementById('buy_score.macd_enabled').value = String(score.macd_enabled);
    setValue('buy_score.score_threshold', score.score_threshold);
    setValue('buy_score.score_thresholds', JSON.stringify(score.score_thresholds || {}));
}

// 매수 주문 설정 로드

// 설정 저장
function saveSettings(card = null) {
    // 기존 설정을 복사하여 누락되는 섹션이 없도록 한다
    const settings = JSON.parse(JSON.stringify(currentSettings));

    // 거래 설정
    settings.trading.investment_amount = getNumberValue('trading.investment_amount');
    settings.trading.max_coins = getNumberValue('trading.max_coins');
    settings.trading.coin_selection = {
        min_price: getNumberValue('trading.min_price'),
        max_price: getNumberValue('trading.max_price'),
        min_volume_24h: getNumberValue('trading.min_volume_24h'),
        min_volume_1h: getNumberValue('trading.min_volume_1h'),
        min_tick_ratio: getNumberValue('trading.min_tick_ratio'),
        excluded_coins: excludedCoins
    };


    // 알림 설정
    settings.notifications = {
        trade: {
            start: getBooleanValue('notifications.trade.start'),
            complete: getBooleanValue('notifications.trade.complete'),
            profit_loss: getBooleanValue('notifications.trade.profit_loss')
        },
        system: {
            error: getBooleanValue('notifications.system.error'),
            daily_summary: getBooleanValue('notifications.system.daily_summary'),
            signal: getBooleanValue('notifications.system.signal')
        }
    };

    // 매수 점수 설정
    settings.buy_score = {
        strength_weight: getNumberValue('buy_score.strength_weight'),
        strength_threshold_low: getNumberValue('buy_score.strength_threshold_low'),
        strength_threshold: getNumberValue('buy_score.strength_threshold'),
        volume_spike_weight: getNumberValue('buy_score.volume_spike_weight'),
        volume_spike_threshold_low: getNumberValue('buy_score.volume_spike_threshold_low'),
        volume_spike_threshold: getNumberValue('buy_score.volume_spike_threshold'),
        orderbook_weight: getNumberValue('buy_score.orderbook_weight'),
        orderbook_threshold: getNumberValue('buy_score.orderbook_threshold'),
        momentum_weight: getNumberValue('buy_score.momentum_weight'),
        momentum_threshold: getNumberValue('buy_score.momentum_threshold'),
        near_high_weight: getNumberValue('buy_score.near_high_weight'),
        near_high_threshold: getNumberValue('buy_score.near_high_threshold'),
        trend_reversal_weight: getNumberValue('buy_score.trend_reversal_weight'),
        williams_weight: getNumberValue('buy_score.williams_weight'),
        williams_enabled: document.getElementById('buy_score.williams_enabled').value === 'true',
        stochastic_weight: getNumberValue('buy_score.stochastic_weight'),
        stochastic_enabled: document.getElementById('buy_score.stochastic_enabled').value === 'true',
        macd_weight: getNumberValue('buy_score.macd_weight'),
        macd_enabled: document.getElementById('buy_score.macd_enabled').value === 'true',
        score_threshold: getNumberValue('buy_score.score_threshold'),
        score_thresholds: JSON.parse(document.getElementById('buy_score.score_thresholds').value || '{}')
    };

    // 매수 주문 설정
    settings.buy_settings = {
        ENTRY_SIZE_INITIAL: getNumberValue('buy_settings.ENTRY_SIZE_INITIAL'),
        LIMIT_WAIT_SEC_1: getNumberValue('buy_settings.LIMIT_WAIT_SEC_1'),
        "1st_Bid_Price": document.getElementById('buy_settings.1st_Bid_Price').value,
        LIMIT_WAIT_SEC_2: getNumberValue('buy_settings.LIMIT_WAIT_SEC_2'),
        "2nd_Bid_Price": document.getElementById('buy_settings.2nd_Bid_Price').value
    };

    // 매도 주문 설정
    settings.sell_settings = {
        TP_PCT: getNumberValue('sell_settings.TP_PCT'),
        MINIMUM_TICKS: getNumberValue('sell_settings.MINIMUM_TICKS')
    };

    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('설정이 저장되었습니다.', 'success');
            currentSettings = settings;
            const btn = card ? card.querySelector('.save-btn') : document.querySelector('button.btn-warning');
            if (btn) {
                btn.classList.remove('btn-warning');
                btn.classList.add('btn-primary');
            }
        } else {
            showNotification(data.error || '설정 저장 중 오류가 발생했습니다.', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('설정 저장 중 오류가 발생했습니다.', 'error');
    });
}

function saveCard(btn) {
    const card = btn.closest('.card');
    saveSettings(card);
}

// 설정 초기화
function resetSettings() {
    if (confirm('모든 설정을 초기화하시겠습니까?')) {
        fetch('/api/settings/reset', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('설정이 초기화되었습니다.', 'success');
                    loadSettings();
                } else {
                    showNotification(data.error || '설정 초기화 중 오류가 발생했습니다.', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('설정 초기화 중 오류가 발생했습니다.', 'error');
            });
    }
}

// 유틸리티 함수
function setValue(id, value) {
    const element = document.getElementById(id);
    if (element) {
        if (element.type === 'checkbox') {
            element.checked = Boolean(value);
        } else {
            element.value = value !== undefined ? value : '';
        }
    }
}

function getValue(id) {
    const element = document.getElementById(id);
    if (element) {
        if (element.type === 'checkbox') {
            return element.checked;
        } else {
            return element.value;
        }
    }
    return null;
}

function getNumberValue(id) {
    const value = getValue(id);
    return value !== null ? Number(value) : null;
}

function getBooleanValue(id) {
    return getValue(id) === true;
}

// 알림 표시
function showNotification(message, type = 'info') {
    // Bootstrap 알림 생성
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    alert.style.zIndex = '9999';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    document.body.appendChild(alert);
    
    // 3초 후 자동으로 닫기
    setTimeout(() => {
        alert.remove();
    }, 3000);
}

// Socket.IO 이벤트 리스너
socket.on('settings_updated', (settings) => {
    console.log('Settings updated from server');
    loadSettings();
});

socket.on('settings_error', (data) => {
    showNotification(data.message, 'error');
});

// 에러 메시지 표시
function showErrorMessage(message) {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
}

// 성공 메시지 표시
function showSuccessMessage(message) {
    const successDiv = document.getElementById('success-message');
    if (successDiv) {
        successDiv.textContent = message;
        successDiv.style.display = 'block';
        setTimeout(() => {
            successDiv.style.display = 'none';
        }, 3000);
    }
}

// 에러 메시지 숨기기
function hideErrorMessage() {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

// 섹션 상태 업데이트
function updateSectionState(toggleId) {
    const toggle = document.getElementById(toggleId);
    if (!toggle) return;

    // 자동 거래 활성화 토글 처리
    if (toggleId === 'trading.enabled') {
        const tradingSection = document.querySelector('.col-md-3:first-child');
        const tradingInputs = tradingSection.querySelectorAll('input:not(#trading\\.enabled)');
        tradingInputs.forEach(input => {
            input.disabled = !toggle.checked;
        });
        return;
    }

}

// 모든 섹션 상태 업데이트
function updateAllSectionStates() {
    // 자동 거래 상태 업데이트
    updateSectionState('trading.enabled');
}

// 이벤트 리스너 설정
document.addEventListener('DOMContentLoaded', () => {
    // 저장 버튼 이벤트
    if (saveButton) {
        saveButton.addEventListener('click', saveSettings);
    }
    
    // 토글 이벤트
    const toggles = settingsForm.querySelectorAll('input[type="checkbox"]');
    toggles.forEach(toggle => {
        toggle.addEventListener('change', () => {
            updateSectionState(toggle.id);
        });
    });
    
    // 폼 제출 방지
    if (settingsForm) {
        settingsForm.addEventListener('submit', (e) => {
            e.preventDefault();
        });
    }
    
    // 초기 상태 업데이트
    updateAllSectionStates();
}); 
