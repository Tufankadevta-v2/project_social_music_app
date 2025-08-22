// Social Task Management App - Frontend JavaScript

class TaskApp {
    constructor() {
        this.apiBase = '/api';
        this.currentUser = null;
        this.authToken = localStorage.getItem('authToken');
        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.loadInitialData();
        this.updateUI();
    }

    setupEventListeners() {
        // Navigation
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-nav]')) {
                e.preventDefault();
                this.navigateTo(e.target.dataset.nav);
            }
        });

        // Task actions
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-task-complete]')) {
                this.completeTask(e.target.dataset.taskComplete);
            }
            if (e.target.matches('[data-task-delete]')) {
                this.deleteTask(e.target.dataset.taskDelete);
            }
        });

        // Form submissions
        document.addEventListener('submit', (e) => {
            if (e.target.matches('#taskForm')) {
                e.preventDefault();
                this.createTask(new FormData(e.target));
            }
            if (e.target.matches('#loginForm')) {
                e.preventDefault();
                this.login(new FormData(e.target));
            }
        });

        // Real-time updates
        this.setupWebSocket();
    }

    async loadInitialData() {
        try {
            // Load user data
            if (this.authToken) {
                await this.loadUserProfile();
                await this.loadDashboardData();
            }
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showNotification('Error loading data', 'error');
        }
    }

    async loadUserProfile() {
        try {
            const response = await this.apiCall('/auth/profile/');
            this.currentUser = response;
        } catch (error) {
            console.error('Error loading user profile:', error);
            this.logout();
        }
    }

    async loadDashboardData() {
        try {
            const [tasks, activities, stats] = await Promise.all([
                this.apiCall('/tasks/'),
                this.apiCall('/feed/'),
                this.apiCall('/tasks/statistics/')
            ]);

            this.renderTasks(tasks.results || tasks);
            this.renderActivityFeed(activities.results || activities);
            this.renderStats(stats);
        } catch (error) {
            console.error('Error loading dashboard data:', error);
        }
    }

    async apiCall(endpoint, options = {}) {
        const url = `${this.apiBase}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...(this.authToken && { 'Authorization': `Bearer ${this.authToken}` })
            },
            ...options
        };

        const response = await fetch(url, config);
        
        if (!response.ok) {
            if (response.status === 401) {
                this.logout();
                throw new Error('Authentication required');
            }
            throw new Error(`API call failed: ${response.statusText}`);
        }

        return await response.json();
    }

    navigateTo(section) {
        // Hide all sections
        document.querySelectorAll('.section').forEach(el => {
            el.classList.add('hidden');
        });

        // Show target section
        const targetSection = document.getElementById(section);
        if (targetSection) {
            targetSection.classList.remove('hidden');
            targetSection.classList.add('fade-in');
        }

        // Update navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[data-nav="${section}"]`)?.classList.add('active');
    }

    renderStats(stats) {
        const statsContainer = document.getElementById('statsContainer');
        if (!statsContainer) return;

        statsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon tasks">📋</div>
                <div class="stat-number">${stats.total_tasks || 0}</div>
                <div class="stat-label">Total Tasks</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon friends">👥</div>
                <div class="stat-number">${stats.completed_tasks || 0}</div>
                <div class="stat-label">Completed</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon points">⭐</div>
                <div class="stat-number">${stats.total_points_earned || 0}</div>
                <div class="stat-label">Points Earned</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon achievements">🏆</div>
                <div class="stat-number">${stats.pending_tasks || 0}</div>
                <div class="stat-label">Pending</div>
            </div>
        `;
    }

    renderTasks(tasks) {
        const tasksContainer = document.getElementById('tasksContainer');
        if (!tasksContainer) return;

        if (!tasks || tasks.length === 0) {
            tasksContainer.innerHTML = `
                <div class="text-center">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📝</div>
                    <h3>No tasks yet</h3>
                    <p>Create your first task to get started!</p>
                    <button class="btn btn-primary" data-nav="create-task">Create Task</button>
                </div>
            `;
            return;
        }

        const tasksList = tasks.map(task => `
            <div class="task-item">
                <div class="task-checkbox ${task.status === 'completed' ? 'completed' : ''}" 
                     data-task-complete="${task.id}"></div>
                <div class="task-content">
                    <div class="task-title ${task.status === 'completed' ? 'completed' : ''}">${task.title}</div>
                    <div class="task-meta">
                        <span class="priority-badge priority-${task.priority}">${task.priority}</span>
                        <span>⭐ ${task.points_value} points</span>
                        ${task.deadline ? `<span>📅 ${new Date(task.deadline).toLocaleDateString()}</span>` : ''}
                    </div>
                </div>
                <button class="btn btn-sm btn-outline" data-task-delete="${task.id}">Delete</button>
            </div>
        `).join('');

        tasksContainer.innerHTML = `<div class="task-list">${tasksList}</div>`;
    }

    renderActivityFeed(activities) {
        const feedContainer = document.getElementById('activityFeed');
        if (!feedContainer) return;

        if (!activities || activities.length === 0) {
            feedContainer.innerHTML = `
                <div class="text-center">
                    <div style="font-size: 2rem; margin-bottom: 1rem;">📱</div>
                    <p>No recent activities</p>
                </div>
            `;
            return;
        }

        const activitiesList = activities.map(activity => `
            <div class="activity-item">
                <div class="activity-avatar">${this.getActivityIcon(activity.activity_type)}</div>
                <div class="activity-content">
                    <div class="activity-text">${activity.title}</div>
                    <div class="activity-time">${this.formatTimeAgo(activity.created_at)}</div>
                </div>
            </div>
        `).join('');

        feedContainer.innerHTML = activitiesList;
    }

    getActivityIcon(activityType) {
        const icons = {
            'task_completed': '✅',
            'achievement_earned': '🏆',
            'friend_joined': '👋',
            'milestone_reached': '🎯',
            'shared_task_completed': '🤝'
        };
        return icons[activityType] || '📱';
    }

    formatTimeAgo(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);

        if (diffInSeconds < 60) return 'Just now';
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
        return `${Math.floor(diffInSeconds / 86400)}d ago`;
    }

    async completeTask(taskId) {
        try {
            await this.apiCall(`/tasks/${taskId}/complete_task/`, {
                method: 'POST'
            });
            
            this.showNotification('Task completed! 🎉', 'success');
            await this.loadDashboardData();
        } catch (error) {
            console.error('Error completing task:', error);
            this.showNotification('Error completing task', 'error');
        }
    }

    async deleteTask(taskId) {
        if (!confirm('Are you sure you want to delete this task?')) return;

        try {
            await this.apiCall(`/tasks/${taskId}/`, {
                method: 'DELETE'
            });
            
            this.showNotification('Task deleted', 'success');
            await this.loadDashboardData();
        } catch (error) {
            console.error('Error deleting task:', error);
            this.showNotification('Error deleting task', 'error');
        }
    }

    async createTask(formData) {
        try {
            const taskData = {
                title: formData.get('title'),
                description: formData.get('description'),
                priority: formData.get('priority'),
                deadline: formData.get('deadline') || null,
                points_value: parseInt(formData.get('points_value')) || 10
            };

            await this.apiCall('/tasks/', {
                method: 'POST',
                body: JSON.stringify(taskData)
            });

            this.showNotification('Task created successfully! 🎯', 'success');
            document.getElementById('taskForm').reset();
            this.navigateTo('dashboard');
            await this.loadDashboardData();
        } catch (error) {
            console.error('Error creating task:', error);
            this.showNotification('Error creating task', 'error');
        }
    }

    async login(formData) {
        try {
            const loginData = {
                phone_number: formData.get('phone_number'),
                password: formData.get('password') || '123456' // Demo password
            };

            // For demo purposes, we'll simulate login
            this.authToken = 'demo-token';
            localStorage.setItem('authToken', this.authToken);
            
            this.currentUser = {
                phone_number: loginData.phone_number,
                username: `user_${loginData.phone_number.replace(/\D/g, '')}`
            };

            this.showNotification('Welcome back! 👋', 'success');
            this.navigateTo('dashboard');
            await this.loadDashboardData();
        } catch (error) {
            console.error('Error logging in:', error);
            this.showNotification('Error logging in', 'error');
        }
    }

    logout() {
        this.authToken = null;
        this.currentUser = null;
        localStorage.removeItem('authToken');
        this.navigateTo('login');
        this.showNotification('Logged out successfully', 'success');
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span>${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;

        document.body.appendChild(notification);

        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);

        // Manual close
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.remove();
        });
    }

    setupWebSocket() {
        // WebSocket setup for real-time updates
        if (this.authToken && window.WebSocket) {
            try {
                const wsUrl = `ws://${window.location.host}/ws/notifications/`;
                this.ws = new WebSocket(wsUrl);
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                };
                
                this.ws.onclose = () => {
                    // Reconnect after 5 seconds
                    setTimeout(() => this.setupWebSocket(), 5000);
                };
            } catch (error) {
                console.log('WebSocket not available');
            }
        }
    }

    handleWebSocketMessage(data) {
        if (data.type === 'notification') {
            this.showNotification(data.message, 'info');
        } else if (data.type === 'task_update') {
            this.loadDashboardData();
        }
    }

    updateUI() {
        // Update user info in header
        const userInfo = document.getElementById('userInfo');
        if (userInfo && this.currentUser) {
            userInfo.innerHTML = `
                <span>Welcome, ${this.currentUser.username}!</span>
                <button class="btn btn-sm btn-outline" onclick="app.logout()">Logout</button>
            `;
        }

        // Show/hide sections based on auth state
        if (this.authToken) {
            this.navigateTo('dashboard');
        } else {
            this.navigateTo('login');
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TaskApp();
});

// Add notification styles
const notificationStyles = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        max-width: 400px;
        padding: 1rem;
        border-radius: 0.75rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        animation: slideInRight 0.3s ease;
    }
    
    .notification-info {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    .notification-success {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
    }
    
    .notification-error {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
        color: white;
    }
    
    .notification-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .notification-close {
        background: none;
        border: none;
        color: white;
        font-size: 1.5rem;
        cursor: pointer;
        padding: 0;
        margin-left: 1rem;
    }
    
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;

// Add styles to head
const styleSheet = document.createElement('style');
styleSheet.textContent = notificationStyles;
document.head.appendChild(styleSheet);