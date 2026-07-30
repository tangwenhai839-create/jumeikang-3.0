// ============================================================
// 电子秤连接模块 — 基于 Web Serial API 最佳实践
// 参考: https://web.dev/serial/
// ============================================================

// --- 状态机 -------------------------------------------------
const ScaleState = {
    IDLE: 'idle',
    CONNECTING: 'connecting',
    CONNECTED: 'connected',
    READING: 'reading',
    DISCONNECTING: 'disconnecting'
};

let scaleState = ScaleState.IDLE;
let scalePort = null;
let scaleBaudRate = 9600;
let scaleReadBuffer = '';
let scaleWeightHistory = [];
let scaleStableStartTime = null;
let scaleLastWeight = null;
let scaleReader = null;
let scaleReadableClosed = null;
let scaleStabilityCheckInterval = null;

const SCALE_STABLE_THRESHOLD = 0.1;
const SCALE_STABLE_DURATION = 3000;
const SCALE_HISTORY_SIZE = 5;

// --- 工具函数 -----------------------------------------------
function getScaleState() { return scaleState; }
function setScaleState(s) {
    scaleState = s;
    console.log('[Scale] 状态:', s);
}

window.getScaleState = getScaleState;
window.startScaleReading = startScaleReading;


// --- 连接 ---------------------------------------------------
async function connectScale() {
    if (!('serial' in navigator)) {
        alert('您的浏览器不支持 Web Serial API，请使用 Chrome 89+ / Edge 89+');
        return;
    }
    if (scaleState !== ScaleState.IDLE) {
        console.warn('[Scale] 当前状态:', scaleState, '，忽略重复连接');
        if (scaleState === ScaleState.CONNECTING) alert('正在连接中，请稍候...');
        else if (scaleState === ScaleState.CONNECTED || scaleState === ScaleState.READING) alert('电子秤已连接');
        return;
    }

    setScaleState(ScaleState.CONNECTING);
    const btn = document.getElementById('connectScaleBtn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ 连接中...'; }

    try {
        scaleBaudRate = parseInt(document.getElementById('baudRateSelect').value) || 9600;

        // 1. 获取端口（优先已授权，避免重复弹窗）
        const existing = await navigator.serial.getPorts();
        if (existing.length > 0) {
            scalePort = existing[0];
            console.log('[Scale] 使用已授权端口');
        } else {
            scalePort = await navigator.serial.requestPort({ filters: [] });
            console.log('[Scale] 用户选择了新端口');
        }

        // 2. 如果端口已打开，先关闭；若仍异常则 forget() 彻底重置
        if (scalePort.readable || scalePort.writable) {
            console.log('[Scale] 端口已打开，先关闭...');
            try { await scalePort.close(); } catch (e) {}
            if (scalePort.readable || scalePort.writable) {
                console.log('[Scale] 端口仍异常，调用 forget() 重置');
                try { await scalePort.forget(); } catch (e) {}
                scalePort = await navigator.serial.requestPort({ filters: [] });
            }
        }

        // 3. 打开端口（确保是 closed 状态）
        await scalePort.open({
            baudRate: scaleBaudRate,
            dataBits: 8,
            stopBits: 1,
            parity: 'none',
            flowControl: 'none'
        });

        setScaleState(ScaleState.CONNECTED);
        updateScaleUI('connected');
        speak('电子秤已连接');
        console.log('[Scale] 已连接，波特率:', scaleBaudRate);

        // 如果已识别学员，自动开始读取
        if (window.currentUserId) {
            startScaleReading();
        }

    } catch (err) {
        console.error('[Scale] 连接失败:', err);
        if (err.name !== 'NotFoundError' && err.name !== 'AbortError') {
            if (err.message && err.message.includes('already in progress')) {
                alert('连接失败：端口正在使用中。\n\n请刷新页面或拔插USB线后重试。');
            } else if (err.message && err.message.includes('Failed to open')) {
                alert('连接失败：无法打开串口。\n可能原因：端口被占用 / USB线松动 / 驱动问题');
            } else {
                alert('连接失败: ' + err.message);
            }
        }
        await cleanupScalePort();
        setScaleState(ScaleState.IDLE);
    } finally {
        if (btn) {
            btn.disabled = false;
            if (scaleState !== ScaleState.CONNECTED && scaleState !== ScaleState.READING) {
                btn.textContent = '🔌 连接电子秤';
            }
        }
    }
}

// --- 清理端口（forget 彻底重置）------------------------------
async function cleanupScalePort() {
    if (!scalePort) return;
    try {
        if (scalePort.readable || scalePort.writable) {
            await scalePort.close();
        }
    } catch (e) {}
    try {
        await scalePort.forget();
    } catch (e) {}
    scalePort = null;
}

