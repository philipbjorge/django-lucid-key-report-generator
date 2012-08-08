from lucid_key_report_generator.models import KeyReport
from django.contrib import admin

class KeyReportAdmin(admin.ModelAdmin):
    list_display = ('created_at',)
    class Meta:
        exclude = ('data',)

admin.site.register(KeyReport)
