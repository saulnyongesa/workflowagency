from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('core.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('reports/', include('reports.urls')),
    path('wallet/', include('wallets.urls')),
    path('payments/', include('payments.urls')),
    path('referrals/', include('referrals.urls')),
    path('jobs/', include('jobs.urls')),
    path('products/', include('products.urls')),
    path('support/', include('support.urls')),
]
