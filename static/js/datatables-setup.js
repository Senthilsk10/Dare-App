// DataTables setup for all SPA tables
$(document).ready(function() {
  setTimeout(function() {
    if ($.fn.DataTable) {
      $('#studentsTable').DataTable();
      $('#departmentsTable').DataTable();
      $('#guidesTable').DataTable();
      $('#coursesTable').DataTable();
    }
  }, 300);
});
