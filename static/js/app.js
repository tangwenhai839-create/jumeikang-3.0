/* 通用工具函数 */

// API 基础路径
const API_BASE = '';

// 通用 fetch 包装
async function apiFetch(path, options = {}) {
    const resp = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({error: resp.statusText}));
        throw new Error(err.error || '请求失败');
    }
    return resp.json();
}

// 格式化日期
function formatDate(dateStr) {
    if (!dateStr) return '--';
    return dateStr.slice(0, 10);
}

// 格式化时间
function formatTime(dateStr) {
    if (!dateStr) return '--';
    return dateStr.slice(11, 19);
}

// 防抖
function debounce(fn, delay = 300) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// Toast 消息 (简易)
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        padding: 12px 24px; border-radius: 10px; color: #fff;
        background: ${type === 'error' ? '#e74c3c' : '#2ecc71'};
        z-index: 9999; font-size: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        animation: fadeIn 0.3s;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
}

// 确认对话框
function confirmDialog(message) {
    return new Promise(resolve => {
        resolve(confirm(message));
    });
}

console.log('App.js loaded - 体重管理系统');
