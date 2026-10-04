/* SPDX-License-Identifier: GPL-3.0-or-later */
/** Finite parser regressions only; never substitute for actual authorization tests. */
public final class DevelopmentFilterChecks {
    private static int cases;
    private static void check(boolean expected, String method, String path, String query) {
        cases++;
        if (DevelopmentCatalogFilter.supported(method, path, query) != expected)
            throw new AssertionError("finite request guard " + cases);
    }
    public static void main(String[] arguments) {
        String wfs = "service=WFS&version=1.0.0&request=GetFeature&typename=fixture%3Aprivate_points&outputformat=application%2Fjson";
        String wms = "service=WMS&version=1.1.1&request=GetMap&layers=fixture%3Aprivate_points&styles=&srs=EPSG%3A4326&bbox=0%2C0%2C4%2C4&width=512&height=512&format=image%2Fpng&transparent=FALSE";
        check(true, "GET", "/geoserver/wfs", wfs);
        check(true, "GET", "/geoserver/wms", wms);
        check(true, "GET", "/geoserver/wfs", wfs.replace("service=", "SERVICE="));
        for (String method : new String[]{"POST", "PATCH", "PUT", "DELETE", "HEAD", "OPTIONS"}) {
            check(false, method, "/geoserver/wfs", wfs); check(false, method, "/geoserver/wms", wms);
        }
        for (String path : new String[]{"/geoserver/rest/workspaces", "/geoserver/web/", "/geoserver/ows", "/geoserver/wfs/", "/geoserver//wfs", "/geoserver/wfs;ignored", "/geoserver/%77fs", "/wfs", "/geoserver/gwc/service/wms"}) {
            check(false, "GET", path, wfs); check(false, "GET", path, wms);
        }
        for (String extra : new String[]{"&LAYERS=fixture%3Aprivate_points", "&width=512", "&WIDTH=512", "&%77idth=512", "&sld=http%3A%2F%2Fexample.invalid%2Fstyle", "&viewparams=x", "&filter=x", "&", "&broken", "&x=%FF", "&x=%"}) {
            check(false, "GET", "/geoserver/wfs", wfs + extra); check(false, "GET", "/geoserver/wms", wms + extra);
        }
        check(false, "GET", "/geoserver/wfs", wfs.replace("private_points", "other_points"));
        check(false, "GET", "/geoserver/wfs", wfs.replace("GetFeature", "Transaction"));
        check(false, "GET", "/geoserver/wfs", wfs.replace("1.0.0", "2.0.0"));
        check(false, "GET", "/geoserver/wms", wms.replace("512", "4096"));
        check(false, "GET", "/geoserver/wms", wms.replace("styles=", "styles=other"));
        check(false, "GET", "/geoserver/wms", wms.replace("image%2Fpng", "image%2Fjpeg"));
        check(false, "GET", "/geoserver/wms", "x".repeat(2049));
        check(false, "GET", "/geoserver/wms", null);
        System.out.println("finite_request_guard_cases=" + cases);
    }
}
