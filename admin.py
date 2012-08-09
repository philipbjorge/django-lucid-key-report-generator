from lucid_key_report_generator.models import KeyReport
from django.contrib import admin, messages
from django.http import HttpResponse
import csv, pickle
from base64 import binascii

class KeyReportAdmin(admin.ModelAdmin):
    class Meta:
        exclude = ('data',)

    actions = ['generate_key']
    list_display = ('created_at',)

    def generate_key(self, request, queryset):
        if queryset.count() > 1:
            messages.error(request, "You can only generate one report at a time.")
            return

        report = queryset[0]
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=LucidKey-%s.csv' % str(report).replace('.', '_')
        writer = csv.writer(response)

        report = pickle.loads(binascii.a2b_base64(report.data).decode("zlib"))
        header = report[1].keys()
        header.insert(0, "")
        writer.writerow(header)

        # TODO: Force sorted ordering
        for row_header, vals in report.iteritems():
            r = list()
            r.append(row_header)
            bool_to_s = lambda x: "X" if x else ""
            r.extend([bool_to_s(x) for x in vals.values()])
            writer.writerow(r)

        return response
    generate_key.short_description = "Generate a Lucid Key Report"

admin.site.register(KeyReport, KeyReportAdmin)
