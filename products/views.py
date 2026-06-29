from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Product, ProductCategory, ProductPurchase
from .services import purchase_product


@login_required
def product_list(request):
    products = Product.objects.filter(status=Product.Status.PUBLISHED).select_related("category")
    category_slug = request.GET.get("category", "").strip()
    q = request.GET.get("q", "").strip()
    if category_slug:
        products = products.filter(category__slug=category_slug)
    if q:
        products = products.filter(title__icontains=q)
    categories = ProductCategory.objects.filter(is_active=True)
    paginator = Paginator(products, 24)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(
        request,
        "products/product_list.html",
        {
            "products": page_obj.object_list,
            "page_obj": page_obj,
            "page_query": query_params.urlencode(),
            "categories": categories,
            "selected_category": category_slug,
            "search_query": q,
        },
    )


@login_required
def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)
    purchase = ProductPurchase.objects.filter(
        product=product,
        user=request.user,
        status=ProductPurchase.Status.COMPLETED,
    ).first()
    return render(request, "products/product_detail.html", {"product": product, "purchase": purchase})


@login_required
@require_POST
def purchase_product_view(request, slug):
    product = get_object_or_404(Product, slug=slug)
    try:
        purchase = purchase_product(product=product, user=request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
        return redirect("product_detail", slug=product.slug)
    messages.success(request, "Product purchase completed.")
    return redirect("product_purchase_detail", purchase_id=purchase.pk)


@login_required
def product_library(request):
    purchases = (
        ProductPurchase.objects.filter(user=request.user, status=ProductPurchase.Status.COMPLETED)
        .select_related("product", "product__category")
        .all()
    )
    return render(request, "products/library.html", {"purchases": purchases})


@login_required
def product_purchase_detail(request, purchase_id):
    purchase = get_object_or_404(
        ProductPurchase.objects.select_related("product", "product__category"),
        pk=purchase_id,
    )
    if purchase.user != request.user and not request.user.is_staff:
        return redirect("product_library")
    return render(request, "products/purchase_detail.html", {"purchase": purchase})
