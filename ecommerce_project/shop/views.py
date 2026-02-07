from __future__ import annotations

import secrets
from datetime import timedelta
from hashlib import sha1

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.mail import EmailMessage
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Order, OrderItem, Product, ResetToken, Review, Store


def _ensure_groups_exist():
    Group.objects.get_or_create(name="Vendors")
    Group.objects.get_or_create(name="Buyers")


def _is_vendor(user) -> bool:
    return user.is_authenticated and user.groups.filter(name="Vendors").exists()


def _is_buyer(user) -> bool:
    return user.is_authenticated and user.groups.filter(name="Buyers").exists()


def home(request):
    return redirect("product_list")


def register(request):
    _ensure_groups_exist()

    if request.method == "GET":
        return render(request, "shop/register.html")

    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    account_type = request.POST.get("account_type", "buyer").strip().lower()

    if not username or not password:
        return render(request, "shop/register.html", {"error": "Username and password are required."})

    if account_type not in {"buyer", "vendor"}:
        return render(request, "shop/register.html", {"error": "Invalid account type."})

    from django.contrib.auth.models import User
    if User.objects.filter(username=username).exists():
        return render(request, "shop/register.html", {"error": "Username already exists."})

    user = User.objects.create_user(username=username, password=password, email=email)

    group = Group.objects.get(name="Vendors" if account_type == "vendor" else "Buyers")
    user.groups.add(group)

    login(request, user)
    return redirect("vendor_dashboard" if account_type == "vendor" else "product_list")


def login_view(request):
    if request.method == "GET":
        return render(request, "shop/login.html")

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return render(request, "shop/login.html", {"error": "Invalid credentials."})

    login(request, user)
    return redirect("home")


def logout_view(request):
    logout(request)
    return redirect("login")


# -------------------------
# Vendor dashboard + CRUD
# -------------------------

@login_required(login_url="/login/")
def vendor_dashboard(request):
    if not _is_vendor(request.user):
        return HttpResponseForbidden("Vendors only.")

    stores = Store.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "shop/vendor_dashboard.html", {"stores": stores})


@login_required(login_url="/login/")
def store_create(request):
    if not _is_vendor(request.user):
        return HttpResponseForbidden("Vendors only.")

    if request.method == "GET":
        return render(request, "shop/store_form.html", {"mode": "create"})

    name = request.POST.get("name", "").strip()
    if not name:
        return render(request, "shop/store_form.html", {"mode": "create", "error": "Store name required."})

    Store.objects.create(name=name, owner=request.user)
    return redirect("vendor_dashboard")


@login_required(login_url="/login/")
def store_edit(request, store_id: int):
    if not _is_vendor(request.user):
        return HttpResponseForbidden("Vendors only.")

    store = get_object_or_404(Store, id=store_id, owner=request.user)

    if request.method == "GET":
        return render(request, "shop/store_form.html", {"mode": "edit", "store": store})

    name = request.POST.get("name", "").strip()
    if not name:
        return render(request, "shop/store_form.html", {"mode": "edit", "store": store, "error": "Name required."})

    store.name = name
    store.save()
    return redirect("vendor_dashboard")


@login_required(login_url="/login/")
def store_delete(request, store_id: int):
    if not _is_vendor(request.user):
        return HttpResponseForbidden("Vendors only.")
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    store.delete()
    return redirect("vendor_dashboard")


@login_required(login_url="/login/")
def product_create(request, store_id: int):
    if not _is_vendor(request.user):
        return HttpResponseForbidden("Vendors only.")
    store = get_object_or_404(Store, id=store_id, owner=request.user)

    if request.method == "GET":
        return render(request, "shop/product_form.html", {"mode": "create", "store": store})

    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    price = request.POST.get("price", "0").strip()
    stock_qty = request.POST.get("stock_qty", "0").strip()

    if not name:
        return render(request, "shop/product_form.html", {"mode": "create", "store": store, "error": "Name required."})

    Product.objects.create(
        store=store,
        name=name,
        description=description,
        price=price,
        stock_qty=stock_qty,
    )
    return redirect("vendor_dashboard")


