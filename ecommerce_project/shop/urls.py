from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # auth
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # vendor
    path("vendor/", views.vendor_dashboard, name="vendor_dashboard"),
    path("vendor/store/create/", views.store_create, name="store_create"),
    path("vendor/store/<int:store_id>/edit/", views.store_edit, name="store_edit"),
    path("vendor/store/<int:store_id>/delete/", views.store_delete, name="store_delete"),
    path("vendor/store/<int:store_id>/product/create/", views.product_create, name="product_create"),
    path("vendor/product/<int:product_id>/edit/", views.product_edit, name="product_edit"),
    path("vendor/product/<int:product_id>/delete/", views.product_delete, name="product_delete"),

    # buyer
    path("products/", views.product_list, name="product_list"),
    path("products/<int:product_id>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("review/<int:product_id>/add/", views.review_add, name="review_add"),

    # password reset
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset-password/<str:token>/", views.reset_password_page, name="reset_password_page"),
    path("reset-password/confirm/", views.reset_password_confirm, name="reset_password_confirm"),
]
