document.addEventListener('DOMContentLoaded', function() {
    // Handle toggle switches
    document.querySelectorAll('.toggle input[type="checkbox"]').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const settingType = this.closest('.card').id.replace('-settings', '');
            const settingKey = this.closest('.setting-item').dataset.setting;
            
            updateSetting(settingType, settingKey, this.checked);
        });
    });
    
    // Handle select dropdowns
    document.querySelectorAll('.select-small').forEach(select => {
        select.addEventListener('change', function() {
            const settingType = this.closest('.card').id.replace('-settings', '');
            const settingKey = this.closest('.setting-item').dataset.setting;
            
            updateSetting(settingType, settingKey, this.value);
        });
    });
});

async function updateSetting(type, key, value) {
    try {
        const response = await fetch('/settings/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `type=${type}&key=${key}&value=${value}`
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            showToast('Settings updated successfully', 'success');
        } else {
            showToast('Error updating settings', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error updating settings', 'error');
    }
}

function showToast(message, type = 'success') {
    // Create toast container if it doesn't exist
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    // Add icon based on type
    const icon = type === 'success' ? '✓' : '✕';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    // Add to container
    container.appendChild(toast);
    
    // Remove after delay
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out forwards';
        setTimeout(() => {
            container.removeChild(toast);
            // Remove container if empty
            if (container.children.length === 0) {
                document.body.removeChild(container);
            }
        }, 300);
    }, 3000);
}

async function exportData(type) {
    try {
        const response = await fetch(`/export/${type}`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `pickleball-${type}-export.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
            
            showToast('Data exported successfully', 'success');
        } else {
            throw new Error('Export failed');
        }
    } catch (error) {
        console.error('Export error:', error);
        showToast('Failed to export data', 'error');
    }
}

function confirmDelete() {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <h3>Delete Account</h3>
            <p>This action cannot be undone. All your data will be permanently deleted.</p>
            <div class="modal-actions">
                <button class="button button-secondary" onclick="closeModal()">Cancel</button>
                <button class="button button-danger" onclick="deleteAccount()">Delete Account</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function closeModal() {
    document.querySelector('.modal').remove();
}

async function deleteAccount() {
    try {
        const response = await fetch('/account/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            window.location.href = '/logout';
        } else {
            throw new Error('Delete failed');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showToast('Failed to delete account', 'error');
        closeModal();
    }
}

// Handle account settings forms
document.querySelectorAll('.account-form').forEach(form => {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const endpoint = this.getAttribute('data-endpoint');
        
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            if (data.status === 'success') {
                showToast('Settings updated successfully', 'success');
                if (endpoint.includes('password')) {
                    this.reset();
                }
            } else {
                showToast(data.message || 'Error updating settings', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            showToast('Error updating settings', 'error');
        }
    });
});

// Handle session management
async function loadSessions() {
    try {
        const response = await fetch('/profile/sessions');
        const sessions = await response.json();
        
        const sessionsList = document.querySelector('.sessions-list');
        sessionsList.innerHTML = sessions.map(session => `
            <div class="session-item ${session.is_current ? 'current-session' : ''}">
                <div class="session-info">
                    <span class="session-device">${session.device}</span>
                    <span class="session-details">
                        ${session.location} • Last active ${formatDate(session.last_active)}
                    </span>
                </div>
                ${session.is_current ? '' : `
                    <button class="button button-small" 
                            onclick="revokeSession('${session.id}')">
                        Revoke
                    </button>
                `}
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading sessions:', error);
        showToast('Error loading sessions', 'error');
    }
}

async function revokeSession(sessionId) {
    try {
        const response = await fetch('/profile/sessions/revoke', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `session_id=${sessionId}`
        });
        
        if (response.ok) {
            showToast('Session revoked successfully', 'success');
            loadSessions();
        } else {
            throw new Error('Failed to revoke session');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error revoking session', 'error');
    }
}

async function revokeAllSessions() {
    if (!confirm('Are you sure you want to log out of all other devices?')) {
        return;
    }
    
    try {
        const response = await fetch('/profile/sessions/revoke-all', {
            method: 'POST'
        });
        
        if (response.ok) {
            showToast('All sessions revoked successfully', 'success');
            loadSessions();
        } else {
            throw new Error('Failed to revoke sessions');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error revoking sessions', 'error');
    }
}

// Helper function to format dates
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) { // less than 1 minute
        return 'Just now';
    } else if (diff < 3600000) { // less than 1 hour
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
    } else if (diff < 86400000) { // less than 1 day
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours === 1 ? '' : 's'} ago`;
    } else {
        return date.toLocaleDateString();
    }
}

// Load sessions when the page loads
if (document.querySelector('.sessions-list')) {
    loadSessions();
} 