// --- 断开连接（严格顺序：cancel → wait pipeTo → close）--------
async function disconnectScale() {
    if (scaleState === ScaleState.DISCONNECTING || scaleState === ScaleState.IDLE) return;
    setScaleState(ScaleState.DISCONNECTING);
    console.log('[Scale] 正在断开...');

    stopScaleReading();

    if (scaleReader) {
        try { await scaleReader.cancel(); } catch (e) {}
        scaleReader = null;
    }
    if (scaleReadableClosed) {
        try { await scaleReadableClosed; } catch (e) {}
        scaleReadableClosed = null;
    }
    if (scalePort) {
        try { await scalePort.close(); } catch (e) {}
    }

    scaleReadBuffer = '';
    scaleWeightHistory = [];
    scaleStableStartTime = null;
    scaleLastWeight = null;
    setScaleState(ScaleState.IDLE);
    updateScaleUI('disconnected');
    speak('电子秤已断开');
    console.log('[Scale] 已断开');
}

// --- 开始读取（TextDecoderStream + pipeTo 标准做法）----------
async function startScaleReading() {
    if (scaleState !== ScaleState.CONNECTED || !scalePort) return;
    setScaleState(ScaleState.READING);
    stopScaleReading();
    scaleReadBuffer = '';
    scaleWeightHistory = [];
    scaleStableStartTime = null;
    setStabilityStatus('waiting');

    console.log('[Scale] 开始读取...');

    const textDecoder = new TextDecoderStream();
    scaleReadableClosed = scalePort.readable.pipeTo(textDecoder.writable);
    scaleReader = textDecoder.readable.getReader();

    scaleStabilityCheckInterval = setInterval(checkStability, 100);
    readLoop();
}

async function readLoop() {
    while (scaleState === ScaleState.READING && scaleReader) {
        try {
            const { value, done } = await scaleReader.read();
            if (done) break;
            if (value) {
                scaleReadBuffer += value;
                processScaleBuffer();
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('[Scale] 读取错误:', err);
                speak('电子秤错误：数据读取异常');
            }
            break;
        }
    }
}

function stopScaleReading() {
    if (scaleStabilityCheckInterval) {
        clearInterval(scaleStabilityCheckInterval);
        scaleStabilityCheckInterval = null;
    }
}

// --- 数据解析 -----------------------------------------------
function processScaleBuffer() {
    const lines = scaleReadBuffer.split(/[\r\n]+/);
    scaleReadBuffer = lines.pop() || '';
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        const w = parseScaleData(line);
        if (w !== null && w > 0 && w < 500) {
            addWeightReading(w);
        }
    }
}

function parseScaleData(data) {
    if (!data) return null;
    let m = data.match(/ST,GS,\s*([+-]?\d+\.?\d*),\s*kg/i);
    if (m) return parseFloat(m[1]);
    m = data.match(/\s*([+-]?\d+\.?\d*)\s*kg\b/i);
    if (m) return parseFloat(m[1]);
    m = data.match(/[+-]?\s*(\d+\.?\d*)\s*kg\b/i);
    if (m) return parseFloat(m[1]);
    m = data.match(/^\s*([+-]?\d+\.?\d*)\s*(kg|g|KG|G)?\s*$/i);
    if (m) {
        let w = parseFloat(m[1]);
        const u = (m[2] || 'kg').toLowerCase();
        if (u === 'g') w = w / 1000;
        return w;
    }
    m = data.match(/(\d+\.\d{2})/);
    if (m) {
        const w = parseFloat(m[1]);
        if (w > 0 && w < 500) return w;
    }
    return null;
}

function addWeightReading(weight) {
    weight = Math.round(weight * 100) / 100;
    scaleWeightHistory.push(weight);
    if (scaleWeightHistory.length > SCALE_HISTORY_SIZE) scaleWeightHistory.shift();
    const el = document.getElementById('weightRealtime');
    if (el) el.textContent = weight.toFixed(2);
    if (scaleWeightHistory.length >= 3) checkStability();
}

// --- 稳定性检测（3秒保持平稳）--------------------------------
function checkStability() {
    if (scaleWeightHistory.length < 3) {
        setStabilityStatus('waiting');
        return;
    }
    let maxVal = scaleWeightHistory[0], minVal = scaleWeightHistory[0];
    for (let i = 1; i < scaleWeightHistory.length; i++) {
        if (scaleWeightHistory[i] > maxVal) maxVal = scaleWeightHistory[i];
        if (scaleWeightHistory[i] < minVal) minVal = scaleWeightHistory[i];
    }
    const range = maxVal - minVal;
    const currentWeight = scaleWeightHistory[scaleWeightHistory.length - 1];

    if (range <= SCALE_STABLE_THRESHOLD) {
        if (!scaleStableStartTime) scaleStableStartTime = Date.now();
        const elapsed = Date.now() - scaleStableStartTime;
        const progress = Math.min(elapsed / SCALE_STABLE_DURATION, 1.0);
        if (progress >= 1.0) {
            setStabilityStatus('stable', currentWeight);
            if (currentWeight !== scaleLastWeight && window.currentUserId) {
                autoSaveWeight(currentWeight);
            }
        } else {
            setStabilityStatus('stabilizing', progress);
        }
    } else {
        scaleStableStartTime = null;
        setStabilityStatus('unstable');
    }
}

