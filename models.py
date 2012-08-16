from django.db import models
import json, pickle, zlib
from base64 import binascii
from pnwmoths.species.models import Species, SpeciesRecord, State
from cms.models import Page

from south.modelsinspector import add_introspection_rules
add_introspection_rules([], ["^django-lucid-key-report-generator\.models\.LongTextField"])
class LongTextField(models.TextField):
    def db_type(self):
        return 'longtext'


class KeyReport(models.Model):
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now = True)
    data = LongTextField(editable=False)

    def __unicode__(self):
        return str(self.created_at)
    def save(self, *args, **kwargs):
        if self.pk and len(KeyReport.objects.filter(pk=self.pk)) > 0:
            return #disallows editing

        # create report

        # initialize dict with key=species and val=False
        species_dict = dict()
        species_list = Page.objects.filter(species__isnull=False)
        species_list = [str(a.species_set.all()[:1][0]) for a in species_list]
        for s in species_list:
            species_dict[s] = False

        # list of tuples ("Habrosyne scripta", "WA", 7)
        def cast_None(f, val):
            if val is None:
                return None
            return f(val)

        s_vals = [("%s %s" % (g,s), cast_None(str, st), cast_None(int, m)) for g,s,st,m in SpeciesRecord.objects.all().values_list('species__genus', 'species__species', 'state__code', 'month')]

        # initialize table dict where keys are rows and cols are species_dict
        result = dict()
        for s in State.objects.all():
            result[str(s.code)] = dict(species_dict)
        for s in range(1,13):
            result[s] = dict(species_dict)
        #TODO: ecoregions

        for tup in s_vals:
            species, state, month = tup
            if state and species:
                result[state][species] = True
            if month and month in range(1,13) and species:
                result[month][species] = True
        
        s = binascii.b2a_base64(pickle.dumps(result).encode("zlib"))
        self.data = s

        # decode step
        # pickle.loads(binascii.a2b_base64(kr.data).decode("zlib"))

        super(KeyReport, self).save(*args, **kwargs)
