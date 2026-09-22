/* AmbisGIS authored regression witness; SPDX-License-Identifier: GPL-2.0-or-later */
import java.nio.charset.StandardCharsets;
import java.io.ByteArrayOutputStream;
import org.geoserver.importer.rest.ImportTaskController;
import org.geoserver.rest.RestException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
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
    static byte[] zip(String name, byte[] bytes) throws Exception {
        ByteArrayOutputStream output=new ByteArrayOutputStream();
        try(ZipOutputStream zip=new ZipOutputStream(output)) { zip.putNextEntry(new ZipEntry(name));zip.write(bytes);zip.closeEntry(); }
        return output.toByteArray();
    }
    static class Controller extends ImportTaskController { Controller() { super(null); } }
    static void multipart(byte[] image, String filename, String mime) throws Exception {
        multipart(image, filename, mime, 415, NoJpeg2000Policy.MESSAGE);
    }
    static void multipart(byte[] image, String filename, String mime, int status, String message) throws Exception {
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        // The first part is valid, proving the preflight examines all parts before accepting one.
        body.write("--AmbisGISBoundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"ordinary.txt\"\r\nContent-Type: text/plain\r\n\r\nordinary\r\n".getBytes(StandardCharsets.UTF_8));
        body.write(("--AmbisGISBoundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\""+filename+"\"\r\nContent-Type: "+mime+"\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        body.write(image);body.write("\r\n--AmbisGISBoundary--\r\n".getBytes(StandardCharsets.UTF_8));
        MockHttpServletRequest r=request("/rest/imports/0/tasks","multipart/form-data; boundary=AmbisGISBoundary",body.toByteArray());r.setMethod("POST");
        try { new Controller().handleMultiPartFormUpload(r,null); throw new AssertionError("multipart accepted unsupported image"); }
        catch(RestException expected) { require(expected.getStatus().value()==status,"multipart explicit rejection");require(expected.getMessage().equals(message),"multipart diagnostic"); }
    }
    public static void main(String[] args) throws Exception {
        for(String name: new String[]{"jp2","J2K","jpeg2000","JPEG 2000","JPEG_2000","jpf","image/x-jp2","image/jpm","image/mj2","image/x-jpeg2000","image/jp2; charset=UTF-8"}) require(NoJpeg2000Policy.format(name),"alias missed");
        for(String name: new String[]{"jpeg","image/jpeg","image/png","geotiff","image/tiff","myjp2"}) require(!NoJpeg2000Policy.format(name),"unrelated format blocked");
        require(NoJpeg2000Policy.signature(JP2),"JP2 signature");require(NoJpeg2000Policy.signature(J2K),"codestream signature");
        require(NoJpeg2000Policy.signature(new byte[]{(byte)255,79}),"truncated SOC rejection");
        require(NoJpeg2000Policy.signature(Arrays.copyOf(JP2,8)),"truncated JP2 rejection");
        require(!NoJpeg2000Policy.signature(new byte[]{(byte)255,(byte)216,(byte)255,(byte)224}),"JPEG must remain supported");
        for(byte[] bytes: new byte[][]{JP2,J2K}) {
            reject(request("/rest/workspaces/fixture/coveragestores/rejected/file.geotiff?unused", "image/tiff",bytes));
            reject(request("/rest/imports/0/tasks/disguised.png", "application/octet-stream",bytes));
        }
        reject(request("/rest/workspaces/fixture/coveragestores/rejected/file.geotiff","application/json",JP2));
        reject(request("/rest/imports/0/tasks/disguised.png","application/xml",J2K));
        reject(request("/rest/workspaces/fixture/coveragestores/rejected/file.jp2","image/png",new byte[0]));
        reject(request("/rest/imports/0/tasks/disguised.png","image/jp2",new byte[0]));
        for(String operation:new String[]{"GetMap","getCoverage","GETTILE"}) {
            MockHttpServletRequest r=request("/ows","text/plain",new byte[0]);r.setMethod("GET");
            r.setParameter("ReQuEsT",operation);r.setParameter("FORMAT","image/jp2");reject(r);
        }
        for(byte[] input:new byte[][]{new byte[0],new byte[]{1,2},"not JPEG2000 streamed input".getBytes(StandardCharsets.UTF_8)}) {
            MockHttpServletRequest r=request("/rest/imports/0/tasks/ordinary.tif","image/tiff",input);
            MockHttpServletResponse response=new MockHttpServletResponse();
            new NoJpeg2000Filter().doFilter(r,response,(a,b)->require(Arrays.equals(input,a.getInputStream().readAllBytes()),"lookahead changed stream"));
            require(response.getStatus()==200,"valid input status changed");
        }
        for(String metadataType:new String[]{"application/json","application/xml"}) {
            MockHttpServletRequest metadata=request("/rest/workspaces/fixture/coveragestores/ordinary.jp2",metadataType,"{\"coverageStore\":{\"enabled\":true}}".getBytes(StandardCharsets.UTF_8));
            MockHttpServletResponse metadataResponse=new MockHttpServletResponse();
            final boolean[] invoked={false};
            new NoJpeg2000Filter().doFilter(metadata,metadataResponse,(a,b)->{invoked[0]=true;require(a==metadata,"metadata request parser changed");});
            require(invoked[0] && metadataResponse.getStatus()==200,"ordinary store named jp2 metadata must remain native");
        }
        MockHttpServletRequest reader=request("/rest/workspaces/fixture/coveragestores/store/external.geotiff","text/plain","file:/tmp/plain.tif".getBytes(StandardCharsets.UTF_8));
        new NoJpeg2000Filter().doFilter(reader,new MockHttpServletResponse(),(a,b)->require(a.getReader().readLine().equals("file:/tmp/plain.tif"),"reader lookahead lost bytes"));
        MockHttpServletRequest json=request("/rest/imports/0/tasks/0","application/json","{\"format\":\"image/jp2\"}".getBytes(StandardCharsets.UTF_8));
        new NoJpeg2000Filter().doFilter(json,new MockHttpServletResponse(),(a,b)->require(a==json,"native JSON parser input must remain unchanged"));
        reject(request("/rest/imports/0/tasks/ordinary.zip","application/zip",zip("disguised.png",JP2)));
        multipart(zip("disguised.tif",J2K),"ordinary.zip","application/zip");
        byte[] ordinaryZip=zip("ordinary.txt","ordinary streamed data".getBytes(StandardCharsets.UTF_8));
        new NoJpeg2000Filter().doFilter(request("/rest/imports/0/tasks/ordinary.zip","application/zip",ordinaryZip),new MockHttpServletResponse(),
                (a,b)->require(Arrays.equals(ordinaryZip,a.getInputStream().readAllBytes()),"valid ZIP changed in staging"));
        MockHttpServletResponse badZip=new MockHttpServletResponse();
        new NoJpeg2000Filter().doFilter(request("/rest/imports/0/tasks/invalid.zip","application/zip",new byte[]{80,75,3,4}),badZip,
                (a,b)->{throw new AssertionError("invalid archive reached persistent importer");});
        require(badZip.getStatus()==400,"malformed ZIP controlled 400");
        multipart(JP2,"disguised.png","image/png");
        multipart(J2K,"disguised.tif","application/octet-stream");
        multipart(new byte[0],"named.jp2","image/png");
        MockHttpServletRequest oversized=new MockHttpServletRequest("PUT","/geoserver/rest/imports/0/tasks/large.zip") {
            @Override public long getContentLengthLong() { return NoJpeg2000Policy.MAX_ARCHIVE_BYTES+1; }
        };
        oversized.setContextPath("/geoserver");oversized.setContentType("application/zip");oversized.setContent(new byte[]{80,75,3,4});
        MockHttpServletResponse limitResponse=new MockHttpServletResponse();
        new NoJpeg2000Filter().doFilter(oversized,limitResponse,
                (a,b)->{throw new AssertionError("over-limit archive reached importer");});
        require(limitResponse.getStatus()==413,"declared compressed byte limit status");
        require(limitResponse.getContentAsString().equals(NoJpeg2000Policy.LIMIT_MESSAGE),"limit diagnostic");
        Path limited=Path.of(args[0]+"-copy-limit.tmp");
        java.lang.reflect.Method bounded=NoJpeg2000Policy.class.getDeclaredMethod("stageArchive",java.io.InputStream.class,Path.class,long.class);
        bounded.setAccessible(true);
        try {
            try { bounded.invoke(null,new java.io.ByteArrayInputStream(new byte[16385]),limited,16384L);throw new AssertionError("copy bound ignored"); }
            catch(java.lang.reflect.InvocationTargetException expected) { require(expected.getCause() instanceof NoJpeg2000Policy.InputLimit,"copy bound exception"); }
            require(Files.size(limited)<=16384,"copy wrote past controlled limit");
            try(java.io.RandomAccessFile file=new java.io.RandomAccessFile(limited.toFile(),"rw")) {file.setLength(NoJpeg2000Policy.MAX_ARCHIVE_BYTES+1);}
            try {NoJpeg2000Policy.archive(limited);throw new AssertionError("archive size ignored");}
            catch(NoJpeg2000Policy.InputLimit expected) {require(true,"sparse compressed size boundary");}
        } finally {Files.deleteIfExists(limited);}
        ByteArrayOutputStream manyBytes=new ByteArrayOutputStream();
        try(ZipOutputStream z=new ZipOutputStream(manyBytes)) {
            for(int i=0;i<=NoJpeg2000Policy.MAX_ARCHIVE_MEMBERS;i++) { z.putNextEntry(new ZipEntry("ordinary-"+i+".txt"));z.closeEntry(); }
        }
        multipart(manyBytes.toByteArray(),"many.zip","application/zip",413,NoJpeg2000Policy.LIMIT_MESSAGE);
        Path dir=Path.of(args[0]);Files.createDirectory(dir);Files.write(dir.resolve("disguised.png"),JP2);
        require(NoJpeg2000Policy.tree(dir),"ZIP/mosaic extracted content detection");
        Files.delete(dir.resolve("disguised.png"));Files.write(dir.resolve("ordinary.jpeg"),new byte[]{(byte)255,(byte)216});
        require(!NoJpeg2000Policy.tree(dir),"ordinary JPEG directory must remain eligible");
        try(var files=Files.list(Path.of(System.getProperty("java.io.tmpdir")))) { require(files.findAny().isEmpty(),"transient archive staging not cleaned"); }
        System.out.println("NO_JPEG2000_GUARD_ASSERTIONS="+assertions);
    }
}
