from pathlib import Path
import hashlib,json,math,sys
from qgis.core import (Qgis,QgsApplication,QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform,QgsGeometry,QgsProject,QgsVectorLayer)
app=QgsApplication([],False)
app.initQgis()
p=Path(sys.argv[1]).resolve()
v=QgsVectorLayer(str(p),"College Park selection","ogr")
print(str(p),v.isValid(),v.featureCount(),v.crs().authid(),flush=True)
assert v.isValid() and v.featureCount()==3 and v.crs().authid() in {"EPSG:4326","OGC:CRS84"}
tx=QgsCoordinateTransform(v.crs(),QgsCoordinateReferenceSystem("EPSG:2236"),QgsProject.instance())
results=[]
for f in v.getFeatures():
    g=QgsGeometry(f.geometry())
    assert not g.isEmpty()
    g.transform(tx)
    expected=float(f["parcel_area_us_survey_sqft"])
    assert math.isclose(g.area(),expected,rel_tol=1e-10,abs_tol=0.01)
    results.append({"parcel_id":f["county_parcel_id"],"county_object_ids":str(f["county_object_ids"]),"projected_area_us_survey_sqft":g.area()})
assert len({r["parcel_id"] for r in results})==3
report={"qgis_version":Qgis.QGIS_VERSION,"source_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"source_crs":v.crs().authid(),
        "comparison_crs":"EPSG:2236","features":results}
Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(Qgis.QGIS_VERSION,len(results),flush=True)
