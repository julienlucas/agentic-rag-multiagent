from .views import index, upload_file, process_question, load_file
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', index),
    path('load-file', load_file),
    path('upload-file', upload_file),
    path('process-question', process_question),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[1])
    urlpatterns += static('/', document_root=settings.STATICFILES_DIRS[1])