@login_required(login_url="/login/")
def product_edit(request, product_id: int):
    if not _is_vendor(request.user):
        return HttpResponseForbidden("Vendors only.")
    product = get_object_or_404(Product, id=product_id, store__owner=request.user)

    if request.method == "GET":
        return render(request, "shop/product_form.html", {"mode": "edit", "product": product})

    product.name = request.POST.get("name", "").strip()
    product.description = request.POST.get("description", "").strip()
    product.price = request.POST.get("price", product.price)
    product.stock_qty = request.POST.get("stock_qty", product.stock_qty)
    product.is_active = True if request.POST.get("is_active") == "on" else False
    product.save()
    return redirect("vendor_dashboard")


@login_required(login_url="/login/")
def product_delete(request, product_id: int):
    if not _is_vendor(request.user):
        return HttpResponseForbidden("Vendors only.")
    product = get_object_or_404(Product, id=product_id, store__owner=request.user)
    product.delete()
    return redirect("vendor_dashboard")


# -------------------------
# Buyer browsing + cart
# -------------------------

def product_list(request):
    products = Product.objects.filter(is_active=True).select_related("store").order_by("name")
    return render(request, "shop/product_list.html", {"products": products})


def product_detail(request, product_id: int):
    product = get_object_or_404(Product.objects.select_related("store"), id=product_id, is_active=True)
    reviews = product.reviews.select_related("buyer").order_by("-created_at")
    return render(request, "shop/product_detail.html", {"product": product, "reviews": reviews})


def _get_cart(session) -> dict[str, int]:
    return session.get("cart", {})


def _save_cart(session, cart: dict[str, int]) -> None:
    session["cart"] = cart
    session.modified = True


def cart_add(request, product_id: int):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart = _get_cart(request.session)

    key = str(product.id)
    cart[key] = cart.get(key, 0) + 1
    _save_cart(request.session, cart)
    return redirect("cart")


def cart_remove(request, product_id: int):
    cart = _get_cart(request.session)
    key = str(product_id)
    if key in cart:
        cart.pop(key)
        _save_cart(request.session, cart)
    return redirect("cart")


def cart_view(request):
    cart = _get_cart(request.session)
    items = []
    total = 0

    for pid_str, qty in cart.items():
        product = get_object_or_404(Product, id=int(pid_str))
        line_total = float(product.price) * int(qty)
        total += line_total
        items.append({"product": product, "qty": qty, "line_total": line_total})

    return render(request, "shop/cart.html", {"items": items, "total": total})


@login_required(login_url="/login/")
def checkout(request):
    # Buyers only for checkout
    if not _is_buyer(request.user):
        return HttpResponseForbidden("Buyers only.")

    cart = _get_cart(request.session)
    if not cart:
        return render(request, "shop/cart.html", {"items": [], "total": 0, "error": "Cart is empty."})

    # Create order
    order = Order.objects.create(buyer=request.user)

    lines = []
    for pid_str, qty in cart.items():
        product = get_object_or_404(Product, id=int(pid_str), is_active=True)
        qty = int(qty)

        if product.stock_qty < qty:
            return render(request, "shop/cart.html", {"error": f"Not enough stock for {product.name}."})

        # decrement stock
        product.stock_qty -= qty
        product.save()

        item = OrderItem.objects.create(
            order=order,
            product=product,
            store=product.store,
            quantity=qty,
            unit_price=product.price,
        )
        lines.append(item)

    # clear cart session
    _save_cart(request.session, {})

    # Build invoice email
    subject = f"Invoice for Order #{order.id}"
    body_lines = [
        f"Hi {request.user.username},",
        "",
        f"Thanks for your purchase. Here is your invoice for Order #{order.id}:",
        "",
    ]
    grand_total = 0
    for item in lines:
        lt = item.line_total()
        grand_total += lt
        body_lines.append(
            f"- {item.product.name} (Store: {item.store.name}) x {item.quantity} @ {item.unit_price} = {lt}"
        )
    body_lines += ["", f"Total: {grand_total}", "", "Regards,", "eCommerce App"]

    if request.user.email:
        EmailMessage(subject, "\n".join(body_lines), None, [request.user.email]).send(fail_silently=True)

    return render(request, "shop/checkout_success.html", {"order": order, "items": lines})


