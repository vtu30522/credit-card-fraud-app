// ==========================================
// 1. THEME MANAGEMENT LOGIC
// ==========================================

function toggleTheme() {
    const body = document.body;
    const themeText = document.getElementById('theme-text');
    const themeIcon = document.getElementById('theme-icon');
    
    if (body.classList.contains('light-theme')) {
        body.classList.remove('light-theme');
        localStorage.setItem('fraudex-theme', 'dark');
        if (themeText) themeText.textContent = 'Light Mode';
        if (themeIcon) themeIcon.textContent = '☀️';
    } else {
        body.classList.add('light-theme');
        localStorage.setItem('fraudex-theme', 'light');
        if (themeText) themeText.textContent = 'Dark Mode';
        if (themeIcon) themeIcon.textContent = '🌙';
    }
}

// Read saved preference from localStorage instantly on load to avoid layout flash
(function() {
    const savedTheme = localStorage.getItem('fraudex-theme');
    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
    }
})();

// Ensure button icons match the loaded theme once DOM is parsed
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('fraudex-theme');
    const themeText = document.getElementById('theme-text');
    const themeIcon = document.getElementById('theme-icon');
    
    if (savedTheme === 'light') {
        if (themeText) themeText.textContent = 'Dark Mode';
        if (themeIcon) themeIcon.textContent = '🌙';
    } else {
        if (themeText) themeText.textContent = 'Light Mode';
        if (themeIcon) themeIcon.textContent = '☀️';
    }
});


// ==========================================
// 2. MOBILE RESPONSIVE SIDEBAR NAVIGATION
// ==========================================

// Toggles mobile sidebar open/closed state
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
}

// Detects clicks outside the sidebar view to auto-close it when active on mobile viewports
window.addEventListener('click', function (event) {
    const sidebar = document.querySelector('.sidebar');
    const toggle = document.querySelector('.mobile-toggle');
    
    if (!sidebar || !toggle) return;
    
    // Close sidebar if the click was outside both the sidebar and the mobile toggle button
    if (!sidebar.contains(event.target) && !toggle.contains(event.target) && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
    }
});