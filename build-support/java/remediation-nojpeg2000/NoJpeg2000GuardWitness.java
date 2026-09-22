/* AmbisGIS authored regression witness; SPDX-License-Identifier: GPL-2.0-or-later */
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import org.geoserver.filters.NoJpeg2000Filter;
import org.geoserver.filters.NoJpeg2000Policy;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

public final class NoJpeg2000GuardWitness {
    static int assertions;
    static void require(boolean value, String message) {
        assertions++;
        if (!value) throw new AssertionError(message);
    }
    static byte[] JP2 = {0,0,0,12,106,80,32,32,13,10,(byte)135,10,0,0,0,0};
    static byte[] J2K = {(byte)255,79,(byte)255,81,0,0,0,0};
    static MockHttpServletRequest request(String path, String type, byte[] bytes) {
        MockHttpServletRequest r = new MockHttpServletRequest("PUT", "/geoserver"+path);
        r.setContextPath("/geoserver");r.setContentType(type);r.setContent(bytes);return r;
    }
    static void reject(MockHttpServletRequest request) throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();
        new NoJpeg2000Filter().doFilter(request,response,(a,b)->{throw new AssertionError("rejection reached downstream");});
        require(response.getStatus()==415,"explicit 415 required");
        require(response.getContentAsString().equals(NoJpeg2000Policy.MESSAGE),"safe bounded diagnostic required");
    }
    public static void main(String[] args) throws Exception {
        for(String name: new String[]{"jp2","J2K","jpeg2000","image/jp2; charset=UTF-8"}) require(NoJpeg2000Policy.format(name),"alias missed");
        for(String name: new String[]{"jpeg","image/jpeg","image/png","geotiff","image/tiff","myjp2"}) require(!NoJpeg2000Policy.format(name),"unrelated format blocked");
        require(NoJpeg2000Policy.signature(JP2),"JP2 signature");require(NoJpeg2000Policy.signature(J2K),"codestream signature");
        require(!NoJpeg2000Policy.signature(new byte[]{(byte)255,(byte)216,(byte)255,(byte)224}),"JPEG must remain supported");
        for(byte[] bytes: new byte[][]{JP2,J2K}) {
            reject(request("/rest/workspaces/fixture/coveragestores/rejected/file.geotiff?unused", "image/tiff",bytes));
            reject(request("/rest/imports/0/tasks/disguised.png", "application/octet-stream",bytes));
        }
        reject(request("/rest/workspaces/fixture/coveragestores/rejected/file.jp2","image/png",new byte[0]));
        reject(request("/rest/imports/0/tasks/disguised.png","image/jp2",new byte[0]));
        for(String operation:new String[]{"GetMap","getCoverage","GETTILE"}) {
            MockHttpServletRequest r=request("/ows","text/plain",new byte[0]);r.setMethod("GET");
            r.setParameter("request",operation);r.setParameter("FORMAT","image/jp2");reject(r);
        }
        for(byte[] input:new byte[][]{new byte[0],new byte[]{1,2},"not JPEG2000 streamed input".getBytes(StandardCharsets.UTF_8)}) {
            MockHttpServletRequest r=request("/rest/imports/0/tasks/ordinary.tif","image/tiff",input);
            MockHttpServletResponse response=new MockHttpServletResponse();
            new NoJpeg2000Filter().doFilter(r,response,(a,b)->require(Arrays.equals(input,a.getInputStream().readAllBytes()),"lookahead changed stream"));
            require(response.getStatus()==200,"valid input status changed");
        }
        MockHttpServletRequest reader=request("/rest/workspaces/fixture/coveragestores/store/external.geotiff","text/plain","file:/tmp/plain.tif".getBytes(StandardCharsets.UTF_8));
        new NoJpeg2000Filter().doFilter(reader,new MockHttpServletResponse(),(a,b)->require(a.getReader().readLine().equals("file:/tmp/plain.tif"),"reader lookahead lost bytes"));
        MockHttpServletRequest json=request("/rest/imports/0/tasks/0","application/json","{\"format\":\"image/jp2\"}".getBytes(StandardCharsets.UTF_8));
        new NoJpeg2000Filter().doFilter(json,new MockHttpServletResponse(),(a,b)->require(a==json,"native JSON parser input must remain unchanged"));
        Path dir=Path.of(args[0]);Files.createDirectory(dir);Files.write(dir.resolve("disguised.png"),JP2);
        require(NoJpeg2000Policy.tree(dir),"ZIP/mosaic extracted content detection");
        Files.delete(dir.resolve("disguised.png"));Files.write(dir.resolve("ordinary.jpeg"),new byte[]{(byte)255,(byte)216});
        require(!NoJpeg2000Policy.tree(dir),"ordinary JPEG directory must remain eligible");
        System.out.println("NO_JPEG2000_GUARD_ASSERTIONS="+assertions);
    }
}
