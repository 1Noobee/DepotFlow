from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    path("", views.expense_list, name="expense_list"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/approve/", views.expense_approve, name="expense_approve"),
    path("expenses/<int:pk>/reverse/", views.expense_reverse, name="expense_reverse"),

    path("supplier-payments/", views.supplier_payment_list, name="supplier_payment_list"),
    path("supplier-payments/new/", views.supplier_payment_create, name="supplier_payment_create"),
    path("supplier-payments/<int:pk>/reverse/", views.supplier_payment_reverse, name="supplier_payment_reverse"),

    path("supplier-rebates/", views.supplier_rebate_list, name="supplier_rebate_list"),
    path("supplier-rebates/new/", views.supplier_rebate_create, name="supplier_rebate_create"),
    path("supplier-rebates/<int:pk>/reverse/", views.supplier_rebate_reverse, name="supplier_rebate_reverse"),

    path("ledger/", views.ledger_list, name="ledger_list"),
]