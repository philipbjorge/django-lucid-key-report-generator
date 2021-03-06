from django.db import models
import json, pickle, zlib
from base64 import binascii
from cms.models import Page

def module_exists(module_name):
    try:
        __import__(module_name)
    except ImportError:
        return False
    else:
        return True

if module_exists('pnwmoths'):
    from pnwmoths.app.species.models import Species, SpeciesRecord, State

if module_exists('pnwsawflies'):
    from pnwsawflies.app.species.models import Species, SpeciesRecord, State

if module_exists('pnwbutterflies'):
    from pnwbutterflies.app.species.models import Species, SpeciesRecord, State

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


	# Initialize geography vars
	import gdal
	from osgeo import ogr, osr

	# load the shape file as a layer
	ds_in = ogr.Open("/usr/local/lib/python2.6/site-packages/django-lucid-key-report-generator/48US_BC_Ecoregions_simple.shp")
	lyr_in = ds_in.GetLayerByIndex(0)
	lyr_in.ResetReading()

	# field index for which i want the data extracted
	idx_reg = lyr_in.GetLayerDefn().GetFieldIndex("ECOREGION")
	idx_state = lyr_in.GetLayerDefn().GetFieldIndex("STATE")

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

        s_vals = [("%s %s" % (g,s), cast_None(str, st), cast_None(int, m)) for g,s,st,m in SpeciesRecord.records.all().values_list('species__genus', 'species__species', 'state__code', 'month')]

        # initialize table dict where keys are rows and cols are species_dict
        result = dict()
        for s in State.objects.all():
            result[str(s.code)] = dict(species_dict)
        for s in range(1,13):
            result[s] = dict(species_dict)
	for s in lyr_in:  # ecoregions
	    # ecoregion key by "ecoregion (state)"
	    if s.GetFieldAsString(idx_state).lower() in ["washington", "oregon", "montana", "idaho", "british columbia"]:
                result[str(s.GetFieldAsString(idx_reg) + " (" + s.GetFieldAsString(idx_state) + ")")] = dict(species_dict)

	# ECOREGIONS
	#
	cached = dict()
	def check(lat, lon, lyr_in, idx_reg):
	    # create point geometry
	    pt = ogr.Geometry(ogr.wkbPoint)
	    pt.SetPoint_2D(0, lon, lat)
	    spatialRef = osr.SpatialReference()
	    spatialRef.ImportFromEPSG(4326)
	    coordTransform = osr.CoordinateTransformation(spatialRef, lyr_in.GetSpatialRef())
	    pt.Transform(coordTransform)

	    lyr_in.SetSpatialFilter(pt)

	    # go over all the polygons in the layer see if one include the point
	    for feat_in in lyr_in:
		ply = feat_in.GetGeometryRef()
		# test
		if ply and ply.Contains(pt):
		    # ecoregion name
		    return (feat_in.GetFieldAsString(idx_reg), feat_in.GetFieldAsString(idx_state))
	    return (None, None)

	# Gets a unique set of (lat,lon,species) tuples limited to WA, OR, MT, ID, and BC
	lat_lon_species = set( ((rec.latitude, rec.longitude, rec.species.name) for rec in SpeciesRecord.records.select_related('species').filter(latitude__isnull=False, longitude__isnull=False, state__code__in=["WA", "OR", "MT", "ID", "BC"]))) 
	for (lat, lon, species) in lat_lon_species:
	    if (lat > -90 and lat < 90) and (lon > -180 and lon < 180):
		# Use a dictionary cache to speed up slow Contains lookup
		if (lat, lon) in cached:
		    ecoregion, state = cached[(lat, lon)]
		else:
	            ecoregion, state = check(lat, lon, lyr_in, idx_reg)
		    cached[(lat, lon)] = (ecoregion, state)

	        if ecoregion and state and species and str(ecoregion + " (" + state + ")") in result:
		    # ATTENTION: This is silly, but don't delete this print. For whatever reason it tricks apache into letting this request
		    # run longer then 30 seconds!
		    print ecoregion
		    result[str(ecoregion + " (" + state + ")")][species] = True
	# END ECOREGIONS

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
