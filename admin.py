from models import KeyReport
from pnwmoths.species.models import Species
from cms.models import Page
from django.contrib import admin, messages
from django.http import HttpResponse
import csv, pickle
from base64 import binascii

def module_exists(module_name):
    try:
        __import__(module_name)
    except ImportError:
        return False
    else:
        return True
if module_exists('pnwmoths'):
    from pnwmoths.species.models import Species

if module_exists('pnwbutterflies'):
    from pnwbutterflies.species.models import Species

class KeyReportAdmin(admin.ModelAdmin):
    class Meta:
        exclude = ('data',)

    actions = ['generate_key', 'compare_keys']
    list_display = ('created_at',)

    def get_actions(self, request):
        """ Remove Delete Selected to prevent accidental deletions."""
        actions = super(KeyReportAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions

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

        def keys_added_removed(writer, header,ndict,odict):
            key_rows_change = DictDiffer(ndict, odict)
            added = ["%s Added" % header]
            added.extend(list(key_rows_change.added()))
            writer.writerow(added)
            removed = ["%s Removed" % header]
            removed.extend(list(key_rows_change.removed()))
            writer.writerow(removed)

        # Large global changes
        # List changed rows
        keys_added_removed(writer, "Rows", nreport, oreport)
        # List changed species
        keys_added_removed(writer, "Species", nreport[1], oreport[1])

        # Finegrained changes
        # List modifications for each species
        months_en = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "Novemeber", "December"]

	# sort the output by states then ecoregions (using (len, str) sorting combo)
	# sorting by length with a max of 3 is a trick to sort the list by month, state, ecoregions
	order_out = list(nreport.iteritems())
	order_out.sort(key=lambda i: (min(3, len(str(i[0]))), i[0]))

        for row_header, vals in order_out:
            r = list()

            # convert to english month
            row_head = row_header
            if isinstance(row_head, int):
                row_head= months_en[row_head]
            r.append(row_head)

            bool_to_s = lambda x: "added" if x else "removed"

            if row_header in oreport:
                # present in new and old
                diff = DictDiffer(vals, oreport[row_header])
                r.extend(["%s %s" % (x, bool_to_s(vals[x])) for x in diff.changed()])
                writer.writerow(r)
            else:
                # the species is present in new, absent in old
                # newly added state/month etc.
                # so we could only interested in things that have been added as all vals
                # in old are effectively false.
                # if a species is in the old, but not in the new it would be marked
                # for wholesale delete above as species removed
                r.extend(["%s %s" % (x, bool_to_s(vals[x])) for x in vals if vals[x]])
                writer.writerow(r)

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

        months_en = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "Novemeber", "December"]
	# sort the output by states then ecoregions (using (len, str) sorting combo)
	# sorting by length with a max of 3 is a trick to sort the list by month, state, ecoregions
	order_out = list(report.iteritems())
	order_out.sort(key=lambda i: (min(3, len(str(i[0]))), i[0]))
        for row_header, vals in order_out:
            r = list()
            # convert to english month
            if isinstance(row_header, int):
                row_header = months_en[row_header]
            r.append(row_header)
            bool_to_s = lambda x: "X" if x else ""
            r.extend([bool_to_s(vals[x]) for x in species_list])
            writer.writerow(r)

        return response
    generate_key.short_description = "Generate a Lucid Key Report"

admin.site.register(KeyReport, KeyReportAdmin)
