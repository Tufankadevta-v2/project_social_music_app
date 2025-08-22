document.addEventListener('DOMContentLoaded', () => {
    const app = {
        // --- STATE ---
        API_BASE_URL: '/api',
        token: localStorage.getItem('authToken'),
        currentUser: null,

        // --- DOM ELEMENTS ---
        elements: {
            loginSection: document.getElementById('login'),
            appContainer: document.getElementById('app-container'),
            mainNav: document.getElementById('main-nav'),
            mainContent: document.getElementById('main-content'),
            sections: document.querySelectorAll('.section'),
            navLinks: document.querySelectorAll('.nav-link'),
            loginForm: document.getElementById('loginForm'),
            loginError: document.getElementById('login-error'),
            taskForm: document.getElementById('taskForm'),
            taskFormError: document.getElementById('task-form-error'),
            userProfileContainer: document.getElementById('user-profile-container'),
            dashboardFeed: document.getElementById('dashboard-feed'),
            allTasksFeed: document.getElementById('all-tasks-feed'),
            fullActivityFeed: document.getElementById('full-activity-feed'),
            loadingOverlay: document.getElementById('loadingOverlay'),
            createTaskSection: document.getElementById('create-task'),
            fab: document.getElementById('fab-create-task'),
        },

        // --- INITIALIZATION ---
        init() {
            this.elements.loginForm.addEventListener('submit', e => {
                e.preventDefault();
                this.login();
            });

            this.elements.taskForm.addEventListener('submit', e => {
                e.preventDefault();
                this.createTask();
            });

            document.body.addEventListener('click', e => {
                const navTarget = e.target.closest('[data-nav]');
                if (navTarget) {
                    e.preventDefault();
                    this.navigate(navTarget.dataset.nav);
                }

                const taskCheckbox = e.target.closest('.task-checkbox');
                if (taskCheckbox && !taskCheckbox.classList.contains('completed')) {
                    const taskId = taskCheckbox.closest('.task-item').dataset.taskId;
                    this.completeTask(taskId);
                }
            });

            this.checkLoginState();
        },

        // --- API & AUTHENTICATION ---
        async fetchAPI(endpoint, options = {}) {
            this.showLoading(true);
            const headers = { 'Content-Type': 'application/json', ...options.headers };
            if (this.token) {
                headers['Authorization'] = `Bearer ${this.token}`;
            }

            try {
                const response = await fetch(`${this.API_BASE_URL}${endpoint}`, { ...options, headers });
                if (response.status === 204) return true;
                const data = await response.json();

                if (!response.ok) {
                    console.error('API Error:', data);
                    if (response.status === 401 && this.token) this.logout();
                    throw new Error(data.detail || data.error || JSON.stringify(data));
                }
                return data;
            } catch (error) {
                console.error('Fetch Error:', error);
                throw error;
            } finally {
                this.showLoading(false);
            }
        },

        async login() {
            const formData = new FormData(this.elements.loginForm);
            const data = Object.fromEntries(formData.entries());
            this.elements.loginError.classList.add('hidden');

            try {
                const response = await this.fetchAPI('/auth/jwt/login/', {
                    method: 'POST',
                    body: JSON.stringify(data),
                });
                this.token = response.access;
                this.currentUser = response.user;
                localStorage.setItem('authToken', this.token);
                localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
                this.showMainApp();
            } catch (error) {
                this.elements.loginError.textContent = "Login failed. Please check credentials.";
                this.elements.loginError.classList.remove('hidden');
            }
        },

        logout() {
            this.token = null;
            this.currentUser = null;
            localStorage.clear();
            this.showLoginPage();
        },

        checkLoginState() {
            const userJson = localStorage.getItem('currentUser');
            if (this.token && userJson) {
                try {
                    this.currentUser = JSON.parse(userJson);
                    this.showMainApp();
                } catch(e) {
                    this.logout();
                }
            } else {
                this.showLoginPage();
            }
        },

        // --- UI RENDERING & STATE MANAGEMENT ---
        showLoading(isLoading) {
            this.elements.loadingOverlay.classList.toggle('hidden', !isLoading);
        },

        showLoginPage() {
            this.elements.appContainer.classList.add('hidden');
            this.elements.createTaskSection.classList.add('hidden');
            this.elements.loginSection.classList.remove('hidden');
        },

        async showMainApp() {
            this.elements.loginSection.classList.add('hidden');
            this.elements.appContainer.classList.remove('hidden');
            this.renderUserProfile();
            this.navigate('dashboard');
        },

        renderUserProfile() {
            if (!this.currentUser) return;
            const profile = this.currentUser.profile;
            const displayName = profile.display_name || this.currentUser.username;
            this.elements.userProfileContainer.innerHTML = `
                <div class="user-avatar">${displayName.charAt(0).toUpperCase()}</div>
                <div class="user-info">
                    <div class="name">${displayName}</div>
                    <div class="points">${profile.total_points} points</div>
                </div>
                <button id="logoutButton" class="btn" title="Logout"><i class="fas fa-sign-out-alt"></i></button>
            `;
            document.getElementById('logoutButton').addEventListener('click', () => this.logout());
        },

        async renderDashboard() {
            try {
                const [tasksResponse, activitiesResponse] = await Promise.all([
                    this.fetchAPI('/tasks/?ordering=-created_at'),
                    this.fetchAPI('/feed/activities/?ordering=-created_at')
                ]);

                const tasks = tasksResponse.results.map(item => ({ ...item, type: 'task', date: item.created_at }));
                const activities = activitiesResponse.results.map(item => ({ ...item, type: 'activity', date: item.created_at }));

                const combinedFeed = [...tasks, ...activities].sort((a, b) => new Date(b.date) - new Date(a.date));

                if (combinedFeed.length === 0) {
                    this.elements.dashboardFeed.innerHTML = '<p class="text-center p-8 text-gray-500">Your feed is empty. Create a task to get started!</p>';
                    return;
                }
                
                this.elements.dashboardFeed.innerHTML = combinedFeed.map(item => {
                    return item.type === 'task' ? this.getTaskHtml(item) : this.getActivityHtml(item);
                }).join('');
            } catch (error) {
                this.elements.dashboardFeed.innerHTML = `<p class="text-center p-8 text-red-500">Could not load dashboard feed.</p>`;
            }
        },

        renderTasks(tasks, container) {
            if (!tasks || tasks.length === 0) {
                container.innerHTML = '<p class="text-center p-8 text-gray-500">No tasks found. Great job, or time to create one!</p>';
                return;
            }
            container.innerHTML = tasks.map(task => this.getTaskHtml(task)).join('');
        },

        renderActivityFeed(activities, container) {
            if (!activities || activities.length === 0) {
                container.innerHTML = '<p class="text-center p-8 text-gray-500">No recent activity.</p>';
                return;
            }
            container.innerHTML = activities.map(activity => this.getActivityHtml(activity)).join('');
        },

        getTaskHtml(task) {
            const isCompleted = task.status === 'completed';
            return `
                <div class="card task-item" data-task-id="${task.id}">
                    <div class="item-actions">
                         <div class="task-checkbox ${isCompleted ? 'completed' : ''}" title="Mark as complete">
                            ${isCompleted ? '<i class="fas fa-check"></i>' : ''}
                         </div>
                    </div>
                    <div class="item-content">
                        <div class="item-title ${isCompleted ? 'completed' : ''}">${task.title}</div>
                        <p>${task.description || ''}</p>
                        <div class="item-meta">
                            <span class="priority priority-${task.priority}">● ${task.priority}</span>
                            <span>⭐ ${task.points_value} pts</span>
                            ${task.deadline ? `<span>🕒 ${this.formatTimeAgo(task.deadline)}</span>` : ''}
                        </div>
                    </div>
                </div>`;
        },

        getActivityHtml(activity) {
            const icons = { task_completed: 'fa-check', achievement_earned: 'fa-trophy', friend_joined: 'fa-user-plus' };
            const icon = icons[activity.activity_type] || 'fa-rss';
            return `
                <div class="card activity-item">
                    <div class="item-icon"><i class="fas ${icon}"></i></div>
                    <div class="item-content">
                        <div class="item-title">${activity.user.profile.display_name || activity.user.username}</div>
                        <p>${activity.title}</p>
                        <div class="item-meta">
                            <span>${this.formatTimeAgo(activity.created_at)}</span>
                        </div>
                    </div>
                </div>`;
        },

        // --- TASK ACTIONS ---
        async createTask() {
            const formData = new FormData(this.elements.taskForm);
            let data = Object.fromEntries(formData.entries());
            data.points_value = parseInt(data.points_value);
            this.elements.taskFormError.classList.add('hidden');

            if (data.deadline) data.deadline = new Date(data.deadline).toISOString();
            else delete data.deadline;
            
            try {
                await this.fetchAPI('/tasks/', { method: 'POST', body: JSON.stringify(data) });
                this.elements.taskForm.reset();
                this.navigate('dashboard');
            } catch (error) {
                this.elements.taskFormError.textContent = `Error creating task: ${error.message}`;
                this.elements.taskFormError.classList.remove('hidden');
            }
        },

        async completeTask(taskId) {
            try {
                const response = await this.fetchAPI(`/tasks/${taskId}/complete_task/`, { method: 'POST' });
                // Re-render the dashboard to show updated state and new activity
                this.renderDashboard(); 
                this.currentUser.profile.total_points += response.points_earned;
                this.renderUserProfile();
            } catch (error) {
                console.error(`Failed to complete task ${taskId}:`, error);
                alert(`Error: Could not complete task. ${error.message}`);
            }
        },

        // --- NAVIGATION & PAGE VIEWS ---
        navigate(sectionId) {
            // Hide all main content sections
            this.elements.appContainer.querySelectorAll('#main-content .section').forEach(s => s.classList.add('hidden'));
            // Hide create task section
            this.elements.createTaskSection.classList.add('hidden');

            // Show the target section
            const targetSection = document.getElementById(sectionId);
            if (targetSection) {
                 targetSection.classList.remove('hidden');
            } else {
                 document.getElementById('dashboard').classList.remove('hidden');
            }
            
            this.elements.fab.classList.toggle('hidden', sectionId === 'create-task');
            
            // Update nav link styles
            this.elements.navLinks.forEach(link => {
                link.classList.toggle('active', link.dataset.nav === sectionId);
            });
            
            switch (sectionId) {
                case 'dashboard': this.renderDashboard(); break;
                case 'tasks': this.renderAllTasks(); break;
                case 'feed': this.renderFullFeed(); break;
            }
        },
        
        async renderAllTasks() {
            try {
                const response = await this.fetchAPI('/tasks/?ordering=-created_at');
                this.renderTasks(response.results, this.elements.allTasksFeed);
            } catch(error) {
                this.elements.allTasksFeed.innerHTML = `<p class="text-center p-8 text-red-500">Could not load tasks.</p>`;
            }
        },
        
        async renderFullFeed() {
             try {
                const response = await this.fetchAPI('/feed/activities/?ordering=-created_at');
                this.renderActivityFeed(response.results, this.elements.fullActivityFeed);
            } catch(error) {
                this.elements.fullActivityFeed.innerHTML = `<p class="text-center p-8 text-red-500">Could not load activity feed.</p>`;
            }
        },
        
        // --- UTILITIES ---
        formatTimeAgo(dateString) {
            if (!dateString) return '';
            const date = new Date(dateString);
            const now = new Date();
            const seconds = Math.floor((now - date) / 1000);
            if (seconds < 60) return "just now";
            const minutes = Math.floor(seconds / 60);
            if (minutes < 60) return `${minutes}m ago`;
            const hours = Math.floor(minutes / 60);
            if (hours < 24) return `${hours}h ago`;
            const days = Math.floor(hours / 24);
            return `${days}d ago`;
        }
    };

    app.init();
    window.app = app; // For debugging
});