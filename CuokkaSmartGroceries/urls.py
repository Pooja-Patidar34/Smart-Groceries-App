"""
URL configuration for CuokkaSmartGroceries project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: HttpResponse("Welcome to Cuokka")),
    path('accounts/',include('accounts.urls')),
    path('profile/',include('profile_section.urls')),
    path('home/',include('home_section.urls')),
    path('pantry/',include('pantry_section.urls')),
    path('recipe/',include('recipe_section.urls')),
    path('meals/',include('meal_planner.urls')),
    path('AdminDashboard/',include("AdminDashboard.urls")),
    path('chat/',include('chat.urls')),
    path('notifications/',include('notifications.urls')),
    path('shoppinglist/',include('shoppinglist.urls')),
    path("ckeditor5/", include("django_ckeditor_5.urls")),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
