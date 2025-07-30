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
// Check Alpine only (this listener does NOT wrap Angular code)
document.addEventListener('DOMContentLoaded', function () {
    if (typeof Alpine === 'undefined') {
        console.error('Alpine.js is not loaded properly. Check script inclusion order.');
    } else {
        console.log('Alpine.js is loaded and ready.');
    }

    // Initialize AngularJS app after Alpine is ready
    /* Initialize AngularJS app with ngRoute for SPA functionality */
    const app = angular.module('dareApp', ['ngRoute']);

    /* ------------------------------------------------------------------
     * ROUTING CONFIGURATION
     * ------------------------------------------------------------------*/
    app.config(['$routeProvider', '$locationProvider', function($routeProvider, $locationProvider) {
        // Use simple '#/route' instead of default '#!/route'
        $locationProvider.hashPrefix('');
        $routeProvider
            .when('/departments', {
                templateUrl: '/static/js/partials/departments.html',
                controller: 'DepartmentCtrl'
            })
            .when('/guides', {
                templateUrl: '/static/js/partials/guides.html',
                controller: 'GuideCtrl'
            })
            .when('/students', {
                templateUrl: '/static/js/partials/students.html',
                controller: 'StudentCtrl'
            })
            .when('/courses', {
                templateUrl: '/static/js/partials/courses.html',
                controller: 'CourseCtrl'
            })
            .otherwise({ redirectTo: '/departments' });
    }]);

    /* ------------------------------------------------------------------
     * CENTRAL DATA SERVICE (stubbed for now)
     * Replace with real $http calls to your Django API endpoints later.
     * ------------------------------------------------------------------*/
    app.factory('DataService', ['$http', function($http) {
        const base = '/api/'; // will automatically use https if site is served over https
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value || 
                       document.querySelector('meta[name=csrf-token]').getAttribute('content');
        $http.defaults.headers.common['X-CSRFToken'] = csrfToken;
        function list(type) {
            return $http.get(base + type + '/').then(r => {
                // Patch for students: convert date strings to Date objects
                if (type === 'students') {
                    r.data.forEach(s => {
                        if (s.enrollment_date) s.enrollment_date = new Date(s.enrollment_date);
                        if (s.created_at) s.created_at = new Date(s.created_at);
                        if (s.updated_at) s.updated_at = new Date(s.updated_at);
                    });
                }
                return r.data;
            });
        }
        function save(type, item) {
            if (type === 'students') {
                item.enrollment_date = new Date(item.enrollment_date).toISOString().slice(0, 10);
            }
            if (item.id) {
                console.log(`saving type with id:${item.id}`);
                return $http.put(base + type + '/' + item.id + '/', item).then(r => r.data);
            }
            return $http.post(base + type + '/', item).then(r => r.data);
        }
        function remove(type, item) {
            return $http.delete(base + type + '/' + item.id + '/');
        }
        return { list, save, remove };
    }]);


    /* ------------------------------------------------------------------
     * CONTROLLERS
     * ------------------------------------------------------------------*/
    app.controller('AppController', ['$scope', function($scope) {
        $scope.appName = 'DARE PhD Management System';
        $scope.toggleSidebar = function() {
            if (window.Alpine) {
                window.Alpine.store('sidebar').toggle();
            }
        };
        $scope.isAlpineAvailable = function() {
            return typeof window.Alpine !== 'undefined';
        };
    }]);

    app.controller('DepartmentCtrl', ['$scope', 'DataService', function($scope, DataService) {
        $scope.departments = [];
        $scope.selectedDept = null;
        $scope.showPanel = false;
        $scope.facultyChoices = [
            {value: 'FACULTY_OF_AGRICULTURE', label: 'Faculty of Agriculture'},
            {value: 'FACULTY_OF_ARTS', label: 'Faculty of Arts'},
            {value: 'FACULTY_OF_DENTISTRY', label: 'Faculty of Dentistry'},
            {value: 'FACULTY_OF_EDUCATION', label: 'Faculty of Education'},
            {value: 'FACULTY_OF_ENGINEERING_TECHNOLOGY', label: 'Faculty of Engineering & Technology'},
            {value: 'FACULTY_OF_FINE_ARTS', label: 'Faculty of Fine Arts'},
            {value: 'FACULTY_OF_INDIAN_LANGUAGES', label: 'Faculty of Indian Languages'},
            {value: 'FACULTY_OF_MARINE_SCIENCES', label: 'Faculty of Marine Sciences'},
            {value: 'FACULTY_OF_MEDICINE', label: 'Faculty of Medicine'},
            {value: 'FACULTY_OF_SCIENCE', label: 'Faculty of Science'}
        ];
        // Load departments for dropdowns elsewhere
        $scope.departmentsList = [];
        function refresh() {
            DataService.list('departments').then(list => {
                $scope.departments = list;
                $scope.departmentsList = list;
            });
        }
        refresh();
        $scope.openPanelForNew = function() {
            $scope.selectedDept = { 
                name: '', 
                code: '', 
                faculty: 'FACULTY_OF_SCIENCE', // Default value
                head_of_department: '', 
                contact_email: '', 
                phone: '' 
            };
            $scope.showPanel = true;
        };
        $scope.openPanelForEdit = function(dept) {
            $scope.selectedDept = angular.copy(dept);
            $scope.showPanel = true;
        };
        $scope.closePanel = function() {
            $scope.selectedDept = null;
            $scope.showPanel = false;
        };
        $scope.saveDept = function() {
            DataService.save('departments', $scope.selectedDept).then(function() {
                $scope.closePanel();
                refresh();
            });
        };
        $scope.deleteDept = function() {
            if (window.confirm('Are you sure you want to delete this department? This action cannot be undone.')) {
                DataService.remove('departments', $scope.selectedDept).then(function() {
                    $scope.closePanel();
                    refresh();
                });
            }
        };
    }]);

    app.controller('GuideCtrl', ['$scope', 'DataService', function($scope, DataService) {
        $scope.guides = [];
        $scope.selectedGuide = null;
        $scope.showPanel = false;
        $scope.departmentsList = [];
        function refresh() {
            DataService.list('guides').then(list => $scope.guides = list);
            DataService.list('departments').then(list => $scope.departmentsList = list);
        }
        refresh();
        $scope.openPanelForNew = function() {
            $scope.selectedGuide = { email: '', employee_id: '', department: '', designation: '', specialization: '', phone: '', is_active: true, max_students: 5 };
            $scope.showPanel = true;
        };
        $scope.openPanelForEdit = function(guide) {
            $scope.selectedGuide = angular.copy(guide);
            $scope.showPanel = true;
        };
        $scope.closePanel = function() {
            $scope.selectedGuide = null;
            $scope.showPanel = false;
        };
        $scope.saveGuide = function() {
            DataService.save('guides', $scope.selectedGuide).then(function() {
                $scope.closePanel();
                refresh();
            });
        };
        $scope.deleteGuide = function() {
            if (window.confirm('Are you sure you want to delete this guide? This action cannot be undone.')) {
                DataService.remove('guides', $scope.selectedGuide).then(function() {
                    $scope.closePanel();
                    refresh();
                });
            }
        };
        $scope.getDepartmentName = function(deptId) {
            var d = $scope.departmentsList.find(x => x.id === deptId);
            return d ? d.name : '';
        };
    }]);

    app.controller('StudentCtrl', ['$scope', 'DataService', function($scope, DataService) {
        $scope.students = [];
        $scope.selectedStudent = null;
        $scope.showPanel = false;
        $scope.coursesList = [];
        $scope.guidesList = [];
        $scope.statusOptions = [
            'ENROLLED', 'PROJECT_PHASE', 'SYNOPSIS_SUBMITTED', 'EVALUATOR_ASSIGNED', 'PROJECT_SUBMITTED',
            'UNDER_EVALUATION', 'VIVA_READY', 'VIVA_COMPLETED', 'COMPLETED', 'DISCONTINUED'
        ];
        function refresh() {
            DataService.list('students').then(list => $scope.students = list);
            DataService.list('courses').then(list => $scope.coursesList = list);
            DataService.list('guides').then(list => $scope.guidesList = list);
        }
        refresh();
        $scope.openPanelForNew = function() {
            $scope.selectedStudent = { student_id: '', email: '', course: '', guide: '', enrollment_date: '', current_semester: 1, status: 'ENROLLED', phone: '', address: '', is_active: true };
            $scope.showPanel = true;
        };
        $scope.openPanelForEdit = function(student) {
            $scope.selectedStudent = angular.copy(student);
            $scope.showPanel = true;
        };
        $scope.closePanel = function() {
            $scope.selectedStudent = null;
            $scope.showPanel = false;
        };
        $scope.saveStudent = function() {
            DataService.save('students', $scope.selectedStudent).then(function() {
                $scope.closePanel();
                refresh();
            });
        };
        $scope.deleteStudent = function() {
            if (window.confirm('Are you sure you want to delete this student? This action cannot be undone.')) {
                DataService.remove('students', $scope.selectedStudent).then(function() {
                    $scope.closePanel();
                    refresh();
                });
            }
        };
        $scope.getCourseName = function(courseId) {
            var c = $scope.coursesList.find(x => x.id === courseId);
            return c ? c.name : '';
        };
    }]);

    app.controller('CourseCtrl', ['$scope', 'DataService', function($scope, DataService) {
        $scope.courses = [];
        $scope.selectedCourse = null;
        $scope.showPanel = false;
        $scope.departmentsList = [];
        function refresh() {
            DataService.list('courses').then(list => $scope.courses = list);
            DataService.list('departments').then(list => $scope.departmentsList = list);
        }
        refresh();
        $scope.openPanelForNew = function() {
            $scope.selectedCourse = { name: '', code: '', department: '', total_semesters: 8, min_project_semester: 4, fee_per_semester: 0 };
            $scope.showPanel = true;
        };
        $scope.openPanelForEdit = function(course) {
            $scope.selectedCourse = angular.copy(course);
            $scope.showPanel = true;
        };
        $scope.closePanel = function() {
            $scope.selectedCourse = null;
            $scope.showPanel = false;
        };
        $scope.saveCourse = function() {
            DataService.save('courses', $scope.selectedCourse).then(function() {
                $scope.closePanel();
                refresh();
            });
        };
        $scope.deleteCourse = function() {
            if (window.confirm('Are you sure you want to delete this course? This action cannot be undone.')) {
                DataService.remove('courses', $scope.selectedCourse).then(function() {
                    $scope.closePanel();
                    refresh();
                });
            }
        };
        $scope.getDepartmentName = function(deptId) {
            var d = $scope.departmentsList.find(x => x.id === deptId);
            return d ? d.name : '';
        };
    }]);

    // Angular app is ready – log route events
    app.run(['$rootScope', function ($rootScope) {
        $rootScope.$on('$routeChangeError', function (event, current, previous, rejection) {
            console.error('Route change error:', rejection);
        });
        $rootScope.$on('$routeChangeStart', function (evt, next) {
            console.log('Navigating to', next.originalPath);
        });
    }]);

    // Only bootstrap AngularJS SPA if on /onboarding/ route
    if (window.location.pathname.startsWith('/onboarding/')) {
        angular.bootstrap(document, ['dareApp']);
    }
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