@login_required(login_url="/login/")
def review_add(request, product_id: int):
    if not _is_buyer(request.user):
        return HttpResponseForbidden("Buyers only.")

    product = get_object_or_404(Product, id=product_id, is_active=True)
    if request.method != "POST":
        return redirect("product_detail", product_id=product.id)

    rating = int(request.POST.get("rating", "5"))
    comment = request.POST.get("comment", "").strip()

    # verified if buyer purchased this product before
    has_bought = OrderItem.objects.filter(order__buyer=request.user, product=product).exists()

    Review.objects.create(
        product=product,
        buyer=request.user,
        rating=max(1, min(5, rating)),
        comment=comment,
        verified=has_bought,
    )
    return redirect("product_detail", product_id=product.id)


# -------------------------
# Password reset (token + expiry)
# -------------------------

def forgot_password(request):
    if request.method == "GET":
        return render(request, "shop/forgot_password.html")

    email = request.POST.get("email", "").strip()
    if not email:
        return render(request, "shop/forgot_password.html", {"error": "Email required."})

    from django.contrib.auth.models import User
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return render(request, "shop/forgot_password.html", {"error": "No user with that email."})

    raw_token = secrets.token_urlsafe(16)
    token_hash = sha1(raw_token.encode()).hexdigest()
    expiry = timezone.now() + timedelta(minutes=10)

    ResetToken.objects.create(user=user, token_hash=token_hash, expiry_date=expiry)

    reset_url = request.build_absolute_uri(f"/reset-password/{raw_token}/")
    subject = "Password Reset"
    body = f"Hi {user.username},\n\nUse this link to reset your password (expires in 10 minutes):\n{reset_url}\n"

    EmailMessage(subject, body, None, [user.email]).send(fail_silently=True)

    return render(request, "shop/forgot_password.html", {"message": "Reset email sent (check console output)."})


def reset_password_page(request, token: str):
    token_hash = sha1(token.encode()).hexdigest()
    try:
        rt = ResetToken.objects.get(token_hash=token_hash, used=False)
    except ResetToken.DoesNotExist:
        rt = None

    if rt is None or rt.is_expired():
        if rt is not None:
            rt.delete()
        return render(request, "shop/reset_password.html", {"error": "Token invalid or expired.", "valid": False})

    # store token + user in session so confirm step is safe
    request.session["reset_user_id"] = rt.user_id
    request.session["reset_token_hash"] = token_hash

    return render(request, "shop/reset_password.html", {"valid": True})


def reset_password_confirm(request):
    if request.method != "POST":
        return redirect("login")

    user_id = request.session.get("reset_user_id")
    token_hash = request.session.get("reset_token_hash")

    password = request.POST.get("password", "")
    password_conf = request.POST.get("password_conf", "")
    if not password or password != password_conf:
        return render(request, "shop/reset_password.html", {"error": "Passwords do not match.", "valid": True})

    from django.contrib.auth.models import User
    user = get_object_or_404(User, id=user_id)

    rt = get_object_or_404(ResetToken, token_hash=token_hash, used=False)
    if rt.is_expired():
        rt.delete()
        return render(request, "shop/reset_password.html", {"error": "Token expired.", "valid": False})

    user.set_password(password)
    user.save()

    rt.used = True
    rt.save()

    # clear session
    request.session.pop("reset_user_id", None)
    request.session.pop("reset_token_hash", None)

    return redirect("login")
