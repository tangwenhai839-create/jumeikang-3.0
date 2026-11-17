(function() {
  'use strict';

  var deferredInstallPrompt = null;

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function isIOS() {
    var ua = navigator.userAgent || '';
    return /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  function setInstallUIVisible(visible) {
    ['pwaInstallTip', 'pwaInstallLink'].forEach(function(id) {
      var element = document.getElementById(id);
      if (element) element.style.display = visible ? '' : 'none';
    });
  }

  function refreshInstallUI() {
    if (isStandalone()) {
      setInstallUIVisible(false);
      return;
    }
    setInstallUIVisible(isIOS() || deferredInstallPrompt !== null);
  }

  window.showPWAInstallGuide = async function() {
    if (isStandalone()) {
      alert('当前已经是主屏幕 App 模式。');
      return;
    }
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt = null;
      refreshInstallUI();
      return;
    }
    if (isIOS()) {
      alert('安装方法：\n1. 使用 Safari 打开当前页面\n2. 点击 Safari 底部的“分享”按钮\n3. 向下找到“添加到主屏幕”\n4. 点击右上角“添加”');
      return;
    }
    alert('请打开浏览器菜单，选择“安装应用”或“添加到主屏幕”。');
  };

  window.addEventListener('beforeinstallprompt', function(event) {
    event.preventDefault();
    deferredInstallPrompt = event;
    refreshInstallUI();
  });

  window.addEventListener('appinstalled', function() {
    deferredInstallPrompt = null;
    setInstallUIVisible(false);
  });

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
      navigator.serviceWorker.register('/service-worker.js', {scope: '/'}).catch(function(error) {
        console.warn('PWA service worker registration failed', error);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', refreshInstallUI);
})();
