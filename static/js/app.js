// Initialize Alpine.js globally
document.addEventListener('alpine:init', () => {
    // Make Alpine data available globally
    window.Alpine = Alpine;
    
    // Define global Alpine data/state
    Alpine.store('sidebar', {
        open: false,
        toggle() {
            this.open = !this.open;
        },
        close() {
            this.open = false;
        }
    });

    // Add notifications store for global notification management
    Alpine.store('notifications', {
        items: [],
        unread: 0,
        init() {
            // Simulate fetching notifications
            this.items = [
                { id: 1, message: 'New message from Dr. Smith', read: false },
                { id: 2, message: 'Deadline approaching: Project Submission', read: false },
                { id: 3, message: 'New announcement posted', read: false }
            ];
            this.updateUnreadCount();
        },
        markAsRead(id) {
            const notification = this.items.find(item => item.id === id);
            if (notification) {
                notification.read = true;
                this.updateUnreadCount();
            }
        },
        markAllAsRead() {
            this.items.forEach(item => item.read = true);
            this.updateUnreadCount();
        },
        updateUnreadCount() {
            this.unread = this.items.filter(item => !item.read).length;
        }
    });

    // Add user store for user-related functionality
    Alpine.store('user', {
        profile: {},
        init() {
            // This would normally fetch from an API
            // For now we'll just use placeholder data
            this.profile = {
                isLoggedIn: true
            };
        }
    });
});

// Make sure Alpine directives are processed before AngularJS bootstraps
document.addEventListener('DOMContentLoaded', function() {
    // Check if Alpine.js is loaded properly
    if (typeof Alpine === 'undefined') {
        console.error('Alpine.js is not loaded properly. Check script inclusion order.');
    } else {
        console.log('Alpine.js is loaded and ready.');
    }

    // Initialize AngularJS app after Alpine is ready
    angular.module('dareApp', [])
        .controller('AppController', ['$scope', function($scope) {
            // AngularJS controller logic here
            $scope.appName = 'DARE PhD Management System';
            
            // Bridge between Alpine.js and AngularJS if needed
            $scope.toggleSidebar = function() {
                if (window.Alpine) {
                    window.Alpine.store('sidebar').toggle();
                }
            };

            // Add a method to check if Alpine.js is available
            $scope.isAlpineAvailable = function() {
                return typeof window.Alpine !== 'undefined';
            };
        }]);
});

// Add a global helper to debug Alpine.js issues
window.checkAlpine = function() {
    if (typeof Alpine === 'undefined') {
        console.error('Alpine.js is not loaded.');
        return false;
    }
    console.log('Alpine.js version:', Alpine.version);
    return true;
};
