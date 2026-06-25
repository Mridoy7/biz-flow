from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/add/", views.supplier_form, name="supplier_add"),
    path("suppliers/<int:pk>/edit/", views.supplier_form, name="supplier_edit"),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/add/", views.invoice_form, name="invoice_add"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/edit/", views.invoice_form, name="invoice_edit"),
    path("invoices/<int:pk>/pdf/", views.invoice_pdf_view, name="invoice_pdf"),
    path("invoices/<int:pk>/file/", views.invoice_file_download, name="invoice_file_download"),
    path("invoices/<int:pk>/file/preview/", views.invoice_file_preview, name="invoice_file_preview"),
    path("invoices/attachments/<int:pk>/", views.invoice_attachment_download, name="invoice_attachment_download"),
    path("invoices/attachments/<int:pk>/preview/", views.invoice_attachment_preview, name="invoice_attachment_preview"),
    path("invoices/export/<str:filetype>/", views.invoice_export, name="invoice_export"),
    path("end-of-day/", views.endofday_list, name="endofday_list"),
    path("end-of-day/archived/", views.archived_endofday_list, name="archived_endofday_list"),
    path("end-of-day/add/", views.endofday_form, name="endofday_add"),
    path("end-of-day/<int:pk>/", views.endofday_detail, name="endofday_detail"),
    path("end-of-day/<int:pk>/edit/", views.endofday_form, name="endofday_edit"),
    path("end-of-day/<int:pk>/pdf/", views.endofday_pdf_view, name="endofday_pdf"),
    path("end-of-day/<int:pk>/file/<str:file_kind>/", views.endofday_file_download, name="endofday_file_download"),
    path("end-of-day/<int:pk>/file/<str:file_kind>/preview/", views.endofday_file_preview, name="endofday_file_preview"),
    path("end-of-day/<int:pk>/archive/", views.endofday_archive, name="endofday_archive"),
    path("end-of-day/export/<str:filetype>/", views.endofday_export, name="endofday_export"),
]
