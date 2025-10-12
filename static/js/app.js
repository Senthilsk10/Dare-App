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
            .when('/mailings', {
                templateUrl: '/static/js/partials/mailings.html',
                controller: 'MailingsCtrl'
            })
            .when('/notifications', {
                templateUrl: '/static/js/partials/notifications.html',
                controller: 'NotificationCtrl'
            })
            .otherwise({ redirectTo: '/departments' });
    }]);

    // Global toast notification function
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type} animate-slide-in w-72 rounded-lg border-l-4 p-4 shadow bg-white`;
        
        // Customize border color and icon based on type
        const icons = {
            info: '📣',
            success: '✅',
            error: '❌',
            warning: '⚠️',
        };
        const borderColors = {
            info: 'border-blue-500',
            success: 'border-green-500',
            error: 'border-red-500',
            warning: 'border-yellow-500',
        };
        
        toast.classList.add(borderColors[type] || borderColors.info);
        
        toast.innerHTML = `<div class="text-sm font-medium text-gray-800">${icons[type] || 'ℹ️'} ${message}</div>`;
        
        const container = document.getElementById('toast-container');
        container.appendChild(toast);
        
        // Auto-remove after 4s
        setTimeout(() => {
            toast.classList.add('opacity-0', 'translate-x-4');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
    
    
    /* ------------------------------------------------------------------
     * CENTRAL DATA SERVICE
     * ------------------------------------------------------------------*/
    app.factory('DataService', ['$http', '$location', '$rootScope', function($http, $location, $rootScope) {
        const base = '/api/'; // will automatically use https if site is served over https
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value || 
                       document.querySelector('meta[name=csrf-token]').getAttribute('content');
        $http.defaults.headers.common['X-CSRFToken'] = csrfToken;
        
        function getCurrentParams() {
            return $location.search();
        }

        function list(type) {
            const params = getCurrentParams();
            let url = base + type + '/';
            const query = Object.keys(params)
                .filter(k => params[k] !== undefined && params[k] !== null && params[k] !== '')
                .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(params[k])).join('&');
            
            if (query) url += '?' + query;
            return $http.get(url).then(r => {
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
        // Accepts optional params for filtering (e.g., department)
        function save(type, item) {
            const method = item.id ? 'put' : 'post';
            let url = item.id ? `${base}${type}/${item.id}/` : `${base}${type}/`;
            const params = getCurrentParams();
            const query = Object.keys(params)
                .filter(k => params[k] !== undefined && params[k] !== null && params[k] !== '')
                .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(params[k])).join('&');
            if (query) url += '?' + query;
            if (type=='students'){
                item.enrollment_date = new Date(item.enrollment_date).toISOString().slice(0, 10);
            }
            return $http[method](url, item)
                .then(r => {
                    showToast(`${type.slice(0, -1)} ${item.id ? 'updated' : 'created'} successfully`, 'success');
                    return r.data;
                })
                .catch(error => {
                    if (error.status === 400 && error.data) {
                        showToast('Please fix the form errors', 'error');
                        return Promise.reject(error);
                    }
                    showToast(`Failed to save ${type.slice(0, -1)}: ${error.statusText || 'Unknown error'}`, 'error');
                    return Promise.reject(error);
                });
        }
        function remove(type, item) {
            return $http.delete(base + type + '/' + item.id + '/')
                .then(() => {
                    showToast(`${type.slice(0, -1)} deleted successfully`, 'success');
                })
                .catch(error => {
                    showToast(`Failed to delete ${type.slice(0, -1)}: ${error.statusText || 'Unknown error'}`, 'error');
                    throw error;
                });
        }
        return { list, save, remove };
    }]);


    /* ------------------------------------------------------------------
     * CONTROLLERS
     * ------------------------------------------------------------------*/
    app.controller('AppController', ['$scope', '$location', '$route', function($scope, $location, $route) {
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
    

    app.controller('DepartmentCtrl', ['$scope', 'DataService', '$location', '$route', '$timeout', function($scope, DataService, $location, $route, $timeout) {
        $scope.user = window.CURRENT_USER;
        $scope.departments = [];
        $scope.selectedDept = null;
        $scope.showPanel = false;
        $scope.formErrors = {};
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

        $scope.goTo = function(path) {
            const deptId = $scope.selectedDept?.id || $location.search().department || null;
            const currentPath = $location.path();
            const newPath = `/${path}`;
            const newQuery = deptId ? { department: deptId } : {};
        
            // Navigate or reload
            if (currentPath === newPath) {
                $location.search(newQuery).replace();
                $route.reload();
            } else {
                $location.path(newPath).search(newQuery);
            }
        
            // Defer jQuery DOM setup after route change and rendering
            $timeout(() => {
                $timeout(() => {
                    ['#studentsTable', '#departmentsTable', '#guidesTable', '#coursesTable'].forEach(id => {
                        if ($.fn.DataTable.isDataTable(id)) {
                            $(id).DataTable().destroy();
                        }
                        $(id).DataTable({
                            responsive: true,
                            pageLength: 10,
                            destroy: true
                        });
                    });
                }, 200);
            }, 0);
        };
        

        $scope.goBack = function(path) {
            const deptId = $location.search().department;
            const newPath = `/${path}`;
            
            $location.path(newPath).search({ department: deptId });
        
            // Same pattern: wait for render, then apply DataTables
            $timeout(() => {
                $timeout(() => {
                    ['#studentsTable', '#departmentsTable', '#guidesTable', '#coursesTable'].forEach(id => {
                        if ($.fn.DataTable.isDataTable(id)) {
                            $(id).DataTable().destroy();
                        }
                        $(id).DataTable({
                            responsive: true,
                            pageLength: 10,
                            destroy: true
                        });
                    });
                }, 200);
            }, 0);
        };
        
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
        $scope.validateDepartment = function(dept) {
            $scope.formErrors = {};
            let isValid = true;
            if (!dept.name || dept.name.trim().length < 2) {
                $scope.formErrors.name = 'Department name is required (min 2 characters)'; isValid = false;
            }
            if (!dept.code || !/^[A-Z0-9]+$/.test(dept.code)) {
                $scope.formErrors.code = 'Code must contain only uppercase letters and numbers'; isValid = false;
            }
            if (!dept.faculty) {
                $scope.formErrors.faculty = 'Please select a faculty'; isValid = false;
            }
            if (!dept.head_of_department || dept.head_of_department.trim().length < 2) {
                $scope.formErrors.head_of_department = 'Head of Department is required (min 2 characters)'; isValid = false;
            }
            if (!dept.contact_email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(dept.contact_email)) {
                $scope.formErrors.contact_email = 'Valid email is required'; isValid = false;
            }
            if (dept.phone && !/^[0-9+\- ]*$/.test(dept.phone)) {
                $scope.formErrors.phone = 'Invalid phone number format'; isValid = false;
            }
            return isValid;
        };
        $scope.saveDept = function() {
            if (!$scope.validateDepartment($scope.selectedDept)) {
                showToast('Please fix the form errors', 'error');
                return;
            }
            DataService.save('departments', $scope.selectedDept).then(function() {
                $scope.closePanel();
                refresh();
            }).catch(function(error) {
                if (error.data) {
                    $scope.formErrors = error.data;
                }
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

    app.controller('GuideCtrl', ['$scope', 'DataService', '$location', '$route', '$timeout', function($scope, DataService, $location, $route, $timeout) {
        $scope.user = window.CURRENT_USER;
        $scope.formErrors = {};
        $scope.validateGuide = function(guide) {
            $scope.formErrors = {};
            let isValid = true;
            if (!guide.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(guide.email)) {
                $scope.formErrors.email = 'Valid email is required'; isValid = false;
            }
            if (!guide.employee_id || guide.employee_id.trim().length === 0) {
                $scope.formErrors.employee_id = 'Employee ID is required'; isValid = false;
            }
            if (!guide.name || guide.name.trim().length < 2) {
                $scope.formErrors.name = 'Name is required (min 2 characters)'; isValid = false;
            }
            if (!guide.department) {
                $scope.formErrors.department = 'Department is required'; isValid = false;
            }
            if (guide.phone && !/^[0-9+\- ]+$/.test(guide.phone)) {
                $scope.formErrors.phone = 'Invalid phone number format'; isValid = false;
            }
            if (guide.max_students < 0 || guide.max_students > 20) {
                $scope.formErrors.max_students = 'Max students must be between 0 and 20'; isValid = false;
            }
            return isValid;
        };
        $scope.goBack = function() {
            // Navigate back to departments list
            $location.path('/departments');
            
            // Reinitialize DataTables after navigation
            $timeout(() => {
                $timeout(() => {
                    ['#studentsTable', '#departmentsTable', '#guidesTable', '#coursesTable'].forEach(id => {
                        if ($.fn.DataTable.isDataTable(id)) {
                            $(id).DataTable().destroy();
                        }
                        $(id).DataTable({
                            responsive: true,
                            pageLength: 10,
                            destroy: true
                        });
                    });
                }, 200);
            }, 0);
        };
        var _saveGuide = $scope.saveGuide;
        $scope.saveGuide = function() {
            if (!$scope.validateGuide($scope.selectedGuide)) {
                showToast('Please fix the form errors', 'error');
                return;
            }
            let params = {};
            if ($scope.user && $scope.user.is_admin && $scope.user.department) {
                params.department = $scope.user.department;
            }
            DataService.save('guides', $scope.selectedGuide, params).then(function() {
                $scope.closePanel();
                refresh();
            });
        };

        $scope.guides = [];
        $scope.selectedGuide = null;
        $scope.showPanel = false;
        $scope.departmentsList = [];
        function refresh() {
            let params = {};
            if ($scope.user && $scope.user.is_admin && $scope.user.department) {
                params.department = $scope.user.department;
            }
            DataService.list('guides', params).then(list => $scope.guides = list);
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

    app.controller('StudentCtrl', ['$scope', 'DataService', '$location', '$route', '$timeout', function($scope, DataService, $location, $route, $timeout) {
        $scope.user = window.CURRENT_USER;
        $scope.formErrors = {};
        $scope.validateStudent = function(student) {
            $scope.formErrors = {};
            let isValid = true;
            if (!student.student_id || student.student_id.trim().length === 0) {
                $scope.formErrors.student_id = 'Student ID is required'; isValid = false;
            }
            if (!student.name || student.name.trim().length < 2) {
                $scope.formErrors.name = 'Name is required (min 2 characters)'; isValid = false;
            }
            if (!student.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(student.email)) {
                $scope.formErrors.email = 'Valid email is required'; isValid = false;
            }
            if (!student.course) {
                $scope.formErrors.course = 'Course is required'; isValid = false;
            }
            if (!student.enrollment_date) {
                $scope.formErrors.enrollment_date = 'Enrollment date is required'; isValid = false;
            }
            if (!student.current_semester || student.current_semester < 1 || student.current_semester > 12) {
                $scope.formErrors.current_semester = 'Semester must be between 1 and 12'; isValid = false;
            }
            if (student.phone && !/^[0-9+\- ]+$/.test(student.phone)) {
                $scope.formErrors.phone = 'Invalid phone number format'; isValid = false;
            }
            return isValid;
        };
        $scope.goBack = function() {
            // Navigate back to departments list
            $location.path('/departments');
            
            // Reinitialize DataTables after navigation
            $timeout(() => {
                $timeout(() => {
                    ['#studentsTable', '#departmentsTable', '#guidesTable', '#coursesTable'].forEach(id => {
                        if ($.fn.DataTable.isDataTable(id)) {
                            $(id).DataTable().destroy();
                        }
                        $(id).DataTable({
                            responsive: true,
                            pageLength: 10,
                            destroy: true
                        });
                    });
                }, 200);
            }, 0);
        };
        var _saveStudent = $scope.saveStudent;
        $scope.saveStudent = function() {
            if (!$scope.validateStudent($scope.selectedStudent)) {
                showToast('Please fix the form errors', 'error');
                return;
            }
            let params = {};
            if ($scope.user && $scope.user.is_admin && $scope.user.department) {
                params.department = $scope.user.department;
            }
            DataService.save('students', $scope.selectedStudent, params).then(function() {
                $scope.closePanel();
                refresh();
            });
        };

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
            let params = {};
            if ($scope.user && $scope.user.is_admin && $scope.user.department) {
                params.department = $scope.user.department;
            }
            DataService.list('students', params).then(list => $scope.students = list);
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

    app.controller('CourseCtrl', ['$scope', 'DataService', '$location', '$route', '$timeout', function($scope, DataService, $location, $route, $timeout) {
        $scope.user = window.CURRENT_USER;
        $scope.formErrors = {};
        $scope.validateCourse = function(course) {
            $scope.formErrors = {};
            let isValid = true;
            if (!course.name || course.name.trim().length < 2) {
                $scope.formErrors.name = 'Course name is required (min 2 characters)'; isValid = false;
            }
            if (!course.code || !/^[A-Z0-9]+$/.test(course.code)) {
                $scope.formErrors.code = 'Valid course code is required (uppercase letters and numbers only)'; isValid = false;
            }
            if (!course.department) {
                $scope.formErrors.department = 'Department is required'; isValid = false;
            }
            if (!course.total_semesters || course.total_semesters < 1 || course.total_semesters > 12) {
                $scope.formErrors.total_semesters = 'Total semesters must be between 1 and 12'; isValid = false;
            }
            if (!course.min_project_semester || course.min_project_semester < 1 || course.min_project_semester > course.total_semesters) {
                $scope.formErrors.min_project_semester = `Project semester must be between 1 and ${course.total_semesters}`; isValid = false;
            }
            if (!course.fee_per_semester || course.fee_per_semester < 0) {
                $scope.formErrors.fee_per_semester = 'Fee must be a positive number'; isValid = false;
            }
            return isValid;
        };
        $scope.goBack = function() {
            // Navigate back to departments list
            $location.path('/departments');
            
            // Reinitialize DataTables after navigation
            $timeout(() => {
                $timeout(() => {
                    ['#studentsTable', '#departmentsTable', '#guidesTable', '#coursesTable'].forEach(id => {
                        if ($.fn.DataTable.isDataTable(id)) {
                            $(id).DataTable().destroy();
                        }
                        $(id).DataTable({
                            responsive: true,
                            pageLength: 10,
                            destroy: true
                        });
                    });
                }, 200);
            }, 0);
        };
        var _saveCourse = $scope.saveCourse;
        $scope.saveCourse = function() {
            if (!$scope.validateCourse($scope.selectedCourse)) {
                showToast('Please fix the form errors', 'error');
                return;
            }
            let params = {};
            if ($scope.user && $scope.user.is_admin && $scope.user.department) {
                params.department = $scope.user.department;
            }
            DataService.save('courses', $scope.selectedCourse, params).then(function() {
                $scope.closePanel();
                refresh();
            });
        };

        $scope.courses = [];
        $scope.selectedCourse = null;
        $scope.showPanel = false;
        $scope.departmentsList = [];
        function refresh() {
            let params = {};
            if ($scope.user && $scope.user.is_admin && $scope.user.department) {
                params.department = $scope.user.department;
            }
            DataService.list('courses', params).then(list => $scope.courses = list);
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
    
    // Mailing List / Calendar Controller
    app.controller('MailingsCtrl', ['$scope', '$http', '$timeout', function($scope, $http, $timeout) {
        let calendar = null;
         // State
         $scope.year = new Date().getFullYear();
         $scope.month = new Date().getMonth() + 1;
         $scope.mailType = 'approach';
         $scope.summary = {};
         $scope.entries = [];
         $scope.calendarDays = [];
         $scope.selected = null;
         const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value || 
                document.querySelector('meta[name=csrf-token]').getAttribute('content');
        $http.defaults.headers.common['X-CSRFToken'] = csrfToken;

        $scope.generateCalendar = function() {
            $scope.calendarDays = [];
            const daysInMonth = new Date($scope.year, $scope.month, 0).getDate();
            for (let d = 1; d <= daysInMonth; d++) {
                const key = `${$scope.year}-${('0' + $scope.month).slice(-2)}-${('0' + d).slice(-2)}`;
                const count = ($scope.summary[key] || {})[$scope.mailType] || 0;
                $scope.calendarDays.push({ year: $scope.year, month: $scope.month, date: d, key, count });
            }
        };
         // Fetch monthly entries, build counts, and refresh calendar
         $scope.loadSummary = function() {
             $http.get('/api/email-list/', { params: { year: $scope.year, month: $scope.month, type: $scope.mailType } }).then(r => {
                 const list = r.data || [];
                 // ensure dates formatted and build summary map
                 const summary = {};
                 list.forEach(item=>{
                    console.log('item',item);
                     // format next dates to YYYY-MM-DD for binding
                     if(item.next_approach_email_date){
                         item.next_approach_email_date = item.next_approach_email_date.slice(0,10);
                     }
                     if(item.next_evaluation_email_date){
                         item.next_evaluation_email_date = item.next_evaluation_email_date.slice(0,10);
                     }
                     let keyVal = $scope.mailType==='approach' ? item.next_approach_email_date : item.next_evaluation_email_date;
                     if(keyVal){
                         if(keyVal instanceof Date){
                             keyVal = `${keyVal.getFullYear()}-${('0'+(keyVal.getMonth()+1)).slice(-2)}-${('0'+keyVal.getDate()).slice(-2)}`;
                         }
                         if(!summary[keyVal]) summary[keyVal] = {approach:0, project:0};
                         summary[keyVal][$scope.mailType] += 1;
                     }
                 });
                 $scope.summary = summary;
                 $scope.generateCalendar();
                 $timeout(renderCalendar, 0);
             });
         };

        // Select a date and load details
        $scope.selectDate = function(day) {
             const dateStr = `${day.year}-${('0'+day.month).slice(-2)}-${('0'+day.date).slice(-2)}`;
             $http.get('/api/email-details/', { params: { date: dateStr, type: $scope.mailType } }).then(r => {
                // console.log(r.data,day);
                $scope.entries = r.data;
                $scope.selected = null;
            });
        };

        // Open detail panel
        function toInputDate(val){
            // console.log("date:" , val);
            if(!val) return '';
            
            return new Date(val);
        }

        $scope.openDetail = function(entry) {
            const cloned = angular.copy(entry);
            cloned.next_approach_email_date = toInputDate(cloned.next_approach_email_date);
            cloned.next_evaluation_email_date = toInputDate(cloned.next_evaluation_email_date);
            $scope.selected = cloned;
        };

        // Close detail panel
        $scope.closeDetail = function() {
            $scope.selected = null;
            if(calendar){
                $timeout(()=>{ calendar.updateSize(); }, 0);
            }
        };

        // Close list panel
        $scope.closeList = function() {
            $scope.entries = [];
            $scope.selected = null;
            if(calendar){
                $timeout(()=>{ calendar.updateSize(); }, 0);
            }
        };

        // Switch mail type and reload
        $scope.switchMailType = function(type) {
            if ($scope.mailType === type) return;
            $scope.mailType = type;
            $scope.closeList();
            $scope.loadSummary();
        };




        // Update next email date
        $scope.updateNextDate = function(type) {
            
            $http.post('/api/email-details/', {
                id: $scope.selected.id,
                type: type,
                next_date: type === 'approach' ? $scope.selected.next_approach_email_date : $scope.selected.next_evaluation_email_date
            }).then(() => {
                $scope.loadSummary();
                $scope.selectDate({ year: $scope.year, month: $scope.month, date: new Date($scope.selected.next_approach_email_date || $scope.selected.next_evaluation_email_date).getDate() });
            });
        };

        // Send email
        $scope.sendEmail = function(isProject) {
            const url = isProject ? '/send-project-email/' : '/send-email/';
            $http.post(url, { project_pool_id: $scope.selected.id }).then(() => {
                $scope.loadSummary();
            });
        };

        function renderCalendar() {
            if (!window.FullCalendar) { console.warn('FullCalendar not loaded'); return; }
            const calEl = document.getElementById('mailing-calendar');
            if (!calEl) return;
            const events = [];            
            for (const [dateKey, obj] of Object.entries($scope.summary)) {
                if (obj && obj[$scope.mailType] > 0) {
                    events.push({ title: obj[$scope.mailType].toString(), start: dateKey, allDay: true, backgroundColor:'#3182ce', borderColor:'#3182ce', textColor:'#fff' });
                }
            }
            if(!calendar){
                calendar = new FullCalendar.Calendar(calEl, {
                initialView: 'dayGridMonth',
                initialDate: `${$scope.year}-${('0'+$scope.month).slice(-2)}-01`,
                height: 'auto',
                events: events,
                handleWindowResize: true,
                windowResizeDelay: 200,
                dateClick: function(info) {
                     const clickedDate = info.date;
                    //  $scope.selectedDate = dateStr;
                     $scope.selectDate({year:clickedDate.getFullYear(), month: clickedDate.getMonth()+1, date: clickedDate.getDate()});
                 },
                datesSet: function(info){
                    const dt = (info.view && info.view.currentDate) ? info.view.currentDate: calendar.getDate();
                    const newYear  = dt.getFullYear();
                    const newMonth = dt.getMonth() + 1;
                    if(newYear!==$scope.year || newMonth!==$scope.month){
                        $scope.$apply(()=>{
                            $scope.year=newYear;
                            $scope.month=newMonth;
                        });
                        $scope.loadSummary();
                    }
                }
            });
                calendar.render();
            } else {
                calendar.removeAllEvents();
                events.forEach(ev=>calendar.addEvent(ev));
            }
        }

        // Init
        $scope.loadSummary();
    }]);
    // Notification Controller
    app.controller('NotificationCtrl', ['$scope', '$http', '$timeout', function($scope, $http, $timeout) {
        $scope.notifications = [];
        $scope.activeTab = 'unread';
        $scope.unreadCount = 0;
        $scope.readCount = 0;
        $scope.currentPage = 1;
        $scope.pageSize = 20;
        $scope.totalPages = 1;
        $scope.loading = false;
        $scope.showPanel = false;
        $scope.selectedNotification = null;
        $scope.assignmentData = {};
        $scope.projects = [];
        $scope.updating = false;

        const NOTIFICATIONS_URL = '/api/admin-notifications/';
        const PROJECTS_URL = '/api/projects/';
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value || document.querySelector('meta[name=csrf-token]').getAttribute('content');
        $http.defaults.headers.common['X-CSRFToken'] = csrfToken;

        function loadCounts() {
            $http.get(NOTIFICATIONS_URL + 'counts/').then(function(r){
                $scope.unreadCount = r.data.unread_count || 0;
                $scope.readCount = r.data.read_count || 0;
            });
        }

        function loadNotifications() {
            $scope.loading = true;
            const params = {
                page: $scope.currentPage,
                page_size: $scope.pageSize,
                is_read: $scope.activeTab === 'read'
            };
            $http.get(NOTIFICATIONS_URL, { params: params }).then(function(r){
                $scope.notifications = r.data.results || [];
                $scope.totalPages = Math.ceil((r.data.count || 0) / $scope.pageSize);
                $scope.loading = false;
            }).catch(function(){ $scope.loading = false; });
        }

        $scope.setActiveTab = function(tab){
            $scope.activeTab = tab;
            $scope.currentPage = 1;
            loadNotifications();
        };

        $scope.openPanel = function(notification){
            console.log(notification);
            // get projects related to the mail (find student id or from email or project id)
            // but now i will simulate with all projects only
            $scope.projects = $http.get(PROJECTS_URL).then(function(r){
                console.log('r',r,'data',r.data);
                $scope.projects = r.data || [];
                console.log($scope.projects);
            });
            
            $scope.selectedNotification = notification;
            $scope.showPanel = true;
            $scope.assignmentData = { project_id: notification.project_id || '', notification_type: notification.notification_type };
        };

        $scope.closePanel = function(){
            $scope.showPanel = false;
            $scope.selectedNotification = null;
            $scope.assignmentData = {};
        };

        $scope.updateNotification = function(){
            if(!$scope.selectedNotification) return;
            let data = Object.assign({}, $scope.assignmentData, { id: $scope.selectedNotification.id, email: $scope.selectedNotification.from_email, is_read: true });
            $http.patch(NOTIFICATIONS_URL + $scope.selectedNotification.id + '/', data).then(function(){
                $scope.closePanel();
                loadCounts();
                loadNotifications();
            });
        };

        $scope.getPageRange = function(){
            const range = [];
            const start = Math.max(1, $scope.currentPage-2);
            const end = Math.min($scope.totalPages, $scope.currentPage+2);
            for(let i=start;i<=end;i++) range.push(i);
            return range;
        };

        $scope.goToPage = function(p){ if(p>=1 && p<= $scope.totalPages){ $scope.currentPage=p; loadNotifications(); }};

        // init
        loadCounts();
        loadNotifications();
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