function setStabilityStatus(status, value) {
    const bar = document.getElementById('stabilityProgress');
    const txt = document.getElementById('stabilityText');
    const ind = document.getElementById('stabilityIndicator');
    if (!bar || !txt || !ind) return;
    ind.className = 'stability-indicator';
    bar.style.width = '0%';
    if (status === 'waiting') {
        ind.classList.add('waiting');
        txt.textContent = '等待站上秤面...';
    } else if (status === 'stabilizing') {
        ind.classList.add('stabilizing');
        const pct = Math.round((value || 0) * 100);
        bar.style.width = pct + '%';
        txt.textContent = '稳定中... ' + pct + '%';
    } else if (status === 'stable') {
        ind.classList.add('stable');
        bar.style.width = '100%';
        txt.textContent = '已稳定! ' + (value ? value.toFixed(2) : '') + ' kg';
    } else if (status === 'unstable') {
        ind.classList.add('unstable');
        bar.style.width = '100%';
        txt.textContent = '读数波动中，请站稳...';
    } else if (status === 'saved') {
        ind.classList.add('saved');
        bar.style.width = '100%';
        txt.textContent = '✅ 已保存';
    }
}

// --- 自动保存 -----------------------------------------------
async function autoSaveWeight(weight) {
    if (!window.currentUserId) return;
    scaleLastWeight = weight;
    const userName = document.getElementById('userName').textContent;
    try {
        const resp = await fetch('/api/weigh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: window.currentUserId, weight: weight })
        });
        if (resp.status === 409) {
            const overwrite = await fetch('/api/weigh', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: window.currentUserId, weight: weight })
            });
            if (overwrite.ok) {
                speak('体重已稳定，' + weight + '公斤，自动保存成功。');
                speak(userName + '今日已称重，数据已覆盖。');
                updateScaleUI('saved');
                setTimeout(resetScaleAfterSave, 3000);
            }
            return;
        }
        if (resp.ok) {
            speak('体重已稳定，' + weight + '公斤，自动保存成功。');
            updateScaleUI('saved');
            setTimeout(resetScaleAfterSave, 3000);
        }
    } catch (err) {
        console.error('[Scale] 保存失败:', err);
        speak('电子秤错误：保存失败');
    }
}

function resetScaleAfterSave() {
    scaleWeightHistory = [];
    scaleStableStartTime = null;
    scaleLastWeight = null;
    const el = document.getElementById('weightRealtime');
    if (el) el.textContent = '--.--';
    setStabilityStatus('waiting');
    updateScaleUI('connected');
}

// --- UI 更新 ------------------------------------------------
function updateScaleUI(state) {
    const connectBtn = document.getElementById('connectScaleBtn');
    const disconnectBtn = document.getElementById('disconnectScaleBtn');
    const hint = document.getElementById('scaleHint');
    const scaleDisplay = document.getElementById('scaleDisplay');
    const stabilityIndicator = document.getElementById('stabilityIndicator');

    if (state === 'connected') {
        connectBtn.style.display = 'none';
        disconnectBtn.style.display = 'inline-flex';
        hint.textContent = '电子秤已连接，请站上秤面';
        hint.className = 'scale-hint connected';
        scaleDisplay.style.display = 'block';
        stabilityIndicator.style.display = 'block';
    } else if (state === 'disconnected') {
        connectBtn.style.display = 'inline-flex';
        disconnectBtn.style.display = 'none';
        hint.textContent = '点击连接，选择USB串口电子秤';
        hint.className = 'scale-hint';
        scaleDisplay.style.display = 'none';
        stabilityIndicator.style.display = 'none';
        setStabilityStatus('waiting');
    } else if (state === 'saved') {
        setStabilityStatus('saved');
        hint.textContent = '已保存，请下秤';
        hint.className = 'scale-hint saved';
    }
}

function toggleManualInput() {
    const area = document.getElementById('manualInputArea');
    if (area) area.style.display = area.style.display === 'none' ? 'block' : 'none';
}

// --- 初始化检测 ---------------------------------------------
(function() {
    if (!('serial' in navigator)) {
        const hint = document.getElementById('scaleHint');
        if (hint) {
            hint.textContent = '当前浏览器不支持 Web Serial API，请使用 Chrome/Edge 或手动输入';
            hint.className = 'scale-hint unsupported';
        }
        const btn = document.getElementById('connectScaleBtn');
        if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
    }
})();
