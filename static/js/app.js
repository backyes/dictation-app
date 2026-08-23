/**
 * 英语听写练习应用 - 公共JavaScript
 */

// ==================== Toast 消息提示 ====================
function showToast(message, type = 'info') {
    // 移除已有的toast
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // 3秒后自动消失
    setTimeout(function() {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s';
        setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
}

// ==================== 工具函数 ====================
function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 页面加载初始化 ====================
document.addEventListener('DOMContentLoaded', function() {
    var currentPath = window.location.pathname;
    document.querySelectorAll('.nav-links a').forEach(function(link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});
