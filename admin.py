from lucid_key_report_generator.models import KeyReport
from pnwmoths.species.models import Species
from cms.models import Page
from django.contrib import admin, messages
from django.http import HttpResponse
import csv, pickle
from base64 import binascii

class KeyReportAdmin(admin.ModelAdmin):
    class Meta:
        exclude = ('data',)

    actions = ['generate_key', 'compare_keys']
    list_display = ('created_at',)

    def compare_keys(self, request, queryset):
        if queryset.count() != 2:
            messages.error(request, "You can only generate a report for two items.")
            return

        class DictDiffer(object):
            """
            Calculate the difference between two dictionaries as:
            (1) items added
            (2) items removed
            (3) keys same in both but changed values
            (4) keys same in both and unchanged values
            """
            def __init__(self, current_dict, past_dict):
                self.current_dict, self.past_dict = current_dict, past_dict
                self.set_current, self.set_past = set(current_dict.keys()), set(past_dict.keys())
                self.intersect = self.set_current.intersection(self.set_past)
            def added(self):
                return self.set_current - self.intersect
            def removed(self):
                return self.set_past - self.intersect
            def changed(self):
                return set(o for o in self.intersect if self.past_dict[o] != self.current_dict[o])
            def unchanged(self):
                return set(o for o in self.intersect if self.past_dict[o] == self.current_dict[o])

        newest, oldest = list(queryset.order_by('-created_at'))
        nreport = pickle.loads(binascii.a2b_base64(newest.data).decode("zlib"))
        oreport = pickle.loads(binascii.a2b_base64(oldest.data).decode("zlib"))

        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=LucidKeyDiff-%s-%s.csv' % (str(newest).replace('.', '_'), str(oldest).replace('.', '_'))
        writer = csv.writer(response)

        # DEBUG
        oreport.pop("WA")
        oreport.pop("ID")
        nreport.pop("OR")

        # List changed rows
        key_rows_change = DictDiffer(nreport, oreport)
        added = ["Rows Added"]
        added.extend(list(key_rows_change.added()))
        writer.writerow(added)
        removed = ["Rows Removed"]
        removed.extend(list(key_rows_change.removed()))
        writer.writerow(removed)
        # TODO: List dict changes per species
        return response

    compare_keys.short_description = "Generate a difference report"

    def generate_key(self, request, queryset):
        if queryset.count() > 1:
            messages.error(request, "You can only generate one report at a time.")
            return

        report = queryset[0]
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=LucidKey-%s.csv' % str(report).replace('.', '_')
        writer = csv.writer(response)

        report = pickle.loads(binascii.a2b_base64(report.data).decode("zlib"))
        # Force correct ordering of printed results
        species_list = Page.objects.filter(species__isnull=False)
        species_list = [str(a.species_set.all()[:1][0]) for a in species_list]
        diff = [item for item in species_list if item not in list(report[1].keys())]
        species_list = [item for item in species_list if item not in diff]

        header = list(species_list)
        header.insert(0, "")
        writer.writerow(header)

        for row_header, vals in sorted(report.iteritems()):
            r = list()
            r.append(row_header)
            bool_to_s = lambda x: "X" if x else ""
            r.extend([bool_to_s(vals[x]) for x in species_list])
            writer.writerow(r)

        return response
    generate_key.short_description = "Generate a Lucid Key Report"

admin.site.register(KeyReport, KeyReportAdmin)
