from .views import index, upload_file, process_question, load_file
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', index),
    path('api/load-file', load_file),
    path('api/upload-file', upload_file),
    path('api/process-question', process_question),
]

if settings.DEBUG and len(settings.STATICFILES_DIRS) > 0:
    static_dir = settings.STATICFILES_DIRS[0]
    urlpatterns += static(settings.STATIC_URL, document_root=static_dir)
